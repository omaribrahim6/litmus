"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import {
  ArrowUp, BookOpenText, ChartLine, ChevronDown, Copy, Database, FileText, Film, GitCommitHorizontal, GitCompareArrows,
  ListTree, Receipt, Search, ShieldCheck, Table2, Waves,
} from "lucide-react";
import { AiMark } from "@/components/ui";
import { useEvidence } from "@/components/evidence/EvidenceProvider";
import { VegaChart } from "@/components/charts/VegaChart";
import { RichText } from "./RichText";
import { useAsk } from "./AskProvider";
import { newSessionId, saveSession, type Session, type Turn } from "@/lib/sessions";
import type { AskAnswer, Evidence } from "@/lib/types";

export interface ExperimentOption { slug: string; name: string; resultLabel: string }

/* ------------------------------------------------------------------ tool steps */

const STEP: Record<string, { icon: typeof Search; text: (a: Record<string, unknown>) => string }> = {
  list_runs: { icon: ListTree, text: () => "Listed every run of the experiment" },
  get_dataset: { icon: Table2, text: () => "Read the experiment's data table" },
  get_run_timeline: { icon: GitCommitHorizontal, text: (a) => `Read the commit timeline of ${a.run ?? "a run"}` },
  query_readings: { icon: Database, text: (a) => `Queried ${a.sensor ?? "sensor"} readings from the Tiger Data hypertable${a.run ? ` for ${a.run}` : ""}` },
  search_events: { icon: Search, text: (a) => `Hybrid search over commits (pgvector + full text): “${a.query ?? ""}”` },
  diff_runs: { icon: GitCompareArrows, text: (a) => `Diffed ${a.candidate ?? "the run"} against ${a.control ?? "the control"}, judged against reference variation` },
  make_chart: { icon: ChartLine, text: (a) => `Drew a chart${a.kind ? ` (${String(a.kind).replaceAll("_", " ")})` : ""}` },
  get_evidence: { icon: Receipt, text: (a) => `Opened receipt ${a.id ?? ""}` },
};

const KIND_OF: Record<string, { label: string; icon: typeof Search }> = {
  event: { label: "Commit", icon: GitCommitHorizontal },
  frame: { label: "Frame", icon: Film },
  series: { label: "Readings", icon: Waves },
  reading: { label: "Reading", icon: Waves },
  run: { label: "Run", icon: FileText },
};

function useEvidenceSummaries(ids: string[]) {
  const [map, setMap] = useState<Record<string, Evidence | null>>({});
  const key = ids.join(",");
  useEffect(() => {
    if (!key) return;
    let alive = true;
    fetch(`/api/evidence?ids=${encodeURIComponent(key)}`).then((r) => r.json()).then((m) => alive && setMap(m)).catch(() => {});
    return () => { alive = false; };
  }, [key]);
  return map;
}

function References({ ids }: { ids: string[] }) {
  const { open, setHighlighted } = useEvidence();
  const shown = ids.slice(0, 6);
  const map = useEvidenceSummaries(shown);
  if (!ids.length) return null;
  return (
    <div className="mt-5">
      <p className="mb-2 text-[11.5px] font-semibold tracking-[0.04em] text-ink-2">RECEIPTS</p>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {shown.map((id, i) => {
          const e = map[id];
          const kind = KIND_OF[e?.type ?? id.split(":")[0].replace("evt", "event").replace("frm", "frame").replace("ser", "series").replace("rdg", "reading")] ?? KIND_OF.event;
          const Icon = kind.icon;
          return (
            <button key={id} type="button" onClick={() => open([id])} onMouseEnter={() => setHighlighted([id])} onMouseLeave={() => setHighlighted([])}
              className="group rounded-xl border border-rule bg-surface p-3 text-left transition hover:border-rule-strong hover:shadow-panel">
              <span className="flex items-center gap-1.5 text-[11.5px] text-ink-3">
                <Icon size={12} />
                {kind.label}{e?.run_label ? ` · ${e.run_label}` : ""}
                <span className="num ml-auto text-base">[{i + 1}]</span>
              </span>
              {e?.type === "frame" && e.url ? (
                <span className="mt-1.5 flex items-center gap-2.5">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={e.url} alt="" className="h-11 w-16 shrink-0 rounded-md object-cover ring-1 ring-rule" />
                  <span className="text-[13px] font-medium leading-snug text-ink">Camera frame{e.reason ? ` · ${e.reason}` : ""}</span>
                </span>
              ) : (
                <span className="mt-1 line-clamp-2 block text-[13px] font-medium leading-snug text-ink">
                  {e?.summary ?? (e?.sensor ? `${e.sensor}${e.mean != null ? `, mean ${e.mean.toFixed(3)}` : ""}` : e === undefined ? <span className="shimmer">Resolving…</span> : id)}
                </span>
              )}
              <span className="num mt-1 block truncate text-[10.5px] text-ink-3">{e?.hash ? `#${e.hash.slice(0, 10)}` : id}</span>
            </button>
          );
        })}
      </div>
      {ids.length > shown.length ? (
        <button type="button" onClick={() => open(ids, "Every receipt in this answer")} className="mt-2 text-[12.5px] font-medium text-base hover:underline">
          Show all {ids.length} receipts
        </button>
      ) : null}
    </div>
  );
}

