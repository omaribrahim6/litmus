"use client";

import clsx from "clsx";
import { useEvidence } from "./EvidenceProvider";

/** Wrap any number or sentence: clicking it opens the evidence behind it ("blame"). */
export function Blame({ ids, title, children, className, quiet }: {
  ids: string[];
  title?: string;
  children: React.ReactNode;
  className?: string;
  quiet?: boolean;
}) {
  const { open, setHighlighted } = useEvidence();
  if (!ids?.length) return <span className={className}>{children}</span>;
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        open(ids, title);
      }}
      onMouseEnter={() => setHighlighted(ids)}
      onMouseLeave={() => setHighlighted([])}
      onFocus={() => setHighlighted(ids)}
      onBlur={() => setHighlighted([])}
      className={clsx(
        "cursor-pointer text-left underline decoration-dotted underline-offset-[3px] transition-colors hover:text-base hover:decoration-solid",
        quiet ? "decoration-transparent hover:decoration-current" : "decoration-ink-3",
        className,
      )}
      title={`Show evidence (${ids.length})`}
    >
      {children}
    </button>
  );
}
