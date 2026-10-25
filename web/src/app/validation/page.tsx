import { Suspense } from "react";
import type { Metadata } from "next";
import { connection } from "next/server";
import { listAnalyses } from "@/lib/data";
import { AskContext } from "@/components/ask/AskProvider";
import { Skeleton } from "@/components/ui";
import { fmtNumber } from "@/lib/format";

export const metadata: Metadata = { title: "Validation" };

interface Validation {
  experiment: string;
  runs: number;
  synthetic_runs: number;
  flip_timing: { n: number; within_1s: number; mean_abs_error_s: number | null; max_abs_error_s: number | null; sources: string[]; rows: { run: string; detected_s: number; truth_s: number; error_s: number; source: string }[] };
  probe_agreement: { n: number; agree: number; mean_abs_delta_s: number | null; tolerance_s: number; rows: { run: string; delta_s: number; agree: boolean }[] };
  hidden_faults: { n: number; found: number; rows: { run: string; planted: string; top_difference: string | null; found: boolean }[] };
  false_alarms: { pairs: number; pairs_with_alarm: number; total_alarms: number; comparisons?: number; rows: { a: string; b: string; false_alarms: string[] }[] };
  traceability: { claims: number; traced: number; flagged_gaps: number; percent: number | null };
}

function Figure({ value, of, unit, children }: { value: React.ReactNode; of?: React.ReactNode; unit?: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-rule pt-4">
      <div className="flex items-baseline gap-1.5">
        <span className="num text-[30px] leading-none">{value}</span>
        {of !== undefined ? <span className="num text-[16px] text-ink-2">/ {of}</span> : null}
        {unit ? <span className="text-[14px] text-ink-2">{unit}</span> : null}
      </div>
      <div className="mt-2 max-w-[42ch] text-[13.5px] leading-snug text-ink-2">{children}</div>
    </div>
  );
}

async function Content() {
  await connection();
  const [latest] = await listAnalyses("validation");
  const v = latest?.content as Validation | undefined;
  if (!v) {
    return (
      <p className="mt-8 rounded-xl border border-dashed border-rule-strong p-6 text-[14px] text-ink-2">
        No validation run yet. Record reference runs, fill <code className="num text-[12px]">demo/validation/manual_flips.csv</code> from video review,
        then run <code className="num text-[12px]">python -m litmus_worker.validate</code>.
      </p>
    );
  }
  const ft = v.flip_timing;
  const pa = v.probe_agreement;
  return (
    <>
      {v.synthetic_runs ? (
        <p className="mt-6 rounded-lg border border-dashed border-ink-3 px-4 py-2.5 text-[13.5px] text-ink-2">
          {v.synthetic_runs} of {v.runs} runs in this validation are synthetic test data. Numbers from real station runs replace them as they are recorded.
        </p>
      ) : null}
      <section className="mt-8 grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
        <Figure value={ft.within_1s} of={ft.n}>
          detected color flips within 1 s of {ft.sources.join(" and ") || "ground truth"}. Mean error {fmtNumber(ft.mean_abs_error_s, 2)} s, worst {fmtNumber(ft.max_abs_error_s, 2)} s.
        </Figure>
        <Figure value={pa.agree} of={pa.n}>
          runs where the light-sensor colorimeter confirmed the camera’s flip within {pa.tolerance_s} s. Mean gap {fmtNumber(pa.mean_abs_delta_s, 2)} s.
        </Figure>
        <Figure value={v.hidden_faults.found} of={v.hidden_faults.n}>
          planted confounds surfaced as the top difference by the diff engine.
        </Figure>
        <Figure value={v.false_alarms.total_alarms} of={v.false_alarms.comparisons} unit="comparisons">
          variables flagged as different between reference runs that followed the same protocol ({v.false_alarms.pairs} pairs). These are false alarms.
        </Figure>
        <Figure value={v.traceability.percent != null ? `${fmtNumber(v.traceability.percent, 1)}%` : "n/a"}>
          of {v.traceability.claims} AI-written claims and report sentences cite evidence in the record{v.traceability.flagged_gaps ? `; ${v.traceability.flagged_gaps} unsupported sentences were flagged, not shown as fact` : ""}.
        </Figure>
        <Figure value={0}>
          probabilities shown anywhere. Claims use four labels: observed, possible explanation, contradicted, missing evidence.
        </Figure>
      </section>

      <section className="mt-14 grid gap-10 lg:grid-cols-2">
        <div>
          <h2 className="text-[16px] font-semibold">Flip timing, run by run</h2>
          <table className="mt-3 w-full text-[13.5px]">
            <thead className="text-left text-[12px] text-ink-2"><tr><th className="py-1.5 font-medium">Run</th><th className="font-medium">Detected</th><th className="font-medium">Truth</th><th className="font-medium">Error</th></tr></thead>
            <tbody>
              {ft.rows.map((r) => (
                <tr key={r.run} className="border-t border-rule">
                  <td className="py-1.5">{r.run}</td>
                  <td className="num">{fmtNumber(r.detected_s, 2)} s</td>
                  <td className="num">{fmtNumber(r.truth_s, 2)} s</td>
                  <td className={
um ${Math.abs(r.error_s) > 1 ? "text-accent" : ""}`}>{r.error_s > 0 ? "+" : ""}{fmtNumber(r.error_s, 2)} s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h2 className="text-[16px] font-semibold">Reference pairs compared</h2>
          <table className="mt-3 w-full text-[13.5px]">
            <thead className="text-left text-[12px] text-ink-2"><tr><th className="py-1.5 font-medium">Pair</th><th className="font-medium">Flagged as notable</th></tr></thead>
            <tbody>
              {v.false_alarms.rows.map((r) => (
                <tr key={`${r.a}-${r.b}`} className="border-t border-rule">
                  <td className="py-1.5">{r.a} vs {r.b}</td>
                  <td className={r.false_alarms.length ? "text-accent" : "text-ink-2"}>{r.false_alarms.length ? r.false_alarms.join(", ") : "nothing"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

export default function Page() {
  return (
    <div className="mx-auto max-w-[1080px] px-8 pb-24 pt-10 max-md:px-4">
      <AskContext page="validation" description="Validation numbers" />
      <h1 className="wide text-[30px] font-semibold tracking-[-0.015em]">How we know Litmus is right</h1>
      <p className="mt-2 max-w-[66ch] text-[15px] text-ink-2">
        The station is checked against independent evidence: a light sensor shining through the tube, manual review of the video,
        confounds we planted on purpose, and pairs of runs that should look identical.
      </p>
      <Suspense fallback={<div className="mt-8 grid gap-8 sm:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>}>
        <Content />
      </Suspense>
    </div>
  );
}
