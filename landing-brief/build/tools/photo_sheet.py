"""Пронумерованные листы фото фирмы, чтобы выбрать фото для макета глазами, не открывая каждое.

Запуск: python3 tools/photo_sheet.py <id> [--all]
Берёт data/drafts/<id>.json (его создаёт gis_collect.js). По умолчанию только фото от владельца и из Instagram,
с --all ещё и фото посетителей. Номер на плитке равен индексу в списке photos черновика.
Листы сохраняются в .cache/<id>/sheet-1.jpg, sheet-2.jpg и так далее (по 40 фото на лист).
"""
import io
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

HERE = Path(__file__).resolve().parent.parent
TILE, COLS, PER_SHEET = 220, 8, 40


def fetch(url, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Referer": "https://2gis.ru/", "User-Agent": "Mozilla/5.0"})
            return urllib.request.urlopen(req, timeout=40).read()
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(2 ** k)


def thumb(item):
    i, p = item
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(fetch(p["url"])))).convert("RGB")
        return i, p, ImageOps.fit(im, (TILE - 4, TILE - 4))
    except Exception:
        return i, p, None


def main():
    cid = sys.argv[1]
    show_all = "--all" in sys.argv
    draft = json.loads((HERE / "data" / "drafts" / f"{cid}.json").read_text(encoding="utf-8"))
    keep = [(i, p) for i, p in enumerate(draft["photos"])
            if show_all or p["source"] in ("2gis_owner", "instagram")]
    out = HERE / ".cache" / cid
    out.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(8) as ex:
        tiles = list(ex.map(thumb, keep))
    for s in range(0, len(tiles), PER_SHEET):
        chunk = tiles[s:s + PER_SHEET]
        rows = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * TILE, rows * TILE), "white")
        draw = ImageDraw.Draw(sheet)
        for k, (i, p, im) in enumerate(chunk):
            x, y = (k % COLS) * TILE, (k // COLS) * TILE
            if im:
                sheet.paste(im, (x + 2, y + 2))
            label = f"{i} {p['source'][:3]} {p['w']}x{p['h']}"
            draw.rectangle([x + 2, y + 2, x + 8 + 7 * len(label), y + 18], fill="black")
            draw.text((x + 5, y + 4), label, fill="white")
        path = out / f"sheet-{s // PER_SHEET + 1}.jpg"
        sheet.save(path, quality=80)
        print(path)


if __name__ == "__main__":
    main()
