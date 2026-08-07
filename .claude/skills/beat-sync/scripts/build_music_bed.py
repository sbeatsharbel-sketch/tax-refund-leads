#!/usr/bin/env python3
"""Trim, crossfade, and loudness-normalize several songs into one soundtrack bed."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


class SongAction(argparse.Action):
    """Collect --song/--start/--duration/--label into ordered song records."""

    def __call__(self, parser, namespace, value, option_string=None):
        songs = getattr(namespace, "songs", None) or []
        key = option_string.lstrip("-")
        if key == "song":
            songs.append({"path": value, "start": 0.0, "duration": None, "label": None})
        else:
            if not songs:
                parser.error(f"--{key} must follow a --song")
            songs[-1][key] = value
        namespace.songs = songs


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        sys.exit(f"Could not read duration of {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--song", action=SongAction, help="Path to a song (repeatable)")
    ap.add_argument("--start", action=SongAction, type=float, help="Start offset within the preceding song")
    ap.add_argument("--duration", action=SongAction, type=float, help="Seconds to take from the preceding song")
    ap.add_argument("--label", action=SongAction, help="Name for the preceding song in the report")
    ap.add_argument("--crossfade", type=float, default=2.5, help="Crossfade seconds between songs")
    ap.add_argument("--out", default="work/music.wav")
    ap.add_argument("--report", default=None, help="Write a JSON timeline of song seams")
    ap.add_argument("--target-lufs", type=float, default=-14.0, help="Integrated loudness target")
    ap.add_argument("--fade-in", type=float, default=1.0)
    ap.add_argument("--fade-out", type=float, default=4.0)
    args = ap.parse_args()

    songs = getattr(args, "songs", None) or []
    if not songs:
        ap.error("at least one --song is required")

    for s in songs:
        path = Path(s["path"]).expanduser()
        if not path.exists():
            sys.exit(f"No such file: {path}")
        s["path"] = str(path)
        available = probe_duration(path) - s["start"]
        if available <= 0:
            sys.exit(f"--start {s['start']} is past the end of {path.name}")
        s["duration"] = min(s["duration"], available) if s["duration"] else available
        s["label"] = s["label"] or path.stem

    xf = args.crossfade if len(songs) > 1 else 0.0
    # Each crossfade overlaps two songs, so the bed is shorter than the sum.
    for s in songs:
        if s["duration"] <= xf:
            sys.exit(f"Segment '{s['label']}' ({s['duration']:.1f}s) is shorter than "
                     f"the {xf}s crossfade. Lengthen it or reduce --crossfade.")

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for s in songs:
        cmd += ["-ss", str(s["start"]), "-t", str(s["duration"]), "-i", s["path"]]

    parts, seams = [], []
    for i, s in enumerate(songs):
        # Resample everything to a common rate/layout; acrossfade requires it.
        parts.append(f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=48000:"
                     f"channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]")

    if len(songs) == 1:
        chain_out = "a0"
        total = songs[0]["duration"]
    else:
        prev, total = "a0", songs[0]["duration"]
        for i in range(1, len(songs)):
            seams.append({
                "at": round(total - xf, 3),
                "from": songs[i - 1]["label"],
                "to": songs[i]["label"],
                "crossfade": xf,
            })
            label = f"x{i}"
            parts.append(f"[{prev}][a{i}]acrossfade=d={xf}:c1=tri:c2=tri[{label}]")
            prev = label
            total += songs[i]["duration"] - xf
        chain_out = prev

    fade_out_start = max(0.0, total - args.fade_out)
    parts.append(
        f"[{chain_out}]afade=t=in:st=0:d={args.fade_in},"
        f"afade=t=out:st={fade_out_start:.3f}:d={args.fade_out},"
        # Normalize the assembled bed as one piece so the dynamic arc between
        # songs survives; per-song normalization would flatten it.
        f"loudnorm=I={args.target_lufs}:TP=-1.5:LRA=11[out]"
    )

    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd += ["-filter_complex", ";".join(parts), "-map", "[out]",
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(out_path)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit("ffmpeg failed building the music bed")

    actual = probe_duration(out_path)
    report = {
        "output": str(out_path),
        "duration": round(actual, 3),
        "target_lufs": args.target_lufs,
        "crossfade": xf,
        "songs": [{k: s[k] for k in ("label", "path", "start", "duration")} for s in songs],
        "seams": seams,
    }
    if args.report:
        rp = Path(args.report).expanduser()
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Music bed: {out_path}  ({actual:.1f}s, {len(songs)} song(s))")
    for seam in seams:
        print(f"  seam at {seam['at']:.2f}s: {seam['from']} -> {seam['to']} "
              f"({seam['crossfade']}s crossfade) - hide a hard visual cut here")
    print("Re-run analyze_music.py on this file to get the beat grid the edit will use.")


if __name__ == "__main__":
    main()
