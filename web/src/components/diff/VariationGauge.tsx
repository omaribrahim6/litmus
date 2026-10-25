import type { DiffItem } from "@/lib/types";
import { fmtNumber } from "@/lib/format";

/** Where candidate and control sit relative to the reference runs' normal variation. */
export function VariationGauge({ item, height = 34, labels = false, decimals = 1 }: { item: DiffItem; height?: number; labels?: boolean; decimals?: number }) {
  const c = typeof item.candidate.value === "number" ? item.candidate.value : null;
  const k = typeof item.control.value === "number" ? item.control.value : null;
  const refs = (item.reference?.values ?? []).map((v) => Number(v.value)).filter((v) => Number.isFinite(v));
  if (c === null || k === null) return null;
  const mean = item.reference?.mean ?? (refs.length ? refs.reduce((a, b) => a + b, 0) / refs.length : k);
  const band = item.band ?? 0;
  const lo0 = Math.min(c, k, ...refs, k - band, mean - band);
  const hi0 = Math.max(c, k, ...refs, k + band, mean + band);
  const pad = (hi0 - lo0 || Math.abs(k) || 1) * 0.15;
  const lo = lo0 - pad;
  const hi = hi0 + pad;
  const W = 300;
  const x = (v: number) => ((v - lo) / (hi - lo)) * W;
  const mid = labels ? height / 2 + 2 : height / 2;
  return (
    <svg viewBox={`0 0 ${W} ${height}`} className="h-auto w-full overflow-visible" role="img"
      aria-label={`Candidate ${fmtNumber(c, decimals)}, control ${fmtNumber(k, decimals)}, normal variation plus or minus ${fmtNumber(band, decimals)}`}>
      {/* band of normal variation centered on the control */}
      <rect x={x(k - band)} y={mid - 7} width={Math.max(1, x(k + band) - x(k - band))} height={14} rx={3} fill="var(--sunken)" stroke="var(--rule-strong)" strokeWidth={0.75} />
      <line x1={0} x2={W} y1={mid} y2={mid} stroke="var(--rule)" />
      {refs.map((v, i) => <line key={i} x1={x(v)} x2={x(v)} y1={mid - 4} y2={mid + 4} stroke="var(--ink-3)" strokeWidth={1.25} />)}
      <circle cx={x(k)} cy={mid} r={5} fill="var(--base)" stroke="var(--surface)" strokeWidth={1.5} />
      <circle cx={x(c)} cy={mid} r={5.5} fill="var(--accent)" stroke="var(--surface)" strokeWidth={1.5} />
      {labels ? (
        <>
          <text x={x(k)} y={mid - 11} textAnchor="middle" fontSize={10.5} fill="var(--base)">control</text>
          <text x={x(c)} y={mid + 21} textAnchor="middle" fontSize={10.5} fill="var(--accent)">candidate</text>
        </>
      ) : null}
    </svg>
  );
}