function Steps({ answer }: { answer: AskAnswer }) {
  if (!answer.tool_calls.length) return <p className="text-[12.5px] text-ink-2">Answered directly from the conversation; no lookups were needed.</p>;
  return (
    <ol className="relative space-y-2.5 border-l border-rule pl-4">
      {answer.tool_calls.map((c, i) => {
        const s = STEP[c.name] ?? { icon: BookOpenText, text: () => c.name };
        const Icon = s.icon;
        return (
          <li key={i} className="relative flex items-start gap-2 text-[12.5px] text-ink-2">
            <span className="absolute -left-[22px] top-0.5 flex size-[11px] items-center justify-center rounded-full border border-rule-strong bg-paper" />
            <Icon size={13} className="mt-0.5 shrink-0 text-ink-3" />
            <span>{s.text(c.args ?? {})}</span>
          </li>
        );
      })}
      <li className="relative flex items-start gap-2 text-[12.5px] text-ink-2">
        <span className="absolute -left-[22px] top-0.5 size-[11px] rounded-full bg-ok" />
        <ShieldCheck size={13} className="mt-0.5 shrink-0 text-ok" />
        <span>Checked every citation against the record{answer.dropped_citations?.length ? `; removed ${answer.dropped_citations.length} that did not exist` : ""}. No probability language allowed.</span>
      </li>
    </ol>
  );
}

