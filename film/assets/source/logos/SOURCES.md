# Partner logo sources

Every file used in the S13 logo wall must be a genuine official mark. Nothing
here is drawn, traced, approximated or generated. If a file cannot be sourced
from the institution itself, it is reported as missing rather than substituted.

Display order is client-specified and must not be alphabetised or re-sorted.

| # | Institution | City | File | Status | Retrieved | Source |
|---|---|---|---|---|---|---|
| 1 | Galilee Medical Center | Nahariya | `01_galilee.svg` | **OBTAINED** | 2026-08-10 | Client-supplied `BTI2026_PorgramFinal.pdf`, page 1 header — live vector artwork extracted with `pdftocairo -svg` and cropped by viewBox (`scripts/extract_brand.py`) |
| 2 | Rambam Health Care Campus | Haifa | `02_rambam.svg` | **MISSING** | — | Not yet retrieved |
| 3 | Hadassah Medical Organization | Jerusalem | `03_hadassah.svg` | **MISSING** | — | Not yet retrieved |
| 4 | Sheba Medical Center, Tel HaShomer | Ramat Gan | `04_sheba.svg` | **MISSING** | — | Not yet retrieved |

## Galilee Medical Center — provenance note

The host institution's mark was taken from the client's own conference
programme, which is an Adobe Illustrator PDF export containing live vector
paths. This is a stronger provenance than a website download: it is the file
the institution is itself using for this conference, at this date.

Two variants are written:

- `01_galilee_colour.svg` — the official full-colour mark, unmodified.
- `01_galilee.svg` — a single-colour knockout in `#E8EDF2`, produced by
  remapping the fill colours of the *same paths*. No geometry is altered.
  The brief calls for white/knockout variants because the film's background is
  deep navy and full-colour marks go muddy on dark.

The conference lockup and subtitle were extracted from the same page and are
stored separately in `assets/source/brand/`, since they are conference identity
rather than institutional logos.

## Rules for sourcing the three outstanding marks

1. Go to the institution's own website, press room, media kit or brand
   guidelines page. Prefer the source over any third party.
2. Take vector (SVG / EPS / AI / PDF) wherever possible. If only raster exists,
   take the highest resolution available and never upscale a small PNG.
3. Prefer the white or single-colour knockout variant.
4. Verify the mark is current — cross-check against the logo in the
   institution's live homepage header before accepting a file from an archive
   or an older press kit. Hospitals rebrand.
5. Never take a logo from a stock site, a logo-aggregator, a fan page or a news
   article thumbnail. These are frequently outdated or subtly wrong.
6. Log the source URL and retrieval date in the table above.

## Note on which institutions appear

The four rows above are the partner list given in the brief. The conference
programme (`BTI2026_PorgramFinal.pdf`) lists speakers from a wider set:

- Galilee Medical Center, Nahariya (host)
- Rambam Health Care Campus, Haifa
- Sheba Medical Center, Tel Aviv
- Hadassah Medical Center / Hadassah University Center, Jerusalem
- Tzafon Medical Center, Baruch Padeh
- EMMS Hospital, Nazareth

Team photographs have additionally been supplied from **Carmel Medical Center**
and **Bnai Zion Medical Center**, neither of which appears in the programme.

This discrepancy needs a client decision before S13 is finalised — see
`docs/OPEN_QUESTIONS.md`.

## Commercial sponsors

Sponsor logos are a separate category and belong in S16, in their own row.
They must not be merged into the partner wall. None have been supplied.
