#!/usr/bin/env python3
"""Backgrounds for the placeholder beats.

Deliberately quiet: a deep navy ground, one large soft light source, a vignette
and a little grain. No line art, no diagrams, no particle mesh. The particle
network is reserved for the brand moments - the title card and the credit - so
the opening and the ending do not look like the same frame.

The light moves and warms across the film, so the piece has a direction:
low and cold at the cold open, rising and warmer through the procedures,
wide and open at the bridge, bright and high by the legacy beat.
"""
import numpy as np
from PIL import Image

from filmlib import W, H, BG, CYAN, MAGENTA

# (x, y, radius, warmth 0..1, strength) per section, as fractions of the frame.
SECTION_LOOK = {
    "Cold open":     (0.30, 0.72, 0.62, 0.00, 0.55),
    "The image":     (0.62, 0.60, 0.70, 0.10, 0.68),
    "Thrombectomy":  (0.38, 0.46, 0.60, 0.42, 0.85),
    "Coiling":       (0.66, 0.44, 0.62, 0.34, 0.80),
    "Embolization":  (0.34, 0.40, 0.66, 0.26, 0.78),
    "Bridge":        (0.50, 0.36, 0.86, 0.12, 0.72),
    "Collaboration": (0.50, 0.42, 0.92, 0.16, 0.86),
    "Legacy":        (0.50, 0.34, 1.00, 0.08, 1.00),
}
DEFAULT_LOOK = (0.5, 0.5, 0.7, 0.15, 0.7)

_GRID = {}


def _grid(w, h):
    if (w, h) not in _GRID:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        _GRID[(w, h)] = (xx / w, yy / h)
    return _GRID[(w, h)]


def field(section, phase=0.0, w=W, h=H, seed=0):
    """One background still. `phase` (0..1) drifts the light within a section."""
    cx, cy, rad, warmth, strength = SECTION_LOOK.get(section, DEFAULT_LOOK)
    cx += 0.05 * np.sin(phase * np.pi * 2 + seed)
    cy -= 0.03 * phase

    fx, fy = _grid(w, h)
    aspect = w / h
    d = np.sqrt(((fx - cx) * aspect) ** 2 + (fy - cy) ** 2)
    glow = np.exp(-(d / rad) ** 1.7).astype(np.float32)

    tint = np.array(CYAN, np.float32) * (1 - warmth) + \
        np.array(MAGENTA, np.float32) * warmth
    base = np.array(BG, np.float32)

    img = base[None, None, :] + glow[..., None] * tint[None, None, :] * strength * 0.62

    # a second, much softer bounce keeps the corners from going flat black
    d2 = np.sqrt(((fx - (1 - cx)) * aspect) ** 2 + (fy - 0.5) ** 2)
    img += np.exp(-(d2 / 1.15) ** 2)[..., None] * tint[None, None, :] * 0.10

    # vignette
    r = np.sqrt(((fx - 0.5) * 1.9) ** 2 + ((fy - 0.5) * 1.9) ** 2)
    img *= np.clip(1.04 - 0.30 * r ** 2, 0, 1)[..., None]

    # fine grain, so large flat areas do not band on a big screen
    rng = np.random.default_rng(seed + 17)
    img += rng.normal(0, 1.7, (h, w, 1)).astype(np.float32)

    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


if __name__ == "__main__":
    from filmlib import ROOT
    out = ROOT / "build" / "_chk"
    out.mkdir(parents=True, exist_ok=True)
    names = list(SECTION_LOOK)
    cols, tw, th = 4, 470, 264
    sheet = Image.new("RGB", (cols * tw, ((len(names) + cols - 1) // cols) * th))
    for i, n in enumerate(names):
        sheet.paste(field(n, 0.3, seed=i).resize((tw, th)),
                    ((i % cols) * tw, (i // cols) * th))
    sheet.save(out / "fields.jpg", quality=92)
    print(out / "fields.jpg")
