import feedparser
import requests
from bs4 import BeautifulSoup, NavigableString
from markdownify import MarkdownConverter
import html
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
import uuid

def md_safe(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "html.parser")

    # 1. Убираем <u>, но сохраняем текст
    for tag in soup.find_all("u"):
        tag.unwrap()

    # 2. Убираем вложенные <em> внутри <strong>
    for strong in soup.find_all("strong"):
        for em in strong.find_all("em"):
            em.unwrap()

    # 3. Защищаем Windows пути
    for text in list(soup.find_all(string=True)):
        if not isinstance(text, NavigableString):
            continue
        if text.find_parent("code"):
            continue

        s = str(text)
        matches = list(re.finditer(r'([A-Z]:\\[^\s<"]+)', s))
        if not matches:
            continue

        new_nodes = []
        last = 0
        for m in matches:
            if m.start() > last:
                new_nodes.append(s[last:m.start()])
            code_tag = soup.new_tag("code")
            code_tag.string = m.group(1)
            new_nodes.append(code_tag)
            last = m.end()

        if last < len(s):
            new_nodes.append(s[last:])

        for node in reversed(new_nodes):
            text.insert_after(node)
        text.extract()

    # =========================
    # INLINE PRESERVE SYSTEM
    # =========================

    INLINE_TAGS = ["strong", "em", "code", "mark"]

    placeholders = {}

    for tag in soup.find_all(INLINE_TAGS):
        key = f"INLINEPLACEHOLDER{uuid.uuid4().hex}END"
        placeholders[key] = str(tag)
        tag.replace_with(key)

    # 4. Конвертируем в Markdown
    md = MarkdownConverter(
        heading_style="ATX",
        strip=["span"],
        escape_underscores=False,
    ).convert(str(soup))

    # 5. Возвращаем inline HTML обратно
    for key, value in placeholders.items():
        md = md.replace(key, value)

    # 6. Минимальная чистка
    md = re.sub(r'\(<(https?://[^>]+)>\)', r'(\1)', md)
    md = re.sub(r'\*\*\*+', '**', md)

    return md

# ================= НАСТРОЙКИ =================

RSS_URL = "https://teletype.in/rss/bearsocietatis"

# Teletype/.obsidian/Teletype.py
VAULT_ROOT = Path(__file__).resolve().parent.parent
CACHE_ROOT = VAULT_ROOT / "Teletype_0x" / "Cach"
LOG_PATH = CACHE_ROOT / "import_log.txt"

RSS_STATE_PATH = CACHE_ROOT / "rss_state.json"
USED_IMAGES_PATH = CACHE_ROOT / ".used_images.json"

AUTHOR = "Alexander"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_SLUG_LEN = 120

# === ГЛОБАЛЬНЫЙ ЛИМИТ ОБРАБОТКИ ===
# None = без ограничений
# Например: 300 — обработать максимум 300 записей за запуск
PROCESS_LIMIT = None # Если много записей новых или на обновление выстави лимит, и каждый запуск увеличивай его что бы обработать все, если записей очень много

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

    "images_http_downloaded": 0,
    "images_iframe_rendered": 0,
    "images_placeholder_created": 0,

    "images_removed": 0,
    "cache_removed": 0,
    "categories_removed": 0,
}

IFRAME_LIMIT = asyncio.Semaphore(3)

# ================= LOGGING =====================

log_file = open(LOG_PATH, "a", encoding="utf-8")

_original_print = print

def print(*args, **kwargs):
    _original_print(*args, **kwargs)
    text = " ".join(str(a) for a in args)
    end = kwargs.get("end", "\n")
    log_file.write(text + ("" if end == "" else "\n"))
    log_file.flush()

# ================= PLAYWRIGHT SESSION (ASYNC) =====================

playwright_instance = None
browser_instance = None
context_instance = None


async def get_browser():
    global playwright_instance, browser_instance, context_instance

    if browser_instance:
        return browser_instance, context_instance

    playwright_instance = await async_playwright().start()
    browser_instance = await playwright_instance.chromium.launch(
        headless=True,
        args=[
            "--disable-http2",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox"
        ]
    )
    context_instance = await browser_instance.new_context(
        viewport={"width": 2000, "height": 1500},
        device_scale_factor=2
    )

    return browser_instance, context_instance


async def close_browser():
    global playwright_instance, browser_instance, context_instance

    if context_instance:
        await context_instance.close()

    if browser_instance:
        await browser_instance.close()

    if playwright_instance:
        await playwright_instance.stop()

    context_instance = None
    browser_instance = None
    playwright_instance = None


# ================= IFRAME IMAGE EXPORT ===================
from PIL import Image, ImageDraw, ImageFont, ImageChops


