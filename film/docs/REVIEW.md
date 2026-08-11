# REVIEW — *Beyond the Image 2026* opening film

Reviewed: `out/beyond_the_image_2026_1080p.mp4` — 150.00s, 1920×1080, 24fps, silent.
Method: frames extracted every 2s across the whole film, every 1s across S12 (1:30–1:55),
and at 0.2–0.5s intervals across every section boundary and every card transition.
Text sizes measured directly off the alpha channels in `build/text/*.png`.

---

## Verdict

**Not screenable in its present state.** This is not a "13 shots are still placeholders"
problem — that is understood and priced in. The problem is that the film in `out/` is a
*production artefact wearing the costume of a film*, and if it were played in the Galilee
Medical Center lobby on 9 September it would read to the room as a mistake rather than as
work in progress.

The single worst problem: **the film ends on a magenta production warning.** From 2:27 to
2:30 — the last three seconds, the frame the audience is left staring at while the lights
come up — the screen reads `SPONSOR LOGOS PENDING — NOT FOR SCREENING` above
`supply logo files + tier order`. There is no fade out; the film simply stops on it. A card
whose literal text is "not for screening" cannot be the closing image of a screening. Every
other finding on this list is secondary to that one.

Close behind it: **roughly 110 of the film's 150 seconds carry developer-facing chrome** —
a full-width magenta rule welded to the top edge of every placeholder frame, the word
`PLACEHOLDER`, internal shot IDs, `source: existing`, `in @ 0:00`, raw repository file paths
(`awaiting: assets/generated/S07.mp4`), and internal direction notes the client wrote to
themselves (`Upscale. Remove cursive line.`, `Hero clip.`). None of that is a placeholder
*image*; it is scaffolding text, and it is the thing that makes the piece look unfinished
rather than unfilled. A dark navy card with the caption alone would read as deliberate. This
reads as a screen-share of somebody's build directory.

And in the one section that is fully real — S12, the emotional core — the two things that go
wrong are the two things that hurt most in a room full of the people in the photographs:
identifiable clinicians are captioned with the wrong role (Hadassah's angiography team,
including a doctor whose name badge is legible on his lead apron, is labelled
**"Industry Partners"** at 1:47), and the 0.4s cross-dissolves between photographs leave
**ghost faces floating over other people's faces** at every slot change.

What is genuinely good: the S15 title card is correct, well-set and handsome; "BEYOND THE
IMAGE 2026" reads cleanly, the date is right (September 9, 2026), the venue is right, and the
client's own lockup makes it look like the poster everyone has already seen. The pacing
skeleton is sound. Fix the list below and there is a real film here.

---

## Findings

