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

class SafeMarkdownConverter(MarkdownConverter):
    def escape(self, text, parent_tags=None):
        # вызываем оригинальный escape корректно
        text = super().escape(text, parent_tags=parent_tags)

        # убираем экранирование markdown-символов
        text = text.replace(r"\*", "*")
        text = text.replace(r"\_", "_")

        return text


def md_safe(html_text: str) -> str:
    return SafeMarkdownConverter(heading_style="ATX").convert(html_text)

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
    log_file.write(text + "\n")
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


# ================= IFRAME IMAGE EXPORT ===================
from PIL import Image, ImageDraw, ImageFont, ImageChops


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
            html = f"""
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

            await page.set_content(html)

            # ждём загрузку iframe
            await page.wait_for_selector("iframe")
            # даём iframe начать загрузку
            await asyncio.sleep(0.5)

            element = None

            print("🔎 Waiting for viewer render...")
            # ищем svg ИЛИ canvas
            for frame in page.frames:
                try:
                    await frame.wait_for_selector("svg, canvas", timeout=10000)
                    elements = await frame.query_selector_all("svg, canvas")
                    if elements:
                        element = elements[0]
                        break
                except:
                    continue

            if not element:
                print("⚠ SVG/Canvas не найден → placeholder")
                create_placeholder(img_path, url)
                return

            box = await element.bounding_box()

            if not box:
                print("⚠ Bounding box не найден → placeholder")
                create_placeholder(img_path, url)
                return

            tmp_path = img_path.with_suffix(".tmp.png")

            old_hash = file_sha(img_path)

            await page.screenshot(path=str(tmp_path), clip=box)

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
        # print("⚠ Page iframe not found — 👉 в HTML не найдено ни одного <iframe>")
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
            # удаляем iframe, который не поддерживаем
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
    return text.strip() + "\n"



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

            content_list = entry.get("content") or []
            raw_html = content_list[0].get("value", "") if content_list else ""
            html_hash = sha(normalize_html_for_hash(raw_html))

            article_cache = CACHE_ROOT / slug
            hash_path = article_cache / ".content.hash"
            old_hash = hash_path.read_text("utf-8") if hash_path.exists() else None

            # Если RSS HTML не изменился — пропускаем полностью
            if md_path.exists() and old_hash == html_hash:
                stats["articles_unchanged"] += 1
                continue

            # Только если изменился — тогда идём на страницу за iframe
            page_soup = BeautifulSoup("", "html.parser")

            try:
                r = session.get(url, timeout=20)
                if r.status_code == 200:
                    page_soup = BeautifulSoup(r.text, "html.parser")
            except:
                pass

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

                if img_url not in image_index:
                    r = await asyncio.to_thread(session.get, img_url, timeout=20)
                    if r.status_code == 200:
                        (article_cache / img_name).write_bytes(r.content)
                        image_index[img_url] = img_name
                        stats["images_http_downloaded"] += 1
                        print(f"⬇ IMG: {slug}/{img_name}")
                    else:
                        continue  # пропускаем битое изображение

                current_used.add(image_index[img_url])
                img_file = article_cache / image_index[img_url]

                width_part = ""

                try:
                    from PIL import Image
                    with Image.open(img_file) as im:
                        new_width = int(im.width * 0.50)
                        width_part = f"|{new_width}"
                except:
                    pass

                img.replace_with(
                    f"OBSIDIAN_IMAGE::{slug}/{image_index[img_url]}{width_part}"
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
                    s = str(text)
                    for t in all_titles:
                        if t != title:
                            s = re.sub(rf'(?<!\[\[)\b{re.escape(t)}\b(?!\]\])', f"[[{t}]]", s)
                    if s != text:
                        text.replace_with(s)

            # нормализуем путь для Obsidian: убираем \_ и все \ в пути
            content_md = md_safe(str(soup))

            content_md = re.sub(
                r"OBSIDIAN\\?_IMAGE::([^\n]+)",
                r"![[Teletype_0x/Cach/\1]]",
                content_md
            )

            content_md = html.unescape(content_md)
            # FIX: убираем лишний \ перед ** и __
            content_md = re.sub(r'\\(?=\*\*|__)', '', content_md)

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

            article_cache.mkdir(parents=True, exist_ok=True)
            hash_path.write_text(html_hash, "utf-8")

            if is_new:
                print(f"➕ NEW: {slug}")
                stats["articles_new"] += 1
            else:
                print(f"✏ UPDATE: {slug}")
                stats["articles_updated"] += 1

            processed_count += 1

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