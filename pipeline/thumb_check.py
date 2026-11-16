"""Section 8 T5: build the thumbnail gate sheets. The judging is done by eye, this only makes the views.

    python pipeline/thumb_check.py <thumbnail> --out jobs/<job>/thumb/check [--refs <folder or files...>]

Writes <out>_sheet.png: the thumbnail at 168x94 and 320x180 (real pixels, how YouTube shows it),
greyscale, and Gaussian blur 12 px (measured on a 1280x720 copy).
With --refs also writes <out>_grid.png: ours among up to 8 references, 320x180 each, in a random
slot with no label so it is judged fairly; the slot is printed here.
"""
import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
BG = (24, 24, 24)

def fit(img, size):
    return ImageOps.fit(img, size, Image.LANCZOS)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("thumb")
    ap.add_argument("--out", required=True, help="output path without extension")
    ap.add_argument("--refs", nargs="*", default=[])
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    src = Image.open(a.thumb).convert("RGB")
    if abs(src.width / src.height - 16 / 9) > 0.02:
        print(f"WARN: {src.width}x{src.height} is not 16:9; views are centre-cropped")
    base = fit(src, (1280, 720))
    views = [("168x94 (suggested / sidebar)", fit(src, (168, 94))),
             ("320x180 (home grid)", fit(src, (320, 180))),
             ("greyscale: does the subject separate?", fit(ImageOps.grayscale(base).convert("RGB"), (640, 360))),
             ("blur 12 px: one focal point?", fit(base.filter(ImageFilter.GaussianBlur(12)), (640, 360)))]
    pad, label_h = 24, 22
    sheet = Image.new("RGB", (pad * 3 + 640 * 2, pad * 3 + label_h * 2 + 360 + 180), BG)
    d = ImageDraw.Draw(sheet)
    spots = [(pad, pad), (pad + 168 + pad, pad), (pad, pad * 2 + label_h + 180), (pad * 2 + 640, pad * 2 + label_h + 180)]
    for (label, im), (x, y) in zip(views, spots):
        d.text((x, y), label, fill=(200, 200, 200))
        sheet.paste(im, (x, y + label_h))
    sheet.save(out.with_name(out.name + "_sheet.png"))
    print("wrote", out.with_name(out.name + "_sheet.png"))

    refs = []
    for p in map(Path, a.refs):
        refs += sorted(f for f in p.iterdir() if f.suffix.lower() in IMAGE_EXT) if p.is_dir() else [p]
    refs = [r for r in refs if r.resolve() != Path(a.thumb).resolve()][:8]
    if refs:
        if len(refs) < 8:
            print(f"WARN: only {len(refs)} references; the gate asks for 8")
        tiles = [fit(Image.open(r).convert("RGB"), (320, 180)) for r in refs]
        slot = random.Random(a.seed).randrange(len(tiles) + 1)
        tiles.insert(slot, fit(src, (320, 180)))
        cols = 3
        rows = -(-len(tiles) // cols)
        g = 12
        grid = Image.new("RGB", (g + cols * (320 + g), g + rows * (180 + g)), BG)
        for i, t in enumerate(tiles):
            grid.paste(t, (g + (i % cols) * (320 + g), g + (i // cols) * (180 + g)))
        grid.save(out.with_name(out.name + "_grid.png"))
        print(f"wrote {out.with_name(out.name + '_grid.png')}; ours is tile {slot + 1} "
              f"(row {slot // cols + 1}, column {slot % cols + 1})")
    print("Now judge by eye against the T5 gate in MASTER_PLAN.md section 8.")

if __name__ == "__main__":
    main()
