#!/usr/bin/env python3
import base64
import zlib
import urllib.parse
import urllib.request
import json
from pathlib import Path

# =========================
# ВСТАВЬ ССЫЛКУ СЮДА
# =========================
URL = """"""
OUTPUT_FILE = "diagram.svg"
# =========================


EXPORT_URL = "https://convert.diagrams.net/export"


from urllib.parse import urlparse, unquote


from urllib.parse import urlparse, unquote
import urllib.request


def extract_mxfile_from_url(url: str) -> str:
    parsed = urlparse(url)

    if not parsed.fragment:
        raise ValueError("Нет fragment в ссылке.")

    fragment = parsed.fragment

    # 🔹 Формат #R (встроенная диаграмма)
    if fragment.startswith("R"):
        data = fragment[1:]
        data = unquote(data)

        import base64, zlib

        missing_padding = len(data) % 4
        if missing_padding:
            data += "=" * (4 - missing_padding)

        decoded = base64.b64decode(data)

        try:
            decompressed = zlib.decompress(decoded, -15)
        except zlib.error:
            decompressed = zlib.decompress(decoded)

        return decompressed.decode("utf-8")

    # 🔹 Формат #U (внешний файл)
    elif fragment.startswith("U"):
        external_url = unquote(fragment[1:])
        print("Найдена внешняя ссылка:", external_url)

        with urllib.request.urlopen(external_url) as response:
            return response.read().decode("utf-8")

    else:
        raise ValueError("Неизвестный формат fragment.")


def export_svg(mxfile_xml: str) -> bytes:
    payload = {
        "format": "svg",
        "xml": mxfile_xml,
        "base64": False
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        EXPORT_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(request) as response:
        return response.read()


def main():
    print("Извлечение mxfile из ссылки...")
    mxfile = extract_mxfile_from_url(URL)

    print("Отправка в export API...")
    svg_data = export_svg(mxfile)

    Path(OUTPUT_FILE).write_bytes(svg_data)

    print(f"✓ Полный SVG сохранён: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()