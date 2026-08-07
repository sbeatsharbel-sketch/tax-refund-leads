---
name: beat-sync
description: Analyze music for beats, downbeats, and energy sections, then build a multi-song soundtrack and a cut list locked to the rhythm. Use whenever cuts or transitions should land on the music - montages, tribute videos, trailers, reels, sizzle reels - or when several songs must be stitched into one bed with clean crossfades and consistent loudness.
---

# Beat Sync

A montage feels amateur when cuts land near the beat instead of on it. The human
ear detects a 40ms error, so cut points must be computed from the audio, never
eyeballed or spaced evenly by dividing total duration by clip count.

The work splits in two: analyze the music, then build the bed.

## 1. Analyze

```bash
python3 scripts/analyze_music.py song.mp3 --out work/beats.json
```

Produces tempo, every beat time, inferred downbeats, and energy sections.

**Cut on downbeats, not beats.** A cut on every beat at 120 BPM is a cut every
half second - exhausting past a few seconds. Downbeats (start of each bar) give
one cut per two seconds at the same tempo, which reads as deliberate. Use plain
beats only for deliberate rapid-fire bursts.

**`sections` is where the edit gets its shape.** Each section carries a
normalized `energy` value from 0 to 1. Map that onto content:

| Energy | Feel | Put here |
|---|---|---|
| < 0.3 | Intro, breakdown | Title cards, slow establishing shots, a single held portrait |
| 0.3 - 0.6 | Verse | Story beats, clips with dialogue or laughter, longer holds |
| > 0.6 | Chorus, drop | The best material. Fast cuts, group shots, the emotional payoff |

Save the strongest footage for the highest-energy section. That is the whole
trick behind montages that land.

**Check `confidence` before trusting the grid.** Below 0.5 the tempo estimate is
shaky - common with rubato ballads, live recordings, or tracks with a long
ambient intro. When confidence is low, say so and fall back to cutting on
`sections` boundaries and manual timings rather than pretending the grid is real.

## 2. Build the bed

```bash
python3 scripts/build_music_bed.py \
    --song intro.mp3   --start 0    --duration 22 \
    --song main.mp3    --start 47   --duration 95 \
    --song finale.mp3  --start 12   --duration 40 \
    --crossfade 2.5 --out work/music.wav --report work/music.json
```

Songs are trimmed, crossfaded, loudness-normalized as one piece, and written as
WAV so no generation loss accumulates before the final mux.

**Pick `--start` from the analysis, not from zero.** Song intros are usually dead
air for an edit. Run `analyze_music.py` on each song, find the first section with
energy above 0.5, and start there. For the finale, start where the track begins
its resolve.

**Normalize once, at the end.** `build_music_bed.py` applies EBU R128 loudnorm to
the assembled bed. Normalizing each song separately before joining defeats the
purpose - it flattens the intentional dynamic arc between quiet intro and loud
chorus.

**Crossfade across a downbeat when the tempos differ.** Two songs at different
BPM will never lock; the least jarring seam is a 2-3 second crossfade landing on
a downbeat of the incoming track. `build_music_bed.py --report` writes the exact
timeline position of every seam so the video edit can hide a hard visual cut
there - a picture change at the seam masks the audio change remarkably well.

## 3. Re-analyze the bed

The bed is a new piece of music with its own timeline. Analyze **it**, not the
original songs, to get the cut list the video will actually use:

```bash
python3 scripts/analyze_music.py work/music.wav --out work/beats.json
```

This is the step people skip, and it is why their cuts drift after the first song
change. Beat times from `main.mp3` mean nothing once that song sits 22 seconds
into the bed and starts 47 seconds in.

## Producing a cut list

```bash
python3 scripts/plan_cuts.py work/beats.json --clips 42 --out work/cuts.json
```

Distributes N clips across the bed on downbeat boundaries, giving each shot a
whole number of bars, allocating shorter holds in high-energy sections and longer
ones in low-energy sections. The output feeds straight into `video-montage`.

Two rules it enforces, worth knowing:

- **No shot shorter than 0.4s** unless explicitly requested. Below that a viewer registers a flash, not an image.
- **Transitions steal from the outgoing shot.** A 0.5s crossfade means each shot is on screen 0.5s less than its slot. `plan_cuts.py` accounts for this so the last cut still lands on the final downbeat instead of drifting early.

## Ducking under speech and laughter

When a clip carries audio worth hearing - someone laughing, a voice, a toast -
the music must drop under it or the moment is lost. `video-montage` handles the
mix, but the decision belongs here: mark those clips in the cut list with
`"duck": true` and the music drops 12dB for their duration with a 300ms ramp on
either side.