function AssistantTurn({ turn, compact }: { turn: Turn; compact?: boolean }) {
  const [why, setWhy] = useState(false);
  const [copied, setCopied] = useState(false);
  const a = turn.answer;
  if (turn.error) {
    return (
      <div className="flex gap-3">
        <AiMark size={22} className="mt-0.5" />
        <div className="rounded-xl border border-accent/25 bg-accent-soft px-3.5 py-2.5 text-[13.5px] text-accent">{turn.error}. Check that the worker is running, then ask again.</div>
      </div>
    );
  }
  if (!a) return null;
  const receipts = a.citations ?? [];
  const model = a.model === "deterministic-fallback" ? "Offline rules" : a.model.replace(/^gemini-/, "Gemini ").replaceAll("-", " ");
  return (
    <div className="rise flex gap-3">
      <AiMark size={22} className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <div className="mb-2 flex flex-wrap items-center gap-2 text-[12px]">
          <span className="font-semibold text-ink">Litmus</span>
          <span className="rounded-full bg-sunken px-2 py-0.5 text-ink-2">{model}</span>
          {receipts.length ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-ok-soft px-2 py-0.5 font-medium text-ok">
              <ShieldCheck size={12} /> Grounded in {receipts.length} receipt{receipts.length === 1 ? "" : "s"}
            </span>
          ) : (
            <span className="rounded-full bg-amber-soft px-2 py-0.5 font-medium text-amber">No receipts cited</span>
          )}
          {a.cached ? <span className="text-ink-3">replayed</span> : null}
        </div>

        {a.charts.map((c) => (
          <figure key={c.id} className="mb-3 rounded-xl border border-rule bg-surface p-4 shadow-panel">
            <VegaChart spec={c.spec} />
            {c.note ? <figcaption className="mt-2 text-[12px] text-ink-2">{c.note} Click a point to open its source.</figcaption> : null}
          </figure>
        ))}

        {a.text ? <div className="text-[14.5px] leading-[1.7] text-ink"><RichText text={a.text} citations={receipts} /></div> : null}

        {!compact ? <References ids={receipts} /> : null}

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <button type="button" onClick={() => setWhy((v) => !v)}
            className={clsx("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12.5px] font-medium transition",
              why ? "border-base/30 bg-base-soft text-base" : "border-rule text-ink-2 hover:border-rule-strong hover:text-ink")}>
            <ListTree size={13} /> Why this answer?
            <ChevronDown size={13} className={clsx("transition", why && "rotate-180")} />
          </button>
          {a.analyses.length ? (
            <Link href={`/compare/${a.analyses[0]}`} className="inline-flex items-center gap-1.5 rounded-full border border-rule px-2.5 py-1 text-[12.5px] font-medium text-ink-2 hover:border-rule-strong hover:text-ink">
              <GitCompareArrows size={13} /> Open the full diff
            </Link>
          ) : null}
          <button type="button" aria-label="Copy answer" onClick={() => { navigator.clipboard?.writeText(a.text); setCopied(true); setTimeout(() => setCopied(false), 1200); }}
            className="rounded-full p-1.5 text-ink-3 hover:bg-hover hover:text-ink">
            {copied ? <span className="px-1 text-[11.5px]">Copied</span> : <Copy size={13} />}
          </button>
        </div>
        {why ? <div className="mt-3 rounded-xl border border-rule bg-side p-4"><Steps answer={a} /></div> : null}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ composer */

function Composer({ value, onChange, onSend, busy, big, chips }: {
  value: string; onChange: (v: string) => void; onSend: () => void; busy: boolean; big?: boolean; chips?: React.ReactNode;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [value]);
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSend(); }}
      className={clsx("rounded-2xl border border-rule-strong bg-surface shadow-panel transition focus-within:border-ink-3 focus-within:shadow-float", big ? "p-3" : "p-2.5")}>
      <div className="flex items-start gap-2 px-1">
        {big ? <AiMark size={14} className="mt-[5px]" /> : null}
        <textarea ref={ref} value={value} onChange={(e) => onChange(e.target.value)} rows={1}
          placeholder={big ? "Ask about any run, measurement or difference. Every answer cites the record." : "Ask a follow-up"}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); } }}
          className={clsx("flex-1 resize-none bg-transparent leading-relaxed outline-none placeholder:text-ink-3", big ? "min-h-[52px] text-[14.5px]" : "min-h-[24px] text-[14px]")} />
      </div>
      <div className="mt-2 flex items-center gap-1.5">
        {chips}
        <button type="submit" disabled={busy || !value.trim()} aria-label="Send"
          className="ml-auto flex size-8 items-center justify-center rounded-full bg-ink text-paper transition hover:opacity-85 disabled:opacity-25">
          <ArrowUp size={16} strokeWidth={2.4} />
        </button>
      </div>
    </form>
  );
}

function Thinking() {
  const lines = ["Reading the record", "Querying Tiger Data", "Checking every citation"];
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setI((x) => Math.min(x + 1, lines.length - 1)), 2600);
    return () => clearInterval(id);
  }, [lines.length]);
  return (
    <div className="flex items-center gap-3">
      <AiMark size={22} pulse />
      <span className="shimmer text-[14px] font-medium">{lines[i]}…</span>
    </div>
  );
}

/* ------------------------------------------------------------------ conversation */

export function suggestionsFor(resultLabel: string) {
  const r = resultLabel.toLowerCase();
  return [
    { icon: ChartLine, label: "Plot results", q: `Graph the ${r} across every run, formatted for a paper.` },
    { icon: GitCompareArrows, label: "Explain a difference", q: "Why was the latest candidate run different from the control?" },
    { icon: Table2, label: "Summarize the data", q: "Summarize the data table: which run had the highest and lowest values, and what was not recorded?" },
    { icon: BookOpenText, label: "Write the methods", q: "Write the methods section as the latest run actually happened." },
  ];
}

