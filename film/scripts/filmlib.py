"""Shared helpers for Beyond the Image 2026.

Text is rendered to RGBA PNGs with Pillow and composited by ffmpeg.
ffmpeg's drawtext is deliberately not used for anything the audience reads.
"""
import json
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent


def load_storyboard():
    with open(ROOT / "storyboard.json") as fh:
        return json.load(fh)


def load_photos():
    with open(ROOT / "photos.json") as fh:
        return json.load(fh)


SB = load_storyboard()
PAL = SB["palette"]
FONTS = SB["fonts"]
W, H = SB["master"]["w"], SB["master"]["h"]
FPS = SB["fps"]


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


BG = hex2rgb(PAL["bg"])
CYAN = hex2rgb(PAL["cyan"])
MAGENTA = hex2rgb(PAL["magenta"])
SILVER = hex2rgb(PAL["silver"])


def font(key, size):
    path = FONTS[key]
    if not os.path.exists(path):
        raise FileNotFoundError(f"font missing: {path}")
    return ImageFont.truetype(path, size)


def text_width(draw, s, fnt, tracking=0):
    """Width of s including manual letter tracking (px added per gap)."""
    if tracking == 0:
        return draw.textlength(s, font=fnt)
    return sum(draw.textlength(c, font=fnt) for c in s) + tracking * max(0, len(s) - 1)


def draw_tracked(draw, xy, s, fnt, fill, tracking=0):
    """Draw s at xy with manual tracking. Pillow has no letter-spacing."""
    if tracking == 0:
        draw.text(xy, s, font=fnt, fill=fill)
        return
    x, y = xy
    for c in s:
        draw.text((x, y), c, font=fnt, fill=fill)
        x += draw.textlength(c, font=fnt) + tracking


def new_layer(w=W, h=H):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def centred_line(img, s, fnt, y, fill=SILVER, tracking=0, glow=None, shadow=False):
    """Draw one horizontally-centred line, optional soft glow / drop shadow."""
    d = ImageDraw.Draw(img)
    tw = text_width(d, s, fnt, tracking)
    x = (img.width - tw) / 2
    if shadow:
        _shadow_text(img, s, fnt, (x, y), tracking)
    if glow:
        _glow_text(img, s, fnt, (x, y), glow, tracking)
    d = ImageDraw.Draw(img)
    draw_tracked(d, (x, y), s, fnt, fill, tracking)
    return tw


def _shadow_text(img, s, fnt, xy, tracking=0, radius=9, spread=2):
    """Soft dark halo so light type holds over a bright photograph."""
    from PIL import ImageFilter
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for dx, dy in ((0, 0), (0, spread), (spread, 0), (-spread, 0), (0, -spread)):
        draw_tracked(d, (xy[0] + dx, xy[1] + dy), s, fnt, (2, 8, 18, 200), tracking)
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius)))


def left_line(img, s, fnt, x, y, fill=SILVER, tracking=0):
    d = ImageDraw.Draw(img)
    draw_tracked(d, (x, y), s, fnt, fill, tracking)
    return text_width(d, s, fnt, tracking)


def _glow_text(img, s, fnt, xy, colour, tracking=0, radius=18, strength=110):
    from PIL import ImageFilter
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    draw_tracked(d, xy, s, fnt, colour + (strength,), tracking)
    layer = layer.filter(ImageFilter.GaussianBlur(radius))
    img.alpha_composite(layer)


def run(cmd, quiet=True):
    """Run a command, raising with captured stderr on failure."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            f"command failed ({res.returncode}): {' '.join(map(str, cmd))}\n"
            f"{res.stderr[-3000:]}"
        )
    if not quiet:
        print(res.stdout)
    return res


def ffprobe_duration(path):
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True)
    if res.returncode != 0 or not res.stdout.strip():
        return None
    return float(res.stdout.strip())


# Uniform encode settings for every intermediate clip, so concat never
# re-encodes on mismatched parameters.
INTERMEDIATE = [
    "-c:v", "libx264", "-preset", "medium", "-crf", "16",
    "-pix_fmt", "yuv420p", "-r", str(FPS),
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
    "-movflags", "+faststart", "-an",
]


def stills_to_clip(png_dir, out, fps=FPS, pattern="f_%05d.png"):
    run(["ffmpeg", "-y", "-framerate", str(fps), "-i", str(Path(png_dir) / pattern),
         *INTERMEDIATE, str(out)])
