import feedparser
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from pathlib import Path
from datetime import datetime
import sys

# ================= НАСТРОЙКИ =================
RSS_URL = "https://teletype.in/rss/bearsocietatis"
VAULT_ROOT = Path(".")
AUTHOR = "Alexander"
# =============================================

feed = feedparser.parse(RSS_URL)

if not feed.entries:
    print("❌ RSS пустой или недоступен.")
    sys.exit(1)

# ---------- helpers ----------

def normalize_tag(tag: str) -> str:
    return tag.replace(" ", "_").lower()

def safe_filename(title: str) -> str:
    forbidden = r'\/:*?"<>|'
    for ch in forbidden:
        title = title.replace(ch, "")
    return title.strip()

def get_main_folder(entry):
    if entry.get("category"):
        return normalize_tag(entry.category)
    return "misc"

# ---------- URLs из RSS ----------

rss_urls = {e.link for e in feed.entries if e.get("link")}

# ================= ИМПОРТ =================

for entry in feed.entries:
    url = entry.link

    # ✅ ЧЕЛОВЕЧЕСКИЙ ЗАГОЛОВОК
    title = entry.title.strip()

    folder = get_main_folder(entry)
    article_dir = VAULT_ROOT / folder
    article_dir.mkdir(parents=True, exist_ok=True)

    filename = safe_filename(title)
    file_path = article_dir / f"{filename}.md"

    created = ""
    if entry.get("published_parsed"):
        created = datetime(*entry.published_parsed[:6]).date()

    updated = datetime.now().date()

    html = entry.get("content", [{}])[0].get("value", "")
    soup = BeautifulSoup(html, "html.parser")
    content_md = md(str(soup), heading_style="ATX")

    tags = []
    for t in entry.get("tags", []):
        if hasattr(t, "term"):
            tags.append(normalize_tag(t.term))

    tag_links = [f"[[{t}]]" for t in tags]

    # сохранить original created
    if file_path.exists():
        for line in file_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("created:"):
                created = line.replace("created:", "").strip()
                break

    # ❌ НЕТ H1
    frontmatter = f"""---
source: teletype
author: {AUTHOR}
url: {url}
created: {created}
updated: {updated}
tags: [{', '.join(tags)}]
---

**Теги:** {' '.join(tag_links)}

"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(frontmatter)
        f.write(content_md)

    print(f"✔ {title}")

# ================= ПРОВЕРКА УДАЛЁННЫХ =================

missing = []

for md_file in VAULT_ROOT.rglob("*.md"):
    text = md_file.read_text(encoding="utf-8")
    url_line = next((l for l in text.splitlines() if l.startswith("url:")), None)
    if not url_line:
        continue

    if url_line.replace("url:", "").strip() not in rss_urls:
        missing.append(md_file)

if not missing:
    print("✅ Удалённых статей нет.")
else:
    print("\n⚠ Найдены статьи, которых НЕТ в Teletype:")
    for f in missing:
        print(f" - {f.relative_to(VAULT_ROOT)}")

    if input("\nEnter — удалить, любой текст — отмена\n> ") == "":
        for f in missing:
            f.unlink()
            print(f"❌ Удалено: {f.name}")