def create_placeholder(img_path: Path, url: str):
    """Создаёт fallback-изображение с текстом ссылки"""
    img_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (800, 200), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 20)
    except:
        font = ImageFont.load_default()
    text = f"Открыть диаграмму: {url}"
    draw.text((10, 80), text, fill="black", font=font)
    img.save(img_path)
    stats["images_placeholder_created"] += 1
    print(f"⬇ IMG (placeholder): {img_path.name}")

def autocrop_image(path: Path, padding: int = 20):
    with Image.open(path) as img:

        # если есть прозрачность — заменяем на белый фон
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg

        img_rgb = img.convert("RGB")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        diff = ImageChops.difference(img_rgb, bg)
        bbox = diff.getbbox()

        if not bbox:
            return

        cropped = img.crop(bbox)

        if padding:
            padded = Image.new(
                "RGB",
                (cropped.width + padding * 2, cropped.height + padding * 2),
                (255, 255, 255)
            )
            padded.paste(cropped, (padding, padding))
            cropped = padded

        cropped.save(path)

async def export_drawio_via_svg(context, url: str, img_path: Path):
    async with IFRAME_LIMIT:
        page = await context.new_page()

        try:
            html_doc = f"""
            <html>
            <body style="margin:0;padding:0;background:white;">
                <iframe
                    src="{url}"
                    style="width:2000px;height:1500px;border:0;"
                    allowfullscreen>
                </iframe>
            </body>
            </html>
            """

            await page.set_content(html_doc)
            await page.wait_for_selector("iframe")
            await asyncio.sleep(0.5)

            iframe_el = await page.query_selector("iframe")
            if not iframe_el:
                print("⚠ iframe element не найден → placeholder")
                create_placeholder(img_path, url)
                return

            frame = await iframe_el.content_frame()
            if not frame:
                print("⚠ iframe content_frame не найден → placeholder")
                create_placeholder(img_path, url)
                return

            print("🔎 Waiting for viewer render...")

            element = None
            try:
                await frame.wait_for_selector("svg, canvas", timeout=10000)
                elements = await frame.query_selector_all("svg, canvas")
                if elements:
                    element = elements[0]
            except:
                element = None

            if not element:
                print("⚠ SVG/Canvas не найден → placeholder")
                create_placeholder(img_path, url)
                return

            tmp_path = img_path.with_suffix(".tmp.png")
            old_hash = file_sha(img_path)

            await element.screenshot(path=str(tmp_path))

            autocrop_image(tmp_path)

            new_hash = file_sha(tmp_path)

            if new_hash != old_hash:
                tmp_path.replace(img_path)
                stats["images_iframe_rendered"] += 1
                print(f"⬇ IMG updated: {img_path.name}")
            else:
                tmp_path.unlink()
                print(f"✓ IMG unchanged: {img_path.name}")

        except Exception as e:
            print(f"❌ iframe export error: {e}")
            create_placeholder(img_path, url)

        finally:
            await page.close()

async def process_iframes(soup: BeautifulSoup, article_url: str, slug: str, current_used: set, page_soup: BeautifulSoup):
    """Async обработка iframe"""

    real_iframes = page_soup.find_all("iframe")
    if not real_iframes:
        return

    rss_iframes = soup.find_all("iframe")

    article_cache = CACHE_ROOT / slug
    article_cache.mkdir(parents=True, exist_ok=True)

    _, context = await get_browser()

    tasks = []

    real_sources = {
        urljoin(article_url, iframe.get("src"))
        for iframe in real_iframes
        if iframe.get("src")
    }

    for i, iframe in enumerate(rss_iframes):
        src = iframe.get("src")
        if not src:
            iframe.decompose()
            continue

        iframe_url = urljoin(article_url, src)

        if iframe_url not in real_sources:
            iframe.decompose()
            continue

        img_name = f"iframe_{i + 1}.png"
        img_path = article_cache / img_name

        parsed = urlparse(iframe_url)

        if "draw.io" in parsed.netloc or "diagrams.net" in parsed.netloc:
            tasks.append(
                export_drawio_via_svg(context, iframe_url, img_path)
            )

            replacement = f"![[Teletype_0x/Cach/{slug}/{img_name}|500]]\n\n"
            iframe.replace_with(replacement)
        else:
            iframe.decompose()

    if tasks:
        for r in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(r, Exception):
                print(f"❌ iframe export error: {r}")

        for i, iframe in enumerate(rss_iframes):
            img_name = f"iframe_{i + 1}.png"
            img_path = article_cache / img_name
            if img_path.exists():
                current_used.add(img_name)


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
    return text.strip()



