# A helmet about air

Scroll-driven single-page film for a carbon fibre full-face helmet.
Next.js (App Router) + TypeScript + Tailwind, GSAP/ScrollTrigger for the
scroll choreography, Lenis for smooth scroll. No CMS, no backend.

```bash
npm install
npm run dev      # http://localhost:3000
npm run build && npm start
```

## The two things you fill in

### 1. Spec numbers — `data/site.ts`

`SPECS` ships **empty on purpose**. No weight, shell material or standard is
printed anywhere in this repo, because none were supplied. Paste the real
published figures and they appear in the 06 spec list *and* in every marquee
strip:

```ts
export const SPECS: Spec[] = [
  { label: "Shell", value: "…" },
  { label: "Weight", value: "…" },
  { label: "Standards", value: "…" },
];
```

Until then the spec block reads "Awaiting figures" and the marquee falls back
to the chapter titles.

### 2. Photography — `public/img/`

| file            | chapter        | status      |
| --------------- | -------------- | ----------- |
| `01-hero.jpg`   | 01 Hero        | in place    |
| `02-weave.jpg`  | 02 The Weave   | **missing** |
| `03-shape.jpg`  | 03 The Shape   | in place    |
| `04-visor.jpg`  | 04 The Visor   | in place    |
| `05-fit.jpg`    | 05 The Fit     | **missing** |
| `06-object.jpg` | 06 The Object  | **missing** |

A missing file renders a dark placeholder printing its own path in mono — the
page never crashes and never substitutes stock photography. Drop a JPG in with
the right filename and it takes over. Roughly 2400px wide is plenty; `next/image`
serves AVIF/WebP from there.

## Art direction

`#0A0A0B` ground, `#F2EDE4` text, one accent (`#C8703A`). Playfair Display for
the display type, JetBrains Mono for meta labels at 11px / 0.2em. Text always
sits directly on the image. Grain (SVG `feTurbulence`, 4%) and a radial vignette
sit over every section.

## Effects

- Lenis smooth scroll, `lerp: 0.08`
- Each chapter pinned for 140% of a viewport; image scales 1.0 → 1.12 and
  cross-fades through black at the chapter edges
- Parallax: image drifts at ~0.7× the copy's speed
- Headlines reveal line by line — clip-path mask, y 40 → 0, 80ms stagger.
  Chapter 01 does this in CSS at first paint so it is not gated on GSAP.
- Fixed left rail, active chapter at full opacity, rest at 25%, amber progress line
- Infinite marquee between chapters
- Custom 8px cursor dot, scales up over interactive elements (pointer devices only)

## Constraints held

- No horizontal scroll at 360px
- `prefers-reduced-motion: reduce` drops Lenis, pinning, parallax and the
  marquee animation; sections become plain 100svh blocks that fade in
- Everything but the hero image is lazy loaded; GSAP + Lenis load on idle
- Lighthouse mobile (production build): performance 91, accessibility 96,
  best practices 96

## Deploy

Vercel, zero config — root directory `helmet-site`.
