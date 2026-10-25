"use client";

import { useRef } from "react";
import clsx from "clsx";
import { Activity, Clapperboard, GitCommitHorizontal, ListChecks, Mic, Palette, ScanEye } from "lucide-react";
import type { StripStop } from "@/lib/color";
import type { Frame, LitmusEvent, Provenance } from "@/lib/types";
import { fmtNumber, KIND_TEXT } from "@/lib/format";
import type { LaneSeries } from "./Lanes";

const GUTTER = 148;
const PROV_COLOR: Record<Provenance, string> = { measured: "var(--ink-2)", reported: "var(--base)", inferred: "var(--amber)" };
// Step clips: one hue each, mixed into the surface so they read in light and dark themes.
const STEP_HUES = ["#3d6fe0", "#d07a16", "#23955e", "#8a52d6", "#d0436e", "#2a8c9b"];

export interface Mark { e: LitmusEvent; t: number }

function clock(t: number) {
  const s = Math.max(0, t);
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}

/** Two rows: a pill drops to the second row when it would overlap the previous one. */
function rows(ms: Mark[], D: number): Map<string, number> {
  const out = new Map<string, number>();
  const lastEnd = [-Infinity, -Infinity];
  for (const m of ms) {
    const r = m.t >= lastEnd[0] ? 0 : m.t >= lastEnd[1] ? 1 : (lastEnd[0] <= lastEnd[1] ? 0 : 1);
    out.set(m.e.id, r);
    lastEnd[r] = m.t + D * 0.16;
  }
  return out;
}

function valueAt(points: { t: number; v: number }[], t: number): number | null {
  let best: number | null = null;
  for (const p of points) {
    if (p.t <= t) best = p.v;
    else break;
  }
  return best;
}

