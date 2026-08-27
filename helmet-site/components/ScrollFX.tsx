"use client";

import { useEffect } from "react";

/**
 * Owns every scroll effect: Lenis, chapter pinning, parallax, cross-fade,
 * line reveals, rail state, progress line.
 *
 * The markup it drives is server-rendered and found by data attribute, so the
 * page still reads and prints fine with JS off.
 */
export function ScrollFX() {
  useEffect(() => {
    let cleanup: (() => void) | undefined;
    let cancelled = false;

    const boot = async () => {
      const [{ gsap }, { ScrollTrigger }, { default: Lenis }] =
        await Promise.all([
          import("gsap"),
          import("gsap/ScrollTrigger"),
          import("lenis"),
        ]);
      if (cancelled) return;

      gsap.registerPlugin(ScrollTrigger);

      const reduced = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches;

      const sections = gsap.utils.toArray<HTMLElement>("[data-chapter]");
      const railItems = new Map<string, HTMLElement>(
        gsap.utils
          .toArray<HTMLElement>("[data-rail-item]")
          .map((el) => [el.dataset.railItem as string, el]),
      );
      const progress = document.querySelector<HTMLElement>("[data-progress]");

      const setActive = (n: string, active: boolean) => {
        const el = railItems.get(n);
        if (el) el.dataset.active = String(active);
      };

      /* --- reduced motion: no Lenis, no pinning, plain fades ------------- */
      if (reduced) {
        const io = new IntersectionObserver(
          (entries) => {
            for (const e of entries) {
              if (e.isIntersecting) e.target.classList.add("is-in");
              const n = (e.target.closest("[data-chapter]") as HTMLElement)
                ?.dataset.chapter;
              if (n) setActive(n, e.isIntersecting);
            }
          },
          { threshold: 0.35 },
        );
        document
          .querySelectorAll<HTMLElement>(".reveal-fade")
          .forEach((el) => io.observe(el));

        const onScroll = () => {
          const max = document.body.scrollHeight - window.innerHeight;
          const p = max > 0 ? window.scrollY / max : 0;
          if (progress) progress.style.transform = `scaleY(${p})`;
        };
        window.addEventListener("scroll", onScroll, { passive: true });
        onScroll();

        cleanup = () => {
          io.disconnect();
          window.removeEventListener("scroll", onScroll);
        };
        return;
      }

      /* --- smooth scroll ------------------------------------------------ */
      const lenis = new Lenis({ lerp: 0.08, wheelMultiplier: 1 });
      lenis.on("scroll", ScrollTrigger.update);
      const raf = (time: number) => lenis.raf(time * 1000);
      gsap.ticker.add(raf);
      gsap.ticker.lagSmoothing(0);

      const anchors = Array.from(
        document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]'),
      );
      const onAnchor = (e: MouseEvent) => {
        const href = (e.currentTarget as HTMLAnchorElement).getAttribute(
          "href",
        );
        if (!href || href === "#") return;
        const target = document.querySelector<HTMLElement>(href);
        if (!target) return;
        e.preventDefault();
        lenis.scrollTo(target, { offset: 0 });
      };
      anchors.forEach((a) => a.addEventListener("click", onAnchor));

      const pinned: { n: string; st: globalThis.ScrollTrigger }[] = [];

      const ctx = gsap.context(() => {
        sections.forEach((section, i) => {
          const media = section.querySelector<HTMLElement>("[data-media]");
          const copy = section.querySelector<HTMLElement>("[data-copy]");
          const lines = section.querySelectorAll<HTMLElement>(".line-in");
          const isFirst = i === 0;
          const isLast = i === sections.length - 1;
          if (!media || !copy) return;

          const tl = gsap.timeline({
            scrollTrigger: {
              trigger: section,
              start: "top top",
              end: "+=140%",
              scrub: true,
              // Pin the section, not its inner frame: the spacer has to land
              // in the flow itself or following chapters ride up over it.
              pin: section,
              pinSpacing: true,
              anticipatePin: 1,
              invalidateOnRefresh: true,
            },
          });

          // Image drifts at ~0.7x the copy's speed and creeps 1.0 -> 1.12.
          tl.fromTo(
            media,
            { yPercent: 3, scale: 1 },
            { yPercent: -11, scale: 1.12, ease: "none", duration: 1 },
            0,
          ).fromTo(
            copy,
            { yPercent: 0 },
            { yPercent: -18, ease: "none", duration: 1 },
            0,
          );

          // Cross-fade in and out through the black ground.
          if (!isFirst) {
            tl.fromTo(
              media,
              { opacity: 0 },
              { opacity: 1, ease: "none", duration: 0.14 },
              0,
            );
          }
          if (!isLast) {
            tl.to(media, { opacity: 0, ease: "none", duration: 0.14 }, 0.86);
            tl.to(copy, { opacity: 0, ease: "none", duration: 0.12 }, 0.86);
          }

          // Line-by-line reveal, 80ms apart. Chapter 01 does this in CSS.
          if (!isFirst) {
            gsap.set(lines, { y: 40, clipPath: "inset(100% 0 0 0)" });
            gsap.to(lines, {
              y: 0,
              clipPath: "inset(0% 0 0 0)",
              duration: 1,
              ease: "power3.out",
              stagger: 0.08,
              scrollTrigger: {
                trigger: section,
                start: "top 65%",
                once: true,
              },
            });
          }

          if (tl.scrollTrigger) {
            pinned.push({
              n: section.dataset.chapter as string,
              st: tl.scrollTrigger,
            });
          }
        });

        // One global trigger drives both the progress line and the rail, so
        // exactly one chapter is lit at a time — including over the marquees.
        ScrollTrigger.create({
          start: 0,
          end: "max",
          invalidateOnRefresh: true,
          onUpdate: (self) => {
            if (progress) progress.style.transform = `scaleY(${self.progress})`;
            const y = self.scroll();
            let active = pinned[0];
            for (const p of pinned) {
              if (y >= p.st.start - window.innerHeight * 0.5) active = p;
            }
            pinned.forEach((p) => setActive(p.n, p === active));
          },
        });
      });

      // Late-loading images change the document height.
      const onLoad = () => ScrollTrigger.refresh();
      window.addEventListener("load", onLoad);

      cleanup = () => {
        window.removeEventListener("load", onLoad);
        anchors.forEach((a) => a.removeEventListener("click", onAnchor));
        gsap.ticker.remove(raf);
        lenis.destroy();
        ctx.revert();
        ScrollTrigger.getAll().forEach((t) => t.kill());
      };
    };

    // GSAP + Lenis are ~50KB of parse work that nothing above the fold needs;
    // hold them until the main thread is free so they don't cost LCP/TBT.
    let idle: number | undefined;
    let timer: number | undefined;
    if (typeof window.requestIdleCallback === "function") {
      idle = window.requestIdleCallback(() => void boot(), { timeout: 1200 });
    } else {
      timer = window.setTimeout(() => void boot(), 300);
    }

    return () => {
      cancelled = true;
      if (idle !== undefined) window.cancelIdleCallback?.(idle);
      if (timer !== undefined) window.clearTimeout(timer);
      cleanup?.();
    };
  }, []);

  return null;
}
