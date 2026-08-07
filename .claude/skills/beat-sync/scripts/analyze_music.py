#!/usr/bin/env python3
"""Extract a beat grid, downbeats, and energy sections from an audio file."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np


def load_audio(path, sr=22050):
    import librosa
    y, sr = librosa.load(str(path), sr=sr, mono=True)
    if y.size == 0:
        sys.exit(f"No audio decoded from {path}")
    return y, sr


def track_beats(y, sr):
    """Return (bpm, beat_times, onset_envelope, confidence)."""
    import librosa
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, aggregate=np.median)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, trim=False)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])

    # Confidence: a steady grid has near-identical inter-beat intervals, and real
    # beats sit on onset peaks. Combine regularity with onset agreement.
    confidence = 0.0
    if len(beat_times) > 3:
        intervals = np.diff(beat_times)
        regularity = 1.0 - min(1.0, float(np.std(intervals) / max(np.mean(intervals), 1e-6)) * 3.0)

        frames = librosa.time_to_frames(beat_times, sr=sr)
        frames = frames[(frames >= 0) & (frames < len(onset_env))]
        if len(frames) and onset_env.max() > 0:
            norm = onset_env / onset_env.max()
            agreement = float(np.mean(norm[frames])) / max(float(np.mean(norm)), 1e-6)
            agreement = min(1.0, agreement / 2.0)
        else:
            agreement = 0.0
        confidence = round(max(0.0, min(1.0, 0.6 * regularity + 0.4 * agreement)), 3)

    return tempo, beat_times, onset_env, confidence


def find_downbeats(beat_times, onset_env, sr, meter=4):
    """Infer bar starts by choosing the phase whose beats carry the most onset energy."""
    import librosa
    if len(beat_times) < meter:
        return beat_times.tolist()

    frames = librosa.time_to_frames(beat_times, sr=sr)
    frames = np.clip(frames, 0, len(onset_env) - 1)
    strengths = onset_env[frames]

    # Try each of the `meter` possible bar phases and keep the strongest.
    best_phase, best_score = 0, -np.inf
    for phase in range(meter):
        score = float(np.mean(strengths[phase::meter]))
        if score > best_score:
            best_phase, best_score = phase, score

    return [float(t) for t in beat_times[best_phase::meter]]


def find_sections(y, sr, duration, target_sections=8):
    """Segment the track structurally and score each segment's energy 0..1."""
    import librosa

    hop = 512
    mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=hop, n_mfcc=13)
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]

    n_frames = mfcc.shape[1]
    n_seg = int(max(2, min(target_sections, n_frames // 20)))

    try:
        # Structural boundaries from timbre similarity - catches verse/chorus
        # changes that pure loudness misses.
        bounds = librosa.segment.agglomerative(mfcc, n_seg)
        bound_times = librosa.frames_to_time(bounds, sr=sr, hop_length=hop)
    except Exception:
        bound_times = np.linspace(0, duration, n_seg + 1)[:-1]

    bound_times = np.unique(np.concatenate([[0.0], np.asarray(bound_times, dtype=float)]))
    bound_times = bound_times[bound_times < duration - 1.0]
    edges = np.append(bound_times, duration)

    rms_max = float(rms.max()) or 1.0
    sections = []
    for i in range(len(edges) - 1):
        start, end = float(edges[i]), float(edges[i + 1])
        if end - start < 1.0:
            continue
        f0 = int(librosa.time_to_frames(start, sr=sr, hop_length=hop))
        f1 = int(librosa.time_to_frames(end, sr=sr, hop_length=hop))
        f0, f1 = max(0, f0), min(len(rms), max(f0 + 1, f1))
        energy = float(np.mean(rms[f0:f1]) / rms_max)
        sections.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3),
            "energy": round(min(1.0, energy), 3),
        })

    for s in sections:
        s["intensity"] = "high" if s["energy"] > 0.6 else ("low" if s["energy"] < 0.3 else "mid")
    return sections


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("audio", help="Audio file to analyze")
    ap.add_argument("--out", default="work/beats.json")
    ap.add_argument("--meter", type=int, default=4, help="Beats per bar (default 4)")
    ap.add_argument("--sections", type=int, default=8, help="Target number of structural sections")
    args = ap.parse_args()

    path = Path(args.audio).expanduser()
    if not path.exists():
        sys.exit(f"No such file: {path}")

    y, sr = load_audio(path)
    duration = float(len(y)) / sr

    tempo, beat_times, onset_env, confidence = track_beats(y, sr)
    downbeats = find_downbeats(beat_times, onset_env, sr, meter=args.meter)
    sections = find_sections(y, sr, duration, target_sections=args.sections)

    result = {
        "source": str(path),
        "duration": round(duration, 3),
        "bpm": round(tempo, 2),
        "meter": args.meter,
        "confidence": confidence,
        "beat_count": len(beat_times),
        "beats": [round(float(t), 3) for t in beat_times],
        "downbeats": [round(t, 3) for t in downbeats],
        "bar_duration": round(args.meter * 60.0 / tempo, 3) if tempo > 0 else None,
        "sections": sections,
    }

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"Analyzed {path.name}: {duration:.1f}s @ {tempo:.1f} BPM")
    print(f"  beats     : {len(beat_times)}   downbeats: {len(downbeats)}")
    print(f"  confidence: {confidence}" + ("   LOW - grid unreliable, prefer section cuts"
                                           if confidence < 0.5 else ""))
    print(f"  sections  : {len(sections)}")
    for s in sections:
        print(f"    {s['start']:7.2f}s - {s['end']:7.2f}s  "
              f"energy {s['energy']:.2f}  {s['intensity']}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
