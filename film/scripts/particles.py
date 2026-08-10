#!/usr/bin/env python3
"""Particle-network / neural-glow background.

This is the connective tissue the brief asks to carry across the film. It is an
abstract brand motif built procedurally - no trademark, no medical imagery, and
nothing presented as a real scan.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from filmlib import ROOT, W, H, FPS, BG, CYAN, MAGENTA, run, INTERMEDIATE

GLOW_DIV = 4  # glow rendered at 1/4 res then upscaled - much faster, same look


class Field:
    def __init__(self, n=110, seed=7, w=W, h=H, speed=1.0):
        rng = np.random.default_rng(seed)
        self.w, self.h = w, h
        self.pos = rng.random((n, 2)) * [w, h]
        ang = rng.random(n) * 2 * math.pi
        mag = (0.25 + rng.random(n) * 0.55) * speed
        self.vel = np.stack([np.cos(ang) * mag, np.sin(ang) * mag], axis=1)
        self.size = 1.6 + rng.random(n) * 3.0
        self.warm = rng.random(n) < 0.22   # a minority of magenta nodes
        self.phase = rng.random(n) * 2 * math.pi
        self.link = min(w, h) * 0.20

    def step(self):
        self.pos += self.vel
        self.pos[:, 0] %= self.w
        self.pos[:, 1] %= self.h

    def render(self, t, vignette=True):
        img = Image.new("RGB", (self.w, self.h), BG)
        d = ImageDraw.Draw(img, "RGBA")

        # links
        p = self.pos
        diff = p[:, None, :] - p[None, :, :]
        dist = np.sqrt((diff ** 2).sum(-1))
        iu = np.triu_indices(len(p), 1)
        near = dist[iu] < self.link
        for a, b, dd in zip(iu[0][near], iu[1][near], dist[iu][near]):
            alpha = int(46 * (1 - dd / self.link))
            if alpha <= 1:
                continue
            d.line([tuple(p[a]), tuple(p[b])], fill=CYAN + (alpha,), width=1)

        # nodes + glow
        glow = Image.new("RGB", (self.w // GLOW_DIV, self.h // GLOW_DIV), (0, 0, 0))
        gd = ImageDraw.Draw(glow, "RGBA")
        for i, (x, y) in enumerate(p):
            pulse = 0.55 + 0.45 * math.sin(t * 1.7 + self.phase[i])
            col = MAGENTA if self.warm[i] else CYAN
            r = self.size[i] * (0.75 + 0.45 * pulse)
            d.ellipse([x - r, y - r, x + r, y + r],
                      fill=col + (int(120 + 110 * pulse),))
            gr = r * 4.5 / GLOW_DIV
            gx, gy = x / GLOW_DIV, y / GLOW_DIV
            gd.ellipse([gx - gr, gy - gr, gx + gr, gy + gr],
                       fill=col + (int(30 + 55 * pulse),))

        glow = glow.filter(ImageFilter.GaussianBlur(7)).resize(
            (self.w, self.h), Image.BILINEAR)
        img = Image.blend(img, Image.blend(img, glow, 0.0), 0.0)
        img = Image.fromarray(
            np.clip(np.asarray(img, np.int16) + np.asarray(glow, np.int16), 0, 255
                    ).astype(np.uint8))

        if vignette:
            img = _vignette(img)
        return img


_VIG_CACHE = {}


def _vignette(img):
    key = img.size
    if key not in _VIG_CACHE:
        w, h = key
        yy, xx = np.mgrid[0:h, 0:w]
        cx, cy = w / 2, h / 2
        r = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
        _VIG_CACHE[key] = np.clip(1.06 - 0.34 * r ** 2, 0, 1)[..., None]
    a = np.asarray(img, np.float32) * _VIG_CACHE[key]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def render_frames(dur, out_dir, seed=7, n=110, speed=1.0, w=W, h=H):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    field = Field(n=n, seed=seed, w=w, h=h, speed=speed)
    total = int(round(dur * FPS))
    for i in range(total):
        field.step()
        field.render(i / FPS).save(out_dir / f"bg_{i:05d}.png")
    return total


def background_clip(dur, out_mp4, seed=7, n=110, speed=1.0, cache=True):
    """Render (or reuse) a particle-network background clip of `dur` seconds."""
    out_mp4 = Path(out_mp4)
    if cache and out_mp4.exists():
        return out_mp4
    tmp = ROOT / "build" / f".bgframes_{out_mp4.stem}"
    render_frames(dur, tmp, seed=seed, n=n, speed=speed)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(tmp / "bg_%05d.png"),
         *INTERMEDIATE, str(out_mp4)])
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    return out_mp4


if __name__ == "__main__":
    import sys
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
    out = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / "build" / "bg_test.mp4")
    print(background_clip(dur, out))