export function Conversation({ variant, experiment, experimentLabel, resultLabel, initial, chips }: {
  variant: "page" | "panel";
  experiment: string;
  experimentLabel?: string;
  resultLabel: string;
  initial?: Session | null;
  chips?: React.ReactNode;
}) {
  const { context, pending, takePending } = useAsk();
  const [session, setSession] = useState<Session>(() => initial ?? { id: newSessionId(), title: "", experiment, turns: [], updated: Date.now() });
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const turns = session.turns;
  const page = variant === "page";

  useEffect(() => {
    if (initial) setSession(initial);
  }, [initial]);

  const send = useCallback(async (question: string) => {
    const q = question.trim();
    if (!q || busy) return;
    const history: Turn[] = [...session.turns, { role: "user", text: q }];
    const next = { ...session, experiment, title: session.title || q.slice(0, 64), turns: history, updated: Date.now() };
    setSession(next);
    setInput("");
    setBusy(true);
    let reply: Turn;
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          experiment,
          messages: history.map((t) => ({ role: t.role, text: t.answer?.text ?? t.text })),
          context: { page: context.page, run_id: context.run_id, run_label: context.run_label, analysis_id: context.analysis_id },
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `The lab assistant returned ${res.status}`);
      reply = { role: "assistant", text: data.text, answer: data };
    } catch (err) {
      reply = { role: "assistant", text: "", error: (err as Error).message };
    }
    const done = { ...next, turns: [...history, reply], updated: Date.now() };
    setSession(done);
    saveSession(done);
    setBusy(false);
  }, [busy, session, experiment, context]);

  useEffect(() => {
    if (pending && !busy) {
      const q = takePending();
      if (q) send(q);
    }
  }, [pending, busy, takePending, send]);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, busy]);

  const suggestions = useMemo(() => suggestionsFor(resultLabel), [resultLabel]);

  if (!turns.length) {
    return (
      <div className={clsx("flex flex-1 flex-col", page ? "items-center justify-center px-6 pb-16" : "px-4 py-5")}>
        <div className={clsx("w-full", page ? "max-w-[680px]" : "")}>
          {page ? (
            <div className="mb-8 flex flex-col items-center text-center">
              <div className="relative mb-6">
                <span className="absolute inset-0 scale-[2.2] rounded-full opacity-25 blur-2xl" style={{ background: "var(--ai)" }} />
                <AiMark size={52} className="relative" />
              </div>
              <h1 className="text-[24px] font-semibold tracking-[-0.02em]">What do you want to know about your lab?</h1>
              <p className="mt-2 max-w-[52ch] text-[14px] text-ink-2">
                Gemini answers from {experimentLabel ? <span className="font-medium text-ink">{experimentLabel}</span> : "the record"} in Tiger Data. Every number links to the frame, reading or commit it came from.
              </p>
            </div>
          ) : (
            <p className="mb-4 text-[13.5px] text-ink-2">Answers come from the recorded runs. Every number links to its receipt.</p>
          )}
          {page ? (
            <div className="mb-3 flex flex-wrap justify-center gap-1.5">
              {suggestions.map((s) => (
                <button key={s.label} type="button" onClick={() => send(s.q)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-rule bg-surface px-3 py-1.5 text-[12.5px] font-medium text-ink-2 transition hover:border-rule-strong hover:text-ink">
                  <s.icon size={13} /> {s.label}
                </button>
              ))}
            </div>
          ) : null}
          <Composer value={input} onChange={setInput} onSend={() => send(input)} busy={busy} big={page} chips={chips} />
          {!page ? (
            <div className="mt-4 space-y-1.5">
              {suggestions.map((s) => (
                <button key={s.label} type="button" onClick={() => send(s.q)}
                  className="flex w-full items-center gap-2 rounded-lg border border-rule px-3 py-2 text-left text-[13px] text-ink-2 hover:border-rule-strong hover:text-ink">
                  <s.icon size={13} className="shrink-0" /> {s.q}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className={clsx("scroll-thin flex-1 overflow-y-auto", page ? "px-6" : "px-4")}>
        <div className={clsx("mx-auto space-y-8 py-8", page ? "max-w-[760px]" : "")}>
          {turns.map((t, i) =>
            t.role === "user" ? (
              <div key={i} className="flex justify-end">
                <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-sunken px-4 py-2.5 text-[14px] leading-relaxed">{t.text}</p>
              </div>
            ) : (
              <AssistantTurn key={i} turn={t} compact={!page} />
            ),
          )}
          {busy ? <Thinking /> : null}
          <div ref={end} />
        </div>
      </div>
      <div className={clsx("pb-4 pt-2", page ? "px-6" : "px-3")}>
        <div className={clsx("mx-auto", page ? "max-w-[760px]" : "")}>
          <Composer value={input} onChange={setInput} onSend={() => send(input)} busy={busy} chips={page ? chips : undefined} />
          {page ? <p className="mt-2 text-center text-[11.5px] text-ink-3">Litmus only states what was recorded. Values Gemini read off the bench are marked inferred.</p> : null}
        </div>
      </div>
    </div>
  );
}
