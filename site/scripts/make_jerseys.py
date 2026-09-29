"""Recolor the CC0 skater sprite into each team's jersey for the Rétro skin.

Reads lib/jerseys.json and public/skins/retro/source/ ("Hockey Players" by Taylor J Glidden, CC0).
Writes to public/skins/retro/jerseys/:
  {id}-up.png, {id}-down.png  two skating frames side by side (background skaters, facing up / down)
  {id}-badge.png              the jersey alone, no stick, cropped square (team avatar)
Run from site/: python3 scripts/make_jerseys.py
"""

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "public/skins/retro/source"
OUT = ROOT / "public/skins/retro/jerseys"

# The source sprite's three jersey colors.
RED, BLUE, WHITE = (255, 4, 33), (16, 20, 247), (255, 255, 255)


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def close(p, c, tol=40) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(p, c))


def is_stick(p) -> bool:
    r, g, b = p
    return r > 40 and abs(r - g) < 8 and r - b > 15


def recolor(im: Image.Image, main, trim, stripe, drop_stick=False) -> Image.Image:
    im = im.copy()
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            p = (r, g, b)
            if drop_stick and is_stick(p):
                px[x, y] = (0, 0, 0, 0)
            elif close(p, RED):
                px[x, y] = (*main, a)
            elif close(p, BLUE):
                px[x, y] = (*trim, a)
            elif close(p, WHITE, 16):
                px[x, y] = (*stripe, a)
    return im


def largest_blob(im: Image.Image) -> Image.Image:
    """Keep the biggest connected group of pixels: the player, without stray stick pixels."""
    px = im.load()
    seen, best = set(), []
    for y in range(im.height):
        for x in range(im.width):
            if (x, y) in seen or px[x, y][3] < 200:
                continue
            blob, todo = [], [(x, y)]
            seen.add((x, y))
            while todo:
                cx, cy = todo.pop()
                blob.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        n = (cx + dx, cy + dy)
                        if 0 <= n[0] < im.width and 0 <= n[1] < im.height and n not in seen and px[n][3] >= 200:
                            seen.add(n)
                            todo.append(n)
            best = max(best, blob, key=len)
    out = Image.new("RGBA", im.size)
    for xy in best:
        out.putpixel(xy, px[xy])
    return out


def union_box(images):
    boxes = [i.getbbox() for i in images]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def strip(frames):
    w, h = frames[0].size
    s = Image.new("RGBA", (w * len(frames), h))
    for k, f in enumerate(frames):
        s.paste(f, (k * w, 0))
    return s


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames = [Image.open(SRC / f"team2-skate{n}.png").convert("RGBA") for n in (1, 2)]
    jerseys = {k: v for k, v in json.loads((ROOT / "lib/jerseys.json").read_text()).items() if k.isdigit()}
    for tid, j in jerseys.items():
        colors = [hex_rgb(j[k]) for k in ("main", "trim", "stripe")]
        up = [recolor(f, *colors) for f in frames]
        box = union_box(up)
        up = [f.crop(box) for f in up]
        strip(up).save(OUT / f"{tid}-up.png")
        strip([f.rotate(180) for f in up]).save(OUT / f"{tid}-down.png")

        badge = largest_blob(recolor(frames[0], *colors, drop_stick=True))
        badge = badge.crop(badge.getbbox())
        side = max(badge.size)
        square = Image.new("RGBA", (side, side))
        square.paste(badge, ((side - badge.width) // 2, (side - badge.height) // 2))
        square.save(OUT / f"{tid}-badge.png")
    print(f"{len(jerseys)} jerseys -> {OUT.relative_to(ROOT)} (frame {up[0].width}x{up[0].height}, badge {side}px)")


if __name__ == "__main__":
    main()
