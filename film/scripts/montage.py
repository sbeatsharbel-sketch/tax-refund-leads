#!/usr/bin/env python3
"""S12 - the team montage (25s, 1:30-1:55). The emotional core.

Hard rules honoured here:
  - photographs are never regenerated, restyled, filtered or face-altered
  - motion is limited to a slow push-in and a few px of drift
  - each institution gets one slot, in the client-specified order
Only geometry (cover-crop, scale) and a bottom scrim for caption legibility
are applied. Pixels inside the frame are the client's own.
"""
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from filmlib import (ROOT, W, H, FPS, BG, CYAN, SILVER, font, load_photos,
                     centred_line, run, INTERMEDIATE)

def _shot_dur(shot_id, default):
    from filmlib import load_storyboard
    for sh in load_storyboard()["shots"]:
        if sh["id"] == shot_id:
            return float(sh["dur"])
    return default


SHOT_DUR = _shot_dur("S12", 25.0)
CLOSING_DUR = min(5.0, SHOT_DUR * 0.21)
# Hard cuts. A dissolve between two group photographs superimposes faces
# on faces - four translucent heads floated over the group at 1:49.9 -
# and the brief calls for hard cuts inside a section anyway.
DISSOLVE = 0.0
ZOOM_START, ZOOM_END = 1.02, 1.095
DRIFT_PX = 26           # horizontal drift across a slot
DEFAULT_ANCHOR = 0.38   # vertical crop anchor; 0 = top, 1 = bottom

# Closing beat: dim the last photograph under "One goal."
DIM_START, DIM_RAMP, DIM_MAX = SHOT_DUR - CLOSING_DUR - 0.2, 1.4, 0.36

# LANCZOS for delivery, BICUBIC while iterating (visually identical at these
# scale factors, roughly 3x faster). Set FILM_QUALITY=final for the master.
RESAMPLE = Image.LANCZOS if os.environ.get("FILM_QUALITY") == "final" \
    else Image.BICUBIC

TEXT = ROOT / "build" / "text"
SHOTS = ROOT / "build" / "shots"
FRAMES = ROOT / "build" / "photos" / "S12"

# Faces sit high in group shots; anchor the crop above centre unless overridden.
ANCHORS = {
    "sheba": 0.34,
    "carmel": 0.40,
    "bnaizion": 0.30,
    "hadassah": 0.40,
}


class Slot:
    """One photograph (or a pending-photo placeholder) with its Ken Burns move."""

    def __init__(self, dur, path=None, anchor=DEFAULT_ANCHOR, pending_label=None,
                 drift_sign=1, crop=None):
        self.dur = dur
        self.anchor = anchor
        self.pending_label = pending_label
        self.drift_sign = drift_sign
        self.base = None
        if path:
            im = Image.open(path).convert("RGB")
            if crop:
                # Fractional [left, top, right, bottom]. Used to exclude
                # something from frame - never to alter what stays in it.
                l, t, r, b = crop
                im = im.crop((int(l * im.width), int(t * im.height),
                              int(r * im.width), int(b * im.height)))
            self.base = self._prescale(im)

    @staticmethod
    def _prescale(im):
        """Scale once to the largest size any frame will need, then crop per frame."""
        cover = max(W / im.width, H / im.height) * ZOOM_END
        return im.resize((max(W, int(im.width * cover)),
                          max(H, int(im.height * cover))), RESAMPLE)

    def render(self, local_t):
        if self.base is None:
            return self._pending_frame()
        p = min(max(local_t / self.dur, 0.0), 1.0)
        eased = p * p * (3 - 2 * p)                      # smoothstep
        zoom = ZOOM_START + (ZOOM_END - ZOOM_START) * eased

        bw, bh = self.base.size
        # window size at this zoom, relative to the fully-zoomed base
        win_w = int(bw * (ZOOM_START / zoom))
        win_h = int(win_w * H / W)
        if win_h > bh:
            win_h = bh
            win_w = int(win_h * W / H)

        drift = self.drift_sign * DRIFT_PX * (eased - 0.5) * 2
        x = (bw - win_w) / 2 + drift
        y = (bh - win_h) * self.anchor
        x = min(max(x, 0), bw - win_w)
        y = min(max(y, 0), bh - win_h)

        crop = self.base.crop((int(x), int(y), int(x) + win_w, int(y) + win_h))
        return crop.resize((W, H), RESAMPLE)

    def _pending_frame(self):
        im = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([260, 360, W - 260, H - 360], radius=8,
                            outline=CYAN + (150,), width=3)
        centred_line(im, self.pending_label or "PHOTOS PENDING",
                     font("sans_semibold", 54), 470, CYAN, tracking=4)
        centred_line(im, "slot reserved — photographs not yet supplied",
                     font("sans", 42), 560, SILVER)
        return im


