#!/usr/bin/env python3
"""Generate animated ASS title cards with correct RTL (Hebrew/Arabic) rendering.

Text is emitted in logical order and handed to libass, which runs FriBidi for
bidirectional reordering and HarfBuzz for shaping. Never pre-reverse strings.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SAFE_MARGIN = 0.06   # keep text this far from every edge
MIN_HOLD = 1.2       # seconds a card must sit still to be readable

ANIMATIONS = {"fade", "zoom", "rise", "blur", "slide", "typewriter", "wordwise", "none"}

# ASS numpad alignment codes for a vertically centred anchor.
ALIGN_CODES = {"left": 4, "center": 5, "right": 6}


def anchor_x(align, canvas):
    """Horizontal anchor for a card, respecting the safe margin."""
    margin = int(canvas["width"] * SAFE_MARGIN)
    if align == "right":
        return canvas["width"] - margin
    if align == "left":
        return margin
    return canvas["width"] // 2

# Presets pair a background treatment with the type settings that suit it.
# Flat colour plus an outlined font is what makes a title look like a default;
# these carry a graded background, grain, letterbox bars and no hard outline.
STYLES = {
    "document": {
        "base": (10, 11, 13), "glow": (150, 165, 185), "glow_pos": (0.5, 0.30),
        "glow_strength": 0.22, "glow_radius": 0.85, "grain": 7.0,
        "vignette": 0.55, "letterbox": 2.39, "outline": 0, "shadow": 2.5,
        "font": "Miriam CLM", "accent": "#C9A227", "ink": "#F2EFE9",
        "muted": "#868C96",
    },
    "cinematic": {
        "base": (13, 12, 10), "glow": (232, 170, 90), "glow_pos": (0.5, 0.72),
        "glow_strength": 0.30, "glow_radius": 0.95, "grain": 9.0,
        "vignette": 0.70, "letterbox": 2.39, "outline": 0, "shadow": 3.0,
        "font": "Frank Ruehl CLM", "accent": "#E8C877", "ink": "#F5F0E6",
        "muted": "#9A9188",
    },
    "bold": {
        "base": (8, 9, 12), "glow": (70, 110, 220), "glow_pos": (0.22, 0.5),
        "glow_strength": 0.34, "glow_radius": 1.05, "grain": 6.0,
        "vignette": 0.45, "letterbox": 0, "outline": 0, "shadow": 3.5,
        "font": "Aharoni CLM", "accent": "#F0B429", "ink": "#FFFFFF",
        "muted": "#6E7681",
    },
}


def make_background(style, w, h, seed=None):
    """Render a graded background: base tint, off-centre glow, grain, vignette.

    Built in numpy rather than with ffmpeg's geq because the gradients need to be
    smooth and the grain fine - both are what separate this from a flat fill.
    """
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xs - style["glow_pos"][0] * w) / (w * 0.5)
    ny = (ys - style["glow_pos"][1] * h) / (h * 0.5)

    # Smooth falloff from the light source; squared cosine avoids the hard edge
    # a linear ramp leaves behind.
    dist = np.sqrt(nx * nx + ny * ny) / max(style["glow_radius"], 1e-3)
    falloff = np.clip(1.0 - dist, 0.0, 1.0) ** 2

    base = np.array(style["base"], dtype=np.float32)
    glow = np.array(style["glow"], dtype=np.float32)
    img = base[None, None, :] + falloff[..., None] * (glow - base)[None, None, :] * style["glow_strength"]

    # Vignette pulls the corners down so the eye stays on the centre.
    vx = (xs - w / 2) / (w / 2)
    vy = (ys - h / 2) / (h / 2)
    vig = 1.0 - style["vignette"] * np.clip(np.sqrt(vx * vx + vy * vy) / 1.414, 0, 1) ** 1.8
    img *= vig[..., None]

    # Grain keeps large flat areas from banding on projectors and cheap panels,
    # and reads as film rather than as a computer gradient.
    if style["grain"] > 0:
        img += rng.normal(0.0, style["grain"], (h, w, 1))

    img = np.clip(img, 0, 255).astype(np.uint8)

    if style.get("letterbox"):
        # Cinemascope bars. Nothing else changes a frame's register this cheaply.
        visible = int(w / style["letterbox"])
        bar = max(0, (h - visible) // 2)
        img[:bar] = 0
        img[h - bar:] = 0

    return Image.fromarray(img)


def make_scrim(direction, strength, w, h):
    """A one-sided gradient of black, opaque where the text sits and clear elsewhere.

    Darkening the whole frame to make text readable also flattens the photograph
    behind it. A scrim buys the same contrast while leaving most of the image at
    full brightness, which is why it is what title sequences actually use.
    """
    import numpy as np
    from PIL import Image

    ramp = np.linspace(0.0, 1.0, w if direction in ("left", "right") else h,
                       dtype=np.float32)
    if direction in ("left", "top"):
        ramp = ramp[::-1]
    # Ease in so the scrim has no visible starting edge.
    ramp = np.clip(ramp, 0, 1) ** 2.2 * strength

    if direction in ("left", "right"):
        alpha = np.tile(ramp[None, :], (h, 1))
    else:
        alpha = np.tile(ramp[:, None], (1, w))

    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(rgba, mode="RGBA")


def ass_color(hex_color, alpha=0):
    """#RRGGBB -> &HAABBGGRR&  (ASS stores BGR, and alpha is inverted)."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"Bad colour {hex_color!r}, expected #RRGGBB")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}&".upper()


