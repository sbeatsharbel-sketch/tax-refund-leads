#!/usr/bin/env python3
"""QC contact sheet - one frame every 2 seconds, to eyeball the whole film
for text errors before anything reaches a lobby screen.
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from filmlib import ROOT, font, ffprobe_duration

OUT = ROOT / "out"
STEP = 2.0
COLS = 6
TILE_W = 480


def main():
    master = OUT / "beyond_the_image_2026_1080p.mp4"
    if not master.exists():
        raise SystemExit("no master encode - run assemble.py first")
    dur = ffprobe_duration(master)
    tmp = ROOT / "build" / "_qc"
    tmp.mkdir(parents=True, exist_ok=True)
    for f in tmp.glob("*.png"):
        f.unlink()

    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(master),
         "-vf", f"fps=1/{STEP},scale={TILE_W}:-1", str(tmp / "q_%04d.png")],
        check=True)

    tiles = sorted(tmp.glob("q_*.png"))
    if not tiles:
        raise SystemExit("no frames extracted")
    tw, th = Image.open(tiles[0]).size
    rows = (len(tiles) + COLS - 1) // COLS
    lab = 30
    sheet = Image.new("RGB", (COLS * tw, rows * (th + lab)), (12, 14, 20))
    d = ImageDraw.Draw(sheet)
    f = font("sans_semibold", 22)

    for i, t in enumerate(tiles):
        x, y = (i % COLS) * tw, (i // COLS) * (th + lab)
        sheet.paste(Image.open(t), (x, y + lab))
        ts = i * STEP
        d.text((x + 8, y + 5), f"{int(ts) // 60}:{int(ts) % 60:02d}",
               font=f, fill=(120, 200, 225))

    out = OUT / "qc_contact_sheet.jpg"
    sheet.save(out, quality=88)
    for t in tiles:
        t.unlink()
    print(f"  -> {out.relative_to(ROOT)}  "
          f"({len(tiles)} frames every {STEP:g}s over {dur:.1f}s)")
    return out


if __name__ == "__main__":
    main()
