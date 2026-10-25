import Link from "next/link";
import type { Run } from "@/lib/types";
import { fmtNumber } from "@/lib/format";
import { ROLE_DOT } from "@/components/ui";

/** Every run's result on one number line, with the reference runs' normal variation shaded. */
export function ResultLine({ runs, unit, label }: { runs: Run[]; unit?: string; label: string }) {
  const pts = runs
    .filter((r) => r.result?.value != null)
    .map((r) => ({ run: r, v: r.result!.value as number }));
  if (pts.length === 0) {
    return <p className="text-[14px] text-ink-2">Results appear here once a run reaches its color flip.</p>;
  }
  const refs = pts.filter((p) => p.run.role === "reference").map((p) => p.v);
  const mean = refs.length ? refs.reduce((a, b) => a + b, 0) / refs.length : null;
  const sd = refs.length >= 3 ? Math.sqrt(refs.reduce((a, b) => a + (b - mean!) ** 2, 0) / (refs.length - 1)) : null;
  const band = sd != null ? 2 * sd : refs.length === 2 ? Math.abs(refs[0] - refs[1]) : null;

  const values = pts.map((p) => p.v).concat(mean != null && band != null ? [mean - band, mean + band] : []);
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  const pad = (hi - lo || 1) * 0.12;
  lo -= pad;
  hi += pad;
  const W = 900;
  const x = (v: number) => ((v - lo) / (hi - lo)) * W;

  // Stack runs that share a value so every run stays visible.
  const stacks = new Map<string, number>();
  const placed = pts.map((p) => {
    const k = p.v.toFixed(3);
    const n = stacks.get(k) ?? 0;
    stacks.set(k, n + 1);
    return { ...p, stack: n };
  });
  const maxStack = Math.max(...placed.map((p) => p.stack));
  const H = 64 + maxStack * 14;
  const baseY = H - 26;
  const ticks = niceTicks(lo, hi, 6);

  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={`${label} for every run`}>
        {mean != null && band != null ? (
          <g>
            <rect x={x(mean - band)} y={8} width={x(mean + band) - x(mean - band)} height={baseY - 8} fill="var(--sunken)" />
            <line x1={x(mean)} x2={x(mean)} y1={8} y2={baseY} stroke="var(--ink-3)" strokeDasharray="3 3" />
          </g>
        ) : null}
        <line x1={0} x2={W} y1={baseY} y2={baseY} stroke="var(--rule-strong)" />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={baseY} y2={baseY + 5} stroke="var(--rule-strong)" />
            <text x={x(t)} y={baseY + 19} textAnchor="middle" className="num" fontSize={11} fill="var(--ink-2)">{fmtNumber(t, 2)}</text>
          </g>
        ))}
        {placed.map(({ run, v, stack }) => {
          const cy = baseY - 12 - stack * 14;
          const emphasized = run.role === "candidate" || run.role === "control";
          return (
            <Link key={run.id} href={`/runs/${run.id}`}>
              <g className="cursor-pointer">
                <title>{`${run.label}: ${fmtNumber(v)} ${unit ?? ""}`}</title>
                <circle cx={x(v)} cy={cy} r={emphasized ? 6.5 : 5} fill={ROLE_DOT[run.role]} stroke="var(--paper)" strokeWidth={2} />
                {emphasized ? (
                  <text x={x(v) + 11} y={cy + 4} fontSize={12.5} fontWeight={600} fill={ROLE_DOT[run.role]}>{run.label}</text>
                ) : null}
              </g>
            </Link>
          );
        })}
      </svg>
      <figcaption className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-[12.5px] text-ink-2">
        <span>{label} ({unit}) per run</span>
        {band != null ? <span><span className="mr-1.5 inline-block h-2.5 w-4 translate-y-[1px] rounded-sm bg-sunken ring-1 ring-rule" />Normal variation: reference mean ± {sd != null ? "2 SD" : "range"} across {refs.length} runs</span> : <span>Record two or more reference runs to see normal variation.</span>}
      </figcaption>
    </figure>
  );
}

function niceTicks(lo: number, hi: number, n: number): number[] {
  const span = hi - lo;
  const raw = span / n;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? mag * 10;
  const out = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) out.push(Number(t.toFixed(6)));
  return out;
}
