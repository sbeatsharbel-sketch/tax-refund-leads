#!/usr/bin/env python3
"""S13 partner logo wall.

Normalises by optical ink area rather than bounding-box height: a wide wordmark
and a compact emblem set to the same height look badly unequal on a big screen.
Each mark is scaled so its rendered ink covers the same area, then clamped so
nothing overruns a sane height or width.

Partner medical centers only. Commercial sponsors live in S16, in their own row.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from filmlib import ROOT, W, H, BG, CYAN, SILVER, font, centred_line

LOGOS = ROOT / "assets" / "source" / "logos"
OUTDIR = ROOT / "build" / "shots"

# Client-specified order. Do not alphabetise or re-sort.
ORDER = [
    ("01_galilee", "Galilee Medical Center", "Nahariya"),
    ("02_rambam", "Rambam Health Care Campus", "Haifa"),
    ("03_hadassah", "Hadassah Medical Organization", "Jerusalem"),
    ("04_sheba", "Sheba Medical Center, Tel HaShomer", "Ramat Gan"),
]

TARGET_INK = 40000.0     # px^2 of visible ink per mark at 1920x1080
MAX_H, MAX_W = 190, 460  # per-logo clamps
GUTTER = 92
# Brand minimum clear-space, as a multiple of each mark's own height.
CLEAR_SPACE = {"01_galilee": 0.5}
DEFAULT_CLEAR = 0.4


def load(slug, px=1400):
    """Return an RGBA raster for a slug, preferring the vector file."""
    svg, png = LOGOS / f"{slug}.svg", LOGOS / f"{slug}.png"
    if svg.exists():
        out = LOGOS / f".render_{slug}.png"
        subprocess.run(["rsvg-convert", "-w", str(px), str(svg), "-o", str(out)],
                       check=True)
        return Image.open(out).convert("RGBA")
    if png.exists():
        return Image.open(png).convert("RGBA")
    return None


def ink_area(img):
    """Visible ink in px^2, weighted by alpha - not the bounding box."""
    a = np.asarray(img.getchannel("A"), dtype=np.float32) / 255.0
    return float(a.sum())


def trim(img):
    bbox = img.getchannel("A").getbbox()
    return img.crop(bbox) if bbox else img


def scale_for_ink(img, target=TARGET_INK):
    """Scale so ink area hits the target, then clamp to MAX_H / MAX_W."""
    img = trim(img)
    ink = ink_area(img)
    if ink <= 0:
        return img, 1.0
    k = (target / ink) ** 0.5
    w, h = max(1, round(img.width * k)), max(1, round(img.height * k))
    if h > MAX_H:
        k *= MAX_H / h
    if round(img.width * k) > MAX_W:
        k *= MAX_W / round(img.width * k)
    w, h = max(1, round(img.width * k)), max(1, round(img.height * k))
    return img.resize((w, h), Image.LANCZOS), k


def build(width=W, height=H, out=None):
    out = Path(out) if out else OUTDIR / "logo_wall.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    scale = width / W

    marks, missing = [], []
    for slug, name, city in ORDER:
        img = load(slug)
        if img is None:
            missing.append((slug, name))
            marks.append((slug, name, None, 0.0))
            continue
        scaled, k = scale_for_ink(img, TARGET_INK * scale * scale)
        marks.append((slug, name, scaled, k))

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    present = [m for m in marks if m[2] is not None]

    if present:
        clear = [int(m[2].height * CLEAR_SPACE.get(m[0], DEFAULT_CLEAR))
                 for m in present]
        widths = [m[2].width + 2 * c for m, c in zip(present, clear)]
        total = sum(widths) + GUTTER * scale * (len(present) - 1)
        x = (width - total) / 2
        centre_y = height * 0.47
        for (slug, name, img, k), c, wdt in zip(present, clear, widths):
            cx = x + wdt / 2
            canvas.alpha_composite(img, (int(cx - img.width / 2),
                                         int(centre_y - img.height / 2)))
            x += wdt + GUTTER * scale

    if missing:
        d = ImageDraw.Draw(canvas, "RGBA")
        y = int(height * 0.66)
        centred_line(canvas, f"{len(missing)} PARTNER LOGO(S) NOT YET SOURCED",
                     font("sans_semibold", int(40 * scale)), y, (199, 79, 168),
                     tracking=3)
        centred_line(canvas, ", ".join(n for _, n in missing),
                     font("sans", int(40 * scale)), y + int(58 * scale), SILVER)

    canvas.save(out)
    print(f"  -> {out.relative_to(ROOT)}  ({width}x{height})")
    print(f"  {'slug':<16}{'scale':>8}{'ink px^2':>12}{'w x h':>14}")
    for slug, name, img, k in marks:
        if img is None:
            print(f"  {slug:<16}{'—':>8}{'MISSING':>12}{'—':>14}")
        else:
            print(f"  {slug:<16}{k:>8.3f}{ink_area(img):>12.0f}"
                  f"{f'{img.width}x{img.height}':>14}")
    if missing:
        print("  override any scale by editing TARGET_INK / MAX_H in this file")
    return out, missing


def main():
    print("partner logo wall ->")
    _, missing = build(W, H, OUTDIR / "logo_wall.png")
    build(3840, 2160, OUTDIR / "logo_wall_4k.png")
    if missing:
        print(f"\n  {len(missing)} logo(s) still required — see "
              f"assets/source/logos/SOURCES.md")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
