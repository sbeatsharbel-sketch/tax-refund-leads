#!/usr/bin/env python3
"""Original orchestral score for Beyond the Image 2026.

Composed and synthesised here rather than licensed. A licensed Artlist or
Epidemic track can replace it by dropping a WAV into assets/source/music/ -
assemble.py picks up whatever is there. Until then this is an original work,
so there is no licensing exposure for in-venue playback.

Tempo is chosen so that every section boundary in the brief's music arc lands
exactly on a bar line, and those bar lines coincide with storyboard cuts:

    96 BPM, 4/4, bar = 2.5s, 60 bars = 150.000s

    bar  0  (0:00)  solo strings, sparse, second voice enters
    bar 12  (0:30)  1s dropout, then hard downbeat - cello + low percussion
    bar 14  (0:35)  full orchestral drive under the procedure sections
    bar 36  (1:30)  drums fall away, warm restrained strings - team montage
    bar 46  (1:55)  building swell through collaboration and legacy
    bar 54  (2:15)  resolve, final chord, decay
"""
import sys
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve

from filmlib import ROOT

SR = 48000
BPM = 96.0
BEAT = 60.0 / BPM          # 0.625s
BAR = 4 * BEAT             # 2.5s
TOTAL_BARS = 60
DURATION = TOTAL_BARS * BAR

MUSIC = ROOT / "assets" / "source" / "music"

# --- pitch -----------------------------------------------------------------

NOTES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6,
         "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def midi(name):
    """'A4' -> 69"""
    i = 1 if len(name) > 2 and name[1] in "#" else 1
    pitch, octave = name[:i + (1 if name[1] == "#" else 0)], name[-1]
    return NOTES[pitch] + 12 * (int(octave) + 1)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def chord(root, quality="min", octave=3):
    """Triad as MIDI numbers."""
    r = NOTES[root] + 12 * (octave + 1)
    third = 3 if quality == "min" else 4
    return [r, r + third, r + 7]


# --- harmonic plan ---------------------------------------------------------
# (start_bar, bars, root, quality)
PROGRESSION = [
    # A - cold open: sparse, unresolved
    (0, 4, "D", "min"), (4, 4, "B", "maj"), (8, 2, "F", "maj"), (10, 2, "C", "maj"),
    # B - the drive
    (12, 2, "D", "min"), (14, 2, "D", "min"), (16, 2, "B", "maj"), (18, 2, "F", "maj"),
    (20, 2, "C", "maj"), (22, 2, "D", "min"), (24, 2, "B", "maj"), (26, 2, "F", "maj"),
    (28, 2, "C", "maj"), (30, 2, "D", "min"), (32, 2, "G", "min"), (34, 2, "A", "min"),
    # C - the team: warm, slower harmonic rhythm
    (36, 4, "B", "maj"), (40, 2, "F", "maj"), (42, 2, "G", "min"), (44, 2, "C", "maj"),
    # D - collaboration and legacy: building
    (46, 2, "B", "maj"), (48, 2, "C", "maj"), (50, 2, "D", "min"), (52, 2, "B", "maj"),
    # E - resolve. Picardy third: D minor lifts to D major.
    (54, 3, "F", "maj"), (57, 3, "D", "maj"),
]
# "B" here means B-flat; the film's key is D minor (D E F G A Bb C).
FLATTEN = {"B"}


def chord_at(bar):
    for start, length, root, qual in PROGRESSION:
        if start <= bar < start + length:
            r = root + "#" if False else root
            base = NOTES[r] - (1 if r in FLATTEN else 0)
            return base, qual
    base, qual = NOTES["D"], "maj"
    return base, qual


def triad(bar, octave=3):
    base, qual = chord_at(bar)
    r = base + 12 * (octave + 1)
    return [r, r + (3 if qual == "min" else 4), r + 7]


# --- synthesis -------------------------------------------------------------

def adsr(n, a, d, s, r, sr=SR):
    a, d, r = int(a * sr), int(d * sr), int(r * sr)
    a, d, r = max(1, a), max(1, d), max(1, r)
    sus = max(0, n - a - d - r)
    env = np.concatenate([
        np.linspace(0, 1, a),
        np.linspace(1, s, d),
        np.full(sus, s),
        np.linspace(s, 0, r),
    ])
    return np.resize(env, n) if len(env) != n else env


