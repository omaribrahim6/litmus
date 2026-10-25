"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { Check, ChevronDown, FlaskConical, Quote, SquarePen } from "lucide-react";
import { Conversation, type ExperimentOption } from "./Conversation";
import { AskContext } from "./AskProvider";
import { getSession, type Session } from "@/lib/sessions";

function ExperimentPicker({ experiments, current }: { experiments: ExperimentOption[]; current: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const cur = experiments.find((e) => e.slug === current);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen((v) => !v)}
        className="inline-flex h-8 max-w-[280px] items-center gap-2 rounded-lg px-2.5 text-[13.5px] font-medium hover:bg-hover">
        <FlaskConical size={14} className="shrink-0 text-ink-3" />
        <span className="truncate">{cur?.name ?? "No experiment"}</span>
        <ChevronDown size={14} className="shrink-0 text-ink-3" />
      </button>
      {open ? (
        <div className="absolute left-0 top-9 z-30 w-[300px] rounded-xl border border-rule bg-surface p-1.5 shadow-float">
          <p className="px-2 pb-1 pt-1.5 text-[11.5px] font-medium text-ink-3">Answer from</p>
          {experiments.map((e) => (
            <button key={e.slug} type="button" onClick={() => { setOpen(false); router.push(`/ask?experiment=${e.slug}`); }}
              className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[13.5px] hover:bg-hover">
              <span className="min-w-0 flex-1 truncate">{e.name}</span>
              {e.slug === current ? <Check size={14} className="text-ink-2" /> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function AskWorkspace({ experiments, current, sessionId, tab, data }: {
  experiments: ExperimentOption[];
  current: string;
  sessionId: string | null;
  tab: "chat" | "data";
  data: React.ReactNode;
}) {
  const [session, setSession] = useState<Session | null>(null);
  const [key, setKey] = useState(0);
  useEffect(() => {
    setSession(sessionId ? getSession(sessionId) : null);
    setKey((k) => k + 1);
  }, [sessionId]);
  const exp = experiments.find((e) => e.slug === current);
  const experiment = session?.experiment ?? current;
  const q = (t: string) => `/ask?experiment=${current}${t === "data" ? "&tab=data" : ""}${sessionId && t === "chat" ? `&session=${sessionId}` : ""}`;

  return (
    <div className="flex h-screen flex-col max-md:h-[calc(100vh-48px)]">
      <AskContext page="ask" description={exp?.name ?? "Ask your lab"} />
      <header className="relative flex h-12 shrink-0 items-center gap-2 px-3">
        <ExperimentPicker experiments={experiments} current={current} />
        <div className="absolute left-1/2 flex -translate-x-1/2 rounded-lg bg-sunken p-0.5 text-[13px] font-medium max-md:static max-md:ml-auto max-md:translate-x-0">
          {(["chat", "data"] as const).map((t) => (
            <Link key={t} href={q(t)} className={clsx("rounded-md px-4 py-1 transition", tab === t ? "bg-surface text-ink shadow-panel" : "text-ink-2 hover:text-ink")}>
              {t === "chat" ? "Chat" : "Data"}
            </Link>
          ))}
        </div>
        <Link href={`/ask?experiment=${current}`} className="ml-auto rounded-lg p-2 text-ink-2 hover:bg-hover hover:text-ink max-md:ml-1" aria-label="New question" title="New question">
          <SquarePen size={16} />
        </Link>
      </header>

      {tab === "data" ? (
        <div className="scroll-thin flex-1 overflow-y-auto px-6 pb-10 pt-4">
          <div className="mx-auto max-w-[1100px]">
            <h1 className="text-[20px] font-semibold tracking-[-0.02em]">{exp?.name}</h1>
            <p className="mb-5 mt-1 text-[13.5px] text-ink-2">Everything Litmus recorded, as one table: a row per run, a column per measurement. Click any value for its receipt.</p>
            {data}
          </div>
        </div>
      ) : (
        <Conversation key={key} variant="page" experiment={experiment} experimentLabel={exp?.name} resultLabel={exp?.resultLabel ?? "result"} initial={session}
          chips={
            <>
              <span className="inline-flex h-7 items-center gap-1.5 rounded-full border border-rule px-2.5 text-[12px] font-medium text-ink-2">
                <FlaskConical size={12} /> <span className="max-w-[180px] truncate">{exp?.name ?? "Experiment"}</span>
              </span>
              <span className="inline-flex h-7 items-center gap-1.5 rounded-full bg-ok-soft px-2.5 text-[12px] font-medium text-ok" title="Every claim must cite a commit, frame or reading; uncited claims are removed">
                <Quote size={11} /> Citations required
              </span>
            </>
          } />
      )}
    </div>
  );
}
