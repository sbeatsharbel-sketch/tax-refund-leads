import { SPECS } from "@/data/site";

export function SpecList() {
  if (SPECS.length === 0) {
    return (
      <dl className="mt-10 max-w-md border-t border-bone/15">
        <div className="flex items-baseline justify-between gap-6 border-b border-bone/10 py-3">
          <dt className="meta">Spec sheet</dt>
          <dd className="meta text-right !opacity-100 text-amber">
            Awaiting figures
          </dd>
        </div>
        <p className="meta mt-4 !tracking-[0.12em] leading-relaxed">
          No numbers are printed here because none were supplied. Add them to
          SPECS in data/site.ts.
        </p>
      </dl>
    );
  }

  return (
    <dl className="mt-10 max-w-md border-t border-bone/15">
      {SPECS.map((s) => (
        <div
          key={s.label}
          className="flex items-baseline justify-between gap-6 border-b border-bone/10 py-3"
        >
          <dt className="meta">{s.label}</dt>
          <dd className="meta text-right !opacity-100">{s.value}</dd>
        </div>
      ))}
    </dl>
  );
}
