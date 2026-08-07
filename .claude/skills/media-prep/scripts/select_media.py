#!/usr/bin/env python3
"""Filter a media manifest down to the subset worth putting on a timeline."""

import argparse
import json
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest", help="Manifest from prep_media.py")
    ap.add_argument("--out", help="Write filtered manifest here (default: stdout summary only)")
    ap.add_argument("--kind", choices=["image", "video"], help="Keep only this kind")
    ap.add_argument("--orientation", choices=["portrait", "landscape", "square"])
    ap.add_argument("--min-duration", type=float, help="Videos shorter than this are dropped")
    ap.add_argument("--max-duration", type=float, help="Videos longer than this are dropped")
    ap.add_argument("--with-audio", action="store_true", help="Keep only clips that have sound")
    ap.add_argument("--min-pixels", type=int, default=0, help="Drop items whose long edge is below this")
    ap.add_argument("--exclude-problems", nargs="*", default=[],
                    help="Drop items carrying any of these problem flags")
    ap.add_argument("--limit", type=int, help="Keep at most N items, evenly spread across the timeline")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    items = manifest.get("items", [])
    kept = []

    for item in items:
        if args.kind and item.get("kind") != args.kind:
            continue
        if args.orientation and item.get("orientation") != args.orientation:
            continue
        if args.with_audio and not item.get("has_audio"):
            continue
        if args.min_pixels and max(item.get("width") or 0, item.get("height") or 0) < args.min_pixels:
            continue
        if args.exclude_problems and (set(args.exclude_problems) & set(item.get("problems") or [])):
            continue
        duration = item.get("duration")
        if item.get("kind") == "video" and duration is not None:
            if args.min_duration is not None and duration < args.min_duration:
                continue
            if args.max_duration is not None and duration > args.max_duration:
                continue
        kept.append(item)

    # Thin evenly rather than truncating, so the selection still spans the whole
    # period the footage covers instead of stopping partway through the story.
    if args.limit and len(kept) > args.limit:
        step = len(kept) / args.limit
        kept = [kept[int(i * step)] for i in range(args.limit)]

    out = dict(manifest)
    out["items"] = kept
    out["counts"] = dict(manifest.get("counts", {}))
    out["counts"]["usable"] = len(kept)
    out["counts"]["images"] = sum(1 for e in kept if e["kind"] == "image")
    out["counts"]["videos"] = sum(1 for e in kept if e["kind"] == "video")
    out["filtered_from"] = str(args.manifest)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        print()

    total_video = sum(e.get("duration") or 0 for e in kept if e["kind"] == "video")
    print(f"Selected {len(kept)}/{len(items)} items "
          f"({out['counts']['images']} images, {out['counts']['videos']} videos, "
          f"{total_video:.1f}s of source video)", file=sys.stderr)


if __name__ == "__main__":
    main()
