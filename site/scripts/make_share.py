"""Link-preview card for the Rétro skin: public/share.jpg (1200x630, the Open Graph size).

Paper grid, the site's black header with its red stripe, Silkscreen, and the 12 team jerseys with their codes
(lib/jerseys.json, images from make_jerseys.py). Everything is drawn at whole-pixel scales so it stays crisp.
Run from site/scripts/: python3 make_share.py
"""

import json

from PIL import Image, ImageDraw, ImageFont

from make_jerseys import OUT as JERSEYS, ROOT

W, H = 1200, 630
INK, PAPER, CARD, RED, BLUE, MUTED = "#1c1b19", "#f4efe4", "#fffdf7", "#d62b2b", "#2440d8", "#6b655a"
# Silkscreen's "&" looks like a "$", so the card spells it out. The share text in app/layout.tsx keeps the "&".
TITLE, TAGLINE = "INSERT COIN", "12 golfeurs, 1 jupe et 1 collant"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ROOT / f"scripts/fonts/Silkscreen-{'Bold' if bold else 'Regular'}.ttf"), size)


def text(d: ImageDraw.ImageDraw, xy, s: str, f, fill, anchor="la"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def main():
    jerseys = {int(k): v for k, v in json.loads((ROOT / "lib/jerseys.json").read_text()).items() if k.isdigit()}
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"

    # 8 px paper grid, as on the site
    grid = "#e9e4d9"
    for x in range(0, W, 8):
        d.line((x, 0, x, H), fill=grid)
    for y in range(0, H, 8):
        d.line((0, y, W, y), fill=grid)

    # Header bar
    d.rectangle((0, 0, W, 79), fill=INK)
    d.rectangle((0, 80, W, 87), fill=RED)
    text(d, (56, 40), "POOL 2026-27", font(32, bold=True), CARD, "lm")
    text(d, (W - 56, 40), "LNH · SAISON 2026-27", font(24), "#b9b2a3", "rm")

    # Title and tagline
    text(d, (56, 136), TITLE, font(96, bold=True), INK)
    d.rectangle((56, 256, 151, 263), fill=RED)
    d.rectangle((168, 256, 263, 263), fill=BLUE)
    text(d, (56, 296), TAGLINE, font(40), MUTED)

    # The 12 teams: jersey badge in a framed card, code tag below
    cell, top = 88, 432
    left = (W - 12 * cell) // 2
    for i, tid in enumerate(sorted(jerseys)):
        j = jerseys[tid]
        x = left + i * cell
        box = (x + 8, top, x + cell - 8, top + cell - 16)
        d.rectangle((box[0] + 4, box[1] + 4, box[2] + 4, box[3] + 4), fill=INK)  # hard shadow
        d.rectangle(box, fill=CARD, outline=INK, width=3)
        badge = Image.open(JERSEYS / f"{tid}-badge.png").convert("RGBA")
        badge = badge.resize((badge.width * 2, badge.height * 2), Image.NEAREST)
        bx = (box[0] + box[2]) // 2 - badge.width // 2
        by = (box[1] + box[3]) // 2 - badge.height // 2
        im.paste(badge, (bx, by), badge)
        tag_font = font(24)
        tb = d.textbbox((0, 0), j["code"], font=tag_font, anchor="la")
        tw = tb[2] - tb[0] + 12
        tx, ty = (box[0] + box[2]) // 2 - tw // 2, box[3] + 20
        light = luminance(j["main"]) > 0.8
        d.rectangle((tx, ty - 4, tx + tw, ty + 26), fill=j["main"], outline=INK if light else None, width=2)
        color = next((c for c in (j["trim"], j["stripe"], INK, CARD) if contrast(c, j["main"]) >= 4.5), INK)  # same rule as the site (lib/jerseys.ts)
        text(d, (tx + tw // 2, ty + 11), j["code"], tag_font, color, "mm")

    im.save(ROOT / "public/share.jpg", quality=92, subsampling=0)
    print("public/share.jpg")


def luminance(hex_color: str) -> float:
    c = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


if __name__ == "__main__":
    main()
