#!/usr/bin/env python3
"""Procedural line-art motifs for the placeholder cards.

Each missing shot gets an abstract figure suggesting its content, drawn in the
brand's own visual language - thin cyan strokes with a soft glow on deep navy.
These are deliberately geometric and stylised. Nothing here is, or could be
mistaken for, real medical imagery.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from filmlib import W, H, CYAN, MAGENTA

GLOW_DIV = 4


class Canvas:
    """Draws to a crisp layer and a parallel low-res layer that becomes glow."""

    def __init__(self, w=W, h=H):
        self.w, self.h = w, h
        self.line_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.glow_img = Image.new("RGB", (w // GLOW_DIV, h // GLOW_DIV), (0, 0, 0))
        self.d = ImageDraw.Draw(self.line_img, "RGBA")
        self.g = ImageDraw.Draw(self.glow_img, "RGBA")

    def line(self, pts, colour=CYAN, alpha=150, width=2, glow=0.5):
        self.d.line(pts, fill=colour + (alpha,), width=width, joint="curve")
        if glow > 0:
            gp = [(x / GLOW_DIV, y / GLOW_DIV) for x, y in pts]
            self.g.line(gp, fill=colour + (int(alpha * glow),),
                        width=max(1, width // GLOW_DIV + 1), joint="curve")

    def dot(self, x, y, r=4, colour=CYAN, alpha=210, glow=1.0):
        self.d.ellipse([x - r, y - r, x + r, y + r], fill=colour + (alpha,))
        if glow > 0:
            gr = r * 3.2 / GLOW_DIV
            self.g.ellipse([x / GLOW_DIV - gr, y / GLOW_DIV - gr,
                            x / GLOW_DIV + gr, y / GLOW_DIV + gr],
                           fill=colour + (int(70 * glow),))

    def arc(self, box, start, end, colour=CYAN, alpha=140, width=2):
        self.d.arc(box, start, end, fill=colour + (alpha,), width=width)
        gb = [v / GLOW_DIV for v in box]
        self.g.arc(gb, start, end, fill=colour + (alpha // 2,), width=1)

    def compose(self, opacity=1.0, gain=2.1):
        glow = self.glow_img.filter(ImageFilter.GaussianBlur(7)).resize(
            (self.w, self.h), Image.BILINEAR)
        arr = np.asarray(glow).astype(np.float32) * gain
        arr = np.clip(arr, 0, 255)
        alpha = np.clip(arr.max(axis=2) * 1.15, 0, 255).astype(np.uint8)
        layer = Image.fromarray(arr.astype(np.uint8)).convert("RGBA")
        layer.putalpha(Image.fromarray(alpha))
        layer.alpha_composite(self.line_img)
        if opacity < 1.0:
            a = layer.getchannel("A").point(lambda v: int(v * opacity))
            layer.putalpha(a)
        return layer


# --- motifs ----------------------------------------------------------------

def _branch(c, x, y, ang, length, width, depth, rng, colour=CYAN, alpha=150,
            dim_after=None, dim_colour=(60, 78, 96)):
    if depth <= 0 or length < 10:
        return
    x2 = x + math.cos(ang) * length
    y2 = y + math.sin(ang) * length
    dim = dim_after is not None and depth <= dim_after
    c.line([(x, y), (x2, y2)],
           colour=dim_colour if dim else colour,
           alpha=70 if dim else alpha,
           width=max(1, int(width)), glow=0.0 if dim else 0.45)
    if depth <= 3 and not dim:
        c.dot(x2, y2, r=max(2, width * 0.9), colour=colour, alpha=180, glow=0.8)
    for s in (-1, 1):
        spread = 0.34 + rng.random() * 0.30
        _branch(c, x2, y2, ang + s * spread, length * (0.70 + rng.random() * 0.12),
                width * 0.72, depth - 1, rng, colour, alpha, dim_after, dim_colour)


def vascular(seed=1, dim_after=None, colour=CYAN, alpha=215, depth=8):
    c = Canvas()
    rng = np.random.default_rng(seed)
    _branch(c, W * 0.5, H * 1.02, -math.pi / 2, H * 0.30, 16, depth, rng,
            colour, alpha, dim_after)
    return c.compose(0.9)


def planes(seed=2):
    """Cross-sectional planes sweeping through a translucent volume."""
    c = Canvas()
    cx, cy, r = W * 0.5, H * 0.5, H * 0.42
    c.arc([cx - r, cy - r * 1.12, cx + r, cy + r * 1.12], 0, 360, alpha=110)
    for i in range(13):
        t = i / 12
        y = cy - r * 1.02 + t * r * 2.04
        half = math.sqrt(max(0.0, 1 - ((y - cy) / (r * 1.12)) ** 2)) * r
        a = 60 + int(120 * math.sin(math.pi * t))
        col = MAGENTA if i == 6 else CYAN
        c.line([(cx - half, y), (cx + half, y)], colour=col, alpha=a,
               width=3 if i == 6 else 2, glow=0.7 if i == 6 else 0.3)
    return c.compose(0.9)


def suite(seed=3):
    """Angio suite, abstracted: a C-arm sweep and a bank of monitors."""
    c = Canvas()
    cx, cy = W * 0.42, H * 0.56
    for k, r in enumerate((392, 420, 448)):
        c.arc([cx - r, cy - r, cx + r, cy + r], 205, 335,
              alpha=150 - k * 40, width=3 if k == 0 else 2)
    c.line([(cx - 330, cy + 274), (cx + 330, cy + 274)], alpha=160, width=4)
    x0 = W * 0.66
    for i in range(3):
        x = x0 + i * 205
        c.line([(x, H * 0.30), (x + 168, H * 0.30), (x + 168, H * 0.54),
                (x, H * 0.54), (x, H * 0.30)],
               colour=MAGENTA if i == 1 else CYAN, alpha=130, width=2)
        for j in range(3):
            yy = H * 0.38 + j * 24
            c.line([(x + 16, yy), (x + 60 + j * 26, yy)], alpha=90, width=2,
                   glow=0.2)
    return c.compose(0.85)


def catheter(seed=4):
    """A microcatheter threading a vessel."""
    c = Canvas()
    rng = np.random.default_rng(seed)
    pts = [(W * 0.08, H * 0.72)]
    x, y = W * 0.08, H * 0.72
    for i in range(1, 34):
        x += W * 0.026
        y += math.sin(i * 0.45) * 40 - 6
        pts.append((x, y))
    c.line(pts, alpha=105, width=40, glow=0.3)          # vessel lumen
    c.line(pts[:24], colour=MAGENTA, alpha=235, width=6, glow=1.0)
    tip = pts[23]
    c.dot(tip[0], tip[1], r=8, colour=MAGENTA, alpha=235)
    for k in range(6):
        px, py = pts[18 + k // 3][0] + k * 12, pts[18 + k // 3][1]
        c.line([(px, py - 16), (px + 9, py + 16)], alpha=170, width=2)
    return c.compose(0.9)


def aneurysm(seed=5):
    c = Canvas()
    y = H * 0.56
    c.line([(W * 0.10, y), (W * 0.90, y)], alpha=130, width=38, glow=0.35)
    cx, cy, r = W * 0.5, y - 150, 158
    c.arc([cx - r, cy - r, cx + r, cy + r], 0, 360, colour=MAGENTA,
          alpha=200, width=4)
    for k, rr in enumerate((r + 20, r + 44)):
        c.arc([cx - rr, cy - rr, cx + rr, cy + rr], 0, 360, colour=MAGENTA,
              alpha=70 - k * 26, width=2)
    c.line([(cx - 46, y), (cx - 22, cy + r * 0.7)], colour=MAGENTA, alpha=150,
           width=3)
    c.line([(cx + 46, y), (cx + 22, cy + r * 0.7)], colour=MAGENTA, alpha=150,
           width=3)
    return c.compose(0.9)


def coil(seed=6):
    c = Canvas()
    cx, cy, r = W * 0.5, H * 0.5, 236
    c.arc([cx - r, cy - r, cx + r, cy + r], 0, 360, colour=MAGENTA, alpha=170,
          width=4)
    pts = []
    for i in range(460):
        t = i / 460
        ang = t * math.pi * 13
        rad = r * 0.92 * (1 - t * 0.72)
        pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad * 0.94))
    c.line(pts, alpha=190, width=3, glow=0.7)
    return c.compose(0.9)


def nidus(seed=7):
    """A tangled arteriovenous nidus, progressively quieting."""
    c = Canvas()
    rng = np.random.default_rng(seed)
    cx, cy = W * 0.5, H * 0.5
    n = 46
    pts = []
    for _ in range(n):
        a = rng.random() * 2 * math.pi
        rad = (rng.random() ** 0.6) * 330
        pts.append((cx + math.cos(a) * rad * 1.5, cy + math.sin(a) * rad))
    for i, p in enumerate(pts):
        for j in range(i + 1, n):
            q = pts[j]
            d = math.dist(p, q)
            if d < 230:
                quiet = i > n * 0.55
                c.line([p, q], colour=(60, 78, 96) if quiet else CYAN,
                       alpha=52 if quiet else int(165 * (1 - d / 230)),
                       width=2, glow=0.0 if quiet else 0.4)
    for i, p in enumerate(pts[:int(n * 0.55)]):
        c.dot(p[0], p[1], r=3.5, alpha=170, glow=0.6)
    c.line([(W * 0.08, cy + 40), (cx - 220, cy + 10)], alpha=120, width=14,
           glow=0.3)
    c.line([(cx + 230, cy - 20), (W * 0.92, cy - 60)], alpha=120, width=14,
           glow=0.3)
    return c.compose(0.88)


def scale_out(seed=8):
    """Pull back from micro to human scale: nested expanding rings."""
    c = Canvas()
    cx, cy = W * 0.5, H * 0.5
    for i in range(9):
        r = 58 + i * 84
        a = int(150 * (1 - i / 10))
        c.arc([cx - r, cy - r * 0.96, cx + r, cy + r * 0.96], 0, 360,
              colour=MAGENTA if i == 0 else CYAN, alpha=a, width=3 if i == 0 else 2)
    c.dot(cx, cy, r=9, colour=MAGENTA, alpha=240)
    for k in range(4):
        ang = math.pi * (0.25 + k * 0.5)
        c.line([(cx + math.cos(ang) * 60, cy + math.sin(ang) * 58),
                (cx + math.cos(ang) * 560, cy + math.sin(ang) * 540)],
               alpha=60, width=1, glow=0.2)
    return c.compose(0.85)


def network(seed=9):
    """Points of light connecting into one network."""
    c = Canvas()
    rng = np.random.default_rng(seed)
    pts = [(rng.random() * W * 0.84 + W * 0.08, rng.random() * H * 0.66 + H * 0.17)
           for _ in range(34)]
    for i, p in enumerate(pts):
        for q in pts[i + 1:]:
            d = math.dist(p, q)
            if d < 400:
                c.line([p, q], alpha=int(135 * (1 - d / 400)), width=2, glow=0.5)
    for i, p in enumerate(pts):
        col = MAGENTA if i % 7 == 0 else CYAN
        c.dot(p[0], p[1], r=7, colour=col, alpha=235)
    return c.compose(0.9)


def field(seed=10):
    """A single point expanding into a vast luminous field."""
    c = Canvas()
    rng = np.random.default_rng(seed)
    cx, cy = W * 0.5, H * 0.5
    for _ in range(300):
        a = rng.random() * 2 * math.pi
        rad = (rng.random() ** 0.45) * H * 0.62
        x, y = cx + math.cos(a) * rad * 1.6, cy + math.sin(a) * rad
        f = 1 - rad / (H * 0.62)
        c.line([(cx + math.cos(a) * rad * 1.6 * 0.82,
                 cy + math.sin(a) * rad * 0.82), (x, y)],
               alpha=int(60 * f), width=1, glow=0.2)
        c.dot(x, y, r=1.6 + 3.4 * f, alpha=int(90 + 130 * f), glow=0.7)
    c.dot(cx, cy, r=13, colour=MAGENTA, alpha=245)
    return c.compose(0.9)


MOTIFS = {
    "S01": lambda: network(21),
    "S02": lambda: vascular(2),
    "S03": planes,
    "S04": suite,
    "S05": lambda: vascular(5, dim_after=4),
    "S06": catheter,
    "S07": lambda: vascular(7, alpha=210, depth=8),
    "S08": aneurysm,
    "S09": coil,
    "S10": nidus,
    "S11": scale_out,
    "S13": network,
    "S14": field,
}


def for_shot(shot_id):
    fn = MOTIFS.get(shot_id)
    return fn() if fn else None


if __name__ == "__main__":
    from filmlib import ROOT, BG
    out = ROOT / "build" / "_chk"
    out.mkdir(parents=True, exist_ok=True)
    cols = 5
    ids = list(MOTIFS)
    tw, th = 384, 216
    sheet = Image.new("RGB", (cols * tw, ((len(ids) + cols - 1) // cols) * th), BG)
    for i, sid in enumerate(ids):
        art = for_shot(sid)
        base = Image.new("RGB", (W, H), BG)
        base.paste(art, (0, 0), art)
        sheet.paste(base.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
    sheet.save(out / "motifs.jpg", quality=90)
    print(out / "motifs.jpg")
