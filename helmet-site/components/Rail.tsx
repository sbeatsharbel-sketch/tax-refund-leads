import { CHAPTERS } from "@/data/site";

/**
 * Fixed left rail. Server-rendered; ScrollFX toggles [data-active] and drives
 * the progress line, so there is no client state here.
 */
export function Rail() {
  return (
    <nav
      className="pointer-events-none fixed top-1/2 left-3 z-40 -translate-y-1/2 sm:left-6"
      aria-label="Chapters"
      data-rail
    >
      {/* Soft scrim so the numbers stay legible over photography and over
          the marquee strips that scroll past behind them. */}
      <div
        className="absolute -inset-y-10 -left-6 right-[-1.5rem] bg-gradient-to-r from-ink/85 via-ink/45 to-transparent [mask-image:linear-gradient(to_bottom,transparent,#000_18%,#000_82%,transparent)]"
        aria-hidden
      />

      <div className="relative flex items-stretch gap-4">
        <div className="relative w-px bg-bone/15">
          <div
            className="absolute top-0 left-0 h-full w-px origin-top bg-amber"
            data-progress
            style={{ transform: "scaleY(0)" }}
          />
        </div>

        <ol className="flex flex-col justify-between gap-5">
          {CHAPTERS.map((c) => (
            <li key={c.n}>
              <a
                href={`#chapter-${c.n}`}
                className="meta pointer-events-auto block !opacity-25 transition-opacity duration-500 data-[active=true]:!opacity-100"
                data-rail-item={c.n}
              >
                {c.n}
              </a>
            </li>
          ))}
        </ol>
      </div>
    </nav>
  );
}
