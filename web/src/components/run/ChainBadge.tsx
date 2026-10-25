import { ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";
import type { VerifyReport } from "@/lib/types";
import { plural, shortHash } from "@/lib/format";

/** Hash-chain status, recomputed by the worker from every commit (and the sealed readings digest). */
export function ChainBadge({ report }: { report: VerifyReport }) {
  if (report.unavailable) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-rule-strong px-2.5 py-1 text-[12.5px] text-ink-2"
        title="The worker that recomputes the hash chain is not reachable right now">
        <ShieldQuestion size={14} /> Chain not checked
      </span>
    );
  }
  if (report.intact) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-ok/30 bg-ok-soft px-2.5 py-1 text-[12.5px] font-medium text-ok"
        title={`Recomputed ${report.checked} hashes${report.sealed ? `, plus ${report.readings} readings and ${report.frames} frames sealed in the record` : ""}. Head ${report.head}`}>
        <ShieldCheck size={14} /> Record intact
        <span className="num font-normal opacity-80">{plural(report.checked, "commit")}{report.head ? `, ${shortHash(report.head)}` : ""}</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-accent/40 bg-accent-soft px-2.5 py-1 text-[12.5px] font-medium text-accent"
      title={report.reason}>
      <ShieldAlert size={14} /> Record modified at commit {report.broken_at_seq}: {report.reason}
    </span>
  );
}