/** One time axis for everything recorded: drag anywhere to move the playhead (and the video). */
export function Timeline({ duration, cursor, onSeek, marks, frames, frameT, strip, series, activeId, onSelect }: {
  duration: number;
  cursor: number;
  onSeek: (t: number) => void;
  marks: Mark[];
  frames: Frame[];
  frameT: (f: Frame) => number;
  strip?: StripStop[];
  series: LaneSeries[];
  activeId: string | null;
  onSelect: (m: Mark) => void;
}) {
  const area = useRef<HTMLDivElement>(null);
  const D = Math.max(duration, 1);
  const pct = (t: number) => `${Math.min(100, Math.max(0, (t / D) * 100))}%`;

  const seekFrom = (clientX: number) => {
    const el = area.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const w = r.width - GUTTER;
    if (w > 0) onSeek(Math.min(D, Math.max(0, ((clientX - r.left - GUTTER) / w) * D)));
  };

  const steps = marks.filter((m) => m.e.kind === "step_confirmed");
  const speech = marks.filter((m) => ["narration", "hypothesis_stated", "session_intro"].includes(m.e.kind));
  const gemini = marks.filter((m) => m.e.provenance === "inferred" && !["narration", "hypothesis_stated", "session_intro", "step_confirmed"].includes(m.e.kind));
  const commits = marks.filter((m) => !steps.includes(m) && !speech.includes(m) && !gemini.includes(m));
  const flip = marks.find((m) => m.e.kind === "flip_detected");
  const speechRows = rows(speech, D);
  const geminiRows = rows(gemini, D);

  // Film strip: evenly spaced thumbnails, each the frame nearest its slot.
  const slots = 14;
  const film = frames.length
    ? Array.from({ length: slots }, (_, i) => {
      const t = ((i + 0.5) / slots) * D;
      return frames.reduce((b, f) => (Math.abs(frameT(f) - t) < Math.abs(frameT(b) - t) ? f : b));
    })
    : [];

  const step = D > 600 ? 120 : D > 240 ? 60 : D > 90 ? 15 : 5;
  const ticks = Array.from({ length: Math.floor(D / step) + 1 }, (_, i) => i * step);

  const Track = ({ icon, label, h = 40, children }: { icon: React.ReactNode; label: React.ReactNode; h?: number; children: React.ReactNode }) => (
    <div className="flex border-t border-rule" style={{ height: h }}>
      <div className="flex shrink-0 items-center gap-2 border-r border-rule bg-side px-3 text-[12px] text-ink-2" style={{ width: GUTTER }}>
        <span className="text-ink-3">{icon}</span>
        <span className="min-w-0 truncate">{label}</span>
      </div>
      <div className="relative flex-1 overflow-hidden">{children}</div>
    </div>
  );

  const Pill = ({ m, tone, text, row }: { m: Mark; tone: "speech" | "gemini"; text: string; row: number }) => (
    <button type="button" onClick={() => onSelect(m)} title={m.e.summary}
      className={clsx("absolute flex h-[24px] max-w-[220px] items-center gap-1.5 truncate rounded-md border px-2 text-[11.5px] font-medium shadow-panel transition hover:z-10 hover:max-w-[420px]",
        tone === "speech" ? "border-base/25 bg-base-soft text-base" : "border-amber/25 bg-amber-soft text-amber",
        activeId === m.e.id && "z-10 ring-2 ring-ink/70")}
      style={{ left: pct(m.t), top: 5 + row * 28 }}>
      {tone === "speech" ? <Mic size={11} className="shrink-0" /> : <ScanEye size={11} className="shrink-0" />}
      <span className="truncate">{text}</span>
    </button>
  );

  return (
    <div ref={area} className="relative select-none overflow-hidden rounded-xl border border-rule bg-surface"
      onPointerDown={(e) => {
        if ((e.target as HTMLElement).closest("button")) return;
        (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
        seekFrom(e.clientX);
      }}
      onPointerMove={(e) => { if (e.buttons === 1) seekFrom(e.clientX); }}>
      {/* ruler */}
      <div className="flex h-7">
        <div className="flex shrink-0 items-center border-r border-rule bg-side px-3 text-[11px] text-ink-3" style={{ width: GUTTER }}>
          <span className="num">{clock(cursor)} / {clock(D)}</span>
        </div>
        <div className="relative flex-1 cursor-ew-resize">
          {ticks.map((t) => (
            <span key={t} className="absolute bottom-0 top-0" style={{ left: pct(t) }}>
              <span className="absolute bottom-0 h-2 w-px bg-rule-strong" />
              <span className="num absolute left-1 top-1.5 text-[10px] text-ink-3">{clock(t)}</span>
            </span>
          ))}
        </div>
      </div>

      <Track icon={<Clapperboard size={13} />} label="Camera" h={52}>
        {film.length ? (
          <div className="absolute inset-y-1.5 left-0 right-0 flex overflow-hidden rounded-md ring-1 ring-rule">
            {film.map((f, i) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={`${f.id}-${i}`} src={f.url} alt="" className="h-full min-w-0 flex-1 object-cover" draggable={false} />
            ))}
          </div>
        ) : <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[11.5px] text-ink-3">No frames</span>}
      </Track>

      {steps.length ? (
        <Track icon={<ListChecks size={13} />} label="Steps">
          {steps.map((m, i) => {
            const end = steps[i + 1]?.t ?? D;
            const title = m.e.summary.replace(/^(Step (seen|confirmed): )/, "");
            return (
              <button key={m.e.id} type="button" onClick={() => onSelect(m)} title={title}
                className={clsx("absolute inset-y-1.5 truncate rounded-md px-2 text-left text-[11.5px] font-medium transition hover:brightness-95", activeId === m.e.id && "ring-2 ring-ink/70")}
                style={{ left: pct(m.t), width: `calc(${pct(end - m.t)} - 2px)`, background: `color-mix(in oklab, ${STEP_HUES[i % 6]} 16%, var(--surface))`,
                  color: `color-mix(in oklab, ${STEP_HUES[i % 6]} 75%, var(--ink))`, boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${STEP_HUES[i % 6]} 28%, transparent)` }}>
                {title}
              </button>
            );
          })}
        </Track>
      ) : null}

      {speech.length ? (
        <Track icon={<Mic size={13} />} label="Speech" h={speechRows.size && Math.max(...speechRows.values()) ? 62 : 34}>
          {speech.map((m) => <Pill key={m.e.id} m={m} tone="speech" row={speechRows.get(m.e.id) ?? 0} text={String((m.e.payload as { text?: string } | null)?.text ?? m.e.summary).replace(/^Session intro: /, "")} />)}
        </Track>
      ) : null}

      {gemini.length ? (
        <Track icon={<ScanEye size={13} />} label="Seen by Gemini" h={geminiRows.size && Math.max(...geminiRows.values()) ? 62 : 34}>
          {gemini.map((m) => <Pill key={m.e.id} m={m} tone="gemini" row={geminiRows.get(m.e.id) ?? 0} text={m.e.summary} />)}
        </Track>
      ) : null}

      <Track icon={<GitCommitHorizontal size={13} />} label="Commits" h={32}>
        {commits.map((m) => (
          <button key={m.e.id} type="button" onClick={() => onSelect(m)} title={`${KIND_TEXT[m.e.kind] ?? m.e.kind}: ${m.e.summary}`}
            className={clsx("absolute top-1/2 size-[9px] -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-[2px] transition hover:scale-150", activeId === m.e.id && "scale-150 ring-2 ring-ink/70")}
            style={{ left: pct(m.t), background: m.e.kind === "flip_detected" ? "var(--accent)" : PROV_COLOR[m.e.provenance] }} />
        ))}
      </Track>

      {strip && strip.length > 1 ? (
        <Track icon={<Palette size={13} />} label="Liquid color" h={30}>
          <div className="absolute inset-x-0 inset-y-2 rounded"
            style={{ background: `linear-gradient(90deg, ${strip.map((s) => `${s.color} ${((s.t / D) * 100).toFixed(2)}%`).join(", ")})` }} />
        </Track>
      ) : null}

      {series.filter((s) => !s.missing && s.points.length > 1).map((s) => {
        const vs = s.points.map((p) => p.v);
        const min = Math.min(...vs);
        const span = Math.max(...vs) - min || 1;
        const d = s.points.map((p, i) => `${i ? "L" : "M"}${((p.t / D) * 1000).toFixed(1)},${(34 - ((p.v - min) / span) * 28).toFixed(1)}`).join(" ");
        const v = valueAt(s.points, cursor);
        return (
          <Track key={s.sensor} icon={<Activity size={13} />} label={<span className="flex justify-between gap-2"><span className="truncate">{s.label}</span>{v != null ? <span className="num text-ink">{fmtNumber(v, Math.abs(v) < 10 ? 2 : 1)}</span> : null}</span>} h={40}>
            <svg viewBox="0 0 1000 38" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden>
              <path d={`${d} L1000,38 L0,38 Z`} fill="var(--base-soft)" opacity={0.6} />
              <path d={d} fill="none" stroke="var(--base)" strokeWidth={1.4} vectorEffect="non-scaling-stroke" />
            </svg>
          </Track>
        );
      })}

      {/* playhead and color-change marker span every track */}
      <div className="pointer-events-none absolute bottom-0 top-0" style={{ left: GUTTER, right: 0 }}>
        {flip ? <div className="absolute inset-y-7 w-px bg-accent/70" style={{ left: pct(flip.t) }} /> : null}
        <div className="absolute bottom-0 top-0 w-[2px] -translate-x-1/2 bg-ink" style={{ left: pct(cursor) }}>
          <span className="absolute -left-[5px] top-0 h-3 w-3 rounded-b-[3px] bg-ink" />
        </div>
      </div>
    </div>
  );
}
