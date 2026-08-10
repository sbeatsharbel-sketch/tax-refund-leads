#!/usr/bin/env python3
"""Placeholder clips for shots whose source has not arrived.

Each card carries the brand's particle background, an abstract line-art motif
for that shot, and a slow push-in - so the rough cut reads as a film rather
than a slide deck, and the pacing can actually be judged.

The lower third (y 780-900) is kept clear on every card, because the shot's
real on-screen caption is composited there at its real timing.
"""
from pathlib import Path

from PIL import Image, ImageDraw

from filmlib import (ROOT, W, H, FPS, BG, CYAN, MAGENTA, SILVER, font,
                     left_line, run, INTERMEDIATE)
import shotart

SHOTS = ROOT / "build" / "shots"
TEXT = ROOT / "build" / "text"

OVERSCAN = 1.10          # still is rendered larger, then pushed into
PUSH = 0.085             # total zoom travel across the shot

# Which text PNG belongs to which shot, and when it appears inside the shot.
SHOT_TEXT = {
    "S02": [("S02_story", 0.8, None)],
    "S03": [("S03_time", 0.8, None)],
    "S05": [("S05_thrombectomy", 0.5, None)],
    "S07": [("S07_minutes", 1.0, None)],
    "S08": [("S08_coiling", 0.5, None)],
    "S10": [("S10_embolization", 0.5, None)],
    "S11": [("S11_behind", 1.4, None)],
    # S13: both lines must fully clear before the logo wall resolves at 2:02.
    "S13": [("S13_first", 0.6, 3.2), ("S13_sector", 4.0, 6.4)],
    "S14": [("S14_many", 1.2, None)],
}


def _wrap(text, fnt, max_w):
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    lines, cur = [], []
    for word in text.split():
        if probe.textlength(" ".join(cur + [word]), font=fnt) <= max_w or not cur:
            cur.append(word)
        else:
            lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))
    return lines


def card(shot):
    """Full-frame placeholder still: particle field + motif + shot identity."""
    from particles import Field
    seed = 40 + int(shot["id"][1:])
    fld = Field(n=88, seed=seed, speed=0.6)
    for _ in range(seed * 3):
        fld.step()
    im = fld.render(seed * 0.7).convert("RGBA")

    art = shotart.for_shot(shot["id"])
    if art is not None:
        im.alpha_composite(art)

    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle([0, 0, W, 5], fill=MAGENTA + (190,))

    left_line(im, "PLACEHOLDER", font("sans_semibold", 40), 120, 96,
              MAGENTA, tracking=9)
    left_line(im, f"{shot['id']}   {shot['section'].upper()}",
              font("sans_semibold", 56), 120, 156, CYAN, tracking=4)

    f = font("sans", 46)
    y = 250
    for ln in _wrap(shot["content"], f, 860):
        left_line(im, ln, f, 120, y, SILVER)
        y += 60

    # Metadata sits below the caption band so the two can never collide.
    meta = (f"{shot['dur']:g}s   ·   {shot['source_kind']}   ·   in @ "
            f"{int(shot['start']) // 60}:{int(shot['start']) % 60:02d}"
            f"   ·   awaiting {Path(shot.get('input') or '-').name}")
    left_line(im, meta, font("sans", 40), 120, 964, (128, 146, 168), tracking=1)
    return im.convert("RGB")


def build(shot, render_dur, out=None):
    SHOTS.mkdir(parents=True, exist_ok=True)
    out = Path(out) if out else SHOTS / f"{shot['id']}.mp4"
    still = card(shot)

    big = still.resize((int(W * OVERSCAN), int(H * OVERSCAN)), Image.LANCZOS)
    bgpng = SHOTS / f".ph_{shot['id']}.png"
    big.save(bgpng)

    frames = max(2, int(round(render_dur * FPS)))
    push = (f"zoompan=z='1+{PUSH}*on/{frames - 1}'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s={W}x{H}:fps={FPS}")

    layers = SHOT_TEXT.get(shot["id"], [])
    cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{render_dur}", "-i", str(bgpng)]
    for name, _, _ in layers:
        cmd += ["-loop", "1", "-t", f"{render_dur}", "-i", str(TEXT / f"{name}.png")]

    steps = [f"[0:v]{push},format=rgba[bg]"]
    prev = "bg"
    for i, (_, fin, fout) in enumerate(layers, start=1):
        f = f"[{i}:v]format=rgba,fade=t=in:st={fin}:d=0.4:alpha=1"
        if fout is not None:
            f += f",fade=t=out:st={fout}:d=0.4:alpha=1"
        steps.append(f + f"[l{i}]")
        tag = "[vout]" if i == len(layers) else f"[v{i}]"
        steps.append(f"[{prev}][l{i}]overlay=0:0:format=auto{tag}")
        prev = f"v{i}"
    if not layers:
        steps.append("[bg]null[vout]")

    cmd += ["-filter_complex", ";".join(steps), "-map", "[vout]",
            *INTERMEDIATE, "-t", f"{render_dur}", str(out)]
    run(cmd)
    bgpng.unlink()
    return out
