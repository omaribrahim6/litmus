"use client";

import { useRef } from "react";
import clsx from "clsx";
import type { StripStop } from "@/lib/color";
import type { LitmusEvent, Provenance } from "@/lib/types";
import { fmtNumber, KIND_TEXT } from "@/lib/format";

export interface LaneSeries {
  sensor: string;
  label: string;
  unit?: string | null;
  points: { t: number; v: number }[];
  provenance?: Provenance;
  missing?: boolean;
  note?: string;
}

const GUTTER = 168;

const PROV_COLOR: Record<Provenance, string> = { measured: "var(--ink-2)", reported: "var(--base)", inferred: "var(--amber)" };

function valueAt(points: { t: number; v: number }[], t: number): number | null {
  if (!points.length) return null;
  let best = points[0];
  for (const p of points) {
    if (p.t <= t) best = p;
    else break;
  }
  return best.v;
}

/** Synced lanes on one time axis. Click or drag anywhere to move the cursor (and the video). */
export function Lanes({ duration, cursor, onSeek, events, strip, series, flipAt, activeId }: {
  duration: number;
  cursor: number;
  onSeek: (t: number) => void;
  events: { e: LitmusEvent; t: number }[];
  strip?: StripStop[];
  series: LaneSeries[];
  flipAt?: number | null;
  activeId?: string | null;
}) {
  const area = useRef<HTMLDivElement>(null);
  const D = Math.max(duration, 1);
  const pct = (t: number) => `${Math.min(100, Math.max(0, (t / D) * 100))}%`;

  const seekFromEvent = (clientX: number) => {
    const el = area.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = clientX - rect.left - GUTTER;
    const w = rect.width - GUTTER;
    if (w <= 0) return;
    onSeek(Math.min(D, Math.max(0, (x / w) * D)));
  };

  const commits = events.filter(({ e }) => e.provenance !== "reported" && e.kind !== "run_sealed");
  const human = events.filter(({ e }) => e.provenance === "reported");
  const ticks = Array.from({ length: Math.floor(D / 15) + 1 }, (_, i) => i * 15).filter((t) => t <= D);

  const Row = ({ label, sub, children, h = 36, value }: { label: string; sub?: string; children: React.ReactNode; h?: number; value?: React.ReactNode }) => (
    <div className="flex border-b border-rule last:border-b-0" style={{ height: h }}>
      <div className="flex shrink-0 flex-col justify-center pr-3" style={{ width: GUTTER }}>
        <span className="flex items-baseline justify-between gap-2 text-[12.5px] leading-tight">
          <span className="truncate">{label}</span>
          {value !== undefined ? <span className="num text-[11.5px] text-ink">{value}</span> : null}
        </span>
        {sub ? <span className="truncate text-[11px] leading-tight text-ink-3">{sub}</span> : null}
      </div>
      <div className="relative flex-1">{children}</div>
    </div>
  );

  return (
    <div
      ref={area}
      className="relative select-none rounded-xl border border-rule bg-surface px-4 py-2"
      onPointerDown={(e) => {
        if ((e.target as HTMLElement).closest("button")) return;
        (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
        seekFromEvent(e.clientX);
      }}
      onPointerMove={(e) => {
        if (e.buttons === 1) seekFromEvent(e.clientX);
      }}
    >
      {/* time axis */}
      <div className="flex h-6 border-b border-rule">
        <div style={{ width: GUTTER }} className="shrink-0 text-[11px] leading-6 text-ink-3">seconds from start</div>
        <div className="relative flex-1">
          {ticks.map((t) => (
            <span key={t} className="num absolute top-1 -translate-x-1/2 text-[10.5px] text-ink-3" style={{ left: pct(t) }}>{t}</span>
          ))}
        </div>
      </div>

      <Row label="Commits" sub="sensors, camera, Gemini" h={34}>
        {commits.map(({ e, t }) => (
          <button key={e.id} type="button" onClick={() => onSeek(t)} title={`${KIND_TEXT[e.kind] ?? e.kind}: ${e.summary}`}
            className={clsx("absolute top-1/2 h-[18px] w-[5px] -translate-x-1/2 -translate-y-1/2 rounded-[2px] transition-transform hover:scale-y-125",
              activeId === e.id && "ring-2 ring-base ring-offset-1 ring-offset-surface")}
            style={{ left: pct(t), background: e.kind === "flip_detected" ? "var(--accent)" : PROV_COLOR[e.provenance] }} />
        ))}
      </Row>

      <Row label="Tube color" sub="camera, measured" h={40}>
        {strip && strip.length > 1 ? (
          <div className="absolute inset-x-0 top-[9px] h-[22px] rounded-[3px]"
            style={{ background: `linear-gradient(90deg, ${strip.map((s) => `${s.color} ${((s.t / D) * 100).toFixed(2)}%`).join(", ")})` }} />
        ) : (
          <div className="absolute inset-x-0 top-[9px] h-[22px] rounded-[3px] border border-dashed border-rule-strong" />
        )}
      </Row>

      {series.map((s) => {
        const v = valueAt(s.points, cursor);
        if (s.missing || !s.points.length) {
          return (
            <Row key={s.sensor} label={s.label} sub={s.note ?? "sensor not connected"} h={30}>
              <div className="absolute inset-x-0 top-1/2 border-t border-dashed border-rule-strong" />
              <span className="absolute left-2 top-1/2 -translate-y-1/2 bg-surface px-1.5 text-[11px] text-ink-3">missing, never estimated</span>
            </Row>
          );
        }
        const vs = s.points.map((p) => p.v);
        const min = Math.min(...vs);
        const max = Math.max(...vs);
        const span = max - min || 1;
        const d = s.points.map((p, i) => `${i ? "L" : "M"}${((p.t / D) * 1000).toFixed(1)},${(36 - ((p.v - min) / span) * 30).toFixed(1)}`).join(" ");
        return (
          <Row key={s.sensor} label={s.label} sub={`${s.provenance ?? "measured"}${s.unit ? `, ${s.unit}` : ""}`} h={44}
            value={v != null ? fmtNumber(v, Math.abs(v) < 10 ? 2 : 1) : undefined}>
            <svg viewBox="0 0 1000 40" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" aria-hidden>
              <path d={d} fill="none" stroke={s.provenance === "reported" ? "var(--base)" : "var(--ink)"} strokeWidth={1.4} vectorEffect="non-scaling-stroke" />
            </svg>
          </Row>
        );
      })}

      <Row label="Researcher" sub="confirmed at the station" h={34}>
        {human.map(({ e, t }) => (
          <button key={e.id} type="button" onClick={() => onSeek(t)} title={e.summary}
            className={clsx("absolute top-1/2 size-[9px] -translate-x-1/2 -translate-y-1/2 rotate-45 border border-base bg-base-soft hover:bg-base",
              activeId === e.id && "bg-base")}
            style={{ left: pct(t) }} />
        ))}
      </Row>

      {/* flip marker and cursor span every lane */}
      <div className="pointer-events-none absolute bottom-2 top-2" style={{ left: `calc(1rem + ${GUTTER}px)`, right: "1rem" }}>
        {flipAt != null ? (
          <div className="absolute inset-y-0 w-px bg-accent/60" style={{ left: pct(flipAt) }}>
            <span className="absolute -top-0.5 left-1 whitespace-nowrap text-[10.5px] font-medium text-accent">flip</span>
          </div>
        ) : null}
        <div className="absolute inset-y-0 w-px bg-base" style={{ left: pct(cursor) }}>
          <span className="num absolute -bottom-0.5 left-1 rounded bg-base px-1 text-[10px] text-paper">{cursor.toFixed(1)}s</span>
        </div>
      </div>
    </div>
  );
}
