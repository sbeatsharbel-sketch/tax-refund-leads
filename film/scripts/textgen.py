#!/usr/bin/env python3
"""Render every on-screen text element to an RGBA PNG.

Typography rules (Part 1 of the brief):
  - exactly two typefaces: Noto Serif Display (display) + Inter (support)
  - no script/cursive faces anywhere
  - nothing below 40px at 1080p
  - one centred band and one lower-third baseline, held for the whole film
"""
from pathlib import Path

from filmlib import (ROOT, W, H, SILVER, CYAN, font, new_layer, centred_line,
                     left_line)

OUT = ROOT / "build" / "text"

# The two positions, fixed for the whole film.
CENTRE_Y = int(H * 0.44)          # statement lines
LOWER_Y = int(H * 0.755)          # lower third: support lines
LABEL_X, LABEL_Y = 120, H - 168   # section labels, lower left

SIZES = {
    "statement": 76,
    "statement_big": 108,
    "lower": 62,
    "role": 50,
    "label": 54,
}


def statement(name, line, big=False, glow=True, shadow=False):
    img = new_layer()
    size = SIZES["statement_big"] if big else SIZES["statement"]
    f = font("serif", size)
    y = CENTRE_Y - (size // 2 if big else 0)
    centred_line(img, line, f, y, SILVER, glow=CYAN if glow else None,
                 shadow=shadow)
    save(img, name)


def lower_third(name, line):
    img = new_layer()
    centred_line(img, line, font("serif", SIZES["lower"]), LOWER_Y, SILVER, glow=CYAN)
    save(img, name)


def role(name, line):
    """Role captions sit over photographs, so they carry a soft dark halo."""
    img = new_layer()
    centred_line(img, line, font("sans_medium", SIZES["role"]), LOWER_Y, SILVER,
                 shadow=True)
    save(img, name)


def label(name, line):
    """Section labels: sans caps, tracked, lower left, small but >= 40px."""
    img = new_layer()
    left_line(img, line.upper(), font("sans_semibold", SIZES["label"]),
              LABEL_X, LABEL_Y, CYAN, tracking=9)
    save(img, name)


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.png"
    img.save(p)
    print(f"  {p.relative_to(ROOT)}")
    return p


def main():
    print("text layer ->")
    statement("S02_story", "Every image tells a story.")
    lower_third("S03_time", "Some stories can only be read in time.")
    label("S05_thrombectomy", "Thrombectomy")
    statement("S07_minutes", "Minutes are brain.")
    label("S08_coiling", "Coiling")
    label("S10_embolization", "Embolization")
    statement("S11_behind", "Behind every image —")

    # S12 captions name the institution in frame, not a profession.
    # Binding the six role words to montage slots by index mislabelled real,
    # identifiable staff - Hadassah's angiography team read "Industry Partners".
    # The full role list still appears in full on the S15 title card.
    from filmlib import load_photos
    cfg = load_photos()
    for key in cfg["montage_order"]:
        rec = cfg["institutions"][key]
        role(f"S12_inst_{key}", f"{rec['name']}  ·  {rec['city']}")
    statement("S12_onegoal", "One goal.", big=True, shadow=True)

    statement("S13_first", "For the first time in Israel —")
    statement("S13_sector", "every sector of imaging, in one room.")
    statement("S14_many", "The first of many.")


if __name__ == "__main__":
    main()