async def main():
    try:

        # ================= RSS =======================

        feed = feedparser.parse(RSS_URL, sanitize_html=False)
        if not feed.entries:
            print("❌ RSS пуст.")
            return

        current_map = {e.link: safe_filename(e.title.strip()) for e in feed.entries}
        current_urls = set(current_map.keys())
        all_titles = [e.title.strip() for e in feed.entries]

        # ================= LOAD PREVIOUS STATE =======

        previous_map = {}
        if RSS_STATE_PATH.exists():
            previous_map = json.loads(RSS_STATE_PATH.read_text("utf-8"))

        previous_urls = set(previous_map.keys())
        new_state_map = previous_map.copy()

        # ================= LOAD USED IMAGES STATE ====

        used_images = {}
        if USED_IMAGES_PATH.exists():
            used_images = {
                k: set(v)
                for k, v in json.loads(USED_IMAGES_PATH.read_text("utf-8")).items()
            }

        # ================= IMPORT ====================
        processed_count = 0
        for entry in feed.entries:

            if PROCESS_LIMIT is not None and processed_count >= PROCESS_LIMIT:
                print(f"⏹ Достигнут лимит обработки: {PROCESS_LIMIT}")
                break

            url = entry.link
            title = entry.title.strip()
            slug = safe_filename(title)

            category = normalize_tag(entry.get("category", "misc"))
            article_dir = VAULT_ROOT / category
            article_dir.mkdir(parents=True, exist_ok=True)

            md_path = article_dir / f"{slug}.md"
            is_new = not md_path.exists()

            article_cache = CACHE_ROOT / slug
            article_cache.mkdir(parents=True, exist_ok=True)

            prev_info = previous_map.get(url)
            if isinstance(prev_info, dict):
                old_slug = prev_info.get("slug")
                old_category = prev_info.get("category")
            else:
                old_slug = prev_info
                old_category = None

            if old_slug and old_category and (old_slug != slug or old_category != category):
                old_md_path = VAULT_ROOT / old_category / f"{old_slug}.md"
                if old_md_path.exists() and old_md_path != md_path:
                    old_md_path.unlink()

            content_list = entry.get("content") or []
            raw_html = content_list[0].get("value", "") if content_list else ""

            # === Получаем iframe из реальной страницы ДО расчёта hash ===
            page_soup = BeautifulSoup("", "html.parser")
            iframe_sources = []

            try:
                r = session.get(url, timeout=20)
                if r.status_code == 200:
                    page_soup = BeautifulSoup(r.text, "html.parser")
                    iframe_sources = sorted(
                        urljoin(url, iframe.get("src"))
                        for iframe in page_soup.find_all("iframe")
                        if iframe.get("src")
                    )
            except Exception as e:
                print(f"⚠ PAGE load error: {e}")

            combined_hash_source = (
                    normalize_html_for_hash(raw_html)
                    + json.dumps(iframe_sources, ensure_ascii=False)
            )

            html_hash = sha(combined_hash_source)

            hash_path = article_cache / ".content.hash"
            old_hash = hash_path.read_text("utf-8") if hash_path.exists() else None

            # Если RSS HTML не изменился — пропускаем полностью
            if md_path.exists() and old_hash == html_hash:
                stats["articles_unchanged"] += 1
                new_state_map[url] = {"slug": slug, "category": category}
                continue

            soup = BeautifulSoup(raw_html, "html.parser")

            # 🔥 обработка iframe (viewer.diagrams.net и др.)
            current_used = set()
            await process_iframes(soup, url, slug, current_used, page_soup)

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

                try:
                    r = await asyncio.to_thread(session.get, img_url, timeout=20)
                    if r.status_code == 200:
                        img_path = article_cache / img_name
                        new_bytes = r.content
                        old_bytes = img_path.read_bytes() if img_path.exists() else None

                        if old_bytes != new_bytes:
                            img_path.write_bytes(new_bytes)
                            stats["images_http_downloaded"] += 1
                            print(f"⬇ IMG: {slug}/{img_name}")
                        else:
                            print(f"✓ IMG unchanged: {slug}/{img_name}")

                        image_index[img_url] = img_name
                    else:
                        continue
                except Exception as e:
                    print(f"❌ IMG download error: {e}")
                    continue

                current_used.add(image_index[img_url])
                img_file = article_cache / image_index[img_url]

                width_part = ""

                try:
                    with Image.open(img_file) as im:
                        new_width = max(1, int(im.width * 0.5))
                        width_part = f"|{new_width}"
                except:
                    pass

                img.replace_with(
                    f"INLINEIMAGEPLACEHOLDER{slug}|||{image_index[img_url]}|||{width_part}END"
                )

            if has_images:
                index_path.write_text(json.dumps(image_index, indent=2), "utf-8")

            # сохраняем только если есть реальные изображения
            if current_used:
                used_images[slug] = set(current_used)
            else:
                used_images.pop(slug, None)

            if is_new:
                for text in soup.find_all(string=True):
                    if not isinstance(text, NavigableString):
                        continue
                    if text.find_parent(["a", "code", "pre"]):
                        continue
                    s = str(text)
                    for t in all_titles:
                        if t != title:
                            s = re.sub(rf'(?<!\[\[)\b{re.escape(t)}\b(?!\]\])', f"[[{t}]]", s)
                    if s != text:
                        text.replace_with(s)

            # нормализуем путь для Obsidian
            content_md = md_safe(str(soup))
            content_md = html.unescape(content_md)

            # Вставляем Obsidian image ссылки
            content_md = re.sub(
                r"INLINEIMAGEPLACEHOLDER(.*?)\|\|\|(.*?)\|\|\|(.*?)END",
                r"![[Teletype_0x/Cach/\1/\2\3]]",
                content_md
            )

            # Убираем markdown-экранирование внутри Obsidian путей
            def unescape_obsidian_links(text: str) -> str:
                def repl(m):
                    inner = m.group(1).replace("\\_", "_").replace("\\", "")
                    return f"![[{inner}]]"
                return re.sub(r'!\[\[(.*?)\]\]', repl, text)

            content_md = unescape_obsidian_links(content_md)

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

            final_content = frontmatter + normalize_md(content_md)

            tmp_md_path = md_path.with_suffix(".tmp")

            tmp_md_path.write_text(final_content, "utf-8")
            tmp_md_path.replace(md_path)

            hash_path.write_text(html_hash, "utf-8")

            if is_new:
                print(f"➕ NEW: {slug}")
                stats["articles_new"] += 1
            else:
                print(f"✏ UPDATE: {slug}")
                stats["articles_updated"] += 1

            processed_count += 1
            new_state_map[url] = {"slug": slug, "category": category}

        # ================= DELETE REMOVED ARTICLES (SAFE) ====

        removed_urls = set(previous_map.keys()) - set(current_map.keys())

        for url in removed_urls:
            prev_info = previous_map[url]
            if isinstance(prev_info, dict):
                slug = prev_info.get("slug")
                old_category = prev_info.get("category")
            else:
                slug = prev_info
                old_category = None

            print(f"🗑 REMOVE: {slug}")

            if old_category:
                md_file = VAULT_ROOT / old_category / f"{slug}.md"
                if md_file.exists():
                    md_file.unlink()
            else:
                for md_file in VAULT_ROOT.rglob(f"{slug}.md"):
                    md_file.unlink()

            cache_dir = CACHE_ROOT / slug
            if cache_dir.exists():
                for f in cache_dir.iterdir():
                    if f.suffix.lower() in IMAGE_EXTS:
                        print(f"🗑 IMG: {slug}/{f.name}")
                        stats["images_removed"] += 1
                shutil.rmtree(cache_dir)

            used_images.pop(slug, None)
            stats["articles_removed"] += 1

        # ================= IMAGE GC ==================

        for slug, imgs in list(used_images.items()):
            cache_dir = CACHE_ROOT / slug
            if not cache_dir.exists():
                continue

            used_names = set(imgs)

            for f in cache_dir.iterdir():
                if f.suffix.lower() in IMAGE_EXTS and f.name not in used_names:
                    f.unlink()
                    print(f"🗑 IMG: {slug}/{f.name}")
                    stats["images_removed"] += 1

            if cache_dir.exists() and not any(
                    p.suffix.lower() in IMAGE_EXTS for p in cache_dir.iterdir()
            ):
                shutil.rmtree(cache_dir)
                used_images.pop(slug, None)
                stats["cache_removed"] += 1

        # ================= CATEGORY GC ===============

        for d in VAULT_ROOT.iterdir():
            if not d.is_dir() or d.name.startswith(".") or d.name == "Teletype_0x":
                continue
            if not any(p.suffix == ".md" for p in d.rglob("*.md")):
                shutil.rmtree(d)
                stats["categories_removed"] += 1

        # ================= SAVE STATE ================

        RSS_STATE_PATH.write_text(json.dumps(new_state_map, indent=2), "utf-8")
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
        print(f"HTTP изображений скачано: {stats['images_http_downloaded']}")
        print(f"Iframe изображений отрендерено: {stats['images_iframe_rendered']}")
        print(f"Placeholder создано: {stats['images_placeholder_created']}")
        print(f"Удалено: статей: {stats['articles_removed']}")
        print(f"         изображений: {stats['images_removed']}")
        print(f"         папок кеша: {stats['cache_removed']}")
        print(f"         категорий: {stats['categories_removed']}")

        print("\n✅ Готово.")

    finally:
        await close_browser()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        log_file.close()
