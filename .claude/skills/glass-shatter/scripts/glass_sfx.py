#!/usr/bin/env python3
"""Synthesize a glass-break sound effect.

Built from scratch rather than sampled, so there is no licensing question and
the length can be matched exactly to the shatter animation it accompanies.

Three layers, which is roughly what breaking glass actually is:
  1. impact  - the strike itself: a low thud plus a broadband crack
  2. shatter - the sheet failing: a dense burst of high-frequency fracture noise
  3. debris  - shards landing: sparse decaying tinkles, the long tail
"""

import argparse
from pathlib import Path

import numpy as np


def _envelope(n, attack, decay, sr):
    """Sharp attack, exponential decay - the shape of anything struck."""
    env = np.zeros(n)
    a = max(1, int(attack * sr))
    env[:a] = np.linspace(0.0, 1.0, a)
    rest = n - a
    if rest > 0:
        env[a:] = np.exp(-np.linspace(0.0, 1.0, rest) * (5.0 / max(decay, 1e-3)))
    return env


def impact_layer(sr, rng):
    """The strike: a low-frequency thud under a bright broadband crack."""
    dur = 0.35
    n = int(sr * dur)
    t = np.arange(n) / sr

    # Body: a pitched thud that drops fast, like the frame taking the hit.
    f = 190 * np.exp(-t * 22) + 55
    thud = np.sin(2 * np.pi * np.cumsum(f) / sr) * _envelope(n, 0.001, 0.30, sr) * 0.55

    # Crack: white noise, brightened, with an almost instantaneous attack.
    noise = rng.standard_normal(n)
    # One-pole high-pass so the crack sits above the thud instead of muddying it.
    hp = np.zeros(n)
    alpha = 0.82
    for i in range(1, n):
        hp[i] = alpha * (hp[i - 1] + noise[i] - noise[i - 1])
    crack = hp * _envelope(n, 0.0005, 0.10, sr) * 0.8

    return thud + crack


def shatter_layer(sr, rng, duration=0.75):
    """The sheet failing: dense high-frequency fracture noise, decaying."""
    n = int(sr * duration)
    noise = rng.standard_normal(n)

    # Band-limit upward by differencing twice - cheap, and the spectral tilt is
    # about right for fracturing glass.
    bright = np.diff(np.diff(noise, prepend=noise[0]), prepend=noise[0])
    bright /= np.max(np.abs(bright)) or 1.0

    # Amplitude falls away fast, but not as fast as the initial crack.
    env = np.exp(-np.linspace(0, 1, n) * 6.0)
    # Granular amplitude modulation gives it the "many pieces at once" texture.
    grain = 1.0 + 0.6 * rng.standard_normal(n) * np.exp(-np.linspace(0, 1, n) * 3)
    return bright * env * grain * 0.42


def debris_layer(sr, rng, duration=1.6, grains=150):
    """Shards landing: sparse pitched tinkles scattered over the tail."""
    n = int(sr * duration)
    out = np.zeros(n)

    # Cluster the grains early - most pieces land soon after the break - but
    # scale the spread with the requested tail so --tail actually lengthens it.
    spread = duration * 0.30
    for _ in range(grains):
        start = int(abs(rng.exponential(spread)) * sr)
        if start >= n - 100:
            continue
        length = int(rng.uniform(0.012, 0.075) * sr)
        length = min(length, n - start)
        t = np.arange(length) / sr

        freq = rng.uniform(1800, 9000)
        # A second inharmonic partial is what makes it read as glass
        # rather than as a bell.
        grain = (np.sin(2 * np.pi * freq * t)
                 + 0.5 * np.sin(2 * np.pi * freq * 2.7 * t))
        grain *= np.exp(-t * rng.uniform(60, 200))

        # Later grains are quieter: the energy is running out.
        amp = rng.uniform(0.05, 0.28) * np.exp(-(start / sr) * (1.6 / max(spread, 0.05)) * 0.5)
        out[start:start + length] += grain * amp

    return out


def make_glass_break(sr=48000, seed=None, tail=1.6):
    rng = np.random.default_rng(seed)

    impact = impact_layer(sr, rng)
    shatter = shatter_layer(sr, rng)
    debris = debris_layer(sr, rng, duration=tail)

    n = max(len(impact), len(shatter), len(debris))
    mono = np.zeros(n)
    mono[:len(impact)] += impact
    # The sheet starts failing a hair after the strike, not with it.
    delay = int(0.012 * sr)
    mono[delay:delay + len(shatter)] += shatter
    mono[:len(debris)] += debris

    peak = np.max(np.abs(mono)) or 1.0
    mono = mono / peak * 0.89

    # Widen to stereo by decorrelating the tail; the impact stays centered so it
    # still punches on a single speaker.
    tail_start = int(0.05 * sr)
    left, right = mono.copy(), mono.copy()
    jitter = int(0.0007 * sr)
    left[tail_start + jitter:] = mono[tail_start:-jitter] * 0.97
    right[tail_start:-jitter] = mono[tail_start + jitter:] * 0.97

    return np.stack([left, right], axis=1).astype(np.float32)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="work/glass.wav")
    ap.add_argument("--sr", type=int, default=48000)
    ap.add_argument("--seed", type=int, default=None,
                    help="Fix for a reproducible break; omit for a fresh one each run")
    ap.add_argument("--tail", type=float, default=1.6, help="Debris tail length in seconds")
    ap.add_argument("--gain", type=float, default=1.0)
    args = ap.parse_args()

    import soundfile as sf

    audio = make_glass_break(sr=args.sr, seed=args.seed, tail=args.tail)
    audio = np.clip(audio * args.gain, -1.0, 1.0)

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), audio, args.sr)
    print(f"Wrote {out}  ({len(audio) / args.sr:.2f}s, {args.sr} Hz stereo)")


if __name__ == "__main__":
    main()
