#!/usr/bin/env python3
"""Turn a beat grid into a cut list: one slot per clip, every cut on a downbeat.

Shot length follows the music - short holds where the track is loud, longer ones
where it breathes. Transitions are centered on the downbeat so the midpoint of
each dissolve lands exactly on the beat.
"""

import argparse
import json
import sys
from pathlib import Path

MIN_SLOT = 0.4  # below this a shot reads as a flash, not an image


def energy_at(sections, t):
    for s in sections:
        if s["start"] <= t < s["end"]:
            return s["energy"]
    return sections[-1]["energy"] if sections else 0.5


def transition_for(energy, style, bar_duration):
    """Loud music wants fast cuts; quiet music wants slow dissolves."""
    if style == "hard":
        return 0.0
    if style == "slow":
        base = 0.9
    elif style == "fast":
        base = 0.25
    else:  # auto
        base = 0.9 - 0.7 * energy
    # Never let a transition eat more than a third of a bar.
    return round(min(base, bar_duration / 3.0), 3)


def allocate_bars(n_shots, total_bars, bar_times, sections):
    """Split total_bars across n_shots, favouring fewer bars where energy is high.

    Runs a few passes: allocate, look at where each shot actually landed, and
    reweight from the energy it sits on.
    """
    weights = [1.0] * n_shots
    counts = [1] * n_shots

    for _ in range(4):
        total_w = sum(weights)
        raw = [w / total_w * total_bars for w in weights]
        counts = [max(1, int(round(r))) for r in raw]

        # Force the allocation to sum exactly to total_bars.
        drift = total_bars - sum(counts)
        order = sorted(range(n_shots), key=lambda i: raw[i] - counts[i], reverse=(drift > 0))
        idx = 0
        while drift != 0 and order:
            i = order[idx % len(order)]
            if drift > 0:
                counts[i] += 1
                drift -= 1
            elif counts[i] > 1:
                counts[i] -= 1
                drift += 1
            idx += 1
            if idx > n_shots * 8:  # cannot shrink further; every shot is at one bar
                break

        # Reweight from the energy each shot now sits on.
        pos, new_weights = 0, []
        for c in counts:
            mid_bar = min(len(bar_times) - 1, pos + c // 2)
            e = energy_at(sections, bar_times[mid_bar])
            new_weights.append(1.0 / (0.45 + e))
            pos += c
        weights = new_weights

    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("beats", help="beats.json from analyze_music.py")
    ap.add_argument("--clips", type=int, required=True, help="How many shots to place")
    ap.add_argument("--out", default="work/cuts.json")
    ap.add_argument("--intro", type=float, default=0.0, help="Seconds reserved at the head for a title")
    ap.add_argument("--outro", type=float, default=0.0, help="Seconds reserved at the tail for an end card")
    ap.add_argument("--style", choices=["auto", "fast", "slow", "hard"], default="auto",
                    help="Transition feel (auto follows the music)")
    ap.add_argument("--grid", choices=["downbeat", "beat"], default="downbeat",
                    help="Cut on bar starts (default) or on every beat")
    args = ap.parse_args()

    data = json.loads(Path(args.beats).read_text(encoding="utf-8"))
    sections = data.get("sections") or []
    duration = data["duration"]
    bar_duration = data.get("bar_duration") or 2.0
    grid = data["downbeats"] if args.grid == "downbeat" else data["beats"]

    if data.get("confidence", 1.0) < 0.5:
        print(f"WARNING: beat confidence {data.get('confidence')} is low - the grid may not "
              f"match what a listener hears. Consider --grid beat or manual timings.",
              file=sys.stderr)

    window_start, window_end = args.intro, duration - args.outro
    if window_end - window_start < MIN_SLOT * args.clips:
        sys.exit(f"Only {window_end - window_start:.1f}s of music for {args.clips} clips. "
                 f"Use fewer clips or a longer bed.")

    marks = [t for t in grid if window_start <= t <= window_end]
    if not marks or marks[0] > window_start + 0.05:
        marks.insert(0, window_start)
    if marks[-1] < window_end - 0.05:
        marks.append(window_end)

    total_bars = len(marks) - 1
    n = args.clips
    if total_bars < n:
        print(f"NOTE: {total_bars} bar(s) available but {n} clips requested. "
              f"Placing {total_bars} clips instead - more would fall below "
              f"{MIN_SLOT}s each.", file=sys.stderr)
        n = max(1, total_bars)

    counts = allocate_bars(n, total_bars, marks, sections)

    # Walk the bar grid, turning bar counts into cut times.
    cut_times, pos = [marks[0]], 0
    for c in counts:
        pos = min(pos + c, total_bars)
        cut_times.append(marks[pos])

    shots = []
    for i in range(n):
        start, end = cut_times[i], cut_times[i + 1]
        energy = energy_at(sections, (start + end) / 2.0)
        t_in = 0.0 if i == 0 else shots[-1]["transition_out"]
        t_out = 0.0 if i == n - 1 else transition_for(energy, args.style, bar_duration)
        shots.append({
            "index": i,
            "start": round(start, 3),
            "end": round(end, 3),
            "slot": round(end - start, 3),
            "bars": counts[i],
            "energy": round(energy, 3),
            "intensity": "high" if energy > 0.6 else ("low" if energy < 0.3 else "mid"),
            "transition_in": round(t_in, 3),
            "transition_out": round(t_out, 3),
            # Segments must be rendered longer than their visible slot: each
            # transition is centered on the cut, so half of it spills either side.
            "render_duration": round((end - start) + t_in / 2.0 + t_out / 2.0, 3),
            "duck": False,
        })

    plan = {
        "source_beats": str(args.beats),
        "music_duration": duration,
        "bpm": data.get("bpm"),
        "bar_duration": bar_duration,
        "grid": args.grid,
        "style": args.style,
        "intro_reserved": args.intro,
        "outro_reserved": args.outro,
        "shot_count": n,
        "shots": shots,
    }

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    slots = [s["slot"] for s in shots]
    print(f"Planned {n} shots across {window_start:.1f}s - {window_end:.1f}s "
          f"at {data.get('bpm')} BPM")
    print(f"  slot length: min {min(slots):.2f}s / mean {sum(slots)/len(slots):.2f}s / "
          f"max {max(slots):.2f}s")
    for label in ("low", "mid", "high"):
        group = [s for s in shots if s["intensity"] == label]
        if group:
            avg = sum(s['slot'] for s in group) / len(group)
            print(f"  {label:>4} energy: {len(group):3d} shots, avg {avg:.2f}s")
    print(f"  last cut lands at {shots[-1]['end']:.2f}s "
          f"(music ends {duration:.2f}s)")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
