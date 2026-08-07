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

ANIMATIONS = {"fade", "zoom", "rise", "blur", "slide", "typewriter", "none"}


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


def build_header(canvas, font, default_size):
    w, h = canvas["width"], canvas["height"]
    margin_x = int(w * SAFE_MARGIN)
    margin_y = int(h * SAFE_MARGIN)
    # Outline plus shadow keeps text legible over bright or busy footage.
    outline = max(2, round(default_size * 0.035))
    shadow = max(1, round(default_size * 0.02))
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


def line_tags(line, canvas, animation, start, end, y, in_dur, out_dur):
    """Build the ASS override tags that position and animate one line of text."""
    tags = [f"\\an5\\pos({canvas['width'] // 2},{int(y)})"]

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
        tags[0] = (f"\\an5\\move({canvas['width'] // 2},{int(y) + drift},"
                   f"{canvas['width'] // 2},{int(y)},0,{fade_in_ms})")
        tags.append(f"\\fad({fade_in_ms},{fade_out_ms})")
    elif animation == "blur":
        tags.append(f"\\fad({fade_in_ms},{fade_out_ms})")
        tags.append(f"\\blur18\\t(0,{fade_in_ms},\\blur0)")
    elif animation == "slide":
        # Enters from the right, matching Hebrew reading direction.
        off = int(canvas["width"] * 0.28)
        tags[0] = (f"\\an5\\move({canvas['width'] // 2 + off},{int(y)},"
                   f"{canvas['width'] // 2},{int(y)},0,{fade_in_ms})")
        tags.append(f"\\fad({fade_in_ms},{fade_out_ms})")

    return "{" + "".join(tags) + "}"


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


def render_card(card, canvas, default_size, index, warnings):
    start = float(card["start"])
    end = float(card["end"])
    duration = end - start
    animation = card.get("animation", "fade")
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
    cursor = canvas["height"] / 2 - block_height / 2

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

    for i, line in enumerate(lines):
        y = cursor + sizes[i] / 2
        cursor += sizes[i] + gap
        prefix = line_tags(line, canvas, animation, start, end, y, in_dur, out_dur)
        if animation == "typewriter":
            events += typewriter_events(line, canvas, start, end, y, prefix, out_dur)
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


def render_video(ass_path, out_path, canvas, duration, background, fps):
    w, h = canvas["width"], canvas["height"]
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]

    if background in ("black", "gradient"):
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:d={duration}:r={fps}"]
        if background == "gradient":
            # Radial falloff keeps the centre bright enough for text and darkens
            # the edges, which reads as cinematic rather than flat black.
            vf = ("format=gbrp,geq="
                  "r='24+40*(1-hypot((X-W/2)/(W/2),(Y-H/2)/(H/2)))':"
                  "g='26+42*(1-hypot((X-W/2)/(W/2),(Y-H/2)/(H/2)))':"
                  "b='34+52*(1-hypot((X-W/2)/(W/2),(Y-H/2)/(H/2)))',"
                  "noise=alls=6:allf=t+u,format=yuv420p,")
        else:
            vf = "format=yuv420p,"
    else:
        src = Path(background).expanduser()
        if not src.exists():
            sys.exit(f"Background not found: {src}")
        cmd += ["-stream_loop", "-1", "-i", str(src)]
        # Blur and darken so the title stays legible over whatever is behind it.
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
              f"crop={w}:{h},gblur=sigma=28,eq=brightness=-0.22:saturation=0.7,"
              f"fps={fps},format=yuv420p,")

    vf += f"ass={ass_path}"
    cmd += ["-t", str(duration), "-vf", vf, "-c:v", "libx264", "-preset", "medium",
            "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(fps), str(out_path)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit("ffmpeg failed rendering the title card")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", required=True, help="JSON spec describing the cards")
    ap.add_argument("--out", default="work/titles.ass", help="ASS output path")
    ap.add_argument("--render", help="Also render a standalone video to this path")
    ap.add_argument("--background", default="gradient",
                    help="black | gradient | path to an image or video")
    ap.add_argument("--duration", type=float, help="Render length (default: last card end + 0.5s)")
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    canvas = spec.get("canvas") or {"width": 1920, "height": 1080}
    canvas = {"width": int(canvas.get("width", 1920)), "height": int(canvas.get("height", 1080))}
    font = spec.get("font", "Noto Sans Hebrew")
    default_size = int(spec.get("size") or round(canvas["height"] * 0.085))
    cards = spec.get("cards") or []
    if not cards:
        sys.exit("Spec contains no cards")

    check_font(font)

    warnings = []
    events = []
    for i, card in enumerate(cards):
        events += render_card(card, canvas, default_size, i, warnings)

    ass = build_header(canvas, font, default_size) + "\n" + "\n".join(events) + "\n"
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
        render_video(out, render_out, canvas, duration, args.background, args.fps)
        print(f"Rendered {render_out}  ({duration:.2f}s, {canvas['width']}x{canvas['height']})")

    print("Burn onto footage with:  "
          f"ffmpeg -i input.mp4 -vf \"ass={out}\" -c:a copy output.mp4")


if __name__ == "__main__":
    main()
