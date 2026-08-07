# Video editing skills

Four skills that compose into one pipeline for turning a folder of phone media
plus music into an edited film.

| Skill | Does |
|---|---|
| `media-prep` | Probes messy WhatsApp/camera-roll media into a clean manifest. Rotation, HEIC, VFR, capture-time ordering |
| `beat-sync` | Beat/downbeat/energy analysis, multi-song soundtrack assembly, and a beat-locked cut list |
| `hebrew-titles` | Animated titles with correct RTL shaping, via libass. Intro cards, end cards, lower thirds |
| `glass-shatter` | Breaks the frame like a pane of glass to reveal the next scene, with a synthesized break sound |
| `video-montage` | Orchestrates the above into a finished render with beat-aligned transitions |

## Setup

```bash
# ffmpeg must include libx264, libass, libfribidi and libharfbuzz
apt-get install -y ffmpeg fonts-noto-core
python3 -m pip install librosa soundfile numpy pillow pillow-heif

# verify
ffmpeg -hide_banner -buildconf | grep -E "libx264|libass|libfribidi|libharfbuzz"
fc-list :lang=he family | sort -u
```

Without `libass`/`libfribidi`, Hebrew renders backwards. Without a Hebrew-capable
font, it renders as empty boxes. Check both before a long render.

## Pipeline

```bash
python3 media-prep/scripts/prep_media.py ~/media --out work/manifest.json

python3 beat-sync/scripts/build_music_bed.py \
    --song a.mp3 --start 30 --duration 40 \
    --song b.mp3 --start 12 --duration 80 \
    --out work/music.wav --report work/music.json

python3 beat-sync/scripts/analyze_music.py work/music.wav --out work/beats.json
python3 beat-sync/scripts/plan_cuts.py work/beats.json --clips 45 \
    --intro 7 --outro 9 --out work/cuts.json

python3 hebrew-titles/scripts/make_titles.py --spec intro.json \
    --render work/intro.mp4 --background gradient
python3 hebrew-titles/scripts/make_titles.py --spec outro.json \
    --render work/outro.mp4 --background gradient

python3 video-montage/scripts/build_montage.py \
    --manifest work/manifest.json --cuts work/cuts.json --music work/music.wav \
    --intro work/intro.mp4 --outro work/outro.mp4 --out out/montage.mp4
```

Every stage writes JSON the next one reads, so the edit can be adjusted and
re-rendered without redoing the analysis.

## How the sync stays exact

The timeline is laid out in **whole frames**, and it is the cut *boundaries* that
get quantized, not the individual shot durations. Rounding each duration on its
own lets a half-frame error per shot accumulate until the last cut sits visibly
late; rounding boundaries keeps every cut within half a frame of its downbeat no
matter how many shots there are.

Measured on a 17-segment, 61.5s test render at 30fps: maximum cut error 16.3ms
(0.49 frames), mean 6.7ms, and total output length matching the music bed to the
frame.

Transitions are centered on the cut, so each segment is rendered slightly longer
than its visible slot - half of each adjoining transition spills past the
boundary. `build_montage.py` derives those lengths itself; do not hand-edit
`render_duration` in `cuts.json`.
