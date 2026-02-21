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

def normalize_html_for_hash(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return re.sub(r"\s+", " ", soup.decode()).strip()

def normalize_md(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"

# ===== DRAW.IO IFRAME SUPPORT (ссылка) =====
def extract_drawio_link_markdown(iframe_tag):
    """
    Превращает iframe Draw.io в кликабельную ссылку в Markdown.
    """
    src = iframe_tag.get("src")
    if not src:
        return None
    return f"[Open diagram]({src})"

# ===== Тест Draw.io =====
def test_drawio_extraction():
    test_html = '''
    <iframe frameborder="0" style="width:100%;height:203px;"
    src="https://viewer.diagrams.net/?tags=%7B%7D&lightbox=1&highlight=0000ff&edit=_blank&layers=1&nav=1&dark=auto#R%3Cmxfile%3E%3Cdiagram%20name%3D%22Test%22%3EzVjfb%2BMoEP5b7iHS7kMq%2F4jT5LFO2r3TtVLVrvZuH2lME642eDFpkvvrbwYwhjhp06qVToocmBkGmG%2F8wXiQzqrtN0nq1Y0oaDlIomI7SOeDJJmOxvBEwc4IsnFqBEvJCiOKO8E9%2B5daYWSla1bQJjBUQpSK1aFwITinCxXIiJRiE5o9ijKctSZL2hPcL0jZl%2F7FCrUy0kly3sl%2Fp2y5ameOx1OjqUhrbHfSrEghNp4ovRykMymEMq1qO6Mlxq6Nixl3dUTrFiYpV6cMIPzu%2Bmcuftzc%2F8mpvJpPfg1%2FDJO%2BF%2Bu4Ubs2BlKseUHRTTxI882KKXpfkwVqNwA6yFaqKq3ajH4m5dqOHiTjElznTU144Hf8a417zxeiFHKQXoBSLh%2FIF9jGDNp7f1%2B1bwCQq%2BEjqVi5M0MqwUVjVuP0jU4j1Eb11sgV3aohKdmSG0WjiFSeCjcyrCB7jZoLu7NumdBamv9sP90ziDhKNZiu1yKQaQxAMsc2opRhVDJA6jXb2Nm2EL3LTXLcjTeDQcZpMCzY8wFHpQ4MyjXoKIl1t3NkwHeO4DHH1U51C40neSvLnTa%2FdK2R9hKa6GGxk2VOloXGV651SNbNcREOm7iudjo64GXqWvkBf0nrwOYLRqRswr4XISohvAdQcDh%2Bo6KiSu60%2BcowjDMfdeBHG81KHdSxp%2FNniDz5rpNPPTFpOvnSm38%2Fy3TXpZovDF8Aa9d7UwwfAFMZSmhfK80bJjAdEVku68LRBsOcJpZbNx01O761XtLMdO3502qJPRe6fXbUOXC7ewOTjoxfWvTOk5eoFc3vbVdItRJLwUl52Unzjnwj6HU210LUlnL%2FoUrt7NFJ1kq8SsiHwippSRR7Dhd%2FKEp26K1gyCNtmONRdBZG%2Bnwv0o1YywW1w%2Fxz6lVPOnd9V8DdS6p6rjRubkvvh%2FIk5DQ9vuM0BBiBCEEJJAjtXEuASPAJORS1QjCIdTvT7axVXemn3zZjL1qDiW7AkJFnOdXP3LPHdXWHG1JVd9C9401M%2B29iPMmCN7F9WXfhiA9%2FE9PPhu9ShzexYcd25AV26mmzFovEg9IYzyxY%2BJx7SOUhji4Z8h7iuTd20pvUrM0Zz7wp5jbZcEiq7zsfA3gyDgFPkgDw6fiTAD8%2FBXC4ftfYBCvFSHkHxQLhS02xj6wsZ%2BYSOueCo8jeFOclfcQ0wdgwKAourLhiRaGHNkqKJ7o3GK%2BjjC%2Bv9dh5OtIsrogiD3oxyOM1cpeOQ5YP9C1jhqyXzfG2m%2BVx14cfmks1ExxmI0xvkZJGbWiDayukqL9rQrS%2Be0mLL%2FfHIDwNz9Y4DhGOk8%2BCeDLwqzwbyK628qF%2FKUVOywelT1YMpYFfNx%2BEUqKynQMZ0yhIhLZERO4oSLNyRdPJ%2BRSkzqiT3FlcUCRg%2BGOpa8kVDKT81QR7LYdqXQwdvy58RO58Gt9PP5Pv31a8fonPTbmajMx%2FGh%2BrW8EFqXB66%2BiP%2FAaktyWWBdE94c2%2BgV%2FfmmWYQlVWpPR0z0QyAv%2BQWUStJX47edFuQepjJhsLKCpHkaGWqITLJpVDm5b9kULWK1y9ViSnFd8MbrhcHarYIVl58wju24m4rfMhsfS3HW%2BWjZBFuC7nC7by8MTAHfo0nD20qRnY6fQY2s8J%2Bzt7IIunpb6OD%2FdQT7LMwu41vnrbKOhCSLheCz5UK7Z44rSxa2ecIf0ctvVwftHOW05gByRB1H7kCtbUJdm15iUDRRL9xiokCMLVkY8e5j3AvHCy%2F9VV1sxiB4487WlXJqsFycyzaW90bj1W5ZZ02bvRmZWMPfvMOsGAu9I3COQHVsSHiDfdO7XDe3g8%2FSxibic6qSbW1eGbTnDKiwv8wgu9RUmahi1CMg8rZ7pl6m9sn6VxbPs%2F0fIsAtI2%2FfnWM57vvM4tlQyCQuWxO9bryLTlz8FC24MrewGOwxVzOg0R7X3keEPp%2FXJqvLvwHthvQ55591UovfwP%3C%2Fdiagram%3E%3C%2Fmxfile%3E"></iframe>
    '''
    soup = BeautifulSoup(test_html, "html.parser")
    iframe_tag = soup.find("iframe")
    link_md = extract_drawio_link_markdown(iframe_tag)
    print("=== TEST DRAW.IO LINK ===")
    print(link_md)

# ================= RSS =======================

feed = feedparser.parse(RSS_URL)
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

    article_cache = CACHE_ROOT / slug
    hash_path = article_cache / ".content.hash"
    old_hash = hash_path.read_text("utf-8") if hash_path.exists() else None

    if md_path.exists() and old_hash == html_hash:
        stats["articles_unchanged"] += 1
        continue

    soup = BeautifulSoup(raw_html, "html.parser")

    # ===== DRAW.IO IFRAME SUPPORT В ЦИКЛЕ =====
    for iframe in soup.find_all("iframe"):
        link_md = extract_drawio_link_markdown(iframe)
        if link_md:
            iframe.replace_with(link_md)
            print(f"🔗 Draw.io link added: {slug}")

    image_index = {}
    index_path = article_cache / ".images.json"
    if index_path.exists():
        image_index = json.loads(index_path.read_text("utf-8"))

    current_used = set()
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
    content_md = re.sub(
        r"OBSIDIAN\\?_IMAGE::(.+)",
        r"![[Teletype_0x/Cach/\1]]",
        content_md
    )

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

    for f in cache_dir.iterdir():
        if f.suffix.lower() in IMAGE_EXTS and f.name not in imgs:
            f.unlink()
            print(f"🗑 IMG: {slug}/{f.name}")
            stats["images_removed"] += 1

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

print("\n✅ Готово.")

# ===== Запуск теста Draw.io =====
if __name__ == "__main__":
    test_drawio_extraction()