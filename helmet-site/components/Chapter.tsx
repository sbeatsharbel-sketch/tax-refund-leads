import Image from "next/image";
import type { Chapter as ChapterType } from "@/data/site";
import { imageInfo } from "@/lib/images";
import { Grain } from "./Grain";
import { Placeholder } from "./Placeholder";

export function Chapter({
  chapter,
  index,
  children,
}: {
  chapter: ChapterType;
  index: number;
  children?: React.ReactNode;
}) {
  const img = imageInfo(chapter.file);
  const isHero = index === 0;

  return (
    <section
      className="chapter"
      data-chapter={chapter.n}
      id={`chapter-${chapter.n}`}
      aria-labelledby={`h-${chapter.n}`}
    >
      <div className="chapter-pin" data-pin>
        <div className="chapter-media" data-media>
          {img.exists ? (
            <Image
              src={img.src}
              alt=""
              fill
              sizes="100vw"
              quality={72}
              priority={isHero}
              loading={isHero ? "eager" : "lazy"}
              className="object-cover"
            />
          ) : (
            <Placeholder file={chapter.file} />
          )}
        </div>

        <Grain />

        <div className="absolute inset-0 z-[25] flex items-end">
          <div
            className="chapter-copy reveal-fade w-full px-5 pb-14 pl-[calc(env(safe-area-inset-left)+3.25rem)] sm:px-10 sm:pb-20 sm:pl-28 lg:pl-32"
            data-copy
          >
            <p className="meta mb-6">
              <span className="line-mask">
                <span
                  className="line-in"
                  data-hero={isHero ? "" : undefined}
                  style={{ "--i": 0 } as React.CSSProperties}
                >
                  {chapter.n} — {chapter.label}
                </span>
              </span>
            </p>

            <h2 id={`h-${chapter.n}`} className="display max-w-[16ch]">
              {chapter.lines.map((line, i) => (
                <span className="line-mask" key={i}>
                  <span
                    className="line-in"
                    data-hero={isHero ? "" : undefined}
                    style={{ "--i": i + 1 } as React.CSSProperties}
                  >
                    {line.map((part, j) =>
                      part.italic ? (
                        <em key={j}>{part.text}</em>
                      ) : (
                        <span key={j}>{part.text}</span>
                      ),
                    )}
                  </span>
                </span>
              ))}
            </h2>

            {children}
          </div>
        </div>
      </div>
    </section>
  );
}
