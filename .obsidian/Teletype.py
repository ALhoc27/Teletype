import feedparser
import requests
from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify as md
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
import json
import re
import sys
import hashlib
import shutil
import asyncio
from playwright.async_api import async_playwright

# ================= НАСТРОЙКИ =================

RSS_URL = "https://teletype.in/rss/bearsocietatis"

# Teletype/.obsidian/Teletype.py
VAULT_ROOT = Path(__file__).resolve().parent.parent
CACHE_ROOT = VAULT_ROOT / "Teletype_0x" / "Cach"

RSS_STATE_PATH = CACHE_ROOT / "rss_state.json"
USED_IMAGES_PATH = CACHE_ROOT / ".used_images.json"

AUTHOR = "Alexander"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_SLUG_LEN = 120

# =============================================

CACHE_ROOT.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://teletype.in/"
})

# ================= STATS =====================

stats = {
    "articles_new": 0,
    "articles_updated": 0,
    "articles_unchanged": 0,
    "articles_removed": 0,
    "images_downloaded": 0,
    "images_removed": 0,
    "cache_removed": 0,
    "categories_removed": 0,
}

# ================= PLAYWRIGHT SESSION (ASYNC) =====================

playwright_instance = None
browser_instance = None
context_instance = None


async def get_browser():
    global playwright_instance, browser_instance, context_instance

    if browser_instance:
        return browser_instance, context_instance

    playwright_instance = await async_playwright().start()
    browser_instance = await playwright_instance.chromium.launch(headless=True)
    context_instance = await browser_instance.new_context(
        viewport={"width": 2000, "height": 1500},
        device_scale_factor=3
    )

    return browser_instance, context_instance


async def close_browser():
    global playwright_instance, browser_instance

    if browser_instance:
        await browser_instance.close()

    if playwright_instance:
        await playwright_instance.stop()

# ================= IFRAME IMAGE EXPORT ===================
from PIL import Image, ImageDraw, ImageFont

