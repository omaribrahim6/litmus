"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { FlaskConical, MessageSquare, Menu, Moon, Plus, ShieldCheck, Sun, Upload, X } from "lucide-react";
import { AiMark, Wordmark, ROLE_DOT } from "@/components/ui";
import type { Role } from "@/lib/types";
import { listSessions, onSessionsChange, type Session } from "@/lib/sessions";

export interface NavExperiment { slug: string; name: string; runs: number }
export interface NavRun { id: string; label: string; role: Role; recording: boolean; experiment: string }

function ThemeToggle() {
  const [dark, setDark] = useState<boolean | null>(null);
  useEffect(() => {
    const el = document.documentElement;
    setDark(el.dataset.theme ? el.dataset.theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches);
  }, []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "light";
    try {
      localStorage.setItem("litmus-theme", next ? "dark" : "light");
    } catch {
      /* storage unavailable */
    }
  };
  return (
    <button type="button" onClick={toggle} className="rounded-md p-1.5 text-ink-3 hover:bg-hover hover:text-ink" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}>
      {dark ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}

function SourceStatus() {
  const [status, setStatus] = useState<{ source: string; worker: boolean } | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () => fetch("/api/status").then((r) => r.json()).then((s) => alive && setStatus(s)).catch(() => alive && setStatus({ source: "none", worker: false }));
    load();
    const id = setInterval(load, 15000);
    return () => { alive = false; clearInterval(id); };
  }, []);
  if (!status) return <span className="h-4 w-24 animate-pulse rounded bg-hover" />;
  const live = status.source === "live";
  return (
    <span className="inline-flex min-w-0 items-center gap-2 text-[12px] text-ink-2"
      title={live ? `Reading live from Tiger Data${status.worker ? "" : "; the worker is offline, so Gemini answers fall back to rules"}` : "Showing the bundled offline snapshot"}>
      <span className={clsx("inline-block size-1.5 shrink-0 rounded-full", live && status.worker ? "bg-ok" : "bg-amber")} />
      <span className="truncate">{live ? (status.worker ? "Live · Tiger Data" : "Live · worker offline") : status.source === "snapshot" ? "Offline snapshot" : "No data source"}</span>
    </span>
  );
}

function Item({ href, active, icon, children, trailing }: { href: string; active: boolean; icon?: React.ReactNode; children: React.ReactNode; trailing?: React.ReactNode }) {
  return (
    <Link href={href}
      className={clsx("group flex h-8 items-center gap-2.5 rounded-md px-2 text-[13.5px] transition-colors",
        active ? "bg-hover font-medium text-ink" : "text-ink-2 hover:bg-hover hover:text-ink")}>
      {icon ? <span className="flex w-4 shrink-0 justify-center text-ink-3 group-hover:text-ink-2">{icon}</span> : null}
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {trailing}
    </Link>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-5">
      <p className="mb-1 px-2 text-[11.5px] font-medium text-ink-3">{title}</p>
      <div className="space-y-px">{children}</div>
    </div>
  );
}

function Conversations({ active }: { active: string | null }) {
  const [items, setItems] = useState<Session[]>([]);
  useEffect(() => {
    const load = () => setItems(listSessions().slice(0, 6));
    load();
    return onSessionsChange(load);
  }, []);
  if (!items.length) return null;
  return (
    <Section title="Conversations">
      {items.map((s) => (
        <Item key={s.id} href={`/ask?experiment=${s.experiment}&session=${s.id}`} active={active === s.id} icon={<MessageSquare size={13} />}>
          {s.title || "Untitled"}
        </Item>
      ))}
    </Section>
  );
}

