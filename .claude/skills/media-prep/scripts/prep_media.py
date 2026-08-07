#!/usr/bin/env python3
"""Probe a folder of mixed phone/WhatsApp media into a clean editing manifest.

Resolves rotation metadata, converts HEIC, detects variable frame rate, and
recovers capture time so a montage can be ordered chronologically.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".3gp", ".avi", ".mkv", ".webm", ".mpg", ".mpeg"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
HEIC_EXT = {".heic", ".heif"}

# WhatsApp: IMG-20240517-WA0003.jpg / VID-20240517-WA0012.mp4
# Camera:   20240517_143022.jpg / IMG_20240517_143022.jpg / PXL_20240517_143022123.mp4
FILENAME_DATE_PATTERNS = [
    re.compile(r"(?P<Y>\d{4})(?P<M>\d{2})(?P<D>\d{2})[_\-T](?P<h>\d{2})(?P<m>\d{2})(?P<s>\d{2})"),
    re.compile(r"(?P<Y>\d{4})-(?P<M>\d{2})-(?P<D>\d{2})[ _](?P<h>\d{2})[.\-:](?P<m>\d{2})[.\-:](?P<s>\d{2})"),
    re.compile(r"(?P<Y>\d{4})(?P<M>\d{2})(?P<D>\d{2})"),
]


def ffprobe(path):
    """Return parsed ffprobe JSON, or None if the file is unreadable."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=120,
        )
        if out.returncode != 0:
            return None
        return json.loads(out.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None


def stream_rotation(stream):
    """Extract rotation in degrees from either the legacy tag or a display matrix."""
    tags = stream.get("tags") or {}
    if "rotate" in tags:
        try:
            return int(float(tags["rotate"])) % 360
        except ValueError:
            pass
    for sd in stream.get("side_data_list") or []:
        if "rotation" in sd:
            try:
                # ffmpeg reports the matrix rotation as the negative of the
                # display rotation, so -90 in side data means "display at 90".
                return int(-float(sd["rotation"])) % 360
            except ValueError:
                pass
    return 0


def parse_fps(rate):
    """Turn ffprobe's 'num/den' rational into a float."""
    if not rate or rate == "0/0":
        return None
    try:
        num, den = rate.split("/")
        den = float(den)
        return round(float(num) / den, 3) if den else None
    except (ValueError, ZeroDivisionError):
        return None


def parse_iso(value):
    if not value:
        return None
    value = value.strip().replace("Z", "+00:00")
    for candidate in (value, value.split(".")[0]):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    # Exif style: "2024:05:17 14:30:22"
    try:
        return datetime.strptime(value[:19], "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def capture_time_from_metadata(probe):
    """Pull a creation timestamp out of container or stream tags."""
    if not probe:
        return None
    sources = [(probe.get("format") or {}).get("tags") or {}]
    sources += [(s.get("tags") or {}) for s in probe.get("streams") or []]
    for tags in sources:
        lowered = {k.lower(): v for k, v in tags.items()}
        for key in ("creation_time", "date", "datetimeoriginal", "com.apple.quicktime.creationdate"):
            dt = parse_iso(lowered.get(key))
            if dt:
                return dt
    return None


def capture_time_from_exif(path):
    """Read EXIF DateTimeOriginal from a still image."""
    try:
        from PIL import Image, ExifTags
    except ImportError:
        return None
    tag_ids = {v: k for k, v in ExifTags.TAGS.items()}
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            for name in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
                tid = tag_ids.get(name)
                if tid is not None and exif.get(tid):
                    dt = parse_iso(str(exif.get(tid)))
                    if dt:
                        return dt
    except Exception:
        return None
    return None


def capture_time_from_name(path):
    for pattern in FILENAME_DATE_PATTERNS:
        m = pattern.search(path.name)
        if not m:
            continue
        g = m.groupdict()
        try:
            return datetime(
                int(g["Y"]), int(g["M"]), int(g["D"]),
                int(g.get("h") or 0), int(g.get("m") or 0), int(g.get("s") or 0),
                tzinfo=timezone.utc,
            )
        except ValueError:
            continue
    return None


def resolve_capture_time(path, probe, kind):
    """Best-effort capture time, reporting which source produced it."""
    dt = capture_time_from_metadata(probe)
    if dt:
        return dt, "metadata"
    if kind == "image":
        dt = capture_time_from_exif(path)
        if dt:
            return dt, "metadata"
    dt = capture_time_from_name(path)
    if dt:
        return dt, "filename"
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc), "mtime"


def convert_heic(src, outdir):
    """Convert HEIC/HEIF to PNG so ffmpeg can read it. Returns the new path."""
    try:
        import pillow_heif
        from PIL import Image
        pillow_heif.register_heif_opener()
    except ImportError:
        return None
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / (src.stem + ".png")
    try:
        with Image.open(src) as img:
            img = img.convert("RGB")
            img.save(dest, "PNG")
        return dest
    except Exception:
        return None


def orientation_of(width, height):
    if width == height:
        return "square"
    return "landscape" if width > height else "portrait"


def describe(path, converted_dir):
    """Build one manifest entry for a media file."""
    ext = path.suffix.lower()
    source_path = path

    if ext in HEIC_EXT:
        kind = "image"
        converted = convert_heic(path, converted_dir)
        if converted is None:
            return {
                "path": str(path), "source_path": str(path), "kind": "image",
                "problems": ["unreadable"], "note": "HEIC conversion failed",
            }
        path = converted
        ext = ".png"
    elif ext in VIDEO_EXT:
        kind = "video"
    elif ext in IMAGE_EXT:
        kind = "image"
    else:
        return None

    probe = ffprobe(path)
    if probe is None:
        return {
            "path": str(path), "source_path": str(source_path), "kind": kind,
            "problems": ["unreadable"],
        }

    streams = probe.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    problems = []

    if video is None:
        return {
            "path": str(path), "source_path": str(source_path), "kind": kind,
            "problems": ["no_video_stream"],
        }

    raw_w = int(video.get("width") or 0)
    raw_h = int(video.get("height") or 0)
    rotation = stream_rotation(video)
    # A quarter-turn swaps the displayed axes.
    width, height = (raw_h, raw_w) if rotation in (90, 270) else (raw_w, raw_h)

    duration = None
    if kind == "video":
        for source in (video.get("duration"), (probe.get("format") or {}).get("duration")):
            try:
                duration = round(float(source), 3)
                break
            except (TypeError, ValueError):
                continue

    avg_fps = parse_fps(video.get("avg_frame_rate")) if kind == "video" else None
    r_fps = parse_fps(video.get("r_frame_rate")) if kind == "video" else None
    # r_frame_rate is the smallest rate that can express every timestamp; when it
    # far exceeds the average rate, the source is variable frame rate.
    vfr = bool(avg_fps and r_fps and r_fps > avg_fps * 1.15)

    if vfr:
        problems.append("vfr")
    if max(width, height) < 640:
        problems.append("tiny")
    if kind == "video" and duration is not None and duration < 0.5:
        problems.append("very_short")

    captured_at, captured_src = resolve_capture_time(source_path, probe, kind)

    return {
        "path": str(path),
        "source_path": str(source_path),
        "filename": source_path.name,
        "kind": kind,
        "width": width,
        "height": height,
        "raw_width": raw_w,
        "raw_height": raw_h,
        "rotation": rotation,
        "orientation": orientation_of(width, height),
        "duration": duration,
        "fps": avg_fps,
        "vfr": vfr,
        "has_audio": audio is not None,
        "codec": video.get("codec_name"),
        "captured_at": captured_at.isoformat(),
        "captured_at_source": captured_src,
        "size_bytes": source_path.stat().st_size,
        "problems": problems,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_dir", help="Folder of photos and videos")
    ap.add_argument("--out", default="work/manifest.json", help="Manifest output path")
    ap.add_argument("--recursive", action="store_true", help="Descend into subfolders")
    args = ap.parse_args()

    root = Path(args.input_dir).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")

    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    converted_dir = out_path.parent / "converted"

    walker = root.rglob("*") if args.recursive else root.glob("*")
    files = sorted(p for p in walker if p.is_file())

    entries, skipped = [], 0
    for path in files:
        try:
            entry = describe(path, converted_dir)
        except Exception as exc:  # one bad file must not sink the batch
            entry = {
                "path": str(path), "source_path": str(path), "kind": "unknown",
                "problems": ["unreadable"], "note": str(exc),
            }
        if entry is None:
            skipped += 1
            continue
        entries.append(entry)

    usable = [e for e in entries if not ({"unreadable", "no_video_stream"} & set(e.get("problems", [])))]
    usable.sort(key=lambda e: e.get("captured_at") or "")
    unusable = [e for e in entries if e not in usable]

    guessed = sum(1 for e in usable if e.get("captured_at_source") == "mtime")
    manifest = {
        "root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "total_files": len(files),
            "skipped_non_media": skipped,
            "usable": len(usable),
            "unusable": len(unusable),
            "images": sum(1 for e in usable if e["kind"] == "image"),
            "videos": sum(1 for e in usable if e["kind"] == "video"),
            "with_audio": sum(1 for e in usable if e.get("has_audio")),
            "capture_time_guessed": guessed,
        },
        "chronology_reliable": guessed <= len(usable) * 0.25 if usable else False,
        "items": usable,
        "excluded": unusable,
    }

    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    c = manifest["counts"]
    print(f"Manifest: {out_path}")
    print(f"  usable      : {c['usable']}  ({c['images']} images, {c['videos']} videos)")
    print(f"  with audio  : {c['with_audio']}")
    print(f"  excluded    : {c['unusable']}")
    if not manifest["chronology_reliable"] and usable:
        print(f"  WARNING: {guessed}/{len(usable)} items have no real capture time "
              f"(fell back to file mtime) - chronological order is unreliable.")
    flagged = [e for e in usable if e.get("problems")]
    if flagged:
        print(f"  flagged     : {len(flagged)} item(s) with problems")
        for e in flagged[:10]:
            print(f"    - {e['filename']}: {', '.join(e['problems'])}")


if __name__ == "__main__":
    main()
