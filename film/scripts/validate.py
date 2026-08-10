#!/usr/bin/env python3
"""Asset validation. Run this before every build.

Reads the storyboard, reports READY / MISSING / PLACEHOLDER per shot, checks
total runtime against the 150s target and the 155s hard ceiling, and generates
a correctly-timed placeholder for anything that has not arrived.
"""
import sys
from pathlib import Path

from filmlib import ROOT, load_storyboard, ffprobe_duration, load_photos
import placeholders

HANDLE = 0.5  # tail handle for shots followed by a section crossfade

GREEN, YELLOW, RED, DIM, RESET = (
    "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m")


def resolve(shot):
    """(path, status) - a real input, its declared fallback, or nothing."""
    for key in ("input", "fallback"):
        p = shot.get(key)
        if not p:
            continue
        full = ROOT / p
        if full.exists():
            return full, ("READY" if key == "input" else "FALLBACK")
    return None, "MISSING"


def needs_handle(shots, i):
    return i + 1 < len(shots) and shots[i]["section"] != shots[i + 1]["section"]


def main(make_placeholders=True):
    sb = load_storyboard()
    shots = sb["shots"]
    rows, total, missing, placeheld = [], 0.0, [], []

    print(f"\n  {sb['project']} — asset validation")
    print(f"  {'':-<96}")
    print(f"  {'ID':<5}{'SECTION':<15}{'IN':<8}{'DUR':>6}  {'STATUS':<12}SOURCE")
    print(f"  {'':-<96}")

    for i, shot in enumerate(shots):
        path, status = resolve(shot)
        dur = float(shot["dur"])
        render_dur = dur + (HANDLE if needs_handle(shots, i) else 0.0)

        if status == "MISSING":
            missing.append(shot["id"])
            if make_placeholders:
                placeholders.build(shot, render_dur)
                status = "PLACEHOLDER"
                placeheld.append(shot["id"])
                path = ROOT / "build" / "shots" / f"{shot['id']}.mp4"

        actual = ffprobe_duration(path) if path else None
        colour = {"READY": GREEN, "FALLBACK": YELLOW,
                  "PLACEHOLDER": YELLOW, "MISSING": RED}[status]
        mmss = f"{int(shot['start']) // 60}:{int(shot['start']) % 60:02d}"
        src = str(Path(path).relative_to(ROOT)) if path else (shot.get("input") or "-")
        flag = ""
        if actual and actual + 0.02 < render_dur:
            flag = f"  {RED}(short: {actual:.2f}s < {render_dur:.2f}s){RESET}"

        print(f"  {shot['id']:<5}{shot['section']:<15}{mmss:<8}{dur:>5.0f}s  "
              f"{colour}{status:<12}{RESET}{DIM}{src}{RESET}{flag}")
        rows.append((shot["id"], status))
        total += dur

    print(f"  {'':-<96}")
    ceiling = sb["hard_ceiling"]
    ok = total <= ceiling
    tcol = GREEN if ok else RED
    print(f"  timeline {tcol}{total:.1f}s{RESET} / target {sb['target_duration']}s"
          f" / ceiling {ceiling}s")

    ready = sum(1 for _, s in rows if s == "READY")
    print(f"  {ready}/{len(rows)} shots from real sources; "
          f"{len(placeheld)} placeholder(s)")

    _photo_report()

    if placeheld:
        print(f"\n  {YELLOW}placeholders:{RESET} " + ", ".join(placeheld))
    if not ok:
        print(f"\n  {RED}FAIL — timeline exceeds the {ceiling}s hard ceiling{RESET}")
        return 1
    return 0


def _photo_report():
    cfg = load_photos()
    pend = [v["name"] for v in cfg["institutions"].values()
            if not v.get("hero")]
    held = cfg.get("held_back", [])
    n = sum(1 for f in (ROOT / "assets/source/photos").glob("*.jpg"))
    print(f"  photographs: {n} on disk, "
          f"{len(cfg['institutions']) - len(pend)}/{len(cfg['institutions'])} "
          f"institutions cast")
    if pend:
        print(f"  {YELLOW}awaiting photographs:{RESET} " + ", ".join(pend))
    blockers = [h for h in held if h.get("severity") == "blocker"]
    if blockers:
        print(f"  {RED}held back ({len(blockers)}):{RESET} "
              + ", ".join(Path(h["file"]).name for h in blockers))


if __name__ == "__main__":
    sys.exit(main("--no-placeholders" not in sys.argv))
