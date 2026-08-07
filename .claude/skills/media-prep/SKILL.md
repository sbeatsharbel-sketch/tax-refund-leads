---
name: media-prep
description: Ingest and normalize a messy folder of phone/WhatsApp photos and videos into a clean, uniform manifest ready for editing. Use whenever the raw material for a video comes from WhatsApp, a phone camera roll, or any mixed-source dump - before any cutting, montage, or timeline work. Handles rotation metadata, mixed portrait/landscape, HEIC, variable frame rate, missing audio, and chronological ordering by capture time.
---

# Media Prep

Raw phone media lies. A folder exported from WhatsApp will contain portrait clips
that report landscape dimensions, HEIC stills that ffmpeg cannot open, variable
frame rate video that drifts out of sync the moment you concatenate it, and
filenames whose sort order has nothing to do with when anything happened.

Fix all of that **before** editing. Every later stage assumes a clean manifest.

## The pipeline

```bash
python3 scripts/prep_media.py <input_dir> --out work/manifest.json
```

This probes every file and writes a manifest. It does **not** transcode - probing
is cheap and reversible, transcoding is neither. Normalization happens later, in
the montage render, where the target canvas is known.

Read the manifest before planning an edit. It tells you what you actually have.

## What the manifest gives you

Each entry carries:

| Field | Why it matters |
|---|---|
| `kind` | `image` or `video` - they need different treatment on the timeline |
| `width` / `height` | **Display** dimensions, rotation already applied |
| `rotation` | Original metadata rotation, kept for reference |
| `orientation` | `portrait`, `landscape`, or `square` |
| `duration` | Seconds. Images get `null` |
| `fps` | Average frame rate. `vfr: true` flags variable frame rate |
| `has_audio` | Whether there is a soundtrack worth keeping (laughs, speech) |
| `captured_at` | Best-effort capture time from metadata, then filename, then mtime |
| `captured_at_source` | Which of those three won - trust `metadata` far more than `mtime` |
| `problems` | Anything that will bite during render |

## Rules that prevent broken renders

**Never trust the raw stream dimensions.** A phone shoots portrait but stores a
landscape frame plus a `rotate` tag. `prep_media.py` resolves this into
`width`/`height` as displayed. Use those. If you pass raw stream dimensions to a
scale filter you will get sideways video.

**Treat variable frame rate as hostile.** VFR clips (`vfr: true`) drift when
concatenated. Always force a constant rate with `-r` on the segment render, and
never use `-c copy` on a VFR source.

**Order by `captured_at`, not filename.** WhatsApp filenames sort by export
order, not chronology. For a montage that tells a story over time, sort by
`captured_at` and check the result - if most entries show
`captured_at_source: "mtime"`, the timeline is a guess and you should tell the
user rather than silently shipping a wrong order.

**Convert HEIC up front.** ffmpeg cannot read HEIC. `prep_media.py` converts any
HEIC/HEIF it finds into full-quality PNG beside the manifest and points the entry
at the converted file via `path`. Use `path`, always - it is the editable file,
which is not necessarily `source_path`.

**Respect `problems`.** Entries with a non-empty `problems` list still render,
but they are where artifacts come from. Common ones:

- `no_video_stream` - an audio file or a corrupt clip. Exclude from the visual timeline.
- `tiny` - below 640px on the long edge. It will look soft blown up to 1080p; use it briefly or not at all.
- `very_short` - under 0.5s. Too short to read as a shot; treat it as a flash cut or drop it.
- `vfr` - see above.
- `unreadable` - ffprobe failed. Excluded automatically.

## Selecting from a large dump

With hundreds of files, do not put them all in. A montage lives on pacing, and
pacing dies at 200 clips. Use the manifest to narrow:

```bash
# Landscape videos over 2 seconds, in chronological order
python3 scripts/select_media.py work/manifest.json \
    --kind video --min-duration 2 --orientation landscape
```

`select_media.py` filters and prints a manifest subset, so selection stays
declarative and repeatable instead of a hand-copied list of paths.

## Handing off

The manifest is the contract with the next stage. `video-montage` consumes it
directly, and `beat-sync` pairs its beat grid against the entry count to work out
how long each shot can breathe.
