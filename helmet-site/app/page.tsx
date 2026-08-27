import { CHAPTERS, PRODUCT_NAME } from "@/data/site";
import { Chapter } from "@/components/Chapter";
import { Marquee } from "@/components/Marquee";
import { Rail } from "@/components/Rail";
import { SpecList } from "@/components/SpecList";
import { Cursor } from "@/components/Cursor";
import { ScrollFX } from "@/components/ScrollFX";

export default function Page() {
  const last = CHAPTERS.length - 1;

  return (
    <>
      <ScrollFX />
      <Cursor />
      <Rail />

      <header className="pointer-events-none fixed top-0 right-0 left-0 z-40 flex items-center justify-between px-6 py-6 sm:px-10">
        <span className="meta">{PRODUCT_NAME}</span>
        <span className="meta hidden sm:block">Carbon / Six chapters</span>
      </header>

      <main>
        {CHAPTERS.map((c, i) => (
          <div key={c.n}>
            <Chapter chapter={c} index={i}>
              {i === last && (
                <>
                  <SpecList />
                  <div className="mt-8">
                    <a
                      href="#chapter-01"
                      data-cursor
                      className="group inline-flex items-center gap-3 border border-bone/25 px-6 py-4 transition-colors duration-300 hover:border-amber hover:bg-amber/10"
                    >
                      <span className="meta !opacity-100">Ride it again</span>
                      <span
                        aria-hidden
                        className="text-amber transition-transform duration-300 group-hover:-translate-y-0.5"
                      >
                        ↑
                      </span>
                    </a>
                  </div>
                </>
              )}
            </Chapter>
            {i !== last && <Marquee duration={38 + i * 3} />}
          </div>
        ))}
      </main>

      <footer className="relative border-t border-bone/10 px-6 py-16 sm:px-10">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <span className="meta">{PRODUCT_NAME}</span>
          <span className="meta">
            Photography by the owner — no stock imagery
          </span>
        </div>
      </footer>
    </>
  );
}
