"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { Download, Printer } from "lucide-react";
import type { Analysis, Evidence, ReportContent } from "@/lib/types";
import { fetchEvidence, useEvidence } from "@/components/evidence/EvidenceProvider";
import { ProvenanceIcon } from "@/components/ui";
import { KIND_TEXT } from "@/lib/format";

function Receipt({ e, n }: { e: Evidence | null; n: number }) {
  if (!e) return <li className="text-[12px] text-ink-3">[{n}] not found in the record</li>;
  const img = e.type === "frame" ? e.url : e.frames?.[0]?.url;
  return (
    <li className="flex gap-2.5">
      <span className="num pt-[1px] text-[11px] text-ink-3">{n}</span>
      <div className="min-w-0 flex-1">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {img ? <img src={img} alt="" className="mb-1 w-full rounded border border-rule" /> : null}
        <p className="text-[12.5px] leading-snug">
          <ProvenanceIcon p={e.provenance} className="mr-1 align-[-2px]" />
          {e.type === "event" ? <><span className="text-ink-2">{KIND_TEXT[e.kind ?? ""] ?? e.kind}: </span>{e.summary}</> :
            e.type === "series" ? <><span className="num">{e.sensor}</span> <span className="text-ink-2">series, {e.n} samples</span></> :
            e.type === "run" ? <>{e.label} run record</> :
            e.type === "reading" ? <><span className="num">{e.sensor} {e.value}</span></> : "Keyframe"}
        </p>
        <p className="truncate text-[11px] text-ink-3">{e.run_label}</p>
      </div>
    </li>
  );
}

export function ReportView({ report }: { report: Analysis<ReportContent> }) {
  const c = report.content;
  const { open } = useEvidence();
  const [focus, setFocus] = useState<{ s: number; i: number } | null>(null);
  const [ev, setEv] = useState<Record<string, Evidence | null>>({});

  const allIds = useMemo(() => {
    const out: string[] = [];
    for (const sec of c.sections) for (const s of sec.sentences) for (const id of s.evidence_ids) if (!out.includes(id)) out.push(id);
    return out;
  }, [c]);

  const focused = focus ? c.sections[focus.s]?.sentences[focus.i] : null;

  useEffect(() => {
    if (!focused?.evidence_ids.length) return;
    let alive = true;
    fetchEvidence(focused.evidence_ids.slice(0, 6)).then((d) => alive && setEv((prev) => ({ ...prev, ...d })));
    return () => { alive = false; };
  }, [focused]);

  const download = () => {
    const blob = new Blob([c.markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${c.title.replace(/[^\w]+/g, "-").toLowerCase()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mx-auto grid max-w-[1180px] gap-10 px-8 pb-24 pt-7 lg:grid-cols-[minmax(0,1fr)_300px] max-md:px-4">
      <article>
        <nav className="no-print mb-3 text-[13px] text-ink-2">
          <Link href="/" className="hover:text-ink">Lab history</Link>
          <span className="mx-1.5 text-ink-3">/</span>
          {c.verdict_analysis_id ? <Link href={`/compare/${c.verdict_analysis_id}`} className="hover:text-ink">{c.candidate.label} litmus test</Link> : c.candidate.label}
          <span className="mx-1.5 text-ink-3">/</span>
          <span>Report</span>
        </nav>
        <header className="mb-8 border-b border-rule pb-6">
          <h1 className="wide max-w-[24ch] text-[34px] font-semibold leading-[1.1] tracking-[-0.015em]">{c.title}</h1>
          <p className="mt-3 text-[14px] text-ink-2">
            {c.stats.sentences} sentences, {c.stats.traceable} traced to the record
            {c.stats.gaps ? `, ${c.stats.gaps} flagged as unsupported` : ", none unsupported"}. Hover a sentence to see its receipts; click to open them.
          </p>
          <div className="no-print mt-4 flex gap-2">
            <button type="button" onClick={download} className="inline-flex items-center gap-1.5 rounded-md border border-rule-strong px-3 py-1.5 text-[13px] font-medium hover:bg-surface">
              <Download size={14} /> Markdown
            </button>
            <button type="button" onClick={() => window.print()} className="inline-flex items-center gap-1.5 rounded-md border border-rule-strong px-3 py-1.5 text-[13px] font-medium hover:bg-surface">
              <Printer size={14} /> Print or save as PDF
            </button>
          </div>
        </header>

        {c.sections.filter((s) => s.sentences.length).map((sec, si) => (
          <section key={sec.id} className="mb-8">
            <h2 className="mb-2 text-[18px] font-semibold">{sec.heading}</h2>
            <p className="max-w-[70ch] text-[16px] leading-[1.75]">
              {sec.sentences.map((s, i) => {
                const active = focus?.s === si && focus?.i === i;
                if (s.gap) {
                  return (
                    <span key={i} className="mr-1 border-b border-dashed border-accent/60 text-ink-2" title={s.reason}>
                      {s.text} <span className="text-[11px] font-medium text-accent">unsupported</span>{" "}
                    </span>
                  );
                }
                return (
                  <span key={i}>
                    <span role="button" tabIndex={0}
                      onMouseEnter={() => setFocus({ s: si, i })} onFocus={() => setFocus({ s: si, i })}
                      onClick={() => open(s.evidence_ids, s.text)} onKeyDown={(e) => e.key === "Enter" && open(s.evidence_ids, s.text)}
                      className={clsx("cursor-pointer rounded-[3px] transition-colors", active ? "bg-base-soft" : "hover:bg-base-soft/60")}>
                      {s.text}
                    </span>
                    <sup className="num ml-0.5 text-[9.5px] text-base">{s.evidence_ids.map((id) => allIds.indexOf(id) + 1).slice(0, 4).join(",")}</sup>{" "}
                  </span>
                );
              })}
            </p>
          </section>
        ))}

        <footer className="mt-10 border-t border-rule pt-4 text-[12.5px] text-ink-3">
          Written by {c.model === "deterministic-template" ? "the template engine (Gemini offline)" : c.model} from the hash-chained record. Every superscript resolves to a commit, frame or sensor series.
        </footer>
      </article>

      <aside className="no-print hidden lg:block">
        <div className="sticky top-[80px]">
          <h2 className="text-[13px] font-medium text-ink-2">Receipts</h2>
          {focused ? (
            <ul className="mt-3 space-y-3">
              {focused.evidence_ids.slice(0, 6).map((id) => <Receipt key={id} n={allIds.indexOf(id) + 1} e={ev[id] ?? null} />)}
            </ul>
          ) : (
            <p className="mt-3 text-[13px] leading-relaxed text-ink-3">Hover any sentence. The commits, frames and readings it rests on appear here.</p>
          )}
        </div>
      </aside>
    </div>
  );
}
