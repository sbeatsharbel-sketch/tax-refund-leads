---
name: hebrew-titles
description: Render animated Hebrew, English, or mixed-language titles, opening sequences, end cards, and lower thirds onto video with correct right-to-left shaping. Use whenever a video needs text - an intro, a name card, a caption, credits, a farewell message - and especially when any of that text is Hebrew, Arabic, or mixes RTL with LTR words and numbers.
---

# Hebrew Titles

Hebrew text in video breaks in ways Latin text does not: letters come out
reversed, a phone number inside a Hebrew sentence jumps to the wrong end, and
final-form letters render as their medial shape. All three come from the same
mistake - drawing text with a renderer that has no bidirectional algorithm.

## Use libass, never drawtext

ffmpeg's `drawtext` filter draws glyphs in byte order. For Hebrew that means
backwards text and broken mixed-direction strings. It has no reliable bidi pass.

`libass` runs FriBidi for bidirectional reordering and HarfBuzz for shaping. It
gets Hebrew right, handles mixed Hebrew/English/digits correctly, and gives far
better animation control. Every title in this skill goes through an `.ass` file
and the `ass` filter.

Confirm the build has it before starting:

```bash
ffmpeg -hide_banner -buildconf | grep -E "libass|libfribidi|libharfbuzz"
```

If `libass` is missing, stop and install a full ffmpeg build. There is no good
workaround.

## Never apply letter spacing to RTL text

Any `\fsp` value - even 1 - makes libass render Hebrew and Arabic **backwards**,
because letter spacing bypasses its bidi reordering. The text still appears, in
the right font, at the right size, just with the glyphs in reverse order. It
passes a casual look and only gets caught by actually reading the frame.

`make_titles.py` strips `spacing` from any line containing RTL characters and
warns. Get hierarchy from size, weight, and colour instead; those are stronger
tools anyway.

## Preview frames must be sampled after the fade

`--still` renders one frame to compare looks quickly, and it samples the moment
when every card has finished animating in. Sampling at t=0 instead shows a frame
where anything carrying a `\fad` - rules, scrims, fading cards - is still fully
transparent, which reads as "my divider line never rendered". Override with
`--still-at SECONDS` when a card needs inspecting at a specific moment.

The same trap applies when pulling a check frame with ffmpeg by hand: seek into
the card, do not grab frame zero.

## Font choice is not cosmetic

Most fonts have no Hebrew glyphs at all, and a missing glyph renders as a blank
box or silently falls back to something ugly. Verify before rendering:

```bash
fc-list :lang=he family | sort -u
```

`Noto Sans Hebrew` is the safe fallback, but it is a UI font - at display sizes
it reads as a system default, which is most of why a title card can look cheap.
Install the Culmus family for faces actually designed for Hebrew display work:

```bash
apt-get install -y culmus fonts-ldco
```

| Font | Character | Use for |
|---|---|---|
| `Aharoni CLM` | Heavy, geometric, the classic Israeli poster face | Punch lines, single bold statements |
| `Frank Ruehl CLM` | The standard Hebrew book serif | Anything that should feel considered or literary |
| `Miriam CLM` | Clean, neutral sans | Setup lines, captions, credits |
| `David CLM` | Calligraphic serif | Formal or ceremonial titles |

Mixing a serif for the small text with a heavy sans for the big line is the
easiest way to get hierarchy that does not depend on size alone.

## Presets

`--background` takes a preset that pairs a graded background with type settings
that suit it. Each supplies a font, an accent colour, letterbox bars, film grain,
and a vignette:

| Preset | Look |
|---|---|
| `document` | Cool near-black, restrained, Miriam. Formal and understated |
| `cinematic` | Warm amber glow from below, Frank Ruehl serif. The default |
| `bold` | Deep blue wash, heavy Aharoni, high contrast. Graphic and loud |

Inside a card, `"color": "accent"`, `"ink"`, or `"muted"` resolves against the
preset's palette, so the same spec can be re-rendered in any look by changing one
flag. `--still` renders a single PNG instead of a video, which makes comparing
looks fast.

Three things in those presets do most of the work, and they are worth carrying
into any custom look:

- **Letterbox bars.** Nothing else changes a frame's register so cheaply.
- **Film grain.** Stops large flat gradients from banding on projectors, and reads as film rather than as a computer gradient.
- **No hard outline.** A black outline around type is what makes a title look like a burned-in subtitle. On a controlled dark background, shadow alone carries it.

## Making titles

```bash
python3 scripts/make_titles.py --spec titles.json --out work/titles.ass
```

The spec is a list of cards, each with timing, text lines, and an animation:

```json
{
  "canvas": {"width": 1920, "height": 1080},
  "font": "Noto Sans Hebrew",
  "cards": [
    {
      "start": 0.5, "end": 4.5, "animation": "zoom",
      "lines": [
        {"text": "תודה על הכל", "size": 130, "bold": true},
        {"text": "2023 - 2026", "size": 54, "color": "#C9A227"}
      ]
    }
  ]
}
```

Then either burn it onto video, or render it as a standalone card:

```bash
# Burn onto existing footage
ffmpeg -i video.mp4 -vf "ass=work/titles.ass" -c:a copy out.mp4

# Standalone card, cinematic preset
python3 scripts/make_titles.py --spec titles.json --render work/intro.mp4 \
    --background cinematic --duration 6
```

`--background` also accepts `black` or a path to an image or video, which gets
blurred and darkened automatically so the text stays legible on top.

## Animations

| Name | Motion | Use for |
|---|---|---|
| `fade` | Opacity only | Captions, lower thirds, anything that must not distract |
| `zoom` | Scales from 108% down to rest | Opening titles. The standard cinematic reveal |
| `rise` | Fades while drifting upward | Names, dates, subtitles under a main title |
| `blur` | Focus pulls from blurred to sharp | Dramatic single-word reveals |
| `slide` | Enters from the right | Hebrew-native motion - matches reading direction |
| `typewriter` | Character by character | Lists, credits, a punchline landing on a beat |

For Hebrew, prefer `slide` over a left-entering slide. Motion that runs against
reading direction reads as wrong even to viewers who cannot say why.

## Rules that keep titles readable

**Give text a hold, not just a transition.** A title needs roughly 0.4s of
animation in, then at least 1.5s fully settled before it leaves. Text that starts
fading out the moment it arrives is unreadable. `make_titles.py` warns when a
card is too short for its animation.

**Keep it inside the safe area.** Text within 5% of any edge gets cropped by
players, TVs, and social platforms. The generator enforces a 6% margin.

**Contrast beats size.** White text on bright footage disappears no matter how
large. Every card gets a subtle shadow and outline by default; over busy footage
use `"scrim": true` on the card to lay a soft dark gradient behind the text.

**Two lines maximum per card.** Three lines of Hebrew display type at 1080p
forces a size small enough to lose impact on a phone. Split into two cards.

**Never mirror numbers or Latin names manually.** Write the string in logical
order - the order someone types it - and let FriBidi place it. Hand-reversing
text produces something that looks right in the source file and wrong on screen.

## Timing titles to music

An opening title that resolves on a downbeat feels intentional. Take the beat
grid from `beat-sync`, pick the downbeat nearest the intended landing, and set
the card so its animation **completes** there rather than starts there - the
motion should resolve into the beat, not begin on it.
