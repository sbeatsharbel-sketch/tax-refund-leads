#!/usr/bin/env python3
"""Placeholder clips for shots whose source has not arrived.

Every card sits on the brand's particle-network field, the same background the
title card uses, with the node density rising as the film builds. Text is
composited straight over the moving field.

The lower third (y 780-900) is kept clear on every card, because the shot's
real on-screen caption is composited there at its real timing.
"""
import os
from pathlib import Path

from PIL import Image, ImageDraw

from filmlib import (ROOT, W, H, FPS, BG, CYAN, MAGENTA, SILVER, font,
                     left_line, run, INTERMEDIATE)
from particles import background_clip

SHOTS = ROOT / "build" / "shots"
TEXT = ROOT / "build" / "text"

# Dev chrome (shot IDs, file paths, PLACEHOLDER banners) is production
# scaffolding, not film. It is off unless FILM_ANNOTATE=1, so the default
# deliverable can be shown to people.
ANNOTATE = os.environ.get("FILM_ANNOTATE") == "1"

# Which text PNG belongs to which shot, and when it appears inside the shot.
SHOT_TEXT = {
    "S02": [("S02_story", 0.5, None)],
    "S03": [("S03_time", 0.5, None)],
    "S05": [("S05_thrombectomy", 0.3, None)],
    "S07": [("S07_minutes", 0.6, None)],
    "S08": [("S08_coiling", 0.3, None)],
    "S10": [("S10_embolization", 0.3, None)],
    "S11": [("S11_behind", 0.8, None)],
    # S13: both lines must fully clear before the logo wall resolves.
    "S13": [("S13_first", 0.4, 2.8), ("S13_sector", 3.4, 5.8)],
    "S14": [("S14_many", 0.7, None)],
}

# Layers that are not text PNGs. S13's partner wall resolves at 2:02, which is
# after both caption lines have fully cleared at 6.2s.
# Stacking logos under live text makes the frame unreadable at lobby distance.
EXTRA_LAYERS = {
    "S13": [(SHOTS / "logo_wall.png", 6.4, None)],
}


def _layers_for(shot_id):
    out = [(TEXT / f"{n}.png", a, b) for n, a, b in SHOT_TEXT.get(shot_id, [])]
    out += [(p, a, b) for p, a, b in EXTRA_LAYERS.get(shot_id, []) if p.exists()]
    return out


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
    """Full-frame placeholder still: a quiet lit field, nothing else.

    Only used for the annotated production cut; the screening cut composites
    text straight over the moving particle field.
    """
    from particles import Field
    n = int(shot["id"][1:])
    fld = Field(n=_density(shot["section"]), seed=40 + n, speed=0.65)
    for _ in range(n * 7):
        fld.step()
    im = fld.render(n * 0.7).convert("RGBA")
    if ANNOTATE:
        _annotate(im, shot)
    return im.convert("RGB")


# One visual register across the whole film - the brand particle field - with
# density rising as the film builds, so it still travels somewhere.
DENSITY = {
    "Cold open": 72, "The image": 84, "Thrombectomy": 96, "Coiling": 96,
    "Embolization": 92, "Bridge": 78, "Collaboration": 118, "Legacy": 130,
}


def _density(section):
    return DENSITY.get(section, 95)


def _annotate(im, shot):
    """Production scaffolding. Never present in the screening cut."""
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
    meta = (f"{shot['dur']:g}s   ·   {shot['source_kind']}   ·   in @ "
            f"{int(shot['start']) // 60}:{int(shot['start']) % 60:02d}"
            f"   ·   awaiting {Path(shot.get('input') or '-').name}")
    left_line(im, meta, font("sans", 40), 120, 964, (128, 146, 168), tracking=1)


def build(shot, render_dur, out=None):
    SHOTS.mkdir(parents=True, exist_ok=True)
    out = Path(out) if out else SHOTS / f"{shot['id']}.mp4"
    bg = background_clip(render_dur,
                         ROOT / "build" / f".bg_{shot['id']}.mp4",
                         seed=40 + int(shot["id"][1:]),
                         n=_density(shot["section"]), speed=0.65)

    layers = _layers_for(shot["id"])
    cmd = ["ffmpeg", "-y", "-i", str(bg)]
    for path, _, _ in layers:
        cmd += ["-loop", "1", "-t", f"{render_dur}", "-i", str(path)]

    steps = ["[0:v]format=rgba[bg]"]
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
    return out