def bottom_scrim():
    """Navy gradient over the lower band so captions stay legible on any photo.

    Tuned so the caption baseline (y = 0.755H) sits at ~0.62 opacity: white
    Inter on a bright angio-suite photo has to hold at 20 metres.
    """
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(scrim)
    top, bot = int(H * 0.68), H
    for y in range(top, bot):
        a = int(190 * ((y - top) / (bot - top)) ** 0.8)
        d.line([(0, y), (W, y)], fill=BG + (a,))
    return scrim


def dim_layer(opacity):
    """Flat navy wash. Used to sit the closing photograph back under 'One goal.'"""
    return Image.new("RGBA", (W, H), BG + (int(255 * opacity),))


def build_slots():
    cfg = load_photos()
    insts = cfg["institutions"]
    order = cfg["montage_order"]

    cast = [k for k in order
            if insts[k].get("hero") and (ROOT / insts[k]["hero"]).exists()]
    pending = [insts[k]["name"] for k in order if k not in cast]

    # An empty "slot reserved" card is dead screen time in the film's emotional
    # core. Institutions without photographs are simply not cast, and the time
    # is shared between the ones that are - the montage re-expands by itself
    # the moment a photograph lands in photos.json.
    if not cast:
        cast, pending = order, []
    per = (SHOT_DUR - CLOSING_DUR) / len(cast)

    slots = []
    for i, key in enumerate(cast):
        rec = insts[key]
        hero = rec.get("hero")
        path = ROOT / hero if hero else None
        if path and path.exists():
            slots.append(Slot(per, path, ANCHORS.get(key, DEFAULT_ANCHOR),
                              drift_sign=1 if i % 2 == 0 else -1,
                              crop=rec.get("crop")))
        else:
            label = f"{rec['name'].upper()} — {rec['city'].upper()}"
            slots.append(Slot(per, None, pending_label=label))

    closing = cfg["closing_slot"]["preferred"]
    cpath = ROOT / closing
    slots.append(Slot(CLOSING_DUR, cpath if cpath.exists() else None,
                      0.36, pending_label="CLOSING FRAME PENDING"))
    return slots, pending, cast


def caption_schedule(slots, cast):
    """(png, fade_in, fade_out) per slot, keyed to the institution in frame."""
    sched, t = [], 0.0
    for key, s in zip(cast, slots[:-1]):
        p = TEXT / f"S12_inst_{key}.png"
        if p.exists():
            sched.append((p, t + 0.6, t + s.dur - 0.5))
        t += s.dur
    og = TEXT / "S12_onegoal.png"
    if og.exists():
        sched.append((og, t + 0.2, None))
    return sched


def render():
    FRAMES.mkdir(parents=True, exist_ok=True)
    for f in FRAMES.glob("*.png"):
        f.unlink()

    slots, pending, cast = build_slots()
    scrim = bottom_scrim()
    starts, acc = [], 0.0
    for s in slots:
        starts.append(acc)
        acc += s.dur

    captions = [(Image.open(p).convert("RGBA"), a, b) for p, a, b in
                caption_schedule(slots, cast)]

    total = int(round(SHOT_DUR * FPS))
    for n in range(total):
        t = n / FPS
        idx = max(i for i, st in enumerate(starts) if t >= st - 1e-6)
        local = t - starts[idx]
        frame = slots[idx].render(local)

        # cross-dissolve into the next slot
        if DISSOLVE > 0 and idx + 1 < len(slots):
            remain = slots[idx].dur - local
            if remain < DISSOLVE:
                nxt = slots[idx + 1].render(DISSOLVE - remain)
                frame = Image.blend(frame, nxt, 1 - remain / DISSOLVE)

        frame = frame.convert("RGBA")
        frame.alpha_composite(scrim)

        # Closing beat: sit the photograph back so "One goal." carries the frame.
        if t >= DIM_START:
            k = min((t - DIM_START) / DIM_RAMP, 1.0)
            frame.alpha_composite(dim_layer(DIM_MAX * (k * k * (3 - 2 * k))))

        for img, fin, fout in captions:
            a = _alpha(t, fin, fout)
            if a <= 0.001:
                continue
            layer = img if a >= 0.999 else _faded(img, a)
            frame.alpha_composite(layer)
        frame.convert("RGB").save(FRAMES / f"f_{n:05d}.png")

    out = SHOTS / "S12.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(FRAMES / "f_%05d.png"),
         *INTERMEDIATE, str(out)])
    for f in FRAMES.glob("*.png"):
        f.unlink()
    print(f"  -> {out.relative_to(ROOT)}  ({SHOT_DUR}s, {len(slots)} slots)")
    if pending:
        print("  PENDING photographs: " + ", ".join(pending))
    return out


def _alpha(t, fin, fout, d=0.4):
    if t < fin:
        return 0.0
    a = min((t - fin) / d, 1.0)
    if fout is not None and t > fout:
        a = min(a, max(0.0, 1 - (t - fout) / d))
    return a


def _faded(img, a):
    out = img.copy()
    alpha = out.getchannel("A").point(lambda v: int(v * a))
    out.putalpha(alpha)
    return out


if __name__ == "__main__":
    print("S12 team montage ->")
    render()
