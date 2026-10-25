"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import clsx from "clsx";
import { ChevronRight, FileText, GitBranch } from "lucide-react";
import type { Analysis, DiffItem, VerdictContent } from "@/lib/types";
import { fmtNumber, LABEL_TEXT } from "@/lib/format";
import { Blame } from "@/components/evidence/Blame";
import { LabelChip, ProvenanceIcon } from "@/components/ui";
import { VariationGauge } from "./VariationGauge";
import { FramePair } from "./FramePair";

const STATUS_TEXT: Record<DiffItem["status"], string> = {
  notable: "Outside normal variation",
  within_normal: "Within normal variation",
  same: "Same",
  missing_evidence: "Not measured",
};

const STAMP: Record<string, { text: string; cls: string }> = {
  contradicted: { text: "Not supported", cls: "border-accent text-accent" },
  possible_explanation: { text: "Possible, not isolated", cls: "border-amber text-amber" },
  missing_evidence: { text: "Can't be checked", cls: "border-ink-3 text-ink-2 border-dashed" },
};

function ratioText(i: DiffItem): string | null {
  if (i.type !== "numeric" || i.ratio == null || i.status === "same") return null;
  return `${fmtNumber(i.ratio, 1)}× normal variation`;
}

function DiffRow({ item, cand, ctrl, defaultOpen }: { item: DiffItem; cand: string; ctrl: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen);
  const notable = item.status === "notable";
  return (
    <li className="border-b border-rule last:border-b-0">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="grid w-full grid-cols-[18px_minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(120px,1.1fr)] items-center gap-4 px-4 py-3 text-left hover:bg-paper max-md:grid-cols-[18px_1fr_1fr]">
        <ChevronRight size={15} className={clsx("text-ink-3 transition-transform", open && "rotate-90")} />
        <span className="min-w-0">
          <span className={clsx("block truncate text-[14.5px]", notable && "font-semibold")}>{item.label}</span>
          <span className={clsx("text-[12px]", notable ? "text-accent" : item.status === "missing_evidence" ? "text-ink-3" : "text-ink-2")}>
            {STATUS_TEXT[item.status]}{ratioText(item) ? `, ${ratioText(item)}` : ""}
          </span>
        </span>
        <span className="min-w-0 max-md:hidden">
          <span className="block text-[11.5px] text-ink-3">{cand}</span>
          <span className="num flex items-center gap-1.5 truncate text-[13.5px]">{item.candidate.display}<ProvenanceIcon p={item.candidate.provenance} /></span>
        </span>
        <span className="min-w-0 max-md:hidden">
          <span className="block text-[11.5px] text-ink-3">{ctrl}</span>
          <span className="num flex items-center gap-1.5 truncate text-[13.5px]">{item.control.display}<ProvenanceIcon p={item.control.provenance} /></span>
        </span>
        <span className="max-md:hidden">
          {item.type === "numeric" && item.status !== "missing_evidence" ? <VariationGauge item={item} height={22} /> : null}
        </span>
      </button>
      {open ? (
        <div className="space-y-4 px-4 pb-5 pl-[52px]">
          <p className="max-w-[72ch] text-[14px] leading-relaxed text-ink-2">{item.explanation}</p>
          {item.status !== "missing_evidence" ? (
            <div className="max-w-[720px]">
              <FramePair left={item.candidate.evidence_ids} right={item.control.evidence_ids} leftLabel={cand} rightLabel={ctrl} />
            </div>
          ) : (
            <p className="text-[13px] text-ink-2">Nothing was recorded for this variable, so it is listed as missing evidence rather than assumed to be equal.</p>
          )}
          {item.reference?.values.length ? (
            <p className="text-[12.5px] text-ink-3">
              Reference runs: {item.reference.values.map((v) => `${v.label} ${typeof v.value === "number" ? fmtNumber(v.value, 2) : v.value}`).join(", ")}.
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

export function DiffView({ verdict, reveal }: { verdict: Analysis<VerdictContent>; reveal: boolean }) {
  const router = useRouter();
  const v = verdict.content;
  const d = v.diff;
  const r = v.result;
  const cand = v.candidate.label;
  const ctrl = v.controls.map((c) => c.label).join(", ");
  const a = v.assumed_cause;
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exclude, setExclude] = useState<string>("");

  // Drop a claim that repeats an earlier one with the same label on mostly the same evidence.
  const claims = v.claims.filter((c, idx) => !v.claims.slice(0, idx).some((p) => {
    if (p.label !== c.label) return false;
    const shared = c.evidence_ids.filter((e) => !e.startsWith("run:") && p.evidence_ids.includes(e)).length;
    return shared > 0 && shared >= c.evidence_ids.filter((e) => !e.startsWith("run:")).length / 2;
  }));
  const conditions = d.differences.filter((i) => i.role !== "outcome");
  const notable = conditions.filter((i) => i.status === "notable");
  const normal = conditions.filter((i) => i.status === "within_normal" || i.status === "same");
  const missing = conditions.filter((i) => i.status === "missing_evidence");
  const outcomes = d.differences.filter((i) => i.role === "outcome");
  const topConfound = notable.find((i) => !a.variable_keys.includes(i.key));
  const mapped = d.differences.filter((i) => a.variable_keys.includes(i.key));
  const stamp = a.label ? STAMP[a.label] : null;
  const decimals = 1;

  const makeReport = async () => {
    setBusy("report");
    setError(null);
    const res = await fetch("/api/report", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ verdict_id: verdict.id }) });
    const data = await res.json();
    if (!res.ok) {
      setBusy(null);
      setError(data.error);
      return;
    }
    router.push(`/reports/${data.report_id}`);
  };

  const branch = async () => {
    if (!exclude) return;
    setBusy("branch");
    setError(null);
    const res = await fetch("/api/branch", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ analysis_id: verdict.id, exclude: [exclude] }) });
    const data = await res.json();
    if (!res.ok) {
      setBusy(null);
      setError(data.error);
      return;
    }
    router.push(`/compare/${data.verdict_id}?reveal=1`);
  };

  return (
    <div className="mx-auto max-w-[1180px] px-8 pb-24 pt-7 max-md:px-4">
      <nav className="mb-3 text-[13px] text-ink-2">
        <Link href="/" className="hover:text-ink">{d.experiment.name}</Link>
        <span className="mx-1.5 text-ink-3">/</span>
        <Link href={`/runs/${v.candidate.run_id}`} className="hover:text-ink">{cand}</Link>
        <span className="mx-1.5 text-ink-3">/</span>
        <span>Litmus test</span>
      </nav>

      {d.branch ? (
        <p className="mb-4 inline-flex items-center gap-2 rounded-md border border-amber/40 bg-amber-soft px-3 py-1.5 text-[13px] text-amber">
          <GitBranch size={14} /> Branch: reanalysis without {d.branch.excluded_run_ids.length} run. {d.branch.note}
        </p>
      ) : null}

      {/* The result and whether it is outside normal variation */}
      <section className="grid items-end gap-8 border-b border-rule pb-8 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div>
          <h1 className="wide text-[40px] font-semibold leading-[1.05] tracking-[-0.02em]">
            {cand} <span className="font-normal text-ink-3">vs</span> {ctrl}
          </h1>
          <p className="mt-3 text-[15px] text-ink-2">
            Compared across {d.differences.length} recorded variables, judged against {d.references.length} reference runs.
          </p>
        </div>
        <div className="rounded-xl border border-rule bg-surface p-5">
          <div className="text-[12.5px] text-ink-2">{r.label}</div>
          <div className="mt-1 flex items-baseline gap-3">
            <Blame ids={r.candidate.evidence_ids} title={`${cand}: additions up to the detected flip`} quiet>
              <span className="num text-[34px] leading-none text-accent">{r.candidate.display}</span>
            </Blame>
            <span className="text-ink-3">vs</span>
            <Blame ids={r.control.evidence_ids} title={`${ctrl}: additions up to the detected flip`} quiet>
              <span className="num text-[22px] text-base">{r.control.display}</span>
            </Blame>
          </div>
          {r.headline ? <p className="mt-2 text-[15px] font-medium">{r.headline}</p> : null}
          <div className="mt-3"><VariationGauge item={r} labels decimals={decimals} height={46} /></div>
          <p className={clsx("mt-1 text-[12.5px]", r.status === "notable" ? "text-ink" : "text-ink-2")}>
            {r.status === "notable"
              ? `Outside normal variation (±${fmtNumber(r.band, 2)} ${r.unit ?? ""}). The difference is real; the question is why.`
              : r.status === "missing_evidence" ? "One of the runs has no result." : `Within normal variation (±${fmtNumber(r.band, 2)} ${r.unit ?? ""}). This difference could be run-to-run noise.`}
          </p>
        </div>
      </section>

      {/* Assumed cause vs the record */}
      <section className="grid gap-5 py-8 lg:grid-cols-2">
        <article className="relative overflow-hidden rounded-xl border border-rule bg-surface p-6">
          <h2 className="text-[13px] font-medium text-ink-2">What the researcher assumed</h2>
          {a.text ? (
            <>
              <Blame ids={a.evidence_ids.filter((e) => e.startsWith("run:"))} title="The assumed cause, as entered" quiet className="mt-3 block">
                <blockquote className="pr-28 text-[22px] leading-snug tracking-[-0.01em]">“{a.text}”</blockquote>
              </Blame>
              {mapped.length ? (
                <p className="mt-4 text-[14px] text-ink-2">
                  Checked against:{" "}
                  {mapped.map((m, i) => (
                    <span key={m.key}>
                      {i ? ", " : ""}
                      <span className={clsx("text-ink", a.label === "contradicted" && (reveal ? "struck" : "line-through decoration-accent decoration-2"))}>{m.label.toLowerCase()}</span>
                    </span>
                  ))}
                </p>
              ) : null}
              {stamp ? (
                <span className={clsx("absolute right-6 top-6 rounded-md border-2 px-3 py-1 text-[15px] font-bold tracking-wide", stamp.cls)}
                  style={{ transform: "rotate(-6deg)", animation: reveal ? "stamp-in 520ms 650ms cubic-bezier(.2,.8,.2,1.2) both" : undefined }}>
                  {stamp.text}
                </span>
              ) : null}
            </>
          ) : (
            <p className="mt-3 text-[15px] text-ink-2">No assumed cause was entered for {cand}. Add one on the run page to have it checked.</p>
          )}
        </article>

        <article className="rounded-xl border border-ink/80 bg-surface p-6 shadow-panel">
          <h2 className="text-[13px] font-medium text-ink-2">What the record shows</h2>
          <p className="mt-3 text-[18px] leading-snug">{v.headline}</p>
          {a.statement ? (
            <Blame ids={a.evidence_ids} title="Measurements behind the verdict on the assumed cause" className="mt-3 block text-[14.5px] leading-relaxed text-ink-2">
              {a.statement}
            </Blame>
          ) : null}
          {topConfound ? (
            <div className="mt-5">
              <p className="mb-2 text-[14px]"><span className="font-semibold">{topConfound.label}</span> <span className="text-ink-2">differed: {topConfound.candidate.display} vs {topConfound.control.display}</span></p>
              <FramePair left={topConfound.candidate.evidence_ids} right={topConfound.control.evidence_ids} leftLabel={cand} rightLabel={ctrl} />
            </div>
          ) : null}
        </article>
      </section>

      {/* Every variable */}
      <section className="space-y-6">
        <div className="flex items-baseline justify-between">
          <h2 className="text-[18px] font-semibold">Every recorded variable</h2>
          <p className="text-[13px] text-ink-2">Ranked by how far outside normal variation they fall. Open a row to see both runs’ evidence.</p>
        </div>
        {[{ title: "Outside normal variation", items: notable, open: true },
          { title: "Within normal variation", items: normal },
          { title: "Missing evidence", items: missing },
          { title: "Outcomes (consequences of the result, not causes)", items: outcomes }].map((g) =>
          g.items.length ? (
            <div key={g.title}>
              <h3 className="mb-2 text-[13.5px] font-medium text-ink-2">{g.title} <span className="num text-ink-3">{g.items.length}</span></h3>
              <ul className="rounded-xl border border-rule bg-surface">
                {g.items.map((i, n) => <DiffRow key={i.key} item={i} cand={cand} ctrl={ctrl} defaultOpen={g.open && n === 0 && !topConfound} />)}
              </ul>
            </div>
          ) : null,
        )}
      </section>

      {/* Claims */}
      <section className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div>
          <h2 className="text-[18px] font-semibold">Verdict, claim by claim</h2>
          <p className="mt-1 text-[13px] text-ink-2">
            {claims.length} claims, every one citing evidence. {v.validator.rejected ? `${v.validator.rejected} rejected by the validator.` : "None rejected."}
            {v.validator.relabeled ? ` ${v.validator.relabeled} relabeled for lack of a measurement.` : ""} No probabilities are used.
          </p>
          <ul className="mt-4 space-y-3">
            {claims.map((c, i) => (
              <li key={i} className="flex gap-3">
                <LabelChip label={c.label} className="mt-[2px]" />
                <Blame ids={c.evidence_ids} title={LABEL_TEXT[c.label]} className="text-[14.5px] leading-relaxed">{c.text}</Blame>
              </li>
            ))}
          </ul>
          {v.rejected_claims.length ? (
            <details className="mt-4 text-[13px] text-ink-2">
              <summary className="cursor-pointer">Rejected by the validator ({v.rejected_claims.length})</summary>
              <ul className="mt-2 space-y-1.5">
                {v.rejected_claims.map((c, i) => <li key={i}><span className="line-through">{c.text}</span> <span className="text-accent">{c.reason}</span></li>)}
              </ul>
            </details>
          ) : null}
        </div>

        <aside className="space-y-5">
          <div className="rounded-xl border border-rule bg-surface p-5">
            <h2 className="text-[15px] font-semibold">Before building on this, run this check</h2>
            <p className="mt-2 text-[14px] leading-relaxed">{v.follow_up.check}</p>
            <dl className="mt-4 space-y-3">
              {v.follow_up.outcomes.map((o, i) => (
                <div key={i} className="border-l-2 pl-3" style={{ borderColor: o.means === "supported" ? "var(--ok)" : o.means === "explained_by_confound" ? "var(--accent)" : "var(--ink-3)" }}>
                  <dt className="text-[13px] text-ink-2">If {o.if}</dt>
                  <dd className="text-[14px]">{o.text}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="no-print space-y-3 rounded-xl border border-rule p-5">
            <button type="button" onClick={makeReport} disabled={!!busy}
              className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-ink px-4 py-2 text-[14px] font-medium text-paper disabled:opacity-50">
              <FileText size={15} /> {busy === "report" ? "Writing the report with receipts" : "Write the lab report"}
            </button>
            <div className="flex gap-2">
              <select value={exclude} onChange={(e) => setExclude(e.target.value)} aria-label="Run to leave out"
                className="min-w-0 flex-1 rounded-md border border-rule-strong bg-surface px-2 py-1.5 text-[13px]">
                <option value="">Reanalyze without a run…</option>
                {d.references.map((rr) => <option key={rr.run_id} value={rr.run_id}>Without {rr.label}</option>)}
              </select>
              <button type="button" onClick={branch} disabled={!exclude || !!busy}
                className="inline-flex items-center gap-1.5 rounded-md border border-rule-strong px-3 py-1.5 text-[13px] font-medium disabled:opacity-40">
                <GitBranch size={14} /> {busy === "branch" ? "Branching" : "Branch"}
              </button>
            </div>
            <p className="text-[12px] text-ink-3">A branch is a new analysis. The original runs and this verdict are never changed.</p>
            {error ? <p className="text-[13px] text-accent">{error}</p> : null}
          </div>
          <p className="text-[12px] text-ink-3">Verdict written by {v.model === "deterministic-template" ? "the template engine (Gemini offline)" : v.model}; labels decided by code from the diff.</p>
        </aside>
      </section>
    </div>
  );
}
