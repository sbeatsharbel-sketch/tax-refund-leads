# Beyond the Image 2026 — opening film

2:30 conference opening film. Plays once, on a large screen in the Galilee
Medical Center lobby, Nahariya, 9 September 2026. Not published online.

## Build

```bash
./build.sh              # rebuild everything (draft resampling, fast)
./build.sh final        # delivery quality
./build.sh validate     # asset report only, no encode

FILM_ANNOTATE=1 ./build.sh    # production cut: shot IDs, paths, source kinds
```

`FILM_ANNOTATE` is off by default. Placeholder cards carry only the brand
particle field and the shot's real caption, so the rough cut can be shown to
people. Turn it on when you need to see which file each gap is waiting for.

Every shot duration lives in `storyboard.json` and nowhere else — `montage.py`
and `titlecards.py` read theirs from it. Retiming the film is one number per
shot; the brief's original 150s cut was 6,7,8,9,6,10,8,6,10,12,8,25,12,8,10,5.

Requires `ffmpeg`, `rsvg-convert`, `poppler-utils`, and Python with
`pillow` + `numpy`. Fonts: Noto Serif Display, Inter.

## Current state

| | |
|---|---|
| Runtime | **142.00s** — 2:22 (ceiling 155s) |
| Shots from real sources | 3 / 16 — S12, S15, S16 |
| Placeholders | 13 — brand particle field, real caption at real timing |
| Audio | **silent** — awaiting a licensed track in `assets/source/music/` |
| Review | `docs/REVIEW.md` — 4 blockers and 9 majors found, all fixed |

The rough cut is full length and screenable now. Placeholders carry each shot's
real captions at their real timings, so pacing can be judged before any of the
generated or filmed material exists.

## What is real

- **S15 title card** — rebuilt from scratch. The supplied clip read
  "BEYOND THE THE IMAGE 2026"; this uses the client's own vector lockup lifted
  from the conference programme PDF, so the wording is correct by construction.
- **S16 credit** — under the genuine Galilee Medical Center mark, same source.
- **S12 team montage** — 52s. **All 23 supplied photographs**, grouped by
  institution in the client-specified order, 2.14s each, one caption held
  across each institution's group. Nahariya and Rambam are skipped until their
  photographs arrive, at which point the montage re-times itself.

## Layout

```
storyboard.json            single source of truth: 16 shots, timings, text
photos.json                S12 casting, montage order, held-back photos
build.sh                   one-command rebuild
scripts/
  filmlib.py               shared helpers, palette, encode settings
  extract_brand.py         pulls genuine vectors out of the client PDF
  textgen.py               all on-screen text -> RGBA PNGs
  particles.py             particle-network field — every shot sits on it
  titlecards.py            S15 (blocker) and S16
  montage.py               S12 team montage
  logo_wall.py             S13 partner wall, optical-ink-area normalised
  placeholders.py          correctly-timed stand-ins for missing shots
  validate.py              READY / MISSING / PLACEHOLDER report
  assemble.py              normalise, concat, crossfade, encode
  qc.py                    contact sheet, one frame every 2s
assets/source/photos/      team photographs, named by institution
assets/source/logos/       partner marks + SOURCES.md provenance log
assets/source/brand/       conference lockup and subtitle vectors
assets/source/music/       drop the licensed WAV here
assets/source/video/       drop real DSA / B-roll / the original clip here
out/                       deliverables
docs/OPEN_QUESTIONS.md     decisions needed from the client
```

## Deliverables

| File | Spec |
|---|---|
| `out/beyond_the_image_2026_1080p.mp4` | H.264, CRF 18, +faststart |
| `out/beyond_the_image_2026_4k.mp4` | 3840×2160 variant |
| `out/final_frame.png` | held lobby slide |
| `out/preview_720p.mp4` | small shareable cut, ~8 MB |
| `out/qc_contact_sheet.jpg` | one frame every 2s, to catch text errors |

## Hard constraints enforced in code

- `assert_no_duplicate_words()` fails the build on a repeated word in the title.
- `assemble.py` exits non-zero above the 155s ceiling.
- Photographs are never regenerated, restyled or face-altered — geometry only.
- Logos are never drawn or traced. A mark that cannot be sourced is reported
  as missing, and `logo_wall.py` renders a visible NOT SOURCED marker.
- Missing sponsor logos render a PENDING marker rather than an empty box, and
  it clears before the end so the film never closes on it.

## Adding material as it arrives

Drop the file in the right place and rebuild — `validate.py` picks it up and
the placeholder disappears.

| Arriving | Goes to |
|---|---|
| Nahariya / Rambam photos | `assets/source/photos/`, then set `hero` in `photos.json` |
| Partner logos | `assets/source/logos/0N_name.svg`, log in `SOURCES.md` |
| Music | `assets/source/music/` — any WAV/FLAC/MP3 is picked up automatically |
| Real DSA / B-roll | `assets/source/video/` under the name in `storyboard.json` |
| AI-generated shots | `assets/generated/SXX.mp4` |
