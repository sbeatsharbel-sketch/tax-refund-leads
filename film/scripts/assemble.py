#!/usr/bin/env python3
"""Normalise, assemble and encode the film.

Hard cuts inside a section, 0.5s crossfades at section boundaries only.
Each section carries a 0.5s tail handle so the crossfades do not eat the
timeline - the assembled master lands on the storyboard's 150s exactly.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from filmlib import (ROOT, W, H, FPS, load_storyboard, ffprobe_duration, run,
                     INTERMEDIATE)

NORM = ROOT / "build" / "norm"
SHOTS = ROOT / "build" / "shots"
OUT = ROOT / "out"
XFADE = 0.5
MUSIC = ROOT / "assets" / "source" / "music"

SPEC = dict(width=W, height=H, pix_fmt="yuv420p")


def probe(path):
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,pix_fmt,r_frame_rate", "-of", "json", str(path)],
        capture_output=True, text=True)
    st = json.loads(res.stdout)["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    st["fps"] = float(num) / float(den)
    return st


def normalise(src, dst):
    """Uniform pass: 1920x1080, 24fps, yuv420p, BT.709, deinterlaced, no audio."""
    st = probe(src)
    conform = (st["width"] == SPEC["width"] and st["height"] == SPEC["height"]
               and st["pix_fmt"] == SPEC["pix_fmt"] and abs(st["fps"] - FPS) < 0.01)
    if conform:
        shutil.copy2(src, dst)
        return dst
    vf = (f"yadif=deint=interlaced,"
          f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x0A1628,"
          f"setsar=1,fps={FPS}")
    run(["ffmpeg", "-y", "-i", str(src), "-vf", vf, *INTERMEDIATE, str(dst)])
    return dst


def sections(shots):
    groups, cur = [], [shots[0]]
    for s in shots[1:]:
        if s["section"] == cur[-1]["section"]:
            cur.append(s)
        else:
            groups.append(cur)
            cur = [s]
    groups.append(cur)
    return groups


def concat_group(clips, out):
    if len(clips) == 1:
        shutil.copy2(clips[0], out)
        return out
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{Path(c).resolve()}'\n" for c in clips))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(out)])
    lst.unlink()
    return out


def pad_to(src, dst, want):
    """Clone the last frame out to `want` seconds so the crossfade has a handle."""
    have = ffprobe_duration(src)
    if have is not None and have >= want - 0.02:
        run(["ffmpeg", "-y", "-i", str(src), "-t", f"{want}", *INTERMEDIATE,
             str(dst)])
        return dst
    run(["ffmpeg", "-y", "-i", str(src),
         "-vf", f"tpad=stop_mode=clone:stop_duration={want - have + 0.1:.3f}",
         *INTERMEDIATE, "-t", f"{want}", str(dst)])
    return dst


def build_video():
    sb = load_storyboard()
    shots = sb["shots"]
    NORM.mkdir(parents=True, exist_ok=True)

    for s in shots:
        src = SHOTS / f"{s['id']}.mp4"
        if not src.exists():
            sys.exit(f"missing shot clip {src} - run validate.py first")
        normalise(src, NORM / f"{s['id']}.mp4")

    groups = sections(shots)
    parts, durs = [], []
    for gi, g in enumerate(groups):
        gdur = sum(float(s["dur"]) for s in g)
        raw = NORM / f"g{gi:02d}_raw.mp4"
        concat_group([NORM / f"{s['id']}.mp4" for s in g], raw)
        want = gdur + (XFADE if gi < len(groups) - 1 else 0.0)
        parts.append(pad_to(raw, NORM / f"g{gi:02d}.mp4", want))
        durs.append(gdur)
        print(f"  section {g[0]['section']:<15} {gdur:>5.1f}s  "
              f"({', '.join(s['id'] for s in g)})")

    cmd = ["ffmpeg", "-y"]
    for p in parts:
        cmd += ["-i", str(p)]

    steps, prev, offset = [], "0:v", 0.0
    for i in range(1, len(parts)):
        offset += durs[i - 1]
        tag = "[vout]" if i == len(parts) - 1 else f"[x{i}]"
        steps.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={XFADE}"
                     f":offset={offset:.3f}{tag}")
        prev = f"x{i}"

    master = ROOT / "build" / "master_silent.mp4"
    cmd += ["-filter_complex", ";".join(steps), "-map", "[vout]",
            *INTERMEDIATE, str(master)]
    run(cmd)
    print(f"  -> {master.relative_to(ROOT)}  {ffprobe_duration(master):.2f}s")
    return master


def find_music():
    if not MUSIC.exists():
        return None
    for ext in ("*.wav", "*.flac", "*.aiff", "*.mp3", "*.m4a"):
        hits = sorted(MUSIC.glob(ext))
        if hits:
            return hits[0]
    return None


def encode(master, dur):
    OUT.mkdir(parents=True, exist_ok=True)
    track = find_music()
    base = ["ffmpeg", "-y", "-i", str(master)]

    if track:
        # -16 LUFS, 3s fade at the tail. Lobby PA systems clip easily.
        base += ["-i", str(track)]
        af = (f"afade=t=out:st={dur - 3:.2f}:d=3,"
              f"loudnorm=I=-16:TP=-1.5:LRA=11")
        audio = ["-filter:a", af, "-c:a", "aac", "-b:a", "320k", "-ac", "2",
                 "-map", "0:v", "-map", "1:a", "-shortest"]
        print(f"  music: {track.name}")
    else:
        audio = ["-an"]
        print("  music: NONE SUPPLIED — encoding silent")

    hd = OUT / "beyond_the_image_2026_1080p.mp4"
    run([*base, *audio, "-c:v", "libx264", "-preset", "slow", "-crf", "18",
         "-pix_fmt", "yuv420p", "-r", str(FPS), "-colorspace", "bt709",
         "-color_primaries", "bt709", "-color_trc", "bt709",
         "-movflags", "+faststart", "-t", f"{dur}", str(hd)])
    print(f"  -> {hd.relative_to(ROOT)}")

    uhd = OUT / "beyond_the_image_2026_4k.mp4"
    run([*base, "-vf", "scale=3840:2160:flags=lanczos", *audio,
         "-c:v", "libx264", "-preset", "slow", "-crf", "18",
         "-pix_fmt", "yuv420p", "-r", str(FPS), "-colorspace", "bt709",
         "-color_primaries", "bt709", "-color_trc", "bt709",
         "-movflags", "+faststart", "-t", f"{dur}", str(uhd)])
    print(f"  -> {uhd.relative_to(ROOT)}")
    return hd


def main():
    print("assembly ->")
    master = build_video()
    dur = ffprobe_duration(master)
    sb = load_storyboard()
    if dur > sb["hard_ceiling"]:
        sys.exit(f"FAIL - {dur:.2f}s exceeds the {sb['hard_ceiling']}s ceiling")
    encode(master, dur)
    print(f"  runtime {dur:.2f}s (target {sb['target_duration']}s, "
          f"ceiling {sb['hard_ceiling']}s)")


if __name__ == "__main__":
    main()
