#!/usr/bin/env python3
"""S15 (corrected title card) and S16 (credit + sponsor wall).

S15 is rebuilt from scratch, not patched. The supplied clip's end card read
"BEYOND THE THE IMAGE 2026"; the approved wording is set once, here, in
TITLE_MAIN, and rendered fresh from the font outlines.
"""
from pathlib import Path

from PIL import Image, ImageDraw

from filmlib import (ROOT, W, H, FPS, BG, CYAN, MAGENTA, SILVER, font, new_layer,
                     centred_line, text_width, draw_tracked, run, INTERMEDIATE)
from particles import background_clip

# ---------------------------------------------------------------------------
# The corrected wording. This single constant is the fix for the blocker.
TITLE_MAIN = "BEYOND THE IMAGE 2026"
# ---------------------------------------------------------------------------

S15_SUB = "September 9, 2026  ·  Galilee Medical Center — Nahariya"
S15_SUPPORT = ("Bringing Together Physicians, Nurses, Radiologic Technologists, "
               "Biomedical Engineers, Researchers, and Industry Partners")

S16_LINES = [
    "Founded and hosted by Galilee Medical Center, Nahariya",
    "Israel’s first conference of its kind",
]
S16_SPONSOR_HEADING = "Special Thanks to Our Sponsors"

TEXT = ROOT / "build" / "text"
SHOTS = ROOT / "build" / "shots"


def assert_no_duplicate_words(s):
    """Guard against the exact defect being fixed. Runs on every build."""
    words = [w.lower() for w in s.split()]
    for a, b in zip(words, words[1:]):
        if a == b:
            raise SystemExit(
                f"BUILD FAILED - duplicated word {a!r} in title: {s!r}")
    return s


def fit(text, key, start_size, max_w, tracking=0, min_size=40):
    """Largest size at or below start_size whose rendered width fits max_w."""
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    size = start_size
    while size > min_size:
        f = font(key, size)
        if text_width(probe, text, f, tracking) <= max_w:
            return f, size
        size -= 2
    return font(key, min_size), min_size


def wrap(text, key, size, max_w, tracking=0):
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    f = font(key, size)
    lines, cur = [], []
    for word in text.split():
        trial = " ".join(cur + [word])
        if text_width(probe, trial, f, tracking) <= max_w or not cur:
            cur.append(word)
        else:
            lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))
    return lines, f


def rule(img, y, width=520, colour=CYAN, thickness=3):
    d = ImageDraw.Draw(img, "RGBA")
    x0 = (img.width - width) / 2
    d.rectangle([x0, y, x0 + width, y + thickness], fill=colour + (210,))
    for i, a in ((1, 90), (2, 40)):
        d.rectangle([x0 - i * 26, y, x0 - i * 26 + 18, y + thickness],
                    fill=colour + (a,))
        d.rectangle([x0 + width + i * 26 - 18, y, x0 + width + i * 26,
                     y + thickness], fill=colour + (a,))


# --- brand assets ----------------------------------------------------------

BRAND = ROOT / "assets" / "source" / "brand"


def brand_png(name):
    p = BRAND / f"{name}.png"
    return Image.open(p).convert("RGBA") if p.exists() else None