def string_voice(f, dur, amp=1.0, detune=0.006, voices=3, bright=1.0,
                 attack=0.28, vib=4.6, vib_depth=0.004):
    """Bowed-string-ish tone: detuned sawtooth partials with vibrato."""
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    out = np.zeros(n)
    n_harm = int(14 * bright)
    for v in range(voices):
        dt = (v - (voices - 1) / 2) * detune
        fv = f * (1 + dt)
        phase_vib = vib_depth * np.sin(2 * np.pi * vib * t + v)
        for h in range(1, n_harm + 1):
            if fv * h > SR / 2.2:
                break
            out += (1.0 / h ** 1.35) * np.sin(
                2 * np.pi * fv * h * t * (1 + phase_vib) + v * 1.7 + h * 0.3)
    out /= voices
    env = adsr(n, attack, 0.25, 0.78, min(0.6, dur * 0.45))
    return out * env * amp


def timpani(f, dur, amp=1.0):
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    pitch = f * (1 + 0.55 * np.exp(-t * 26))
    body = np.sin(2 * np.pi * np.cumsum(pitch) / SR)
    body += 0.4 * np.sin(2 * np.pi * np.cumsum(pitch * 1.5) / SR)
    noise = np.random.default_rng(3).standard_normal(n) * np.exp(-t * 55)
    env = np.exp(-t * 3.4)
    return (body * env + noise * 0.35 * env) * amp


def add(buf, sig, at):
    i = int(at * SR)
    j = min(len(buf), i + len(sig))
    if i >= len(buf) or j <= i:
        return
    buf[i:j] += sig[:j - i]


# --- reverb ----------------------------------------------------------------

