# Open questions — decisions needed from the client

Ordered by how much they block the build.

---

## 1. Which institutions appear in the film? — blocks S13

The brief names **four** partners for the S13 logo wall:
Galilee, Rambam, Hadassah, Sheba.

The conference programme lists speakers from **six**:
Galilee, Rambam, Sheba, Hadassah, **Tzafon Medical Center (Baruch Padeh)**,
**EMMS Hospital, Nazareth**.

Team photographs have been supplied from **four**, two of which are in neither
list: Sheba, Hadassah, **Carmel Medical Center**, **Bnai Zion Medical Center**.

Three different sets. Before S13 is finalised, confirm:

- the exact institutions in the logo wall, and their order
- whether Carmel and Bnai Zion belong in the team montage even though they are
  not on the programme
- whether Tzafon and EMMS need photographs and logos too

The montage currently runs Nahariya → Rambam → Sheba → Carmel → Bnai Zion →
Hadassah, per the instruction that Nahariya is first and Rambam second.
Re-sequencing is a one-line edit in `photos.json`.

---

## 2. Patient face in a Bnai Zion photograph — blocks that photo

`assets/source/photos/bnaizion_01.jpg` shows a **patient's face** at frame left
during a procedure. Staff consent does not cover a patient. Options:

1. **Tight crop** to the right two-thirds — operators and monitors only. The
   photograph still works, arguably better. *(recommended)*
2. Obtain written patient consent.
3. Drop the photograph.

`bnaizion_02.jpg` has a chilli-pepper emoji sticker pasted over the patient
area. That reads as a mistake on a lobby screen — it needs a clean crop or a
soft blur of the same region instead.

Both are currently **held back** from the montage and will not appear until
this is resolved. See `photos.json` → `held_back`.

---

## 3. Typeface: the brief and the conference identity disagree

The brief specifies a **display serif** for titles. The actual conference
identity — poster and programme — uses a **bold condensed sans**, white with
"2026" in a blue gradient.

**Decision taken:** S15 and S16 now use the client's own vector lockup, lifted
from the programme PDF. A title card in a different typeface from the poster
everyone has already seen would look like a mistake.

The display serif (Noto Serif Display) is retained for the narrative statement
lines — "Every image tells a story.", "Minutes are brain.", "One goal." — which
are film voice, not brand voice. The lockup is treated as a logotype, so the
two-typeface rule still holds: serif for statements, Inter for support.

Confirm this is acceptable.

---

## 4. Role list: the brief and the poster disagree — affects S12 and S15

| Brief | Poster ("Who should attend") |
|---|---|
| Physicians | Physicians |
| Nurses | Nurses |
| Radiologic Technologists | Radiologic Technologists |
| Biomedical Engineers | — |
| Researchers | Researchers |
| Industry Partners | — |
| — | Healthcare Leaders |
| — | Innovators |

The film currently uses the **brief's** list, in both S12 and S15. If the
poster's wording is the approved one, both need changing together.

---

## 5. The official tagline is stronger than the scripted line

The poster carries **"ONE TEAM · ONE MISSION · ONE PATIENT"**.

The brief's S12 payoff line is **"One goal."**

They say the same thing, and the official tagline says it better — and the room
will recognise it. Worth considering as the 1:50 card. Currently building the
brief's "One goal." as written.

---

## 6. Still outstanding from the client

| Item | Status |
|---|---|
| Nahariya (Galilee) team photographs | expected — slot reserved, first |
| Rambam team photographs | expected — slot reserved, second |
| Rambam / Hadassah / Sheba logo files | not retrieved |
| Sponsor logos + tier order | not supplied — S16 shows a PENDING marker |
| Licensed music track (WAV) | not supplied — film currently encodes silent |
| Original clip `VID-20260810-WA0039.mp4` | not supplied — S01 is a placeholder |
| Real DSA / angio footage | optional, high value — S06, S09 |
| Angio suite B-roll | optional, high value — S04 |
| Confirmation of the corrected title wording | see below |

**Title wording:** the programme and poster both read **BEYOND THE IMAGE 2026**
— one "THE". The film uses the client's own vector lockup, so the wording is
correct by construction. The typeset fallback path is additionally guarded by
`assert_no_duplicate_words()`, which fails the build on a repeated word.
