---
name: glass-shatter
description: Break the screen like a pane of glass to reveal what is behind it, with a synthesized glass-break sound. Use for hard-hitting openings, title reveals, dramatic beat drops, or any moment where one scene should violently give way to another - "the screen shatters", "smash cut", "break the title". Also generates standalone glass-break sound effects.
---

# Glass Shatter

Two pieces: a renderer that fractures a frame and throws the pieces away, and a
synthesizer that makes the sound. They are separate because the sound is often
useful on its own, and because the timing between them has to be exact.

## Make the sound first

```bash
python3 scripts/glass_sfx.py --out work/glass.wav --seed 11
```

Synthesized from noise and grain layers rather than sampled, so there is no
licensing question and the length can be tuned to the animation. `--seed` fixes
the result; omit it and every run produces a different break. `--tail` controls
how long the debris keeps tinkling - shorten it to about 1.0s when music enters
right after the break, or the tail fights the downbeat.

## Then render the shatter

```bash
python3 scripts/shatter.py \
    --before work/title.mp4 --after black \
    --hold 6.4 --crack 0.25 --fly 1.6 \
    --impact-x 0.5 --impact-y 0.62 \
    --sfx work/glass.wav --out out/intro.mp4
```

Three phases run back to back:

| Phase | Flag | What happens |
|---|---|---|
| hold | `--hold` | `--before` plays untouched |
| crack | `--crack` | Fracture lines race outward, one white flash frame, the frame shakes |
| fly | `--fly` | The pane comes apart and falls, revealing `--after` |

Total output length is the sum of the three.

## Getting it to land

**Put the impact on the thing you want destroyed.** `--impact-x/--impact-y` are
fractions of the frame. Aim them at the punch line, the name, the word that
matters - the fracture radiates from there and that text is what visibly breaks
apart. An impact in dead center when the important text sits low reads as
generic; an impact *on* the text reads as deliberate.

**Keep `--crack` short.** Between 0.15s and 0.3s. This is the beat where the
audience registers that something happened, and it works because it is almost
too fast to see. Above about 0.4s the pane looks like it is politely waiting.

**Hold long enough to read the text, then break immediately.** No fade out on
the last title card - set its `fade_out` to near zero. Text that is already
dissolving when the glass breaks wastes the impact.

**Land the break on a beat.** Take a downbeat from `beat-sync` and set `--hold`
so the impact frame falls on it. The break is the loudest thing in the piece; if
it is off the grid, everything after it feels off too.

**Reveal the next shot, not black.** `--after` accepts a clip, an image, or a
colour. Revealing the first photo of the montage is stronger than revealing
black and then fading up - the shards come off and the film is already running.

## Tuning the fracture

`--rays` (spokes) and `--rings` set the pattern; shard count is roughly
`rays × rings`. Defaults of 17 and 5 give about 100 pieces, which reads as glass
at 1080p.

- Fewer, larger shards (`--rays 9 --rings 3`) look like thick plate glass and stay legible longer
- More, smaller shards (`--rays 24 --rings 7`) look like a windscreen and render noticeably slower

The pattern is radial-plus-concentric because that is how struck glass actually
fails - spokes out from the impact, rings around it. Voronoi cells, the obvious
alternative, look uniformly random and read as "polygon effect" rather than glass.

Pieces near the impact are small, fast, and drift toward the camera; distant ones
are large, slow, and recede. That size and speed gradient is most of what sells
the effect, and it is why an impact near a frame edge looks worse than one nearer
the middle - half the gradient ends up offscreen.

## Cost

About 100 shards at 1080p renders roughly 30 frames per second of wall time, so
a 1.6s fly phase takes under a minute. Render at final quality directly; there is
little to gain from a draft pass.

## Carrying the sound into a longer edit

`video-montage` strips segment audio while rendering, so a break baked into an
intro clip will not survive into the final mix. Put it back explicitly:

```bash
python3 ../video-montage/scripts/build_montage.py ... --sfx work/glass.wav@6.40
```

The time is the absolute position on the finished timeline - the same value used
for `--hold`, assuming the shatter clip starts the film.
