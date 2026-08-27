export type Chapter = {
  n: string;
  label: string;
  file: string;
  /** Headline split into mask lines. Exactly one word carries `italic`. */
  lines: { text: string; italic?: boolean }[][];
  caption?: string;
};

/**
 * Six chapters. Copy is fixed editorial text — nothing here is a claim about
 * the product, so it needs no source.
 */
export const CHAPTERS: Chapter[] = [
  {
    n: "01",
    label: "Hero",
    file: "01-hero.jpg",
    lines: [
      [{ text: "A helmet" }],
      [{ text: "about " }, { text: "air", italic: true }, { text: "." }],
    ],
  },
  {
    n: "02",
    label: "The Weave",
    file: "02-weave.jpg",
    lines: [
      [{ text: "Woven", italic: true }, { text: "," }],
      [{ text: "not moulded." }],
    ],
  },
  {
    n: "03",
    label: "The Shape",
    file: "03-shape.jpg",
    lines: [
      [{ text: "Shaped by" }],
      [{ text: "the " }, { text: "wind", italic: true }, { text: "." }],
    ],
  },
  {
    n: "04",
    label: "The Visor",
    file: "04-visor.jpg",
    lines: [
      [{ text: "Nothing", italic: true }],
      [{ text: "between you" }],
      [{ text: "and the road." }],
    ],
  },
  {
    n: "05",
    label: "The Fit",
    file: "05-fit.jpg",
    lines: [
      [{ text: "Held", italic: true }, { text: "," }],
      [{ text: "not squeezed." }],
    ],
  },
  {
    n: "06",
    label: "The Object",
    file: "06-object.jpg",
    lines: [
      [{ text: "The " }, { text: "object", italic: true }, { text: "." }],
    ],
  },
];

/**
 * ---------------------------------------------------------------------------
 * SPEC SHEET — AGV Pista GP RR
 * ---------------------------------------------------------------------------
 * INTENTIONALLY EMPTY. Nothing here is invented.
 * Paste the real published figures as { label, value } pairs and they appear
 * in the 06 spec list and in every marquee strip automatically.
 *
 *   export const SPECS: Spec[] = [
 *     { label: "Shell", value: "..." },
 *     { label: "Weight", value: "..." },
 *     { label: "Standards", value: "..." },
 *   ];
 */
export type Spec = { label: string; value: string };

export const SPECS: Spec[] = [];

export const PRODUCT_NAME = "AGV Pista GP RR";

/** Marquee falls back to chapter titles until real spec text exists. */
export const marqueeItems = (): string[] =>
  SPECS.length > 0
    ? SPECS.map((s) => `${s.label} — ${s.value}`)
    : CHAPTERS.map((c) => c.label.toUpperCase());
