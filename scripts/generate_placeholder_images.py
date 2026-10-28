#!/usr/bin/env python3
# Copyright 2026 The Antojo Authors. SPDX-License-Identifier: MIT
"""Generate Antojo's self-made placeholder images with Pillow.

All images are flat shapes and text drawn by this script, so there are no
third-party or copyrighted assets. Run from the repository root:

    python3 scripts/generate_placeholder_images.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "services" / "frontend" / "static"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

CHILE = (179, 38, 30)
CREAM = (253, 246, 236)
AGAVE = (63, 125, 88)
MARIGOLD = (242, 165, 65)


def font(size):
    try:
        return ImageFont.truetype(FONT_BOLD, size)
    except OSError:
        return ImageFont.load_default()


def centered_text(draw, box, text, size, fill):
    f = font(size)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=f)
    x = box[0] + (box[2] - box[0] - (right - left)) / 2
    y = box[1] + (box[3] - box[1] - (bottom - top)) / 2
    draw.text((x, y), text, font=f, fill=fill)


def hero(path, size):
    img = Image.new("RGB", size, CHILE)
    d = ImageDraw.Draw(img)
    w, h = size
    # Papel picado style triangles along the top edge.
    colors = [MARIGOLD, AGAVE, CREAM]
    step = w // 12
    for i in range(12):
        d.polygon([(i * step, 0), ((i + 1) * step, 0), (i * step + step / 2, h // 6)],
                  fill=colors[i % 3])
    centered_text(d, (0, h // 6, w, h), "Antojo", h // 4, CREAM)
    img.save(path)


def favicon(path):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, 62, 62), fill=CHILE)
    centered_text(d, (0, 0, 64, 64), "A", 40, CREAM)
    img.save(path, sizes=[(16, 16), (32, 32), (64, 64)])


LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="160" height="40" viewBox="0 0 160 40">
  <circle cx="20" cy="20" r="18" fill="#B3261E"/>
  <text x="20" y="27" font-family="DejaVu Sans, Arial, sans-serif" font-size="20" font-weight="700" fill="#FDF6EC" text-anchor="middle">A</text>
  <text x="46" y="28" font-family="DejaVu Sans, Arial, sans-serif" font-size="22" font-weight="700" fill="#B3261E">Antojo</text>
</svg>
"""


def dish(path, name, color):
    img = Image.new("RGB", (600, 600), CREAM)
    d = ImageDraw.Draw(img)
    d.ellipse((90, 90, 510, 510), fill=(255, 255, 255), outline=MARIGOLD, width=12)
    d.ellipse((160, 160, 440, 440), fill=color)
    words = name.split()
    lines, line = [], ""
    for word in words:
        if len(line) + len(word) > 14 and line:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    lines.append(line)
    top = 300 - 22 * len(lines)
    for i, text in enumerate(lines):
        centered_text(d, (0, top + i * 44, 600, top + (i + 1) * 44), text, 34, CREAM)
    img.save(path, quality=85)


def brand():
    (STATIC / "icons").mkdir(parents=True, exist_ok=True)
    (STATIC / "images").mkdir(parents=True, exist_ok=True)
    (STATIC / "icons" / "logo.svg").write_text(LOGO_SVG)
    favicon(STATIC / "favicon.ico")
    hero(STATIC / "images" / "hero.png", (800, 800))
    hero(STATIC / "images" / "hero-wide.png", (1600, 400))


def dishes():
    catalog = ROOT / "services" / "productcatalogservice" / "products.json"
    if not catalog.exists():
        return
    palette = {"tortas": CHILE, "caldos": (122, 62, 32), "tacos": AGAVE,
               "bebidas": MARIGOLD, "postres": (196, 120, 70)}
    for p in json.loads(catalog.read_text())["products"]:
        out = STATIC / p["picture"].removeprefix("/static/")
        out.parent.mkdir(parents=True, exist_ok=True)
        color = palette.get(p["categories"][0], CHILE)
        dish(out, p["name"], color)


if __name__ == "__main__":
    brand()
    dishes()
