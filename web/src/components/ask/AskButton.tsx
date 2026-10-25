"use client";

import { AiMark } from "@/components/ui";
import { useAsk } from "./AskProvider";

/** Opens the assistant beside the current page. */
export function AskButton({ label = "Ask" }: { label?: string }) {
  const { setOpen, isOpen } = useAsk();
  return (
    <button type="button" onClick={() => setOpen(!isOpen)}
      className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-rule bg-surface px-2.5 text-[13px] font-medium text-ink shadow-panel hover:border-rule-strong">
      <AiMark size={14} /> {label}
    </button>
  );
}