def create_placeholder(img_path: Path, url: str):
    """Создаёт fallback-изображение с текстом ссылки"""
    img = Image.new("RGB", (800, 200), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    text = f"Открыть диаграмму: {url}"
    draw.text((10, 80), text, fill="black", font=font)
    img.save(img_path)
    stats["images_downloaded"] += 1
    print(f"⬇ IMG (placeholder): {img_path.name}")

async def export_drawio_via_svg(context, url: str, img_path: Path):
    """Async экспорт diagrams.net с hash-проверкой"""

    page = await context.new_page()

    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(3000)

        svg_element = None

        for frame in page.frames:
            svgs = await frame.query_selector_all("svg")
            if svgs:
                svg_element = svgs[0]
                break

        if not svg_element:
            raise Exception("SVG не найден")

        box = await svg_element.bounding_box()
        if not box:
            raise Exception("Bounding box не найден")

        tmp_path = img_path.with_suffix(".tmp.png")

        await page.screenshot(path=str(tmp_path), clip=box)

        new_hash = file_sha(tmp_path)
        old_hash = file_sha(img_path)

        if new_hash != old_hash:
            tmp_path.replace(img_path)
            print(f"⬇ IMG updated: {img_path.name}")
            stats["images_downloaded"] += 1
        else:
            tmp_path.unlink()
            print(f"✓ IMG unchanged: {img_path.name}")

    finally:
        await page.close()

async def process_iframes(soup: BeautifulSoup, article_url: str, slug: str, current_used: set):
    """Async обработка iframe"""

    try:
        r = session.get(article_url, timeout=20)
        if r.status_code != 200:
            return
    except:
        return

    page_soup = BeautifulSoup(r.text, "html.parser")
    real_iframes = page_soup.find_all("iframe")
    if not real_iframes:
        return

    real_sources = [iframe.get("src") for iframe in real_iframes if iframe.get("src")]
    rss_iframes = soup.find_all("iframe")

    article_cache = CACHE_ROOT / slug
    article_cache.mkdir(parents=True, exist_ok=True)

    _, context = await get_browser()

    tasks = []

    for i, iframe in enumerate(rss_iframes):
        if i >= len(real_sources):
            iframe.decompose()
            continue

        iframe_url = urljoin(article_url, real_sources[i])
        img_name = f"iframe_{i+1}.png"
        img_path = article_cache / img_name

        parsed = urlparse(iframe_url)

        if "draw.io" in parsed.netloc or "diagrams.net" in parsed.netloc:
            tasks.append(
                export_drawio_via_svg(context, iframe_url, img_path)
            )

        current_used.add(img_name)

        replacement = f"![[Teletype_0x/Cach/{slug}/{img_name}]]\n\n[Открыть диаграмму]({iframe_url})\n\n"
        iframe.replace_with(replacement)

    if tasks:
        await asyncio.gather(*tasks)

# ================= HELPERS ===================

def normalize_tag(tag: str) -> str:
    return tag.replace(" ", "_").lower()

def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()[:MAX_SLUG_LEN]

def normalize_image_name(name: str) -> str:
    stem = re.sub(r"[^\w\-]+", "_", Path(name).stem.lower())
    ext = Path(name).suffix.lower() or ".jpg"
    return f"{stem}{ext}"

def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def file_sha(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()

def normalize_html_for_hash(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return re.sub(r"\s+", " ", soup.decode()).strip()

def normalize_md(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"

# ================= IFRAME PROCESSING ===================


async def main():
    # ================= RSS =======================

    feed = feedparser.parse(RSS_URL, sanitize_html=False)
    if not feed.entries:
        print("❌ RSS пуст.")
        sys.exit(1)

    current_map = {e.link: safe_filename(e.title.strip()) for e in feed.entries}
    current_urls = set(current_map.keys())
    all_titles = [e.title.strip() for e in feed.entries]

    # ================= LOAD PREVIOUS STATE =======

    previous_map = {}
    if RSS_STATE_PATH.exists():
        previous_map = json.loads(RSS_STATE_PATH.read_text("utf-8"))

    previous_urls = set(previous_map.keys())

    # ================= DELETE REMOVED ARTICLES ====

    for url in previous_urls - current_urls:
        slug = previous_map[url]

        print(f"🗑 REMOVE: {slug}")

        for md_file in VAULT_ROOT.rglob(f"{slug}.md"):
            md_file.unlink()

        cache_dir = CACHE_ROOT / slug
        if cache_dir.exists():
            for f in cache_dir.iterdir():
                if f.suffix.lower() in IMAGE_EXTS:
                    print(f"🗑 IMG: {slug}/{f.name}")
                    stats["images_removed"] += 1
            shutil.rmtree(cache_dir)

        stats["articles_removed"] += 1

    # ================= LOAD USED IMAGES STATE ====

    used_images = {}
    if USED_IMAGES_PATH.exists():
        used_images = {
            k: set(v)
            for k, v in json.loads(USED_IMAGES_PATH.read_text("utf-8")).items()
        }

    # ================= IMPORT ====================

    for entry in feed.entries:
        url = entry.link
        title = entry.title.strip()
        slug = safe_filename(title)

        category = normalize_tag(entry.get("category", "misc"))
        article_dir = VAULT_ROOT / category
        article_dir.mkdir(parents=True, exist_ok=True)

        md_path = article_dir / f"{slug}.md"
        is_new = not md_path.exists()

        raw_html = entry.get("content", [{}])[0].get("value", "")
        html_hash = sha(normalize_html_for_hash(raw_html))

        # 🔥 добавляем hash iframe src из реальной страницы
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 200:
                page_soup = BeautifulSoup(r.text, "html.parser")
                iframe_srcs = sorted(
                    iframe.get("src", "")
                    for iframe in page_soup.find_all("iframe")
                )
                iframe_hash = sha("".join(iframe_srcs))
                html_hash = sha(html_hash + iframe_hash)
        except:
            pass

        article_cache = CACHE_ROOT / slug
        hash_path = article_cache / ".content.hash"
        old_hash = hash_path.read_text("utf-8") if hash_path.exists() else None

        if md_path.exists() and old_hash == html_hash:
            stats["articles_unchanged"] += 1
            continue

        soup = BeautifulSoup(raw_html, "html.parser")

        # 🔥 обработка iframe (viewer.diagrams.net и др.)
        current_used = set()
        await process_iframes(soup, url, slug, current_used)

        image_index = {}
        index_path = article_cache / ".images.json"
        if index_path.exists():
            image_index = json.loads(index_path.read_text("utf-8"))

        has_images = False

        for img in soup.find_all("img"):
            src = img.get("src")
            if not src:
                continue

            has_images = True
            article_cache.mkdir(parents=True, exist_ok=True)

            img_url = urljoin(url, src)
            raw = Path(urlparse(img_url).path).name or "image"
            img_name = normalize_image_name(raw)

            if img_url not in image_index:
                r = session.get(img_url, timeout=20)
                if r.status_code == 200:
                    (article_cache / img_name).write_bytes(r.content)
                    image_index[img_url] = img_name
                    stats["images_downloaded"] += 1
                    print(f"⬇ IMG: {slug}/{img_name}")

            current_used.add(image_index[img_url])
            img.replace_with(f"OBSIDIAN_IMAGE::{slug}/{image_index[img_url]}")

        if has_images:
            index_path.write_text(json.dumps(image_index, indent=2), "utf-8")
            used_images[slug] = current_used

        if is_new:
            for text in soup.find_all(string=True):
                if not isinstance(text, NavigableString):
                    continue
                s = str(text)
                for t in all_titles:
                    if t != title:
                        s = re.sub(rf'(?<!\[\[){re.escape(t)}(?!\]\])', f"[[{t}]]", s)
                if s != text:
                    text.replace_with(s)

        content_md = md(str(soup), heading_style="ATX")
        # нормализуем путь для Obsidian: убираем \_ и все \ в пути
        content_md = md(str(soup), heading_style="ATX")

        content_md = re.sub(
            r"OBSIDIAN\\?_IMAGE::([^\n]+)",
            r"![[Teletype_0x/Cach/\1]]",
            content_md
        )

        content_md = content_md.replace("\\_", "_")

        created = ""
        if entry.get("published_parsed"):
            created = str(datetime(*entry.published_parsed[:6]).date())

        updated = str(datetime.now().date())

        frontmatter = f"""---
    source: teletype
    author: {AUTHOR}
    url: {url}
    created: {created}
    updated: {updated}
    ---
    
    """

        md_path.write_text(frontmatter + normalize_md(content_md), "utf-8")

        article_cache.mkdir(parents=True, exist_ok=True)
        hash_path.write_text(html_hash, "utf-8")

        if is_new:
            print(f"➕ NEW: {slug}")
            stats["articles_new"] += 1
        else:
            print(f"✏ UPDATE: {slug}")
            stats["articles_updated"] += 1

    # ================= IMAGE GC ==================

    for slug, imgs in list(used_images.items()):
        cache_dir = CACHE_ROOT / slug
        if not cache_dir.exists():
            continue

        # Сравниваем по имени файла (для placeholder)
        used_names = set(imgs)

        for f in cache_dir.iterdir():
            if f.suffix.lower() in IMAGE_EXTS and f.name not in used_names:
                f.unlink()
                print(f"🗑 IMG: {slug}/{f.name}")
                stats["images_removed"] += 1

        # Если после удаления нет файлов, удаляем папку
        if not any(p.suffix.lower() in IMAGE_EXTS for p in cache_dir.iterdir()):
            shutil.rmtree(cache_dir)
            used_images.pop(slug, None)

    # ================= CATEGORY GC ===============

    for d in VAULT_ROOT.iterdir():
        if not d.is_dir() or d.name.startswith(".") or d.name == "Teletype_0x":
            continue
        if not any(p.suffix == ".md" for p in d.rglob("*.md")):
            shutil.rmtree(d)
            stats["categories_removed"] += 1

    # ================= SAVE STATE ================

    RSS_STATE_PATH.write_text(json.dumps(current_map, indent=2), "utf-8")
    USED_IMAGES_PATH.write_text(
        json.dumps({k: sorted(v) for k, v in used_images.items()}, indent=2),
        "utf-8"
    )

    # ================= SUMMARY ===================

    print("\n🧾 Итог")
    print(f"Всего статей в RSS: {len(current_urls)}")
    print(
        f"Импортированных: "
        f"+{stats['articles_new']} (новые) / "
        f"~{stats['articles_updated']} (обновлённые) / "
        f"={stats['articles_unchanged']} (без изменений)"
    )
    print(f"Удалено: статей: {stats['articles_removed']}")
    print(f"         изображений: {stats['images_removed']}")
    print(f"         папок кеша: {stats['cache_removed']}")
    print(f"         категорий: {stats['categories_removed']}")

    await close_browser()
    print("\n✅ Готово.")

if __name__ == "__main__":
    asyncio.run(main())