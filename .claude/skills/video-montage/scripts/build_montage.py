#!/usr/bin/env python3
"""Render a beat-synced montage from a media manifest, a cut list, and a music bed.

Two passes: every shot becomes a normalized intermediate segment, then those
segments are joined with transitions centered on the musical cut points.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

XFADE_STYLES = {
    "low": ["fade", "fadeblack", "dissolve"],
    "mid": ["fade", "dissolve", "smoothleft", "smoothright"],
    "high": ["fade", "wipeleft", "wiperight", "slideleft", "circleopen"],
}


def run(cmd, what):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(" ".join(str(c) for c in cmd[:24]) + " ...", file=sys.stderr)
        print(result.stderr[-3000:], file=sys.stderr)
        sys.exit(f"ffmpeg failed: {what}")
    return result


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def contain_size(src_w, src_h, canvas_w, canvas_h):
    """Largest even-dimensioned box fitting the source inside the canvas."""
    if not src_w or not src_h:
        return canvas_w, canvas_h
    scale = min(canvas_w / src_w, canvas_h / src_h)
    w = max(2, int(round(src_w * scale)) // 2 * 2)
    h = max(2, int(round(src_h * scale)) // 2 * 2)
    return min(w, canvas_w), min(h, canvas_h)


def background_chain(canvas_w, canvas_h, blur):
    """Fill the canvas with a blurred, darkened copy so any aspect ratio fits."""
    return (f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
            f"crop={canvas_w}:{canvas_h},gblur=sigma={blur},"
            f"eq=brightness=-0.16:saturation=0.75,setsar=1")


def ken_burns_chain(item, frames, fps, canvas_w, canvas_h, index):
    """Slow zoom and drift across a still, output at the contained size."""
    fw, fh = contain_size(item.get("width"), item.get("height"), canvas_w, canvas_h)
    frames = max(2, int(frames))

    # Feed zoompan an oversized copy so zooming in never upscales past the source.
    over = 1.25
    src_w = int(fw * over) // 2 * 2
    src_h = int(fh * over) // 2 * 2

    zoom_in = index % 2 == 0
    z0, z1 = (over, over * 1.15) if zoom_in else (over * 1.15, over)

    # Alternate the drift direction so consecutive stills do not feel identical.
    corners = [(0.5, 0.35), (0.35, 0.5), (0.5, 0.65), (0.65, 0.5)]
    fx0, fy0 = corners[index % len(corners)]
    fx1, fy1 = 0.5, 0.5

    dz = z1 - z0
    p = f"on/{frames - 1}"
    return (
        f"scale={src_w}:{src_h}:force_original_aspect_ratio=increase,"
        f"crop={src_w}:{src_h},setsar=1,"
        f"zoompan=z='{z0:.5f}+{dz:.5f}*{p}':"
        f"x='(iw-iw/zoom)*({fx0:.4f}+{fx1 - fx0:.4f}*{p})':"
        f"y='(ih-ih/zoom)*({fy0:.4f}+{fy1 - fy0:.4f}*{p})':"
        f"d=1:s={fw}x{fh}:fps={fps}"
    ), fw, fh


def render_segment(item, shot, frames, cfg, out_path, index):
    """Render one shot to a normalized intermediate of exactly `frames` frames.

    Frame counts, not durations, are the unit of truth here: `-frames:v` makes
    every segment land on an exact boundary so lengths cannot drift on assembly.
    """
    fps, cw, ch = cfg["fps"], cfg["width"], cfg["height"]
    duration = frames / fps
    src = item["path"]

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]

    if item["kind"] == "image":
        cmd += ["-loop", "1", "-framerate", str(fps), "-i", src]
        fg_chain, fw, fh = ken_burns_chain(item, frames, fps, cw, ch, index)
        filt = (
            f"[0:v]{background_chain(cw, ch, cfg['blur'])}[bg];"
            f"[0:v]{fg_chain},setsar=1[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
            f"fps={fps},format=yuv420p[v]"
        )
    else:
        start = float(shot.get("source_in") or 0.0)
        avail = (item.get("duration") or 0.0) - start
        take = min(duration, max(0.1, avail))
        # A clip shorter than its slot gets its final frame held rather than
        # looped - a loop reads as a glitch, a hold reads as a beat.
        deficit = duration - take

        cmd += ["-ss", f"{start:.4f}", "-t", f"{take:.4f}", "-i", src]
        fw, fh = contain_size(item.get("width"), item.get("height"), cw, ch)
        # Pad generously; -frames:v trims back to the exact count.
        pad = (f",tpad=stop_mode=clone:stop_duration={deficit + 0.5:.4f}"
               if deficit > 0.001 else "")
        filt = (
            f"[0:v]fps={fps},setpts=PTS-STARTPTS{pad}[base];"
            f"[base]split=2[b1][b2];"
            f"[b1]{background_chain(cw, ch, cfg['blur'])}[bg];"
            f"[b2]scale={fw}:{fh}:flags=lanczos,setsar=1[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]"
        )

    cmd += ["-filter_complex", filt, "-map", "[v]", "-frames:v", str(frames),
            "-an", "-c:v", "libx264", "-preset", cfg["preset"], "-crf", str(cfg["seg_crf"]),
            "-pix_fmt", "yuv420p", "-r", str(fps),
            # Constant frame rate and a fixed timebase; anything else drifts on concat.
            "-vsync", "cfr", "-video_track_timescale", "90000",
            str(out_path)]
    run(cmd, f"segment {index} ({Path(src).name})")


def conform_clip(src, frames, cfg, out_path, what):
    """Force a title clip to exactly the frame count the cut plan reserved.

    An intro one second longer than its reserve pushes every downbeat cut in the
    body a second late, which is the difference between synced and nearly synced.
    """
    fps = cfg["fps"]
    required = frames / fps
    actual = probe_duration(src)
    note = None
    if actual > required + 0.02:
        # Trim the tail: the animation has already resolved by then.
        note = (f"{what} was {actual:.2f}s but the plan reserves {required:.2f}s - "
                f"trimmed {actual - required:.2f}s off the end")
    elif actual < required - 0.02:
        note = (f"{what} was {actual:.2f}s but the plan reserves {required:.2f}s - "
                f"held the last frame for {required - actual:.2f}s")

    # Always re-encode: even a clip of the right length needs its frame count,
    # rate, and timebase pinned before it can join the chain cleanly.
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
           "-filter_complex",
           f"[0:v]fps={fps},setpts=PTS-STARTPTS,"
           f"tpad=stop_mode=clone:stop_duration={max(0.0, required - actual) + 0.5:.4f},"
           f"scale={cfg['width']}:{cfg['height']},setsar=1,format=yuv420p[v]",
           "-map", "[v]", "-frames:v", str(int(frames)),
           "-an", "-c:v", "libx264", "-preset", cfg["preset"],
           "-crf", str(cfg["seg_crf"]), "-pix_fmt", "yuv420p", "-r", str(fps),
           "-vsync", "cfr", "-video_track_timescale", "90000", str(out_path)]
    run(cmd, f"conforming {what}")
    return out_path, probe_duration(out_path), note


def pick_transition(shot, style):
    if style == "hard" or shot["transition_out"] <= 0.01:
        return None
    pool = XFADE_STYLES.get(shot.get("intensity", "mid"), XFADE_STYLES["mid"])
    if style in ("slow",):
        return "fade"
    return pool[shot["index"] % len(pool)]


def build_duck_expression(windows, depth_db, ramp):
    """A smooth music-gain curve that dips under each clip we want to hear."""
    if not windows:
        return None
    depth = 1.0 - 10 ** (-abs(depth_db) / 20.0)
    terms = []
    for a, b in windows:
        a, b = float(a), float(b)
        # Triangular ramp: 0 outside the window, 1 across the middle of it.
        terms.append(
            f"(1-{depth:.4f}*max(0\\,min(1\\,min((t-{a - ramp:.3f})/{ramp:.3f}\\,"
            f"({b + ramp:.3f}-t)/{ramp:.3f}))))"
        )
    return "*".join(terms)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True, help="From media-prep")
    ap.add_argument("--cuts", required=True, help="From beat-sync plan_cuts.py")
    ap.add_argument("--music", required=True, help="Music bed WAV")
    ap.add_argument("--out", default="out/montage.mp4")
    ap.add_argument("--work", default="work/segments")
    ap.add_argument("--intro", help="Pre-rendered intro clip")
    ap.add_argument("--outro", help="Pre-rendered outro clip")
    ap.add_argument("--intro-transition", type=float, default=0.8)
    ap.add_argument("--outro-transition", type=float, default=1.0)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--blur", type=float, default=28, help="Background blur sigma")
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--seg-crf", type=int, default=16, help="Intermediate quality (lower = better)")
    ap.add_argument("--crf", type=int, default=18, help="Final encode quality")
    ap.add_argument("--transition-style", choices=["auto", "fade", "slow", "hard"], default="auto")
    ap.add_argument("--overlay-ass", help="ASS subtitle file to burn over the finished montage")
    ap.add_argument("--duck-db", type=float, default=12.0, help="How far music drops under clip audio")
    ap.add_argument("--clip-audio-gain", type=float, default=1.4)
    ap.add_argument("--keep-segments", action="store_true")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    cuts = json.loads(Path(args.cuts).read_text(encoding="utf-8"))
    items = manifest["items"]
    shots = cuts["shots"]

    if not items:
        sys.exit("Manifest has no usable items")
    if len(items) < len(shots):
        print(f"NOTE: {len(shots)} slots but only {len(items)} media items - "
              f"items will repeat.", file=sys.stderr)
    if len(shots) > 120:
        print(f"NOTE: {len(shots)} segments in one filter graph; this will be slow "
              f"and memory-hungry. Consider fewer, longer shots.", file=sys.stderr)

    cfg = {
        "fps": args.fps, "width": args.width, "height": args.height,
        "blur": args.blur, "preset": args.preset, "seg_crf": args.seg_crf,
    }

    work = Path(args.work).expanduser()
    work.mkdir(parents=True, exist_ok=True)

    # ---- lay out the timeline in whole frames -------------------------------
    # Everything downstream is computed from frame-quantized *boundaries* rather
    # than from durations. Rounding each duration independently would let a
    # half-frame error per segment accumulate until the last cut sits visibly
    # off the beat; rounding the boundaries keeps every cut within half a frame
    # of its downbeat no matter how many shots there are.
    fps = args.fps
    body_start = cuts.get("intro_reserved", 0.0)
    body_end = shots[-1]["end"]
    outro_reserved = cuts.get("outro_reserved", 0.0)

    elements = []  # (kind, payload, visible_start, visible_end)
    if args.intro:
        elements.append(("intro", None, 0.0, body_start))
    for shot in shots:
        elements.append(("shot", shot, shot["start"], shot["end"]))
    if args.outro:
        elements.append(("outro", None, body_end, body_end + outro_reserved))

    # Transition between each adjacent pair, in chain order.
    trans_s = []
    for i in range(len(elements) - 1):
        kind_a, payload_a = elements[i][0], elements[i][1]
        if kind_a == "intro":
            trans_s.append(args.intro_transition)
        elif elements[i + 1][0] == "outro":
            trans_s.append(args.outro_transition)
        else:
            trans_s.append(payload_a["transition_out"])
    if args.transition_style == "hard":
        # xfade cannot do a zero-length transition, so one frame is the hard cut.
        trans_f = [1] * len(trans_s)
    else:
        trans_f = [max(1, int(round(t * fps))) for t in trans_s]

    bounds_f = [int(round(elements[0][2] * fps))] + [int(round(e[3] * fps)) for e in elements]

    # Split each transition between the two segments it joins, in whole frames,
    # so the halves always sum back to the transition itself.
    half_out = [trans_f[i] // 2 for i in range(len(trans_f))] + [0]
    half_in = [0] + [trans_f[i] - trans_f[i] // 2 for i in range(len(trans_f))]

    seg_frames = [
        (bounds_f[i + 1] - bounds_f[i]) + half_in[i] + half_out[i]
        for i in range(len(elements))
    ]
    total_frames = bounds_f[-1] - bounds_f[0]
    acc_len = total_frames / fps

    conform_notes = []
    intro_clip = outro_clip = None
    if args.intro:
        intro_clip, _, note = conform_clip(
            Path(args.intro).expanduser(), seg_frames[0], cfg,
            work / "intro_conformed.mp4", "intro")
        if note:
            conform_notes.append(note)
    if args.outro:
        outro_clip, _, note = conform_clip(
            Path(args.outro).expanduser(), seg_frames[-1], cfg,
            work / "outro_conformed.mp4", "outro")
        if note:
            conform_notes.append(note)

    for note in conform_notes:
        print(f"NOTE: {note}", file=sys.stderr)

    print(f"Rendering {len(shots)} segments at {args.width}x{args.height}@{fps}...")
    segments, assigned = [], []
    shot_offset = 1 if args.intro else 0
    for i, shot in enumerate(shots):
        item = items[i % len(items)]
        seg = work / f"seg_{i:04d}.mp4"
        render_segment(item, shot, seg_frames[i + shot_offset], cfg, seg, i)
        segments.append(seg)
        assigned.append(item)
        if (i + 1) % 10 == 0 or i == len(shots) - 1:
            print(f"  {i + 1}/{len(shots)}")

    # ---- assemble the transition chain -------------------------------------
    chain_inputs = list(segments)
    if intro_clip:
        chain_inputs.insert(0, Path(intro_clip))
    if outro_clip:
        chain_inputs.append(Path(outro_clip))

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for seg in chain_inputs:
        cmd += ["-i", str(seg)]
    music_idx = len(chain_inputs)
    cmd += ["-i", str(Path(args.music).expanduser())]

    parts = []
    for i in range(len(chain_inputs)):
        parts.append(f"[{i}:v]setpts=PTS-STARTPTS,fps={fps},"
                     f"scale={args.width}:{args.height},setsar=1,format=yuv420p[c{i}]")

    acc_label = "c0"
    acc_f = seg_frames[0]
    for i in range(1, len(chain_inputs)):
        tf = trans_f[i - 1]
        style_shot = elements[i - 1][1] or elements[i][1] or shots[0]
        effect = pick_transition(style_shot, args.transition_style) or "fade"
        # xfade's offset is where the transition begins in the accumulated
        # timeline; the cut point sits at its midpoint.
        offset_f = max(0, acc_f - tf)
        label = f"x{i}"
        parts.append(f"[{acc_label}][c{i}]xfade=transition={effect}:"
                     f"duration={tf / fps:.5f}:offset={offset_f / fps:.5f}[{label}]")
        acc_f = acc_f + seg_frames[i] - tf
        acc_label = label

    if acc_f != total_frames:
        print(f"WARNING: chain length {acc_f} frames != planned {total_frames}; "
              f"timeline math is off.", file=sys.stderr)

    video_out = acc_label
    if args.overlay_ass:
        ass_path = str(Path(args.overlay_ass).expanduser()).replace("\\", "/").replace(":", "\\:")
        parts.append(f"[{acc_label}]ass='{ass_path}'[titled]")
        video_out = "titled"

    # ---- audio --------------------------------------------------------------
    duck_windows = []
    clip_audio_labels = []
    audio_extra_inputs = []

    for i, (shot, item) in enumerate(zip(shots, assigned)):
        if not shot.get("duck") or not item.get("has_audio") or item["kind"] != "video":
            continue
        # Shot times are already music-timeline times, and the finished video
        # shares that timeline, so they carry over unchanged.
        t0, t1 = shot["start"], shot["end"]
        duck_windows.append((t0, t1))
        idx = music_idx + 1 + len(audio_extra_inputs)
        audio_extra_inputs.append((item["path"], float(shot.get("source_in") or 0.0),
                                   shot["slot"], t0, idx))

    for path, src_in, dur, t0, idx in audio_extra_inputs:
        cmd += ["-ss", f"{src_in:.4f}", "-t", f"{dur:.4f}", "-i", str(path)]

    for path, src_in, dur, t0, idx in audio_extra_inputs:
        delay_ms = int(round(t0 * 1000))
        label = f"ca{idx}"
        parts.append(
            f"[{idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"asetpts=PTS-STARTPTS,atrim=duration={dur:.4f},"
            f"volume={args.clip_audio_gain},"
            f"afade=t=in:st=0:d=0.15,afade=t=out:st={max(0, dur - 0.2):.4f}:d=0.2,"
            f"adelay={delay_ms}|{delay_ms}[{label}]")
        clip_audio_labels.append(label)

    music_chain = (f"[{music_idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:"
                   f"channel_layouts=stereo")
    duck_expr = build_duck_expression(duck_windows, args.duck_db, 0.3)
    if duck_expr:
        music_chain += f",volume=eval=frame:volume='{duck_expr}'"
    # Pad before trimming so a bed that falls a little short of the video cannot
    # truncate the ending; the tail runs out on silence instead.
    music_chain += f",apad,atrim=duration={acc_len:.4f},asetpts=PTS-STARTPTS[music]"
    parts.append(music_chain)

    if clip_audio_labels:
        inputs = "[music]" + "".join(f"[{l}]" for l in clip_audio_labels)
        parts.append(f"{inputs}amix=inputs={1 + len(clip_audio_labels)}:"
                     f"duration=first:normalize=0,"
                     f"alimiter=limit=0.95,aresample=48000[aout]")
    else:
        parts.append("[music]alimiter=limit=0.95,aresample=48000[aout]")

    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd += ["-filter_complex", ";".join(parts),
            "-map", f"[{video_out}]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
            "-pix_fmt", "yuv420p", "-r", str(args.fps),
            "-profile:v", "high", "-level", "4.2",
            "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
            # An explicit duration rather than -shortest: the video is the
            # authority on length, and -shortest would let a short bed clip it.
            "-t", f"{acc_len:.4f}",
            "-movflags", "+faststart", str(out_path)]

    print(f"Assembling {len(chain_inputs)} segments ({acc_len:.2f}s)...")
    run(cmd, "final assembly")

    if not args.keep_segments:
        shutil.rmtree(work, ignore_errors=True)

    final = probe_duration(out_path)
    print(f"\nMontage: {out_path}")
    print(f"  duration  : {final:.2f}s (planned {acc_len:.2f}s)")
    print(f"  shots     : {len(shots)}"
          + (" + intro" if args.intro else "") + (" + outro" if args.outro else ""))
    print(f"  ducked    : {len(duck_windows)} clip(s) with live audio")
    if abs(final - acc_len) > 0.5:
        print(f"  WARNING: output is {abs(final - acc_len):.2f}s off the plan - "
              f"check for clips shorter than their slots.")


if __name__ == "__main__":
    main()
