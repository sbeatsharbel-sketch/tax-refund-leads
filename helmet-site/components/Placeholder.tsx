/** Shown when the photograph for a chapter has not been dropped in yet. */
export function Placeholder({ file }: { file: string }) {
  return (
    <div className="flex h-full w-full items-start justify-center bg-[#101012] pt-[32svh]">
      <div
        className="flex flex-col items-center gap-3 px-6 text-center"
        style={{ fontFamily: "var(--font-mono)" }}
      >
        <span className="text-[11px] uppercase tracking-[0.2em] text-bone/30">
          Image not found
        </span>
        <span className="text-[11px] tracking-[0.12em] text-bone/55 break-all">
          /public/img/{file}
        </span>
      </div>
    </div>
  );
}