| # | Severity | Timecode | Shot | What is wrong | Recommended fix |
|---|---|---|---|---|---|
| 1 | **BLOCKER** | 2:27–2:30 (t=147.0–150.0), incl. the final frame | S16 | The film's closing image is a magenta-outlined box reading `SPONSOR LOGOS PENDING — NOT FOR SCREENING` / `supply logo files + tier order`. The audience's last impression is a production warning telling them this should not be being shown. `out/final_frame.png` is the S15 title card, so even the intended lobby hold slide disagrees with what the film actually ends on. | Until sponsor logos are supplied, delete the entire sponsor block from S16. End on the GMC mark + "Founded and hosted by Galilee Medical Center, Nahariya". A missing sponsor wall is invisible; a `NOT FOR SCREENING` sign is not. Keep the PENDING marker in an internal QC render only. |
| 2 | **BLOCKER** | 0:00–1:30 and 1:55–2:15 (13 shots) | S01–S11, S13, S14 | Developer-facing scaffolding is on screen for ~110s of 150s: `PLACEHOLDER`, shot IDs (`S06 THROMBECTOMY`), `6s · source: existing · in @ 0:00`, and repository paths (`awaiting: assets/source/video/S06_dsa_run.mp4`). At 2:15 (t=135.0) the S14 card, `awaiting: assets/generated/S14.mp4` and all, cross-dissolves *over the brand starfield of the title card*. | Strip everything except the shot's real caption from `placeholders.py`. A placeholder should be the navy field plus the statement line, nothing else — that reads as an intentional graphic beat. Gate the ID/meta/path block behind an env flag used only for the QC contact sheet. |
| 3 | **BLOCKER** | 0:00–1:30, 1:55–2:15 (every placeholder frame) | S01–S11, S13, S14 | A 7px full-width magenta rule (RGB ≈ 145,71,128) is welded to row 0 of every placeholder frame, edge to edge. Verified present at t=0.5, 1, 3, 7, 15, 25, 45, 65, 85, 116, 125, 130. On a large lobby screen a coloured stripe touching the top bezel does not read as design — it reads as a torn frame or a broken decoder. | Remove it. If a draft-mode tell is wanted, put it in the QC contact sheet, not the deliverable. |
| 4 | **BLOCKER** | 1:47–1:50 (t=106.7–110.0), and 1:41–1:43 (t=100.0–103.3) | S12 | Role captions are bound to institution slots by index, not by who is actually in the frame, so identifiable staff are mislabelled. At 1:47 Hadassah's angiography team — six clinicians, one in a lead apron with a legible name badge — is captioned **"Industry Partners"**. At 1:41 Carmel's radiographers and nurses in white coats are captioned **"Biomedical Engineers"**. These people, and their colleagues, will be in the room. | Decouple role captions from institution slots. Either caption the institution (which is what the photo actually shows) or run the six role words as a separate typographic beat over non-identifying material. Do not label a named person with a job that is not theirs. |
| 5 | **MAJOR** | 0:14–0:21 (t=14.0–20.9), worst at 0:17 and 0:19 | S03 | Direct text collision. The serif line "Some stories can only be read in time." occupies y=835–896; the placeholder metadata line `8s · source: ai · in @ 0:13` sits at y=860–900. The word "stories" is printed straight through "source: ai". Two typefaces, two colours, one set of pixels. | Falls away with finding 2. If the meta block is kept for internal builds, move `serif_lower` up to y≈760 or push meta to y≈1000. |
| 6 | **MAJOR** | 0:31–0:36, 0:55–1:00, 1:12–1:22 | S05, S08, S10 | The section labels `THROMBECTOMY`, `COILING`, `EMBOLIZATION` render at y=958–988 — a 31px cap height, the smallest type in the film, less than half the height of the statement lines — and they straddle the placeholder card's bottom border (y≈955), so the rule cuts through the letterforms and the label butts into the `awaiting:` path line above it. Nominally 42pt, so the "no text below 40px" rule passes on paper; at 5–20 metres it fails in practice. | Raise `SIZES["label"]` to at least 56 (≈42px cap) and lift `LABEL_Y` to about H−200 so it clears the card. These three words carry the clinical spine of the film and are currently the least legible thing on screen. |
| 7 | **MAJOR** | 1:36.7, 1:40.0, 1:43.3, 1:46.7, 1:50.0 (each ±0.2s) | S12 | `montage.py` sets `DISSOLVE = 0.4`, so every photo-to-photo change inside the montage is a cross-dissolve. Because these are all group portraits at similar scale, the result is ghost faces superimposed on other faces. At 1:49.9 four large translucent heads from the previous photo hover above the Nahariya group like apparitions; at 1:43.2 two entire teams occupy the same six faces. This also breaks the stated rule — hard cuts within a section, crossfades only at section boundaries. | Set `DISSOLVE = 0.0`. The comment in the file already anticipates this. Hard cuts will also sharpen the montage's rhythm. |
| 8 | **MAJOR** | 1:30–1:36.7 (t=90.0–96.7), collision at 1:33.3 | S12 | The emotional core opens on 6.7 seconds — 27% of the montage — of two "slot reserved — photographs not yet supplied" cards on empty navy, occupying about 15% of the frame with nothing above or below. Worse, at 1:33.3 the two cards cross-dissolve at identical position, so `GALILEE MEDICAL CENTER — NAHARIYA` and `RAMBAM HEALTH CARE CAMPUS — HAIFA` print through each other into an illegible smear of overlapping capitals. At 1:36.6 the Rambam card is still ghosted across the faces of the Sheba team. | Until Nahariya and Rambam photos arrive, drop both reserved slots and redistribute the 6.7s across the four real institutions (5s each). The montage will be shorter on institutions and much stronger on screen. If the slots must be held, make the transition a hard cut and centre the card in an otherwise composed frame. |
| 9 | **MAJOR** | 2:02–2:07 (t=122.0–127.0) | S13 | Five seconds of the film's designated hero shot are completely inert: the statement lines have cleared and the partner logo wall never arrives. Measured white-ink pixel count is flat at the card's baseline value for the whole stretch — no logos, no motion, nothing. `storyboard.json` promises the overlay `build/shots/S13_logos.mov` at t=122; that file does not exist (only `build/shots/logo_wall.png`, uncomposited). | Either composite `logo_wall.png` into S13 with its `NOT SOURCED` markers, or shorten S13 from 12s to 7s and give the 5s back to S12. Five dead seconds at 2:02 is where a lobby audience starts checking their phones. |
| 10 | **MAJOR** | 2:24.5–2:25.6 (t=144.5–145.6) | S15→S16 | A 1.1-second hole. The title card's text fades out at 2:24.3 and the credit does not fade in until 2:25.6, leaving over a second of bare particle field between the film's climax and its credit. Measured peak luma drops from 254 to 112 across this window — genuinely nothing on screen. | Overlap the fades: hold S15's support text to 2:25.0 and start S16's credit fade at 2:24.8. |
| 11 | **MAJOR** | 0:00 and 2:30 | S01, S16 | No fade in and no fade out. Mean luma is identical (22.61) at t=0.0, 0.1, 0.2, 0.3, 0.4 and 0.5 — the film cuts on hard, mid-brightness, straight to the S01 placeholder card. At the tail, luma is still 19.34 with peak 255 at t=149.95 — it cuts off hard on the sponsor warning. The stated grammar is 0.4s in / 0.4s out. | Add a 0.4s fade from black at the head and a 0.6–1.0s fade to black (or to the held title frame) at the tail. On a lobby screen a hard-off ending looks like the file ran out. |
| 12 | **MAJOR** | 2:15–2:24 (S15), 2:26–2:30 (S16) | S15, S16 | Legibility at distance on the two cards that matter most. Measured ink-band heights: S15 subtitle "The Conference of Interventional Radiology and Neuro-Radiology" = 37px total including descenders (≈26px cap); S15 support block "Bringing Together Physicians, …" = 41px (≈29px cap) across two lines; S16 "Israel's first conference of its kind" = 35px (≈25px cap), and it is set in cyan on navy, the lowest-contrast pairing on the card. Nominal point sizes clear 40, but rendered cap heights are 25–29px. At 20 metres on a 1080p lobby screen none of these will be read. | Raise the S15 support block to ≥54pt (drop the sentence to one line by cutting the role list, per open question 4) and the S16 subline to ≥52pt in silver, not cyan. If it cannot be read from the back of the lobby, it is decoration. |
| 13 | **MAJOR** | 1:47–1:50 (t=106.7–110.0) | S12 | Unflattering framing, worsening across the slot. `hadassah_02` is a selfie: the foreground man's head is cut off at the right frame edge, his face fills roughly 65% of frame height with visible wide-angle distortion, and the Ken Burns push-in (1.02→1.095) crops him harder every second. His colleague's name badge and the lead apron's printed name are legible at 1080p. | Re-anchor this slot's crop, or swap to `hadassah_01`/`hadassah_03` from the reserve. Nobody should be cropped through the skull in the film's warmest section. |
| 14 | **MAJOR** | 1:37–1:40, 1:43–1:47, 1:50–1:55 | S12 | On-screen text is specified English-only. Prominent Hebrew appears in three consecutive slots: the Sheba flag (1:37–1:40); a large orange scrub warning label reading "אין לצאת עם בגד זה מחוץ לחדר הניתוח" — *do not leave the operating theatre in this garment* — dead centre and fully legible at 1:43–1:47; and at 1:50–1:55 a "חדר רופאים" door sign plus a whiteboard densely covered in Hebrew handwriting behind the closing group. The scrub-label one is also tonally wrong: a laundry rule is the sharpest-focus text in the montage's most emotional beat. | The flag and door sign are defensible as environment. The scrub label is not — re-crop `bnaizion_03` or swap the slot. The whiteboard is fine but consider a tighter crop on the closing frame. |
| 15 | **MINOR** | 1:38–1:40 (t=98.0–100.0) | S12 | The caption "Radiologic Technologists" runs left-to-right off the navy scrubs and onto the white flag; the final five letters sit white-on-white with only the scrim (≈53% at that baseline) separating them. The word tail smears at distance. | Nudge the caption left, or lift `LOWER_Y` for this slot, or deepen the scrim locally. |
| 16 | **MINOR** | 1:50–1:55 (t=109.8–115.0) | S12 | The closing photograph — 15 staff, the film's payoff image — is washed with a flat navy dim ramping to 58% opacity under "One goal.". Combined with the standing bottom scrim, faces in the lower half go muddy and the group reads as a silhouette. The statement wins, the people lose. | Drop `DIM_MAX` to ≈0.35 and add a soft radial falloff so the centre of the group stays open. |
| 17 | **MINOR** | 1:36.7–1:55 (all photo slots) | S12 | The bottom scrim starts at y=0.52H and ramps to 88% opacity at the frame edge, so the lower 48% of every team photograph dissolves into navy — legs, hands, badges and the front row's lower bodies vanish. It is doing more work than caption legibility needs. | Start the scrim at y≈0.68H and cap alpha around 190. |
| 18 | **MINOR** | 2:26–2:30 (t=145.6–150.0) | S16 | "Israel's first conference of its kind" uses a straight typewriter apostrophe (U+0027) instead of a typographic one (’). Confirmed at glyph level in `build/text/S16_credit.png`. Small, but it is on a title card in a serif-and-Inter typographic system. | Replace with `’` in `S16_LINES[1]`. |
| 19 | **MINOR** | 0:00–0:06 | S01 | The placeholder body text wraps to leave a single orphaned word, "line.", on its own line. Compounded by the fact that the sentence is an internal instruction to a VFX vendor ("Upscale. Remove cursive line."). Several other cards use a hyphen where an en dash belongs ("DSA run - microcatheter", "Coil deployment - sac filling"). | Falls away with finding 2. |
| 20 | **MINOR** | 2:17–2:24 (t=137.0–144.0) | S15 | The title card is pixel-identical for seven straight seconds — ink count flat at 82,432 — with only the slow particle field behind it. Seven static seconds is a long time on a big screen and lets the eye wander to the edges of the frame. | Either trim S15 to 8s (freeing 2s toward the S13 hole at finding 9), or give the lockup a barely-perceptible 1–2% scale settle across the hold. |
| 21 | **MINOR** | throughout | all | Continuity of look. The film currently has three unrelated visual registers: flat navy cards with a hairline box (S01–S14), photographs (S12), and a particle starfield (S15–S16). The placeholder cards carry none of the brand particle field that the title cards do, so the moment S15 arrives at 2:15 it looks like a different production. | Once the scaffolding is stripped (finding 2), run the same particle background under the placeholder cards. One field, one film — and it costs nothing, `particles.py` already exists. |
| 22 | **MINOR** | 1:41–1:47 | S12 | Employee ID badges are legible at 1080p in the Carmel and Bnai Zion slots (already flagged in `photos.json` → `review_notes`, still unaddressed in the render). Names and photo IDs are readable when the film is projected large. | Decide per photo. A 6–8px blur on badge regions is geometry-safe and does not touch faces, so it stays inside the "never restyle or face-alter" rule. |

---

## Checked and clean

- **Runtime** 150.00s exactly — inside the 155s ceiling.
- **Title wording** — "BEYOND THE IMAGE 2026", one "THE". The duplicated-word defect is fixed.
- **Date and venue** — "September 9, 2026 · Galilee Medical Center — Nahariya" matches
  `screening_date: 2026-09-09`. No misspellings found in any on-screen English copy.
- **Horizontal centring** — every centred text layer measures to within 2px of x=960.
- **Section-boundary transitions** — 0.5s crossfades at all ten boundaries, as specified.
  No slides, spins or bounces anywhere in the film.
- **Typefaces** — Noto Serif Display for statements, Inter for support, client lockup treated
  as logotype. Holds, provided open question 3 is confirmed by the client.
- **Photographs** — geometry only (cover-crop, scale, drift). No restyling or face alteration.
- **Held-back photos** — the patient-face and emoji-sticker images from `photos.json`
  correctly never appear.
