import requests
from bs4 import BeautifulSoup
import html2text
from pathlib import Path
from urllib.parse import urljoin, urlparse
import re

# ==================================================
# ПУТИ (скрипт в .obsidian/)
# ==================================================

SCRIPT_DIR = Path(__file__).resolve().parent        # .obsidian
VAULT_PATH = SCRIPT_DIR.parent                     # Teletype

OUTPUT_FOLDER = VAULT_PATH / "hidden"               # md
ASSETS_ROOT = VAULT_PATH / "Teletype_0x" / "assets" # !!! ВАЖНО

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
ASSETS_ROOT.mkdir(parents=True, exist_ok=True)

# ==================================================
# HTTP СЕССИЯ
# ==================================================

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://teletype.in/"
})

# ==================================================
# ВСПОМОГАТЕЛЬНОЕ
# ==================================================

def normalize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name)
    return name


# ==================================================
# ОСНОВНАЯ ЛОГИКА
# ==================================================

def process_teletype(url: str):
    print(f"\n⏳ {url}")

    resp = session.get(url, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")

    # ❗ noscript НЕ УДАЛЯЕМ
    for tag in soup(["script", "style", "iframe"]):
        tag.decompose()

    # --------------------------------------------------
    # Заголовок
    # --------------------------------------------------

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "Teletype Article"
    safe_title = normalize_filename(title)

    md_path = OUTPUT_FOLDER / f"{safe_title}.md"
    article_assets = ASSETS_ROOT / safe_title
    article_assets.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------
    # ИЗОБРАЖЕНИЯ (Teletype DOM)
    # --------------------------------------------------

    for img in soup.select("figure.m_original img"):
        src = img.get("src")
        if not src:
            continue

        img_url = urljoin(url, src)
        img_name = Path(urlparse(img_url).path).name
        if not img_name:
            continue

        local_img = article_assets / img_name

        if not local_img.exists():
            r = session.get(
                img_url,
                timeout=20,
                headers={"Referer": "https://teletype.in/"}
            )

            if r.status_code != 200:
                print(f"❌ {img_url} [{r.status_code}]")
                continue

            local_img.write_bytes(r.content)
            print(f"🖼 {img_name}")

        # 👉 ВСТАВЛЯЕМ WIKI-LINK ПОД ТВОЮ СТРУКТУРУ
        img.replace_with(
            soup.new_string(
                f"![[../Teletype_0x/assets/{safe_title}/{img_name}]]"
            )
        )

    # --------------------------------------------------
    # HTML → MARKDOWN
    # --------------------------------------------------

    article = soup.find("article") or soup.body
    html_content = str(article)

    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_images = False
    h.ignore_links = False

    markdown = h.handle(html_content)

    # --------------------------------------------------
    # FRONTMATTER
    # --------------------------------------------------

    frontmatter = f"""---
title: "{title}"
source: {url}
type: article
---

"""

    md_path.write_text(frontmatter + markdown, encoding="utf-8")
    print(f"✅ hidden/{md_path.name}")

# ==================================================
# CLI
# ==================================================

print("📥 Teletype → Obsidian")
print("Вставь ссылку на teletype.in и нажми Enter")
print("Пустая строка — выход")

while True:
    user_input = input("\n🔗 Ссылка: ").strip()

    if not user_input:
        print("👋 Выход")
        break

    if "teletype.in" not in user_input:
        print("⚠️ Это не ссылка Teletype")
        continue

    process_teletype(user_input)
