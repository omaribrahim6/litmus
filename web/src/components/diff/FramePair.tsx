"use client";

import { useEffect, useState } from "react";
import { fetchEvidence, useEvidence } from "@/components/evidence/EvidenceProvider";
import { Sparkline } from "@/components/charts/Sparkline";
import { ProvenanceIcon } from "@/components/ui";
import type { Evidence } from "@/lib/types";

function pickFrame(ev: Record<string, Evidence | null>, ids: string[]): { url: string; caption: string; id: string } | null {
  for (const id of ids) {
    const e = ev[id];
    if (e?.type === "frame" && e.url) return { url: e.url, caption: "Keyframe", id };
    if (e?.type === "event" && e.frames?.length) return { url: e.frames[0].url, caption: e.summary ?? "", id };
  }
  return null;
}

function pickSeries(ev: Record<string, Evidence | null>, ids: string[]): Evidence | null {
  for (const id of ids) if (ev[id]?.type === "series") return ev[id];
  return null;
}

function pickEvent(ev: Record<string, Evidence | null>, ids: string[]): Evidence | null {
  for (const id of ids) if (ev[id]?.type === "event") return ev[id];
  return null;
}

/** The two runs' evidence for one variable, side by side. */
export function FramePair({ left, right, leftLabel, rightLabel }: { left: string[]; right: string[]; leftLabel: string; rightLabel: string }) {
  const [ev, setEv] = useState<Record<string, Evidence | null> | null>(null);
  const { open } = useEvidence();
  useEffect(() => {
    let alive = true;
    fetchEvidence([...left.slice(0, 6), ...right.slice(0, 6)]).then((d) => alive && setEv(d));
    return () => { alive = false; };
  }, [left, right]);

  const side = (ids: string[], label: string, tone: string) => {
    if (!ev) return <div className="aspect-video animate-pulse rounded-lg bg-sunken" />;
    const frame = pickFrame(ev, ids);
    const series = frame ? null : pickSeries(ev, ids);
    const event = pickEvent(ev, ids);
    return (
      <button type="button" onClick={() => open(ids, `${label}: evidence`)} className="group block w-full text-left">
        <div className="mb-1.5 flex items-center justify-between text-[12.5px]">
          <span className="font-medium" style={{ color: tone }}>{label}</span>
          {event ? <ProvenanceIcon p={event.provenance} withText /> : series ? <ProvenanceIcon p={series.provenance} withText /> : null}
        </div>
        {frame ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={frame.url} alt={frame.caption} className="aspect-video w-full rounded-lg border border-rule object-cover transition-shadow group-hover:shadow-panel" />
        ) : series ? (
          <div className="rounded-lg border border-rule bg-paper p-3">
            <Sparkline points={(series.points ?? []).map((p) => p.value)} height={64} />
            <p className="num mt-1 text-[11px] text-ink-3">{series.sensor}, {series.n} samples</p>
          </div>
        ) : (
          <div className="flex aspect-[16/7] items-center justify-center rounded-lg border border-dashed border-rule-strong text-[12.5px] text-ink-2">
            {ids.length ? "Recorded as a commit, no frame" : "Not recorded"}
          </div>
        )}
        {event?.summary ? <p className="mt-1.5 text-[13px] leading-snug text-ink-2">{event.summary}</p> : null}
      </button>
    );
  };

  return (
    <div className="grid grid-cols-2 gap-4">
      {side(left, leftLabel, "var(--accent)")}
      {side(right, rightLabel, "var(--base)")}
    </div>
  );
}
