"""Site icons.

Browser tab (app/favicon.ico, 16/32/48): a pixel "P" in Silkscreen Bold over a red bar, drawn pixel-exact at
each size. The skater sprite is too detailed to read at tab size.
Home screen (app/apple-icon.png 180, also used by Android): the CC0 skater sprite (see make_jerseys.py) in a white
jersey with black trim and red stripes.
Run from site/scripts/: python3 make_favicon.py
"""

from PIL import Image, ImageDraw, ImageFont

from make_jerseys import ROOT, SRC, hex_rgb, largest_blob, recolor

INK, WHITE, RED = "#1c1b19", "#ffffff", "#d62b2b"
FONT = ROOT / "scripts/fonts/Silkscreen-Bold.ttf"


def tab_icon(n: int) -> Image.Image:
    im = Image.new("RGBA", (n, n))
    d = ImageDraw.Draw(im)
    d.fontmode = "1"  # no antialiasing: whole pixels only
    d.rounded_rectangle((0, 0, n - 1, n - 1), radius=max(2, n // 5), fill=INK)
    gap, bar = 2 * max(1, n // 16), max(2, n // 8)
    d.rectangle((0, n - gap - bar, n - 1, n - gap - 1), fill=RED)
    font = ImageFont.truetype(str(FONT), n)
    box = d.textbbox((0, 0), "P", font=font)
    top = (n - gap - bar - (box[3] - box[1])) // 2
    d.text(((n - (box[2] - box[0])) // 2 - box[0], top - box[1]), "P", font=font, fill=WHITE)
    return im


def skater_icon(size: int, padding: float, rounded: bool) -> Image.Image:
    sprite = Image.open(SRC / "team2-skate1.png").convert("RGBA")
    badge = largest_blob(recolor(sprite, hex_rgb(WHITE), hex_rgb(INK), hex_rgb(RED), drop_stick=True))
    badge = badge.crop(badge.getbbox())
    scale = max(1, int(size * (1 - 2 * padding) / max(badge.size)))
    badge = badge.resize((badge.width * scale, badge.height * scale), Image.NEAREST)
    out = Image.new("RGBA", (size, size))
    shape = ImageDraw.Draw(out)
    if rounded:
        shape.rounded_rectangle((0, 0, size - 1, size - 1), radius=size * 0.22, fill=INK)
    else:
        shape.rectangle((0, 0, size - 1, size - 1), fill=INK)
    out.paste(badge, ((size - badge.width) // 2, (size - badge.height) // 2), badge)
    return out


def main():
    sizes = [16, 32, 48]
    tabs = [tab_icon(n) for n in sizes]
    tabs[-1].save(ROOT / "app/favicon.ico", sizes=[(n, n) for n in sizes], append_images=tabs[:-1])
    skater_icon(180, 0.14, rounded=False).save(ROOT / "app/apple-icon.png")  # iOS rounds the corners itself
    print("app/favicon.ico, app/apple-icon.png")


if __name__ == "__main__":
    main()
