import { marqueeItems } from "@/data/site";

/**
 * Infinite spec strip between chapters. The track holds the items twice and
 * translates -50%, so the loop is seamless with no JS.
 */
export function Marquee({ duration = 42 }: { duration?: number }) {
  const items = marqueeItems();
  if (items.length === 0) return null;

  const run = (key: string) => (
    <span className="inline-flex shrink-0" key={key} aria-hidden={key === "b"}>
      {items.map((item, i) => (
        <span key={i} className="inline-flex items-center">
          <span className="meta whitespace-nowrap px-6 py-6 sm:px-8">
            {item}
          </span>
          <span className="text-amber/70 text-[9px]">◆</span>
        </span>
      ))}
    </span>
  );

  return (
    <div
      className="marquee relative border-y border-bone/8 bg-ink"
      style={{ ["--marquee-duration" as string]: `${duration}s` }}
    >
      <div className="marquee-track">
        {run("a")}
        {run("b")}
      </div>
    </div>
  );
}