def hall_ir(seconds=2.6, seed=11):
    """Synthetic concert-hall impulse: early reflections + decaying diffuse tail."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    tail = rng.standard_normal(n) * np.exp(-t * 2.6)
    # damp the top of the tail so it does not hiss
    tail = np.convolve(tail, np.ones(24) / 24, mode="same")
    ir = tail
    for delay, gain in ((0.011, 0.5), (0.019, 0.38), (0.031, 0.29),
                        (0.043, 0.22), (0.061, 0.16)):
        k = int(delay * SR)
        ir[k:k + 1] += gain
    ir[0] += 1.0
    return ir / np.abs(ir).max()


def reverb(mono, wet=0.34):
    ir = hall_ir()
    wetsig = fftconvolve(mono, ir)[:len(mono)]
    wetsig /= max(1e-9, np.abs(wetsig).max())
    return (1 - wet) * mono + wet * wetsig * np.abs(mono).max()


# --- the arrangement -------------------------------------------------------

# 8-bar theme, as (bar_offset, beat, scale_degree, beats_long).
# Degrees index the D natural minor scale.
SCALE = [62, 64, 65, 67, 69, 70, 72, 74, 76, 77, 79, 81]  # D4 up
THEME = [
    (0, 0, 4, 2), (0, 2, 5, 2),
    (1, 0, 4, 4),
    (2, 0, 2, 2), (2, 2, 3, 2),
    (3, 0, 4, 4),
    (4, 0, 7, 2), (4, 2, 6, 2),
    (5, 0, 5, 4),
    (6, 0, 4, 2), (6, 2, 3, 2),
    (7, 0, 2, 4),
]


def play_theme(buf, start_bar, amp, octave_shift=0, bright=1.0, attack=0.3):
    for bar_off, beat, degree, length in THEME:
        b = start_bar + bar_off
        if b >= TOTAL_BARS:
            continue
        at = b * BAR + beat * BEAT
        f = hz(SCALE[degree] + 12 * octave_shift)
        add(buf, string_voice(f, length * BEAT * 1.05, amp, bright=bright,
                              attack=attack, voices=2), at)


def build():
    n = int(DURATION * SR)
    pad = np.zeros(n)
    mel = np.zeros(n)
    low = np.zeros(n)
    perc = np.zeros(n)

    for bar in range(TOTAL_BARS):
        at = bar * BAR
        notes = triad(bar, octave=3)

        # --- sustained pad ------------------------------------------------
        if bar < 12:
            amp, voices = 0.16, 2          # sparse cold open
        elif bar < 14:
            amp, voices = 0.0, 2           # the dropout
        elif bar < 36:
            amp, voices = 0.30, 3          # drive
        elif bar < 46:
            amp, voices = 0.26, 3          # montage, warm
        elif bar < 54:
            amp, voices = 0.34, 3          # swell
        else:
            amp, voices = 0.30, 3          # resolve

        if bar == 53:
            amp *= 1.25                    # lift into the title card
        for i, m in enumerate(notes):
            if amp <= 0:
                continue
            dur = BAR * (1.02 if bar < 54 else 1.6)
            add(pad, string_voice(hz(m), dur, amp * (0.9 - 0.12 * i),
                                  voices=voices, bright=0.8,
                                  attack=0.5 if bar < 12 else 0.3), at)

        # --- cello / bass -------------------------------------------------
        root = notes[0] - 12
        if 12 <= bar < 36:
            # driving crotchets under the procedure sections
            for beat in range(4):
                add(low, string_voice(hz(root), BEAT * 0.92, 0.30,
                                      voices=2, bright=1.3, attack=0.03),
                    at + beat * BEAT)
        elif 36 <= bar < 46:
            add(low, string_voice(hz(root), BAR * 1.05, 0.20, voices=2,
                                  bright=0.7, attack=0.4), at)
        elif bar >= 46:
            add(low, string_voice(hz(root), BAR * (1.05 if bar < 54 else 1.8),
                                  0.26, voices=2, bright=0.9, attack=0.25), at)
        elif bar >= 8:
            add(low, string_voice(hz(root), BAR * 1.05, 0.13, voices=1,
                                  bright=0.6, attack=0.6), at)

        # --- low percussion ------------------------------------------------
        if 12 <= bar < 36:
            add(perc, timpani(hz(root - 12), 1.5, 0.55), at)
            if bar >= 14 and bar % 2 == 1:
                add(perc, timpani(hz(root - 12), 0.9, 0.30), at + 2 * BEAT)
        if bar in (46, 50, 52):
            add(perc, timpani(hz(root - 12), 1.8, 0.42), at)
        if bar == 53:
            for k in range(4):
                add(perc, timpani(hz(root - 12), 0.7, 0.30 + 0.12 * k),
                    at + k * BEAT)
        if bar == 54:
            add(perc, timpani(hz(hz_to_midi_root(notes) - 24), 3.0, 0.5), at)

    # --- melody ------------------------------------------------------------
    play_theme(mel, 4, 0.13, bright=0.9, attack=0.45)     # second voice enters
    play_theme(mel, 14, 0.17, bright=1.1, attack=0.16)    # over the drive
    play_theme(mel, 22, 0.15, octave_shift=1, bright=1.0, attack=0.2)
    play_theme(mel, 36, 0.12, bright=0.7, attack=0.5)     # montage, restrained
    play_theme(mel, 46, 0.19, octave_shift=1, bright=1.0, attack=0.25)

    mix = pad + mel + low * 0.9 + perc * 0.8
    mix = _shape(mix)
    mix = reverb(mix, wet=0.36)

    # gentle stereo spread: pad wider than bass
    left = mix + 0.12 * np.roll(pad, 260)
    right = mix + 0.12 * np.roll(pad, -260)
    stereo = np.stack([left, right], axis=1)

    peak = np.abs(stereo).max()
    stereo = np.tanh(stereo / max(peak, 1e-9) * 1.15) * 0.89
    return stereo


def hz_to_midi_root(notes):
    return notes[0]


def _shape(x):
    """Section-level dynamics: the 1s dropout at 0:30 and the final decay."""
    t = np.arange(len(x)) / SR
    g = np.ones_like(t)

    # 1s dropout before the hard downbeat at bar 12 (0:30)
    d0, d1 = 12 * BAR - 1.0, 12 * BAR
    m = (t >= d0) & (t < d1)
    g[m] *= np.linspace(1.0, 0.06, m.sum())

    # drums fall away into the montage - overall lift down at 1:30
    m = (t >= 36 * BAR - 0.6) & (t < 36 * BAR + 0.6)
    g[m] *= np.linspace(1.0, 0.82, m.sum())

    # final decay across the last 3 seconds
    m = t >= DURATION - 3.0
    g[m] *= np.linspace(1.0, 0.0, m.sum()) ** 1.4
    return x * g


def main():
    out = MUSIC / "beyond_the_image_score.wav"
    MUSIC.mkdir(parents=True, exist_ok=True)
    print(f"scoring -> {BPM:g} BPM, {TOTAL_BARS} bars, {DURATION:.3f}s")
    stereo = build()
    from scipy.io import wavfile
    wavfile.write(out, SR, (stereo * 32767).astype(np.int16))
    print(f"  -> {out.relative_to(ROOT)}  "
          f"({stereo.shape[0] / SR:.2f}s, {SR} Hz, stereo)")
    return out


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
