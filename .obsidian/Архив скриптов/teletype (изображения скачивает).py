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

# ================= НАСТРОЙКИ =================

RSS_URL = "https://teletype.in/rss/bearsocietatis"

# скрипт лежит в Teletype/.obsidian/Teletype.py
VAULT_ROOT = Path(__file__).resolve().parent.parent
CACHE_ROOT = VAULT_ROOT / "Teletype_0x" / "Cach"
RSS_STATE_PATH = CACHE_ROOT / "rss_state.json"

AUTHOR = "Alexander"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_SLUG_LEN = 120  # Windows-safe

# =============================================

CACHE_ROOT.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://teletype.in/"
})

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

def normalize_md(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"

# ================= RSS =======================

feed = feedparser.parse(RSS_URL)
if not feed.entries:
    print("❌ RSS пуст.")
    sys.exit(1)

current_map = {
    safe_filename(e.title.strip()): e.link
    for e in feed.entries
}
current_slugs = set(current_map.keys())

# ================= LOAD PREVIOUS STATE =======

if RSS_STATE_PATH.exists():
    previous_map = json.loads(RSS_STATE_PATH.read_text("utf-8"))
else:
    previous_map = {}

previous_slugs = set(previous_map.keys())

# ================= DELETE REMOVED ARTICLES ====

deleted_slugs = previous_slugs - current_slugs

if deleted_slugs:
    print("\n🧹 Удалённые статьи:")

for slug in deleted_slugs:
    # удалить markdown
    for md_file in VAULT_ROOT.rglob(f"{slug}.md"):
        md_file.unlink()
        print(f"🗑 MD: {md_file.relative_to(VAULT_ROOT)}")

    # удалить кеш
    cache_dir = CACHE_ROOT / slug
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print(f"🗑 CACHE: {slug}")

# ================= IMPORT ====================

all_titles = [e.title.strip() for e in feed.entries]

for entry in feed.entries:
    url = entry.link
    title = entry.title.strip()
    slug = safe_filename(title)

    print(f"\n⏳ {title}")

    article_dir = VAULT_ROOT / normalize_tag(entry.get("category", "misc"))
    article_dir.mkdir(parents=True, exist_ok=True)

    md_path = article_dir / f"{slug}.md"
    is_new = not md_path.exists()

    created = (
        datetime(*entry.published_parsed[:6]).date()
        if entry.get("published_parsed")
        else ""
    )

    soup = BeautifulSoup(
        entry.get("content", [{}])[0].get("value", ""),
        "html.parser"
    )

    # ============ CACHE =======================

    article_cache = CACHE_ROOT / slug
    article_cache.mkdir(parents=True, exist_ok=True)

    image_index = {}
    index_path = article_cache / ".images.json"

    if index_path.exists():
        image_index = json.loads(index_path.read_text("utf-8"))

    # ============ IMAGES ======================

    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue

        img_url = urljoin(url, src)
        raw = Path(urlparse(img_url).path).name or "image"
        img_name = normalize_image_name(raw)

        if img_url not in image_index:
            r = session.get(img_url, timeout=20)
            if r.status_code == 200:
                (article_cache / img_name).write_bytes(r.content)
                image_index[img_url] = img_name

        img.replace_with(f"OBSIDIAN_IMAGE::{slug}/{image_index[img_url]}")

    if image_index:
        index_path.write_text(
            json.dumps(image_index, indent=2, ensure_ascii=False),
            "utf-8"
        )

    # ============ AUTOLINK ====================

    if is_new:
        for text in soup.find_all(string=True):
            if not isinstance(text, NavigableString):
                continue
            s = str(text)
            for t in all_titles:
                if t != title:
                    s = re.sub(
                        rf'(?<!\[\[){re.escape(t)}(?!\]\])',
                        f"[[{t}]]",
                        s
                    )
            if s != text:
                text.replace_with(s)

    # ============ MARKDOWN ====================

    content_md = md(str(soup), heading_style="ATX")
    content_md = re.sub(
        r"OBSIDIAN\\?_IMAGE::(.+)",
        r"![[Teletype_0x/Cach/\1]]",
        content_md
    )

    normalized = normalize_md(content_md)
    new_hash = sha(normalized)

    hash_path = article_cache / ".content.hash"
    old_hash = hash_path.read_text("utf-8") if hash_path.exists() else None

    if md_path.exists() and new_hash == old_hash:
        print("⏭ Без изменений")
        continue

    updated = datetime.now().date()

    if md_path.exists():
        for l in md_path.read_text("utf-8").splitlines():
            if l.startswith("created:"):
                created = l.replace("created:", "").strip()
                break

    frontmatter = f"""---
source: teletype
author: {AUTHOR}
url: {url}
created: {created}
updated: {updated}
---

"""

    md_path.write_text(frontmatter + normalized, "utf-8")
    hash_path.write_text(new_hash, "utf-8")

    print("✔ Обновлено")

# ================= SAVE RSS STATE ============

RSS_STATE_PATH.write_text(
    json.dumps(current_map, indent=2, ensure_ascii=False),
    "utf-8"
)

# ================= FINAL IMAGE GC ============

print("\n🧹 Очистка неиспользуемых изображений")

used_images = {}

for md_file in VAULT_ROOT.rglob("*.md"):
    text = md_file.read_text("utf-8")
    for slug, img in re.findall(
        r"Teletype_0x/Cach/([^/]+)/([^\]]+)",
        text
    ):
        used_images.setdefault(slug, set()).add(img)

removed_any = False

for cache_dir in CACHE_ROOT.iterdir():
    if not cache_dir.is_dir():
        continue

    slug = cache_dir.name
    used = used_images.get(slug, set())

    for f in list(cache_dir.iterdir()):
        if f.suffix.lower() in IMAGE_EXTS and f.name not in used:
            f.unlink()
            print(f"🗑 IMAGE: {slug}/{f.name}")
            removed_any = True

    remaining_images = [
        f for f in cache_dir.iterdir()
        if f.suffix.lower() in IMAGE_EXTS
    ]

    if not remaining_images:
        for f in cache_dir.iterdir():
            f.unlink()
        cache_dir.rmdir()
        print(f"🧹 Папка кеша очищена: {slug}")
        removed_any = True

if not removed_any:
    print("✨ Неиспользуемые изображения не найдены")

print("\n✅ Готово. Импорт и очистка завершены.")
