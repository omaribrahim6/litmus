import clsx from "clsx";
import { Activity, CircleDashed, CircleSlash, PenLine, ScanEye, Search, SquareCheck } from "lucide-react";
import type { ClaimLabel, Provenance, Role } from "@/lib/types";
import { LABEL_TEXT, PROVENANCE_TEXT, ROLE_TEXT } from "@/lib/format";
import type { StripStop } from "@/lib/color";

/** The litmus paper glyph: indicator yellow turning to endpoint red. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={clsx("inline-flex items-center gap-2", className)}>
      <span
        aria-hidden
        className="inline-block h-[18px] w-[7px] rounded-[2px]"
        style={{ background: "linear-gradient(180deg, #e8c33a 0%, #e8c33a 46%, #c8264e 54%, #c8264e 100%)" }}
      />
      <span className="wide text-[17px] font-semibold tracking-[-0.01em]">litmus</span>
    </span>
  );
}

const PROV_ICON = { measured: Activity, reported: PenLine, inferred: ScanEye } as const;

export function ProvenanceIcon({ p, className, withText }: { p?: Provenance | null; className?: string; withText?: boolean }) {
  if (!p) return null;
  const Icon = PROV_ICON[p];
  const tone = p === "measured" ? "text-ink-2" : p === "reported" ? "text-base" : "text-amber";
  return (
    <span className={clsx("inline-flex items-center gap-1", tone, className)} title={PROVENANCE_TEXT[p]}>
      <Icon size={13} strokeWidth={2} aria-hidden />
      {withText ? <span className="text-xs capitalize">{p}</span> : <span className="sr-only">{PROVENANCE_TEXT[p]}</span>}
    </span>
  );
}

const LABEL_STYLE: Record<ClaimLabel, string> = {
  observed: "border-rule-strong text-ink bg-surface",
  possible_explanation: "border-amber/40 text-amber bg-amber-soft",
  contradicted: "border-accent/40 text-accent bg-accent-soft",
  missing_evidence: "border-dashed border-ink-3 text-ink-2 bg-transparent",
};
const LABEL_ICON = { observed: Search, possible_explanation: SquareCheck, contradicted: CircleSlash, missing_evidence: CircleDashed } as const;

export function LabelChip({ label, className }: { label: ClaimLabel; className?: string }) {
  const Icon = LABEL_ICON[label];
  return (
    <span className={clsx("inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-[1px] text-[12px] font-medium", LABEL_STYLE[label], className)}>
      <Icon size={12} strokeWidth={2.2} aria-hidden />
      {LABEL_TEXT[label]}
    </span>
  );
}

const ROLE_STYLE: Record<Role, string> = {
  reference: "text-ink-2",
  control: "text-base",
  candidate: "text-accent",
  rerun: "text-amber",
};

export const ROLE_DOT: Record<Role, string> = {
  reference: "var(--ink-3)",
  control: "var(--base)",
  candidate: "var(--accent)",
  rerun: "var(--amber)",
};

export function RoleTag({ role, className }: { role: Role; className?: string }) {
  return <span className={clsx("text-[13px] font-medium", ROLE_STYLE[role], className)}>{ROLE_TEXT[role]}</span>;
}

/** A run's measured tube color over time, painted from camera Lab readings. */
export function LitmusStrip({ stops, duration, className, height = 10, flipAt }: {
  stops?: StripStop[];
  duration?: number;
  className?: string;
  height?: number;
  flipAt?: number | null;
}) {
  if (!stops || stops.length < 2) {
    return (
      <span className={clsx("block rounded-[3px] border border-dashed border-rule-strong", className)} style={{ height }} title="No camera color recorded" />
    );
  }
  const end = duration && duration > 0 ? duration : stops[stops.length - 1].t || 1;
  const gradient = stops.map((s) => `${s.color} ${Math.min(100, Math.max(0, (s.t / end) * 100)).toFixed(2)}%`).join(", ");
  return (
    <span className={clsx("relative block overflow-hidden rounded-[3px]", className)} style={{ height, background: `linear-gradient(90deg, ${gradient})` }}
      title="Tube color measured by the camera, start to end">
      {flipAt != null && end > 0 ? (
        <span className="absolute inset-y-0 w-px bg-ink/70" style={{ left: `${(flipAt / end) * 100}%` }} aria-hidden />
      ) : null}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-md bg-sunken", className)} />;
}

export function SyntheticTag() {
  return (
    <span className="rounded border border-dashed border-ink-3 px-1.5 text-[11px] text-ink-2" title="Generated test data, not a real station recording">
      synthetic
    </span>
  );
}
