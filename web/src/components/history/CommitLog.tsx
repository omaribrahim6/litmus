import Link from "next/link";
import clsx from "clsx";
import type { StripStop } from "@/lib/color";
import type { Run } from "@/lib/types";
import { fmtClock, fmtNumber, secondsBetween, shortHash } from "@/lib/format";
import { LitmusStrip, ROLE_DOT, RoleTag, SyntheticTag } from "@/components/ui";

export interface LogRow {
  run: Run;
  strip?: StripStop[];
  verdictId?: string | null;
  verdictLabel?: string | null;
}

/** The lab history as a git log: newest first, one commit-graph node per run, branches for reruns. */
export function CommitLog({ rows, unit }: { rows: LogRow[]; unit?: string }) {
  const ordered = [...rows].reverse();
  const branched = new Set(ordered.filter((r) => r.run.parent_run_id).map((r) => r.run.id));
  return (
    <ol className="relative">
      {ordered.map(({ run, strip, verdictId, verdictLabel }, i) => {
        const onBranch = branched.has(run.id);
        const duration = secondsBetween(run.started_at, run.ended_at) || undefined;
        const recording = run.status === "recording";
        const value = run.result?.value;
        return (
          <li key={run.id} className="relative grid grid-cols-[44px_minmax(0,1fr)_150px] items-stretch max-lg:grid-cols-[44px_minmax(0,1fr)]">
            {/* commit graph lane */}
            <div className="relative" aria-hidden>
              <span className={clsx("absolute left-[15px] w-px bg-rule-strong", i === 0 ? "top-1/2" : "top-0", i === ordered.length - 1 ? "bottom-1/2" : "bottom-0")} />
              {onBranch ? (
                <>
                  <span className="absolute left-[15px] top-0 h-1/2 w-[14px] rounded-br-[10px] border-b border-r border-rule-strong" />
                  <span className="absolute left-[29px] top-1/2 bottom-0 w-px bg-rule-strong" />
                </>
              ) : null}
              <span
                className={clsx("absolute top-1/2 size-[11px] -translate-y-1/2 rounded-full border-2 border-paper", recording && "live-dot")}
                style={{ left: onBranch ? 24 : 10, background: ROLE_DOT[run.role], boxShadow: "0 0 0 1px var(--rule-strong)" }}
              />
            </div>

            <Link href={`/runs/${run.id}`}
              className="grid grid-cols-[72px_minmax(0,1.3fr)_minmax(140px,1fr)_96px_64px] items-center gap-4 border-b border-rule py-3.5 pr-3 transition-colors hover:bg-surface max-lg:grid-cols-[64px_minmax(0,1fr)_88px]">
              <span className="num text-[12px] text-ink-3" title={run.head_hash ?? undefined}>{shortHash(run.head_hash)}</span>
              <span className="min-w-0">
                <span className="flex items-baseline gap-2">
                  <span className="truncate text-[15px] font-medium">{run.label ?? "Unlabeled run"}</span>
                  {recording ? <span className="shrink-0 text-[12px] font-medium text-accent">recording</span> : null}
                </span>
                <span className="mt-0.5 flex min-w-0 items-center gap-2 text-[13px] text-ink-2">
                  <RoleTag role={run.role} className="shrink-0 text-[12.5px]" />
                  {run.metadata?.synthetic ? <SyntheticTag /> : null}
                  <span className="truncate">
                    {verdictLabel ? verdictLabel : run.assumed_cause ? `Assumed cause: ${run.assumed_cause}` : `${run.event_count ?? 0} commits`}
                  </span>
                </span>
              </span>
              <span className="max-lg:hidden">
                <LitmusStrip stops={strip} duration={duration} height={12} />
              </span>
              <span className="num text-right text-[17px]">
                {value != null ? <>{fmtNumber(value)}<span className="ml-1 text-[12px] text-ink-2">{unit}</span></> : <span className="text-[13px] text-ink-3">{recording ? "running" : "no flip"}</span>}
              </span>
              <span className="num text-right text-[12px] text-ink-3 max-lg:hidden">{fmtClock(run.started_at)}</span>
            </Link>

            <div className="flex items-center justify-end border-b border-rule pr-1 max-lg:hidden">
              {verdictId ? (
                <Link href={`/compare/${verdictId}`} className="rounded-md border border-rule-strong px-2.5 py-1 text-[12.5px] font-medium hover:bg-surface">
                  Open verdict
                </Link>
              ) : run.role === "candidate" && run.status === "complete" ? (
                <Link href={`/compare/start?candidate=${run.id}`} className="rounded-md bg-ink px-2.5 py-1 text-[12.5px] font-medium text-paper hover:opacity-90">
                  Run the litmus test
                </Link>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