function Contents({ experiments, recent, onNavigate }: { experiments: NavExperiment[]; recent: NavRun[]; onNavigate?: () => void }) {
  const pathname = usePathname();
  const params = useSearchParams();
  const current = params.get("experiment");
  return (
    <div className="flex h-full flex-col" onClick={(e) => { if ((e.target as HTMLElement).closest("a")) onNavigate?.(); }}>
      <div className="flex h-12 items-center px-4">
        <Link href="/" aria-label="Litmus home"><Wordmark /></Link>
      </div>

      <div className="px-2.5">
        <Link href="/ask"
          className="flex h-9 items-center gap-2 rounded-lg bg-ink px-3 text-[13.5px] font-medium text-paper shadow-panel transition hover:opacity-90">
          <Plus size={15} strokeWidth={2.4} />
          New question
          <kbd className="num ml-auto rounded border border-paper/20 px-1 text-[10.5px] font-normal text-paper/60">⌘K</kbd>
        </Link>
      </div>

      <nav className="scroll-thin mt-2 flex-1 overflow-y-auto px-2.5 pb-4" aria-label="Main">
        <Section title="Experiments">
          {experiments.length ? experiments.map((e, i) => (
            <Item key={e.slug} href={`/?experiment=${e.slug}`} icon={<FlaskConical size={14} />}
              active={pathname === "/" && (current === e.slug || (!current && i === 0))}
              trailing={<span className="num text-[11px] text-ink-3">{e.runs}</span>}>
              {e.name}
            </Item>
          )) : <p className="px-2 text-[12.5px] text-ink-3">None yet. Start a run at the station.</p>}
        </Section>

        {recent.length ? (
          <Section title="Recent runs">
            {recent.map((r) => (
              <Item key={r.id} href={`/runs/${r.id}`} active={pathname === `/runs/${r.id}`}
                icon={<span className={clsx("inline-block size-2 rounded-full", r.recording && "live-dot")} style={{ background: r.recording ? "var(--accent)" : ROLE_DOT[r.role] }} />}>
                <span title={r.experiment}>{r.label}</span>
              </Item>
            ))}
          </Section>
        ) : null}

        <Conversations active={pathname === "/ask" ? params.get("session") : null} />

        <Section title="Workspace">
          <Item href="/upload" active={pathname.startsWith("/upload")} icon={<Upload size={14} />}>Upload a recording</Item>
          <Item href="/validation" active={pathname.startsWith("/validation")} icon={<ShieldCheck size={14} />}>Validation</Item>
        </Section>
      </nav>

      <div className="flex items-center justify-between gap-2 border-t border-rule px-4 py-2.5">
        <SourceStatus />
        <ThemeToggle />
      </div>
    </div>
  );
}

export function SidebarNav({ experiments, recent }: { experiments: NavExperiment[]; recent: NavRun[] }) {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  // ⌘K / Ctrl+K opens the assistant from anywhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        router.push("/ask");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);

  return (
    <>
      <aside className="no-print sticky top-0 hidden h-screen w-[248px] shrink-0 border-r border-rule bg-side md:block">
        <Contents experiments={experiments} recent={recent} />
      </aside>

      {/* Phones and narrow windows: a slim bar with a drawer. */}
      <div className="no-print sticky top-0 z-40 flex h-12 items-center justify-between border-b border-rule bg-paper/90 px-4 backdrop-blur md:hidden">
        <Link href="/" aria-label="Litmus home"><Wordmark /></Link>
        <div className="flex items-center gap-1">
          <Link href="/ask" className="rounded-md p-2 hover:bg-hover" aria-label="Ask your lab"><AiMark size={16} /></Link>
          <button type="button" onClick={() => setOpen(true)} className="rounded-md p-2 text-ink-2 hover:bg-hover" aria-label="Open menu"><Menu size={18} /></button>
        </div>
      </div>
      {open ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <button type="button" className="absolute inset-0 bg-black/30" aria-label="Close menu" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-[280px] bg-side shadow-float">
            <button type="button" onClick={() => setOpen(false)} className="absolute right-2 top-2.5 rounded-md p-1.5 text-ink-2 hover:bg-hover" aria-label="Close menu"><X size={16} /></button>
            <Contents experiments={experiments} recent={recent} onNavigate={() => setOpen(false)} />
          </div>
        </div>
      ) : null}
    </>
  );
}
