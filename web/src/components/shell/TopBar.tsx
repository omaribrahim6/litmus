"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { Moon, PanelRightOpen, Sun } from "lucide-react";
import { Wordmark } from "@/components/ui";
import { useAsk } from "@/components/ask/AskProvider";

const NAV = [
  { href: "/", label: "History" },
  { href: "/upload", label: "Upload a video" },
  { href: "/validation", label: "Validation" },
];

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
    <button type="button" onClick={toggle} className="rounded-md p-1.5 text-ink-2 hover:bg-sunken hover:text-ink" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}>
      {dark ? <Sun size={17} /> : <Moon size={17} />}
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
  if (!status) return <span className="h-5 w-28 animate-pulse rounded bg-sunken" />;
  const live = status.source === "live";
  return (
    <span className="hidden items-center gap-1.5 text-[12px] text-ink-2 md:inline-flex"
      title={live ? "Reading live from Tiger Data" : "Showing the bundled offline snapshot"}>
      <span className={clsx("inline-block size-1.5 rounded-full", live ? "bg-ok" : "bg-amber")} />
      {live ? "Live record" : status.source === "snapshot" ? "Offline snapshot" : "No data source"}
      {live && !status.worker ? <span className="text-amber">, worker offline</span> : null}
    </span>
  );
}

export function TopBar() {
  const pathname = usePathname();
  const { isOpen, setOpen } = useAsk();
  return (
    <header className="no-print sticky top-0 z-40 h-[57px] border-b border-rule bg-paper/90 backdrop-blur">
      <div className="flex h-full items-center gap-6 px-5">
        <Link href="/" className="shrink-0" aria-label="Litmus home">
          <Wordmark />
        </Link>
        <nav className="flex items-center gap-1" aria-label="Main">
          {NAV.map((n) => {
            const active = n.href === "/" ? pathname === "/" || pathname.startsWith("/runs") || pathname.startsWith("/compare") || pathname.startsWith("/reports") : pathname.startsWith(n.href);
            return (
              <Link key={n.href} href={n.href}
                className={clsx("rounded-md px-2.5 py-1 text-[14px]", active ? "bg-sunken font-medium text-ink" : "text-ink-2 hover:text-ink")}>
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <SourceStatus />
          <ThemeToggle />
          {!isOpen ? (
            <button type="button" onClick={() => setOpen(true)} className="hidden items-center gap-1.5 rounded-md border border-rule-strong px-2.5 py-1 text-[13px] font-medium hover:bg-sunken lg:inline-flex">
              <PanelRightOpen size={15} /> Ask your lab
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
