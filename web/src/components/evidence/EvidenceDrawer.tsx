"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { fetchEvidence } from "./EvidenceProvider";
import { ProvenanceIcon } from "@/components/ui";
import { Sparkline } from "@/components/charts/Sparkline";
import { fmtNumber, fmtValue, KIND_TEXT, shortHash } from "@/lib/format";
import type { Evidence } from "@/lib/types";

function TypeName({ e }: { e: Evidence }) {
  const text = { event: "Commit", frame: "Video frame", series: "Sensor series", reading: "Sensor reading", run: "Run record" }[e.type];
  return <span className="text-[12px] text-ink-2">{text}</span>;
}

function when(e: Evidence): string {
  const t = e.t ?? e.start;
  return t ? new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
}

function runLink(e: Evidence): string {
  const t = e.t ?? e.start;
  return `/runs/${e.run_id}${t ? `?at=${encodeURIComponent(t)}` : ""}`;
}

function EvidenceCard({ id, e }: { id: string; e: Evidence | null | undefined }) {
  if (e === undefined) {
    return <div className="h-28 animate-pulse rounded-lg bg-sunken" />;
  }
  if (e === null) {
    return (
      <div className="rounded-lg border border-dashed border-rule-strong p-3 text-[13px] text-ink-2">
        <div className="num break-all text-[11px] text-ink-3">{id}</div>
        This evidence is not in the record. It may have been removed, which the hash chain would flag.
      </div>
    );
  }
  return (
    <article className="rounded-lg border border-rule bg-surface p-3.5">
      <header className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <TypeName e={e} />
          <ProvenanceIcon p={e.provenance} withText />
        </div>
        <span className="num text-[11px] text-ink-3">{when(e)}</span>
      </header>

      {e.type === "event" ? (
        <div className="space-y-2">
          <p className="text-[15px] leading-snug">
            <span className="text-ink-2">{KIND_TEXT[e.kind ?? ""] ?? e.kind}: </span>
            {e.summary}
          </p>
          {e.provenance === "inferred" && e.confidence != null && e.confidence < 0.6 ? (
            <p className="text-[12px] text-amber">Low-confidence inference. Check the frame or recording.</p>
          ) : null}
          {typeof e.payload?.audio_url === "string" ? (
            <div className="space-y-1">
              {typeof e.payload?.transcript === "string" ? <p className="text-[13px] italic text-ink-2">“{e.payload.transcript}”</p> : null}
              <audio controls preload="none" src={e.payload.audio_url} className="w-full" />
              <p className="text-[11px] text-ink-3">
                Recorded{typeof e.payload?.mic === "string" ? ` on the ${e.payload.mic} mic` : ""}, transcribed by Gemini
                {typeof e.payload?.offset_s === "number" ? `, ${e.payload.offset_s}s into the clip` : ""}
              </p>
            </div>
          ) : null}
          {e.frames?.map((f) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={f.id} src={f.url} alt={`Frame at ${e.summary}`} className="w-full rounded-md border border-rule" />
          ))}
          <div className="num flex flex-wrap gap-x-3 text-[11px] text-ink-3">
            <span>commit {e.seq}</span>
            <span>{shortHash(e.hash, 12)}</span>
          </div>
        </div>
      ) : null}

      {e.type === "frame" ? (
        <div className="space-y-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={e.url} alt="Keyframe" className="w-full rounded-md border border-rule" />
          {e.metrics ? (
            <div className="flex items-center gap-2 text-[12px] text-ink-2">
              <span className="inline-block size-3.5 rounded-sm border border-rule" style={{ background: `rgb(${e.metrics.r} ${e.metrics.g} ${e.metrics.b})` }} />
              <span>Tube color in the measurement region</span>
              <span className="num ml-auto">a* {fmtNumber(e.metrics.lab_a, 1)}</span>
            </div>
          ) : null}
        </div>
      ) : null}

      {e.type === "series" ? (
        <div className="space-y-2">
          <p className="text-[15px]">
            <span className="num">{e.sensor}</span>
            <span className="text-ink-2"> over {e.n} samples</span>
          </p>
          <Sparkline points={(e.points ?? []).map((p) => p.value)} height={56} />
          <dl className="num grid grid-cols-3 gap-2 text-[12px]">
            <div><dt className="text-ink-3">mean</dt><dd>{fmtNumber(e.mean, 3)}</dd></div>
            <div><dt className="text-ink-3">min</dt><dd>{fmtNumber(e.min, 3)}</dd></div>
            <div><dt className="text-ink-3">max</dt><dd>{fmtNumber(e.max, 3)}</dd></div>
          </dl>
        </div>
      ) : null}

      {e.type === "reading" ? (
        <p className="text-[15px]">
          <span className="num">{e.sensor}</span> = <span className="num">{fmtNumber(e.value, 3)}</span> <span className="text-ink-2">{e.unit}</span>
        </p>
      ) : null}

      {e.type === "run" ? (
        <div className="space-y-1 text-[14px]">
          <p className="font-medium">{e.label} <span className="text-ink-2">({e.role})</span></p>
          {e.assumed_cause ? <p className="text-ink-2">Assumed cause, as entered: “{e.assumed_cause}”</p> : null}
          {e.result?.value != null ? (
            <p className="text-ink-2">
              {e.result.label}: <span className="num text-ink">{fmtValue(e.result.value)} {typeof e.result.value === "number" ? e.result.unit : ""}</span>
            </p>
          ) : null}
        </div>
      ) : null}

      <footer className="mt-3 flex items-center justify-between gap-2 border-t border-rule pt-2">
        <span className="truncate text-[12px] text-ink-2">{e.run_label}</span>
        <Link href={runLink(e)} className="shrink-0 text-[12px] font-medium text-base hover:underline">
          Open in run
        </Link>
      </footer>
    </article>
  );
}

export function EvidenceDrawer({ ids, title, onClose }: { ids: string[]; title?: string; onClose: () => void }) {
  const [data, setData] = useState<Record<string, Evidence | null> | null>(null);
  useEffect(() => {
    let alive = true;
    fetchEvidence(ids).then((d) => alive && setData(d)).catch(() => alive && setData({}));
    return () => {
      alive = false;
    };
  }, [ids]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Evidence">
      <button type="button" aria-label="Close evidence" className="absolute inset-0 bg-ink/20 backdrop-blur-[1px]" onClick={onClose} />
      <aside className="scroll-thin relative flex h-full w-full max-w-[460px] flex-col overflow-y-auto border-l border-rule bg-paper shadow-panel">
        <header className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-rule bg-paper/95 px-5 py-4 backdrop-blur">
          <div>
            <h2 className="text-[16px] font-semibold">Evidence</h2>
            <p className="mt-0.5 text-[13px] leading-snug text-ink-2">{title ?? `${ids.length} item${ids.length === 1 ? "" : "s"} from the record`}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-ink-2 hover:bg-sunken hover:text-ink" aria-label="Close">
            <X size={18} />
          </button>
        </header>
        <div className="space-y-3 p-5">
          {ids.map((id) => (
            <EvidenceCard key={id} id={id} e={data ? data[id] : undefined} />
          ))}
        </div>
      </aside>
    </div>
  );
}
