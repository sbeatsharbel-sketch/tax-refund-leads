#!/usr/bin/env python3
"""Placeholder clips for shots whose source has not arrived.

Dark navy, shot ID and description in white, plus the shot's real on-screen
text at its real timing - so a full-length rough cut can be screened for
pacing today and gaps filled as material arrives.
"""
from pathlib import Path

from PIL import Image, ImageDraw

from filmlib import (ROOT, W, H, FPS, BG, CYAN, MAGENTA, SILVER, font,
                     centred_line, left_line, run, INTERMEDIATE)

SHOTS = ROOT / "build" / "shots"
TEXT = ROOT / "build" / "text"

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


def card(shot):
    """Static placeholder background for one shot."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle([0, 0, W, 6], fill=MAGENTA + (200,))
    d.rounded_rectangle([120, 120, W - 120, H - 120], radius=6,
                        outline=(255, 255, 255, 34), width=2)

    left_line(im, "PLACEHOLDER", font("sans_semibold", 42), 168, 168,
              MAGENTA, tracking=8)
    left_line(im, f"{shot['id']}   {shot['section'].upper()}",
              font("sans_semibold", 58), 168, 250, CYAN, tracking=4)

    words, lines, cur = shot["content"].split(), [], []
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    f = font("sans", 46)
    for wd in words:
        if probe.textlength(" ".join(cur + [wd]), font=f) <= W - 460 or not cur:
            cur.append(wd)
        else:
            lines.append(" ".join(cur))
            cur = [wd]
    if cur:
        lines.append(" ".join(cur))
    y = 380
    for ln in lines:
        left_line(im, ln, f, 168, y, SILVER)
        y += 62

    meta = (f"{shot['dur']:g}s   ·   source: {shot['source_kind']}   ·   "
            f"in @ {int(shot['start']) // 60}:{int(shot['start']) % 60:02d}")
    left_line(im, meta, font("sans", 40), 168, H - 220, (150, 165, 185), tracking=1)
    if shot.get("input"):
        left_line(im, f"awaiting: {shot['input']}", font("sans", 40), 168,
                  H - 164, (150, 165, 185))
    return im


def build(shot, render_dur, out=None):
    SHOTS.mkdir(parents=True, exist_ok=True)
    out = Path(out) if out else SHOTS / f"{shot['id']}.mp4"
    bgpng = SHOTS / f".ph_{shot['id']}.png"
    card(shot).save(bgpng)

    layers = SHOT_TEXT.get(shot["id"], [])
    cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{render_dur}", "-i", str(bgpng)]
    for name, _, _ in layers:
        cmd += ["-loop", "1", "-t", f"{render_dur}", "-i", str(TEXT / f"{name}.png")]

    if layers:
        steps, prev = [], "0:v"
        for i, (_, fin, fout) in enumerate(layers, start=1):
            f = f"[{i}:v]format=rgba,fade=t=in:st={fin}:d=0.4:alpha=1"
            if fout is not None:
                f += f",fade=t=out:st={fout}:d=0.4:alpha=1"
            steps.append(f + f"[l{i}]")
            tag = "[vout]" if i == len(layers) else f"[v{i}]"
            steps.append(f"[{prev}][l{i}]overlay=0:0:format=auto{tag}")
            prev = f"v{i}"
        cmd += ["-filter_complex", ";".join(steps), "-map", "[vout]"]

    cmd += [*INTERMEDIATE, "-t", f"{render_dur}", str(out)]
    run(cmd)
    bgpng.unlink()
    return out
