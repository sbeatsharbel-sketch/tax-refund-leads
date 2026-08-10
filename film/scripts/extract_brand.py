#!/usr/bin/env python3
"""Extract genuine brand vectors from the client's own conference PDF.

The programme PDF is an Adobe Illustrator export with live vector artwork, so
the Galilee Medical Center logo and the BEYOND THE IMAGE 2026 lockup can be
lifted as real vectors. Nothing here is drawn, traced or approximated - the
paths are the client's own, cropped by viewBox and (for dark backgrounds)
recoloured, which is the knockout treatment the brief asks for.
"""
import re
import subprocess
import sys
from pathlib import Path

from filmlib import ROOT

SRC_PDF = Path("/root/.claude/uploads/991e6ba0-17df-5799-9d3d-b6ea1e4537dd/"
               "792a0785-BTI2026_PorgramFinal.pdf")
WORK = ROOT / "build" / "_pdf"
LOGOS = ROOT / "assets" / "source" / "logos"
BRAND = ROOT / "assets" / "source" / "brand"

# Measured from a 110 dpi render of page 1, converted to PostScript points.
REGIONS = {
    "galilee_logo":  "24.78 25.44 108.08 43.98",
    "bti_lockup":    "192.28 66.69 210.06 22.97",
    "bti_subtitle":  "110.51 95.47 374.90 13.81",
}

# Fills as they appear in the pdftocairo SVG output.
NAVY = "rgb(3.09906%, 16.899109%, 37.298584%)"
PURPLE = "rgb(47.799683%, 17.298889%, 88.598633%)"

SILVER = "rgb(91.0%, 92.9%, 94.9%)"   # #E8EDF2
CYAN = "rgb(18.4%, 74.9%, 85.5%)"     # #2FBFDA


def page_svg():
    WORK.mkdir(parents=True, exist_ok=True)
    out = WORK / "prog1.svg"
    if not out.exists():
        subprocess.run(["pdftocairo", "-svg", "-f", "1", "-l", "1",
                        str(SRC_PDF), str(out)], check=True)
    return out


PATH_RE = re.compile(r'<path\b[^>]*?/>', re.S)
NUM_RE = re.compile(r'-?\d+(?:\.\d+)?')


def keep_paths_in(body, vb, margin=1.0):
    """Drop every path whose bbox lies outside the crop.

    Without this each cropped file still carries the whole programme page -
    a 2.4 MB 'logo' that opens as the entire conference programme in
    Illustrator. viewBox alone only hides the rest; it does not remove it.
    """
    x0, y0, w, h = vb
    x1, y1 = x0 + w, y0 + h
    kept = []
    for m in PATH_RE.finditer(body):
        chunk = m.group(0)
        d = chunk.find(' d="')
        nums = [float(n) for n in NUM_RE.findall(chunk[d:])] if d >= 0 else []
        if len(nums) < 2:
            continue
        xs, ys = nums[0::2], nums[1::2]
        if (max(xs) >= x0 - margin and min(xs) <= x1 + margin
                and max(ys) >= y0 - margin and min(ys) <= y1 + margin):
            kept.append(chunk)
    return "".join(kept)


def crop(body, view_box, w_px, recolour=None, mono=None):
    vb = [float(v) for v in view_box.split()]
    h_px = int(round(w_px * vb[3] / vb[2]))
    body = keep_paths_in(body, vb)
    if mono:
        body = _mono(body, mono)
    elif recolour:
        for a, b in recolour.items():
            body = body.replace(a, b)
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w_px}" height="{h_px}" viewBox="{view_box}">'
            f'{body}</svg>'), h_px


def _mono(body, colour):
    """Force every fill to one colour - the single-colour knockout variant."""

    return re.sub(r'fill="rgb\([^)]*\)"', f'fill="{colour}"', body)


def main():
    if not SRC_PDF.exists():
        sys.exit(f"source PDF not found: {SRC_PDF}")
    src = page_svg().read_text()
    body = src[src.index(">", src.index("<svg")) + 1: src.rindex("</svg>")]

    LOGOS.mkdir(parents=True, exist_ok=True)
    BRAND.mkdir(parents=True, exist_ok=True)
    made = []

    # 1. Galilee Medical Center - official full colour, plus a knockout for navy
    svg, h = crop(body, REGIONS["galilee_logo"], 2400)
    (LOGOS / "01_galilee_colour.svg").write_text(svg)
    made.append(("01_galilee_colour.svg", f"2400x{h}", "official, full colour"))

    svg, h = crop(body, REGIONS["galilee_logo"], 2400, mono=SILVER)
    (LOGOS / "01_galilee.svg").write_text(svg)
    made.append(("01_galilee.svg", f"2400x{h}", "knockout for dark navy"))

    # 2. Conference lockup, recoloured the way the client's own poster does it
    svg, h = crop(body, REGIONS["bti_lockup"], 3000,
                  recolour={NAVY: SILVER, PURPLE: CYAN})
    (BRAND / "bti_lockup_dark.svg").write_text(svg)
    made.append(("brand/bti_lockup_dark.svg", f"3000x{h}", "white + cyan on navy"))

    svg, h = crop(body, REGIONS["bti_lockup"], 3000)
    (BRAND / "bti_lockup_light.svg").write_text(svg)
    made.append(("brand/bti_lockup_light.svg", f"3000x{h}", "as printed"))

    # 3. Official conference subtitle
    # The subtitle is set in the body navy, not the lockup navy - force mono.
    svg, h = crop(body, REGIONS["bti_subtitle"], 3000, mono=CYAN)
    (BRAND / "bti_subtitle_dark.svg").write_text(svg)
    made.append(("brand/bti_subtitle_dark.svg", f"3000x{h}", "cyan on navy"))

    print("brand extraction ->")
    for name, size, note in made:
        print(f"  {name:<32} {size:>12}  {note}")

    for svgp in [LOGOS / "01_galilee.svg", BRAND / "bti_lockup_dark.svg",
                 BRAND / "bti_subtitle_dark.svg"]:
        png = svgp.with_suffix(".png")
        subprocess.run(["rsvg-convert", "-w", "3000", str(svgp), "-o", str(png)],
                       check=True)
    print("  rasterised PNG companions written alongside each SVG")


if __name__ == "__main__":
    main()
