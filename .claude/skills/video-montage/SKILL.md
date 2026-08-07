---
name: video-montage
description: Build a finished montage video - tribute, farewell, wedding, birthday, recap, sizzle reel - from a pile of photos and clips plus music, with a designed opening, beat-locked cuts, and an end card. Use whenever someone wants photos and videos turned into one edited film rather than a plain slideshow. Orchestrates media-prep, beat-sync, and hebrew-titles into a single render.
---

# Video Montage

A montage is not a slideshow with music behind it. The difference is that every
cut lands on the music, shot length follows the song's energy, and the piece has
a deliberate opening, middle, and ending. This skill produces that.

## Requirements

```bash
ffmpeg -hide_banner -buildconf | grep -E "libx264|libass"   # both required
python3 -c "import librosa"                                  # beat detection
```

## The pipeline

Four stages, each writing a file the next one reads. Never skip straight to
rendering - the intermediate JSON is what makes the edit reviewable and
re-renderable without redoing the analysis.

```
media  ──▶ media-prep    ──▶ manifest.json
music  ──▶ beat-sync     ──▶ music.wav + beats.json + cuts.json
text   ──▶ hebrew-titles ──▶ intro.mp4 + outro.mp4
                             │
                             ▼
                        build_montage.py ──▶ montage.mp4
```

### 1. Prepare the media

```bash
python3 ../media-prep/scripts/prep_media.py ~/media --out work/manifest.json
```

Read the summary it prints. If it warns that capture times fell back to file
mtime, the chronological order is a guess - say so before building a timeline
that claims to tell a story in order.

### 2. Build the soundtrack, then analyze it

```bash
python3 ../beat-sync/scripts/build_music_bed.py \
    --song a.mp3 --start 30 --duration 40 \
    --song b.mp3 --start 12 --duration 70 \
    --crossfade 2.5 --out work/music.wav --report work/music.json

python3 ../beat-sync/scripts/analyze_music.py work/music.wav --out work/beats.json
```

Analyze the **bed**, not the source songs. Beat times from a song mean nothing
once it has been trimmed and moved.

### 3. Plan the cuts

```bash
python3 ../beat-sync/scripts/plan_cuts.py work/beats.json \
    --clips 45 --intro 7 --outro 9 --out work/cuts.json
```

`--intro` and `--outro` reserve time at each end for title cards. The body fills
what is left, on downbeats.

**How many clips?** Divide the body length by the average shot you want. Roughly
2.5-3.5s per shot for an emotional piece, 1-1.5s for a high-energy one. For a
3-minute montage that is about 45-60 shots. More than that and no individual
moment registers.

### 4. Make the titles

```bash
python3 ../hebrew-titles/scripts/make_titles.py --spec intro.json \
    --render work/intro.mp4 --background gradient --duration 7
```

### 5. Render

```bash
python3 scripts/build_montage.py \
    --manifest work/manifest.json \
    --cuts work/cuts.json \
    --music work/music.wav \
    --intro work/intro.mp4 --outro work/outro.mp4 \
    --out out/montage.mp4
```

## Editing decisions that matter more than the tooling

**Order the material deliberately.** Chronological is the safe default and works
for anything covering a span of time. The alternative that works better for a
tribute is thematic grouping - all the work moments, then all the funny ones,
then the goodbyes - because it builds instead of meandering.

**Put the best footage in the loudest section.** Read `sections` from
`beats.json`, find the highest-energy stretch, and hand-assign the strongest
group shots there. This single decision separates a montage that lands from one
that is merely competent.

**Vary the shot rhythm.** `plan_cuts.py` already lengthens shots in quiet
sections, but if every shot is within half a second of the others the piece feels
mechanical. A single long hold - four or five seconds on one photo, in a quiet
section - resets the viewer's attention and makes the next fast section hit
harder.

**Let clips with real audio breathe.** Laughter, a voice, a toast - these are the
moments people replay. Mark those shots `"duck": true` in `cuts.json` and give
them a longer slot than the beat grid suggests. Music under a laugh at full
volume wastes the laugh.

**End on a still, not a cut.** The final shot before the end card should be a
photograph held long enough to read, fading rather than cutting. Ending on motion
feels like the file was truncated.

## Structuring a farewell or tribute piece

A shape that reliably works, scaled to whatever the music gives you:

| Section | Share | Content |
|---|---|---|
| Opening title | ~7s | Name and dates over a quiet intro. Resolve the animation on the first downbeat |
| The beginning | ~20% | Earliest material. Slower cuts, wider shots, establishing who and where |
| The everyday | ~35% | The bulk. Working moments, routine, the texture of the time together |
| The peak | ~25% | Highest-energy music. Group shots, laughing, celebrations. Fastest cuts |
| The wind-down | ~15% | Music softens. Portraits, quiet moments, one long hold |
| End card | ~9s | The message. Held still, fading to black over the music's last bars |

The peak must sit on the loudest part of the music. If it does not, the edit
fights the song and loses.

## Canvas and delivery

Default is 1920x1080 at 30fps - correct for a projector, TV, or laptop, which is
where a farewell video actually gets watched. Use `--width 1080 --height 1920`
only when the piece is destined for phones and stories.

Mixed portrait and landscape source is handled automatically: each shot sits on a
blurred, darkened copy of itself filling the canvas. This looks intentional and
avoids both black bars and the cropping-off-people's-heads problem. Tune with
`--blur`; below about 15 the background competes with the subject.

## When something looks wrong

**Cuts feel slightly off the beat.** Check `confidence` in `beats.json`. Below
0.5 the grid is unreliable - fall back to `--grid beat` or place cuts by hand
from the section boundaries.

**A clip appears sideways.** The manifest's `width`/`height` are rotation-
corrected; something bypassed them. Re-run `prep_media.py`.

**Output duration drifts from the plan.** Source clips are shorter than their
slots, so their final frames are being held. Either shorten those slots or pick
longer source clips.

**Transitions look mushy.** Too long for the tempo. At 120+ BPM keep them under
0.4s; the `auto` style already scales them by energy, but `--transition-style
hard` gives straight cuts, which is often the stronger choice in a fast section.

**The render is slow.** Segment rendering dominates. Use `--preset veryfast
--seg-crf 20` while iterating on structure, then re-render once with the
defaults for the version people will actually watch.
