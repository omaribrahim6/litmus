"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, PanelRightClose } from "lucide-react";
import { useAsk } from "./AskProvider";
import { RichText } from "./RichText";
import { VegaChart } from "@/components/charts/VegaChart";
import type { AskAnswer } from "@/lib/types";

interface Turn {
  role: "user" | "assistant";
  text: string;
  answer?: AskAnswer;
  error?: string;
}

const SUGGESTIONS = [
  "Graph base added across all runs, formatted for a paper.",
  "Why was Method B different?",
  "What did I do differently in trial 4?",
  "Write the methods section as it actually happened.",
];

export function AskPanel() {
  const { isOpen, setOpen, context, pending, takePending } = useAsk();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);

  const send = useCallback(async (question: string) => {
    const q = question.trim();
    if (!q || busy) return;
    const history = [...turns, { role: "user" as const, text: q }];
    setTurns(history);
    setInput("");
    setBusy(true);
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          messages: history.map((t) => ({ role: t.role, text: t.answer?.text ?? t.text })),
          context: { page: context.page, run_id: context.run_id, run_label: context.run_label, analysis_id: context.analysis_id },
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `The lab assistant returned ${res.status}`);
      setTurns((t) => [...t, { role: "assistant", text: data.text, answer: data }]);
    } catch (err) {
      setTurns((t) => [...t, { role: "assistant", text: "", error: (err as Error).message }]);
    } finally {
      setBusy(false);
    }
  }, [busy, turns, context]);

  useEffect(() => {
    if (pending && !busy) {
      const q = takePending();
      if (q) send(q);
    }
  }, [pending, busy, takePending, send]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  if (!isOpen) return null;

  return (
    <aside className="no-print sticky top-[57px] hidden h-[calc(100vh-57px)] w-[400px] shrink-0 flex-col border-l border-rule bg-surface lg:flex" aria-label="Ask your lab">
      <header className="flex items-start justify-between gap-3 border-b border-rule px-5 py-3.5">
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold">Ask your lab</h2>
          <p className="truncate text-[12px] text-ink-2">Looking at: {context.description ?? context.page}</p>
        </div>
        <button type="button" onClick={() => setOpen(false)} className="rounded-md p-1 text-ink-2 hover:bg-sunken hover:text-ink" aria-label="Close Ask panel">
          <PanelRightClose size={18} />
        </button>
      </header>

      <div ref={scroller} className="scroll-thin flex-1 space-y-5 overflow-y-auto px-5 py-4">
        {turns.length === 0 ? (
          <div className="space-y-3">
            <p className="text-[14px] text-ink-2">
              Questions are answered from the recorded runs. Every number links to the reading, frame or commit it came from.
            </p>
            <div className="space-y-1.5">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" onClick={() => send(s)}
                  className="block w-full rounded-lg border border-rule px-3 py-2 text-left text-[13.5px] leading-snug hover:border-rule-strong hover:bg-paper">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {turns.map((t, i) =>
          t.role === "user" ? (
            <p key={i} className="ml-8 rounded-lg bg-sunken px-3 py-2 text-[14px]">{t.text}</p>
          ) : t.error ? (
            <div key={i} className="rounded-lg border border-accent/30 bg-accent-soft px-3 py-2 text-[13px] text-accent">
              {t.error}. Check that the worker is running, then ask again.
            </div>
          ) : (
            <div key={i} className="space-y-3">
              {t.answer?.charts.map((c) => (
                <figure key={c.id} className="rounded-lg border border-rule bg-paper p-3">
                  <VegaChart spec={c.spec} />
                  {c.note ? <figcaption className="mt-1 text-[12px] text-ink-2">{c.note} Click a point to see its source.</figcaption> : null}
                </figure>
              ))}
              {t.text ? <RichText text={t.text} citations={t.answer?.citations ?? []} /> : null}
              {t.answer?.analyses.length ? (
                <Link href={`/compare/${t.answer.analyses[0]}`} className="inline-block text-[13px] font-medium text-base hover:underline">
                  Open the full diff
                </Link>
              ) : null}
              <p className="text-[11px] text-ink-3">
                {t.answer?.model === "deterministic-fallback" ? "Answered without Gemini (offline rules)" : t.answer?.model}
                {t.answer?.cached ? ", replayed from cache" : ""}
                {t.answer?.tool_calls.length ? `, ${t.answer.tool_calls.length} lookups` : ""}
              </p>
            </div>
          ),
        )}
        {busy ? <p className="text-[13px] text-ink-2"><span className="live-dot mr-2 inline-block size-1.5 rounded-full bg-base align-middle" />Reading the record</p> : null}
      </div>

      <form className="border-t border-rule p-3" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <div className="flex items-end gap-2 rounded-lg border border-rule-strong bg-paper px-3 py-2 focus-within:border-base">
          <textarea value={input} onChange={(e) => setInput(e.target.value)} rows={2} placeholder="Ask about any run, reading or difference"
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
            className="max-h-40 min-h-[44px] flex-1 resize-none bg-transparent text-[14px] outline-none placeholder:text-ink-3" />
          <button type="submit" disabled={busy || !input.trim()} aria-label="Ask"
            className="rounded-md bg-ink p-1.5 text-paper disabled:opacity-30">
            <ArrowUp size={16} />
          </button>
        </div>
      </form>
    </aside>
  );
}