def place(img, art, width, y):
    """Paste `art` centred at width px, top edge at y. Returns its height."""
    h = max(1, round(art.height * width / art.width))
    art = art.resize((width, h), Image.LANCZOS)
    img.alpha_composite(art, ((img.width - width) // 2, y))
    return h


# --- S15 elements ----------------------------------------------------------

def s15_title_png():
    """The conference lockup.

    Prefers the client's own vector lockup lifted from the programme PDF, so the
    title card matches the poster and programme exactly. Falls back to typeset
    text - guarded against the duplicated-word defect - if the vector is absent.
    """
    img = new_layer()
    art = brand_png("bti_lockup_dark")
    if art is not None:
        h = place(img, art, 1460, 288)
        rule(img, 288 + h + 54, width=440)
    else:
        assert_no_duplicate_words(TITLE_MAIN)
        f, size = fit(TITLE_MAIN, "serif_bold", 136, 1520, tracking=6)
        centred_line(img, TITLE_MAIN, f, 322, SILVER, tracking=6, glow=CYAN)
        rule(img, 322 + size + 46)
    return _save(img, "S15_title")


def s15_sub_png():
    """Official conference subtitle + the date/venue line."""
    img = new_layer()
    art = brand_png("bti_subtitle_dark")
    if art is not None:
        place(img, art, 1180, 524)
    f, _ = fit(S15_SUB, "sans_medium", 58, 1500, tracking=1)
    centred_line(img, S15_SUB, f, 620, SILVER, tracking=1)
    return _save(img, "S15_sub")


def s15_support_png():
    img = new_layer()
    lines, f = wrap(S15_SUPPORT, "sans", 46, 1440)
    y = 742
    for ln in lines:
        centred_line(img, ln, f, y, (170, 186, 205))
        y += 62
    return _save(img, "S15_support")


# --- S16 elements ----------------------------------------------------------

def s16_credit_png():
    """Founding credit, under the host institution's own logo."""
    img = new_layer()
    y = 118
    logo = ROOT / "assets" / "source" / "logos" / "01_galilee.png"
    if logo.exists():
        y += place(img, Image.open(logo).convert("RGBA"), 390, y) + 78
    f, _ = fit(S16_LINES[0], "sans_medium", 58, 1560)
    centred_line(img, S16_LINES[0], f, y, SILVER)
    f2, _ = fit(S16_LINES[1], "sans", 50, 1440)
    # Cyan on navy was the lowest-contrast pairing on the card.
    centred_line(img, S16_LINES[1], f2, y + 74, SILVER)
    return _save(img, "S16_credit")


def s16_sponsors_png():
    """Sponsor heading + wall. Sponsor logos have not been supplied.

    The supplied clip showed the heading above an empty outlined box, which is
    the defect being fixed - so this renders an unmistakable PENDING marker
    instead. It cannot be mistaken for a finished frame in a screening.
    """
    img = new_layer()
    f, _ = fit(S16_SPONSOR_HEADING, "sans_medium", 52, 1300, tracking=2)
    centred_line(img, S16_SPONSOR_HEADING, f, 604, SILVER, tracking=2)

    wall = ROOT / "build" / "shots" / "sponsor_wall.png"
    if wall.exists():
        w = Image.open(wall).convert("RGBA")
        img.alpha_composite(w, (0, 0))
        return _save(img, "S16_sponsors")

    d = ImageDraw.Draw(img, "RGBA")
    bx0, bx1, by0, by1 = 430, 1490, 700, 906
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=10,
                        outline=MAGENTA + (170,), width=3)
    msg = "SPONSOR LOGOS PENDING — NOT FOR SCREENING"
    fm = font("sans_semibold", 40)
    centred_line(img, msg, fm, 762, MAGENTA, tracking=3)
    fs = font("sans", 40)
    centred_line(img, "supply logo files + tier order", fs, 826, SILVER)
    return _save(img, "S16_sponsors")


def _save(img, name):
    TEXT.mkdir(parents=True, exist_ok=True)
    p = TEXT / f"{name}.png"
    img.save(p)
    print(f"  {p.relative_to(ROOT)}")
    return p


# --- shot assembly ---------------------------------------------------------

def build_card(shot_id, dur, layers, seed, out=None):
    """Composite staggered text layers over a particle background.

    layers: list of (png_path, fade_in_at, fade_out_at or None)
    """
    SHOTS.mkdir(parents=True, exist_ok=True)
    out = Path(out) if out else SHOTS / f"{shot_id}.mp4"
    bg = background_clip(dur, ROOT / "build" / f".bg_{shot_id}.mp4", seed=seed,
                         n=95, speed=0.65)

    cmd = ["ffmpeg", "-y", "-i", str(bg)]
    for png, _, _ in layers:
        cmd += ["-loop", "1", "-t", f"{dur}", "-i", str(png)]

    steps, prev = [], "0:v"
    for i, (_, fin, fout) in enumerate(layers, start=1):
        f = f"[{i}:v]format=rgba,fade=t=in:st={fin}:d=0.4:alpha=1"
        if fout is not None:
            f += f",fade=t=out:st={fout}:d=0.4:alpha=1"
        f += f"[l{i}]"
        steps.append(f)
        tag = f"[v{i}]" if i < len(layers) else "[vout]"
        steps.append(f"[{prev}][l{i}]overlay=0:0:format=auto{tag}")
        prev = f"v{i}"

    cmd += ["-filter_complex", ";".join(steps), "-map", "[vout]",
            *INTERMEDIATE, "-t", f"{dur}", str(out)]
    run(cmd)
    print(f"  -> {out.relative_to(ROOT)}")
    return out


def final_frame():
    """Static held slide for the lobby: the corrected title card, fully up."""
    img = Image.new("RGBA", (W, H), BG + (255,))
    from particles import Field
    f = Field(n=95, seed=15, speed=0.65)
    for _ in range(140):
        f.step()
    img.alpha_composite(f.render(4.0).convert("RGBA"), (0, 0))
    for p in (TEXT / "S15_title.png", TEXT / "S15_sub.png",
              TEXT / "S15_support.png"):
        img.alpha_composite(Image.open(p).convert("RGBA"), (0, 0))
    out = ROOT / "out" / "final_frame.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, quality=97)
    print(f"  -> {out.relative_to(ROOT)}")
    return out


def main():
    print("title cards ->")
    t, s, sup = s15_title_png(), s15_sub_png(), s15_support_png()
    cred, spon = s16_credit_png(), s16_sponsors_png()

    build_card("S15", 10, [(t, 0.5, None), (s, 1.5, None),
                           (sup, 2.4, None)], seed=15)
    # The sponsor marker clears at 3.2s so the film closes on the host
    # institution's credit, not on a card reading NOT FOR SCREENING.
    build_card("S16", 5, [(cred, 0.3, None), (spon, 1.2, 3.2)], seed=23)
    final_frame()


if __name__ == "__main__":
    main()
