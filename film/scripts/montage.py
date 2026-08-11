#!/usr/bin/env python3
"""S12 - the team montage. The emotional core.

Every photograph the client supplied is in here, grouped by institution in the
client-specified order, one caption held across each group.

Hard rules honoured here:
  - photographs are never regenerated, restyled, filtered or face-altered
  - motion is limited to a slow push-in and a few px of drift
  - a fractional crop may exclude something from frame (a patient, a sticker)
    but never alters what stays in it
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
ZMAX = 1.055            # most a cover-framed photograph is ever zoomed in
FIT_MIN, FIT_MAX = 0.88, 0.955   # contain mode: fraction of frame height used
DEFAULT_ANCHOR = 0.38   # vertical crop anchor; 0 = top, 1 = bottom

# A photograph much narrower than 16:9 loses most of itself to a cover crop -
# a 471x1023 portrait keeps 26% of its height and comes out as an anonymous
# torso. Anything below this aspect is framed whole instead, over a blurred
# copy of itself.
CONTAIN_BELOW = 1.15

# One move per photograph, cycled so no two neighbours share one. Amplitudes
# are deliberately small: this should read as a living photograph, not a
# camera move.
MOVES = ["push_in", "pan_r", "pull_out", "rise", "pan_l", "drift", "fall"]

# Travel budget in pixels, each way. A pan proportional to the available margin
# slides a tall portrait a third of the way across the frame, which reads as a
# camera move rather than a living photograph.
PAN_X, PAN_Y = 130, 90
FG_PAN_X, FG_PAN_Y = 55, 40

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


def _smooth(p):
    return p * p * (3 - 2 * p)


class Slot:
    """One photograph with its own move.

    Two framings. A photograph close to 16:9 is framed edge to edge (cover) and
    the move works inside whatever margin the aspect mismatch leaves. A
    photograph much taller than the frame is shown whole (contain) over a
    blurred, darkened copy of itself, which moves at half speed behind it - so
    nobody is cropped out of a picture they are in.
    """

    def __init__(self, dur, path=None, anchor=DEFAULT_ANCHOR, pending_label=None,
                 move="push_in", crop=None):
        self.dur = dur
        self.anchor = anchor
        self.pending_label = pending_label
        self.move = move
        self.base = self.back = None
        self.contain = False
        if not path:
            return

        im = Image.open(path).convert("RGB")
        if crop:
            # Fractional [left, top, right, bottom]. Used to exclude something
            # from frame - never to alter what stays in it.
            l, t, r, b = crop
            im = im.crop((int(l * im.width), int(t * im.height),
                          int(r * im.width), int(b * im.height)))

        self.contain = (im.width / im.height) < CONTAIN_BELOW
        if self.contain:
            fit = min(W / im.width, H / im.height) * FIT_MAX
            self.base = im.resize((max(1, round(im.width * fit)),
                                   max(1, round(im.height * fit))), RESAMPLE)
            self.back = self._blurred_fill(im)
        else:
            cover = max(W / im.width, H / im.height) * ZMAX
            self.base = im.resize((round(im.width * cover),
                                   round(im.height * cover)), RESAMPLE)

    @staticmethod
    def _blurred_fill(im):
        """A soft, dark bed for a portrait, made from the photograph itself."""
        cover = max(W / im.width, H / im.height) * 1.18
        big = im.resize((round(im.width * cover), round(im.height * cover)),
                        Image.BILINEAR)
        x, y = (big.width - int(W * 1.18)) // 2, (big.height - int(H * 1.18)) // 2
        big = big.crop((x, y, x + int(W * 1.18), y + int(H * 1.18)))
        big = big.filter(ImageFilter.GaussianBlur(46))
        return Image.blend(big, Image.new("RGB", big.size, BG), 0.62)

    # -- the moves ---------------------------------------------------------

    def _params(self, e):
        """(zoom 0..1, pan x -1..1, pan y -1..1) for eased progress e."""
        m, c = self.move, 2 * e - 1
        if m == "push_in":
            return e, 0.0, 0.0
        if m == "pull_out":
            return 1 - e, 0.0, 0.0
        if m == "pan_r":
            return 0.45, c, 0.0
        if m == "pan_l":
            return 0.45, -c, 0.0
        if m == "rise":
            return 0.45, 0.0, -c
        if m == "fall":
            return 0.45, 0.0, c
        return 0.30 + 0.45 * e, 0.55 * c, -0.35 * c      # drift

    def render(self, local_t):
        if self.base is None:
            return self._pending_frame()
        e = _smooth(min(max(local_t / self.dur, 0.0), 1.0))
        z, px, py = self._params(e)
        return self._contain_frame(z, px, py) if self.contain \
            else self._cover_frame(z, px, py)

    def _cover_frame(self, z, px, py):
        bw, bh = self.base.size
        scale = 1.0 + (ZMAX - 1.0) * z
        win_w = min(bw, int(W * ZMAX / scale))
        win_h = min(bh, int(win_w * H / W))
        win_w = min(bw, int(win_h * W / H))

        mx, my = bw - win_w, bh - win_h
        x = mx / 2 + px * min(mx / 2, PAN_X)
        y = my * self.anchor + py * min(my / 2, PAN_Y)
        x = min(max(x, 0), mx)
        y = min(max(y, 0), my)
        return self.base.crop((int(x), int(y), int(x) + win_w,
                               int(y) + win_h)).resize((W, H), RESAMPLE)

    def _contain_frame(self, z, px, py):
        # Background moves at half the foreground's rate - real parallax.
        bg = self.back
        bw, bh = bg.size
        bmx, bmy = bw - W, bh - H
        bx = bmx / 2 + px * min(bmx / 2, FG_PAN_X * 0.45)
        by = bmy / 2 + py * min(bmy / 2, FG_PAN_Y * 0.45)
        frame = bg.crop((int(bx), int(by), int(bx) + W, int(by) + H)).copy()

        k = (FIT_MIN + (FIT_MAX - FIT_MIN) * z) / FIT_MAX
        fw, fh = max(1, round(self.base.width * k)), max(1, round(self.base.height * k))
        fg = self.base.resize((fw, fh), RESAMPLE)

        room_x, room_y = (W - fw) / 2, (H - fh) / 2
        fx = room_x + px * min(room_x, FG_PAN_X)
        fy = room_y + py * min(room_y, FG_PAN_Y)
        frame.paste(fg, (int(fx), int(fy)))
        return frame

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
    """Every supplied photograph gets a slot, grouped by institution.

    Institutions with no photographs are skipped rather than filling the film's
    emotional core with an empty reserved card; the montage re-expands by
    itself the moment photographs land in photos.json.
    """
    cfg = load_photos()
    insts = cfg["institutions"]
    order = cfg["montage_order"]

    groups = [(k, insts[k]["photos"]) for k in order
              if [p for p in insts[k].get("photos", [])
                  if (ROOT / p["file"]).exists()]]
    pending = [insts[k]["name"] for k in order
               if not insts[k].get("photos")]

    total = sum(len(ps) for _, ps in groups)
    if total == 0:
        return [Slot(SHOT_DUR, None,
                     pending_label="PHOTOGRAPHS PENDING")], \
            pending, []
    per = (SHOT_DUR - CLOSING_DUR) / total

    slots, layout, i = [], [], 0
    for key, photos in groups:
        start = len(slots)
        for rec in photos:
            path = ROOT / rec["file"]
            if not path.exists():
                continue
            slots.append(Slot(per, path,
                              rec.get("anchor", ANCHORS.get(key, DEFAULT_ANCHOR)),
                              move=rec.get("move", MOVES[i % len(MOVES)]),
                              crop=rec.get("crop")))
            i += 1
        if len(slots) > start:
            layout.append((key, start, len(slots) - start))

    closing = ROOT / cfg["closing_slot"]["preferred"]
    slots.append(Slot(CLOSING_DUR, closing if closing.exists() else None,
                      0.42, pending_label="CLOSING FRAME PENDING",
                      move="pull_out"))
    return slots, pending, layout


def caption_schedule(slots, layout):
    """One caption per institution, held across that institution's whole group.

    A caption per photograph would flash six times in twelve seconds; a caption
    per group reads as a chapter heading, which is what it is.
    """
    starts, acc = [], 0.0
    for s in slots:
        starts.append(acc)
        acc += s.dur

    sched = []
    for key, first, count in layout:
        p = TEXT / f"S12_inst_{key}.png"
        if not p.exists():
            continue
        a = starts[first]
        b = starts[first + count - 1] + slots[first + count - 1].dur
        sched.append((p, a + 0.4, b - 0.45))

    og = TEXT / "S12_onegoal.png"
    if og.exists():
        sched.append((og, starts[-1] + 0.2, None))
    return sched


def render():
    FRAMES.mkdir(parents=True, exist_ok=True)
    for f in FRAMES.glob("*.png"):
        f.unlink()

    slots, pending, layout = build_slots()
    scrim = bottom_scrim()
    starts, acc = [], 0.0
    for s in slots:
        starts.append(acc)
        acc += s.dur

    captions = [(Image.open(p).convert("RGBA"), a, b) for p, a, b in
                caption_schedule(slots, layout)]

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
    print(f"  -> {out.relative_to(ROOT)}  ({SHOT_DUR:g}s, {len(slots)} photographs, {slots[0].dur:.2f}s each)")
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