def ass_time(seconds):
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def escape(text):
    """Protect ASS control characters without touching the logical char order."""
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


# Hebrew, Arabic, and their presentation forms.
RTL_RANGES = ((0x0590, 0x05FF), (0x0600, 0x06FF), (0x0700, 0x074F),
              (0x0750, 0x077F), (0xFB1D, 0xFDFF), (0xFE70, 0xFEFF))


def has_rtl(text):
    return any(any(lo <= ord(ch) <= hi for lo, hi in RTL_RANGES) for ch in text)


def build_header(canvas, font, default_size, outline=None, shadow=None):
    w, h = canvas["width"], canvas["height"]
    margin_x = int(w * SAFE_MARGIN)
    margin_y = int(h * SAFE_MARGIN)
    # A hard outline is what makes titles look like burned-in subtitles. It is
    # only worth paying for over bright or busy footage; on a controlled dark
    # background a soft shadow carries the text on its own.
    if outline is None:
        outline = max(2, round(default_size * 0.035))
    if shadow is None:
        shadow = max(1, round(default_size * 0.02))
    outline = int(round(float(outline)))
    shadow = int(round(float(shadow)))
    return "\n".join([
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {w}",
        f"PlayResY: {h}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font},{default_size},{ass_color('#FFFFFF')},{ass_color('#FFFFFF')},"
        f"{ass_color('#000000')},&H96000000&,0,0,0,0,100,100,0,0,1,{outline},{shadow},5,"
        f"{margin_x},{margin_x},{margin_y},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])


def line_tags(line, canvas, animation, start, end, y, in_dur, out_dur, align="center"):
    """Build the ASS override tags that position and animate one line of text."""
    an = ALIGN_CODES.get(align, 5)
    ax = anchor_x(align, canvas)
    tags = [f"\\an{an}\\pos({ax},{int(y)})"]

    size = line.get("size")
    if size:
        tags.append(f"\\fs{int(size)}")
    if line.get("bold"):
        tags.append("\\b1")
    if line.get("italic"):
        tags.append("\\i1")
    if line.get("color"):
        tags.append(f"\\c{ass_color(line['color'])}")
    if line.get("spacing"):
        # Letter spacing is dropped for RTL text upstream - see check_spacing.
        tags.append(f"\\fsp{line['spacing']}")

    fade_in_ms = int(in_dur * 1000)
    fade_out_ms = int(out_dur * 1000)

    if animation == "none":
        pass
    elif animation == "fade":
        tags.append(f"\\fad({fade_in_ms},{fade_out_ms})")
    elif animation == "zoom":
        # Settle from slightly oversized - the classic cinematic title reveal.
        tags.append(f"\\fad({fade_in_ms},{fade_out_ms})")
        tags.append(f"\\fscx108\\fscy108\\t(0,{fade_in_ms},\\fscx100\\fscy100)")
    elif animation == "rise":
        drift = int(canvas["height"] * 0.035)
        tags[0] = (f"\\an{an}\\move({ax},{int(y) + drift},"
                   f"{ax},{int(y)},0,{fade_in_ms})")
        tags.append(f"\\fad({fade_in_ms},{fade_out_ms})")
    elif animation == "blur":
        tags.append(f"\\fad({fade_in_ms},{fade_out_ms})")
        tags.append(f"\\blur18\\t(0,{fade_in_ms},\\blur0)")
    elif animation == "slide":
        # Enters from the right, matching Hebrew reading direction.
        off = int(canvas["width"] * 0.28)
        tags[0] = (f"\\an{an}\\move({ax + off},{int(y)},"
                   f"{ax},{int(y)},0,{fade_in_ms})")
        tags.append(f"\\fad({fade_in_ms},{fade_out_ms})")
    elif animation == "wordwise":
        # Per-word events are emitted separately; this is just the base style.
        pass

    return "{" + "".join(tags) + "}"


def wordwise_events(line, canvas, start, end, y, style_prefix, out_dur, pace=0.20):
    """Reveal one word at a time, each landing with a small settle.

    For Hebrew this reads especially well right-aligned: each cumulative prefix
    is a complete logical string, so bidi lays it out correctly and the line
    grows leftward - the direction the eye is already travelling.
    """
    words = line["text"].split()
    if len(words) < 2:
        return None
    span = end - start
    step = min(pace, (span * 0.55) / len(words))
    events = []
    for i in range(1, len(words) + 1):
        ev_start = start + step * (i - 1)
        ev_end = end if i == len(words) else start + step * i
        partial = escape(" ".join(words[:i]))
        extra = f"\\fad(0,{int(out_dur * 1000)})" if i == len(words) else ""
        # Each new word arrives fractionally oversized and settles - it reads as
        # weight landing rather than text switching on.
        extra += "\\fscx104\\fscy104\\t(0,90,\\fscx100\\fscy100)"
        tag = style_prefix[:-1] + extra + "}"
        events.append(
            f"Dialogue: 1,{ass_time(ev_start)},{ass_time(ev_end)},Default,,0,0,0,,{tag}{partial}")
    return events


def typewriter_events(line, canvas, start, end, y, style_prefix, out_dur):
    """One event per character reveal, so the text builds up on screen."""
    text = line["text"]
    chars = list(text)
    reveal = min((end - start) * 0.45, 0.06 * len(chars))
    step = reveal / max(1, len(chars))
    events = []
    for i in range(1, len(chars) + 1):
        ev_start = start + step * (i - 1)
        # Each partial string is complete-in-itself, so bidi reorders it correctly.
        partial = escape("".join(chars[:i]))
        ev_end = end if i == len(chars) else start + step * i
        fade = f"\\fad(0,{int(out_dur * 1000)})" if i == len(chars) else ""
        tag = style_prefix[:-1] + fade + "}" if fade else style_prefix
        events.append(f"Dialogue: 0,{ass_time(ev_start)},{ass_time(ev_end)},Default,,0,0,0,,{tag}{partial}")
    return events


def rule_event(card, canvas, start, end, y, in_dur, out_dur, palette):
    """A thin horizontal rule. Small, but it gives a centred card a spine."""
    spec = card["rule"]
    spec = {} if spec is True else dict(spec)
    width = int(spec.get("width", canvas["width"] * 0.13))
    thick = max(1, int(spec.get("thickness", 3)))
    color = spec.get("color", palette.get("accent", "#C9A227"))
    if color in palette:
        color = palette[color]
    alpha = int(spec.get("alpha", 0x20))
    cx = canvas["width"] // 2
    x0, x1 = cx - width // 2, cx + width // 2
    y0, y1 = int(y), int(y) + thick
    draw = (f"{{\\an7\\pos(0,0)\\p1\\c{ass_color(color)}\\alpha&H{alpha:02X}&"
            f"\\bord0\\shad0\\fad({int(in_dur * 1000)},{int(out_dur * 1000)})}}"
            f"m {x0} {y0} l {x1} {y0} l {x1} {y1} l {x0} {y1}{{\\p0}}")
    return f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{draw}"


def render_card(card, canvas, default_size, index, warnings, palette=None):
    palette = palette or {}
    start = float(card["start"])
    end = float(card["end"])
    duration = end - start
    animation = card.get("animation", "fade")
    align = card.get("align", "center")
    if animation not in ANIMATIONS:
        sys.exit(f"Card {index}: unknown animation {animation!r}. "
                 f"Choose from {', '.join(sorted(ANIMATIONS))}")

    in_dur = float(card.get("fade_in", 0.45))
    out_dur = float(card.get("fade_out", 0.45))

    if duration <= 0:
        sys.exit(f"Card {index}: end ({end}) must be after start ({start})")
    hold = duration - in_dur - out_dur
    if hold < MIN_HOLD:
        warnings.append(
            f"Card {index} holds still for only {hold:.2f}s "
            f"(needs ~{MIN_HOLD}s to be readable). Lengthen it or shorten the fades.")

    lines = card.get("lines") or []
    if not lines:
        sys.exit(f"Card {index}: no lines")
    if len(lines) > 2:
        warnings.append(f"Card {index} has {len(lines)} lines; 2 is the readable maximum.")

    sizes = [int(l.get("size") or default_size) for l in lines]
    gap = int(max(sizes) * 0.42)
    block_height = sum(sizes) + gap * (len(lines) - 1)
    # "y" places the block's centre as a fraction of frame height, so cards that
    # share screen time can be stacked instead of landing on top of each other.
    centre_y = float(card.get("y", 0.5)) * canvas["height"]
    cursor = centre_y - block_height / 2

    top, bottom = cursor, cursor + block_height
    limit = canvas["height"] * SAFE_MARGIN
    if top < limit or bottom > canvas["height"] - limit:
        warnings.append(
            f"Card {index} sits outside the {int(SAFE_MARGIN * 100)}% safe area "
            f"and may be cropped by some players. Adjust its \"y\" or line sizes.")

    events = []
    if card.get("scrim"):
        # A soft dark band behind the text block, drawn as an ASS shape.
        pad = int(max(sizes) * 0.9)
        top = int(cursor - pad)
        bottom = int(cursor + block_height + pad)
        w = canvas["width"]
        draw = f"{{\\an7\\pos(0,0)\\p1\\c{ass_color('#000000')}\\alpha&H60&\\bord0\\shad0" \
               f"\\fad({int(in_dur * 1000)},{int(out_dur * 1000)})}}" \
               f"m 0 {top} l {w} {top} l {w} {bottom} l 0 {bottom}{{\\p0}}"
        events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{draw}")

    if card.get("rule"):
        gap_above = int(max(sizes) * 0.55)
        events.append(rule_event(card, canvas, start, end,
                                 cursor - gap_above, in_dur, out_dur, palette))

    for i, line in enumerate(lines):
        y = cursor + sizes[i] / 2
        cursor += sizes[i] + gap
        prefix = line_tags(line, canvas, animation, start, end, y, in_dur, out_dur, align)
        if animation == "typewriter":
            events += typewriter_events(line, canvas, start, end, y, prefix, out_dur)
        elif animation == "wordwise":
            worded = wordwise_events(line, canvas, start, end, y, prefix, out_dur,
                                     pace=float(card.get("pace", 0.20)))
            if worded is None:  # single word: nothing to stagger
                events.append(
                    f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,"
                    f"{prefix[:-1]}\\fad({int(in_dur * 1000)},{int(out_dur * 1000)})}}"
                    f"{escape(line['text'])}")
            else:
                events += worded
        else:
            events.append(
                f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,"
                f"{prefix}{escape(line['text'])}")
    return events


def check_font(font):
    try:
        out = subprocess.run(["fc-list", ":lang=he", "family"],
                             capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return True  # cannot verify; let libass try
    families = out.stdout
    if font.lower() not in families.lower():
        print(f"WARNING: '{font}' was not found among fonts with Hebrew coverage. "
              f"Hebrew may render as empty boxes.\n"
              f"  Available: {', '.join(sorted(set(families.split(chr(10))))[:8])}",
              file=sys.stderr)
        return False
    return True


def render_video(ass_path, out_path, canvas, duration, background, fps,
                 push=0.0, work_dir=None, seed=None, still=False, grade=None):
    grade = grade or {"blur": 14, "darken": 0.16, "saturation": 0.8,
                      "letterbox": 2.39, "grain": 5, "scrim": "right",
                      "scrim_strength": 0.82}
    w, h = canvas["width"], canvas["height"]
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    frames = max(2, int(round(duration * fps)))

    if background in STYLES:
        bg_path = Path(work_dir or out_path.parent) / f"_bg_{background}.png"
        bg_path.parent.mkdir(parents=True, exist_ok=True)
        make_background(STYLES[background], w, h, seed).save(bg_path)
        cmd += ["-loop", "1", "-framerate", str(fps), "-i", str(bg_path)]
        vf = ""
        if push > 0:
            # A background that breathes while the text stays pin-sharp. Nothing
            # in a real title sequence is ever perfectly still.
            over = 1.0 + push
            src_w, src_h = int(w * over) // 2 * 2, int(h * over) // 2 * 2
            vf = (f"scale={src_w}:{src_h},"
                  f"zoompan=z='{over:.4f}-{push:.4f}*on/{frames - 1}':"
                  f"x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':"
                  f"d=1:s={w}x{h}:fps={fps},")
        vf += "format=yuv420p,"
    elif background in ("black", "gradient"):
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:d={duration}:r={fps}"]
        vf = "format=yuv420p,"
    else:
        src = Path(background).expanduser()
        if not src.exists():
            sys.exit(f"Background not found: {src}")
        cmd += ["-stream_loop", "-1", "-i", str(src)]
        # Knock the footage back enough for text to read, but not so far that the
        # photographs stop being the point. Heavy blur and a global brightness cut
        # turn real material into wallpaper - the mistake that makes a title look
        # generic. Prefer a directional scrim: shade only where the text sits.
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
              f"crop={w}:{h},gblur=sigma={grade['blur']},"
              f"eq=brightness={-abs(grade['darken']):.3f}:saturation={grade['saturation']},"
              f"fps={fps},")
        if grade.get("grain"):
            vf += f"noise=alls={int(grade['grain'])}:allf=t+u,"
        vf += "format=yuv420p"

        scrim_dir = grade.get("scrim")
        if scrim_dir and scrim_dir != "none":
            scrim_path = Path(work_dir or out_path.parent) / "_scrim.png"
            make_scrim(scrim_dir, float(grade.get("scrim_strength", 0.82)),
                       w, h).save(scrim_path)
            cmd += ["-i", str(scrim_path)]
            vf = (f"[0:v]{vf}[base];[1:v]format=rgba[sc];"
                  f"[base][sc]overlay=0:0:format=auto")
            filter_is_complex = True
        else:
            vf += ","
            filter_is_complex = False

        if grade.get("letterbox"):
            visible = int(w / grade["letterbox"])
            bar = max(0, (h - visible) // 2)
            if bar:
                box = (f"drawbox=x=0:y=0:w={w}:h={bar}:color=black@1:t=fill,"
                       f"drawbox=x=0:y={h - bar}:w={w}:h={bar}:color=black@1:t=fill")
                vf += (box + ",") if not filter_is_complex else ("," + box)

        if filter_is_complex:
            vf += f",ass={ass_path}[v]"
            cmd += ["-filter_complex", vf, "-map", "[v]"]
            if still:
                cmd += ["-ss", f"{float(still):.3f}", "-frames:v", "1", str(out_path)]
            else:
                cmd += ["-frames:v", str(frames), "-c:v", "libx264", "-preset", "medium",
                        "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(fps), str(out_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(result.stderr, file=sys.stderr)
                sys.exit("ffmpeg failed rendering the title card")
            return

    vf += f"ass={ass_path}"
    if still:
        # Output-side seek, past the fade-ins. A frame grabbed at t=0 shows every
        # \fad element at zero opacity, which looks exactly like it failed to
        # render - the subtitle filter is applied before this seek discards frames.
        cmd += ["-ss", f"{float(still):.3f}", "-vf", vf, "-frames:v", "1", str(out_path)]
    else:
        cmd += ["-vf", vf, "-frames:v", str(frames),
                "-c:v", "libx264", "-preset", "medium",
                "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(fps), str(out_path)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit("ffmpeg failed rendering the title card")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", required=True, help="JSON spec describing the cards")
    ap.add_argument("--out", default="work/titles.ass", help="ASS output path")
    ap.add_argument("--render", help="Also render a standalone video to this path")
    ap.add_argument("--background", default=None,
                    help=f"{' | '.join(STYLES)} | black | path to an image or video "
                         f"(default: the spec's \"style\", else 'cinematic')")
    ap.add_argument("--duration", type=float, help="Render length (default: last card end + 0.5s)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--push", type=float, default=0.03,
                    help="Slow background zoom over the card, 0 to disable")
    ap.add_argument("--still", action="store_true",
                    help="Render a single PNG instead of a video, for fast look tests")
    ap.add_argument("--still-at", type=float, default=None,
                    help="Timestamp for --still (default: once every card has faded in)")
    ap.add_argument("--seed", type=int, default=7, help="Grain pattern seed")
    ap.add_argument("--bg-blur", type=float, default=14,
                    help="Blur applied to a media background (lower keeps the photo readable)")
    ap.add_argument("--bg-darken", type=float, default=0.16)
    ap.add_argument("--bg-saturation", type=float, default=0.8)
    ap.add_argument("--letterbox", type=float, default=2.39,
                    help="Aspect for the black bars, 0 for none")
    ap.add_argument("--grain", type=float, default=5)
    ap.add_argument("--scrim", choices=["right", "left", "top", "bottom", "none"],
                    default="right",
                    help="Directional shade for text to sit on, over a media background")
    ap.add_argument("--scrim-strength", type=float, default=0.82)
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    canvas = spec.get("canvas") or {"width": 1920, "height": 1080}
    canvas = {"width": int(canvas.get("width", 1920)), "height": int(canvas.get("height", 1080))}
    cards = spec.get("cards") or []
    if not cards:
        sys.exit("Spec contains no cards")

    style_name = args.background or spec.get("style") or "cinematic"
    style = STYLES.get(style_name)

    # The preset supplies the font and type weight that suit its background; an
    # explicit value in the spec still wins.
    font = spec.get("font") or (style["font"] if style else "Noto Sans Hebrew")
    default_size = int(spec.get("size") or round(canvas["height"] * 0.085))
    outline = spec.get("outline", style["outline"] if style else None)
    shadow = spec.get("shadow", style["shadow"] if style else None)

    check_font(font)

    # libass renders RTL text backwards as soon as \fsp is applied - any value,
    # even 1 - because letter spacing bypasses its bidi reordering. Silently
    # shipping reversed Hebrew is far worse than losing the tracking, so strip it.
    stripped = 0
    for card in cards:
        for line in card.get("lines") or []:
            if line.get("spacing") and has_rtl(line.get("text", "")):
                line.pop("spacing")
                stripped += 1
    if stripped:
        print(f"WARNING: dropped letter spacing on {stripped} line(s) containing "
              f"right-to-left text. libass reverses RTL glyph order when \\fsp is "
              f"set, so the text would have rendered backwards. Use size and "
              f"colour for hierarchy instead.", file=sys.stderr)

    # Let cards refer to the preset's palette by name instead of repeating hexes.
    palette = {"accent": style["accent"], "ink": style["ink"], "muted": style["muted"]} \
        if style else {}
    for card in cards:
        for line in card.get("lines") or []:
            if line.get("color") in palette:
                line["color"] = palette[line["color"]]
            elif not line.get("color") and palette:
                line["color"] = palette["ink"]

    warnings = []
    events = []
    for i, card in enumerate(cards):
        events += render_card(card, canvas, default_size, i, warnings, palette)

    ass = build_header(canvas, font, default_size, outline, shadow) \
        + "\n" + "\n".join(events) + "\n"
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(ass, encoding="utf-8")

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    print(f"Wrote {out}  ({len(cards)} card(s), {len(events)} event(s))")

    if args.render:
        duration = args.duration or (max(float(c["end"]) for c in cards) + 0.5)
        render_out = Path(args.render).expanduser()
        render_out.parent.mkdir(parents=True, exist_ok=True)
        still_at = None
        if args.still:
            # Land after the slowest fade-in but before the earliest card leaves,
            # so the preview shows every element at full opacity.
            settled = max(float(c["start"]) + float(c.get("fade_in", 0.45))
                          for c in cards) + 0.2
            earliest_end = min(float(c["end"]) for c in cards)
            still_at = args.still_at if args.still_at is not None else \
                min(settled, max(0.0, earliest_end - 0.15))

        render_video(out, render_out, canvas, duration, style_name, args.fps,
                     push=args.push, work_dir=out.parent, seed=args.seed,
                     still=still_at,
                     grade={"blur": args.bg_blur, "darken": args.bg_darken,
                            "saturation": args.bg_saturation,
                            "letterbox": args.letterbox, "grain": args.grain,
                            "scrim": args.scrim, "scrim_strength": args.scrim_strength})
        print(f"Rendered {render_out}  "
              + (f"(single frame at {still_at:.2f}s, " if args.still
                 else f"({duration:.2f}s, ")
              + f"{canvas['width']}x{canvas['height']}, style '{style_name}')")

    print("Burn onto footage with:  "
          f"ffmpeg -i input.mp4 -vf \"ass={out}\" -c:a copy output.mp4")


if __name__ == "__main__":
    main()
