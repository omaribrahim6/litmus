"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Maximize2, X } from "lucide-react";
import { AiMark } from "@/components/ui";
import { useAsk } from "./AskProvider";
import { Conversation } from "./Conversation";

/** The assistant beside any page: knows what you are looking at, answers from the record. */
export function AskPanel() {
  const { isOpen, setOpen, context } = useAsk();
  const pathname = usePathname();
  if (pathname === "/ask") return null;

  if (!isOpen) {
    return (
      <button type="button" onClick={() => setOpen(true)}
        className="no-print fixed bottom-5 right-5 z-40 hidden items-center gap-2 rounded-full border border-rule bg-surface py-2 pl-2.5 pr-4 text-[13.5px] font-medium shadow-float transition hover:border-rule-strong lg:inline-flex">
        <AiMark size={18} /> Ask about this page
      </button>
    );
  }

  return (
    <aside className="no-print sticky top-0 hidden h-screen w-[420px] shrink-0 flex-col border-l border-rule bg-paper lg:flex" aria-label="Ask your lab">
      <header className="flex h-12 shrink-0 items-center gap-2 border-b border-rule px-4">
        <AiMark size={18} />
        <div className="min-w-0 flex-1">
          <p className="text-[13.5px] font-semibold leading-tight">Ask your lab</p>
          <p className="truncate text-[11.5px] text-ink-3">Looking at {context.description ?? context.page}</p>
        </div>
        <Link href={`/ask${context.experiment ? `?experiment=${context.experiment}` : ""}`} className="rounded-md p-1.5 text-ink-3 hover:bg-hover hover:text-ink" aria-label="Open full screen" title="Open full screen">
          <Maximize2 size={14} />
        </Link>
        <button type="button" onClick={() => setOpen(false)} className="rounded-md p-1.5 text-ink-3 hover:bg-hover hover:text-ink" aria-label="Close">
          <X size={16} />
        </button>
      </header>
      <Conversation key={context.experiment ?? "default"} variant="panel" experiment={context.experiment ?? ""} resultLabel={context.result_label ?? "result"} />
    </aside>
  );
}
