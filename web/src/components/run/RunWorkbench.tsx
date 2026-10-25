"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { labCss, type StripStop } from "@/lib/color";
import type { Frame, LitmusEvent, ReadingBucket, Run } from "@/lib/types";
import { fmtOffset, KIND_TEXT, shortHash } from "@/lib/format";
import { ProvenanceIcon } from "@/components/ui";
import { useEvidence } from "@/components/evidence/EvidenceProvider";
import { Lanes, type LaneSeries } from "./Lanes";

const SENSOR_LANES: { sensor: string; label: string }[] = [
  { sensor: "lab_a", label: "Color, red-green (a*)" },
  { sensor: "light", label: "Light through tube" },
  { sensor: "mix_angle", label: "Mixing (holder angle)" },
  { sensor: "temp_c", label: "Temperature" },
  { sensor: "air_quality", label: "Air quality" },
  { sensor: "humidity", label: "Humidity" },
];

function ms(iso: string) {
  return new Date(iso).getTime();
}

export function RunWorkbench({ initialRun, initialEvents, initialReadings, initialFrames, initialAt }: {
  initialRun: Run;
  initialEvents: LitmusEvent[];
  initialReadings: ReadingBucket[];
  initialFrames: Frame[];
  initialAt?: string | null;
}) {
  const [run, setRun] = useState(initialRun);
  const [events, setEvents] = useState(initialEvents);
  const [readings, setReadings] = useState(initialReadings);
  const [frames, setFrames] = useState(initialFrames);
  const video = useRef<HTMLVideoElement>(null);
  const list = useRef<HTMLOListElement>(null);
  const { open } = useEvidence();
  const live = run.status === "recording";
  const actionVideo = typeof run.metadata?.action_video_url === "string" ? run.metadata.action_video_url : null;
  const [cam, setCam] = useState<"bench" | "action">("bench");

  const t0 = useMemo(() => ms(run.started_at ?? events[0]?.t ?? new Date().toISOString()), [run.started_at, events]);
  const videoT0 = useMemo(() => (run.metadata?.video_started_at ? ms(run.metadata.video_started_at) : t0), [run.metadata, t0]);
  const offset = (iso: string) => (ms(iso) - t0) / 1000;

  const lastT = Math.max(
    run.ended_at ? offset(run.ended_at) : 0,
    ...events.filter((e) => e.kind !== "run_sealed").map((e) => offset(e.t)),
    ...readings.map((r) => offset(r.bucket)),
    1,
  );
  const duration = live ? Math.max(lastT + 5, 30) : lastT;
  const [cursor, setCursor] = useState(() => (initialAt ? Math.max(0, offset(initialAt)) : 0));

  // Poll for new commits while the station is recording.
  useEffect(() => {
    if (!live) return;
    let alive = true;
    const tick = async () => {
      const after = events.length ? Math.max(...events.map((e) => e.seq)) : -1;
      try {
        const res = await fetch(`/api/runs/${run.id}/live?after=${after}`, { cache: "no-store" });
        if (!res.ok || !alive) return;
        const data = await res.json();
        setRun(data.run);
        if (data.events.length) setEvents((prev) => [...prev, ...data.events].sort((a, b) => a.t.localeCompare(b.t) || a.seq - b.seq));
        setReadings(data.readings);
        setFrames(data.frames);
      } catch {
        /* next tick retries */
      }
    };
    const id = setInterval(tick, 1500);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [live, run.id, events]);

  const seek = useCallback((t: number) => {
    setCursor(t);
    const v = video.current;
    if (v) {
      const vt = t - (videoT0 - t0) / 1000;
      if (Number.isFinite(vt)) v.currentTime = Math.max(0, Math.min(v.duration || vt, vt));
    }
  }, [videoT0, t0]);

  useEffect(() => {
    if (initialAt) seek(Math.max(0, (ms(initialAt) - t0) / 1000));
    // only on first render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onTime = () => {
    const v = video.current;
    if (v) setCursor(v.currentTime + (videoT0 - t0) / 1000);
  };

  const timeline = useMemo(() => events.filter((e) => e.kind !== "run_sealed").map((e) => ({ e, t: offset(e.t) })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [events, t0]);
  const active = useMemo(() => [...timeline].reverse().find((x) => x.t <= cursor + 0.05)?.e.id ?? null, [timeline, cursor]);

  useEffect(() => {
    if (!active || !list.current) return;
    const el = list.current.querySelector(`[data-id="${active}"]`);
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [active]);

  const bySensor = useMemo(() => {
    const m = new Map<string, { t: number; v: number }[]>();
    for (const r of readings) {
      const arr = m.get(r.sensor) ?? [];
      arr.push({ t: offset(r.bucket), v: r.avg });
      m.set(r.sensor, arr);
    }
    return m;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readings, t0]);

  const strip: StripStop[] = useMemo(() => {
    const L = bySensor.get("lab_l") ?? [];
    const A = bySensor.get("lab_a") ?? [];
    const B = bySensor.get("lab_b") ?? [];
    const n = Math.min(L.length, A.length, B.length);
    const step = Math.max(1, Math.floor(n / 120));
    const out: StripStop[] = [];
    for (let i = 0; i < n; i += step) out.push({ t: L[i].t, color: labCss(L[i].v, A[i].v, B[i].v) });
    return out;
  }, [bySensor]);

  const missing = new Set(((run.metadata?.missing_sensors as string[]) ?? []).map((s) => (s === "temp_probe" ? "temp_c" : s)));
  const series: LaneSeries[] = SENSOR_LANES.filter((l) => bySensor.has(l.sensor) || missing.has(l.sensor) || l.sensor === "temp_c").map((l) => {
    const pts = bySensor.get(l.sensor) ?? [];
    const reported = l.sensor === "temp_c" && events.some((e) => e.kind === "reading_reported" && (e.payload as { sensor?: string } | null)?.sensor === "temp_c");
    return {
      sensor: l.sensor,
      label: l.label,
      points: pts.length > 1 ? pts : [],
      provenance: reported ? "reported" : "measured",
      missing: pts.length <= 1 && !reported,
      note: reported && pts.length <= 1 ? "reported once, from a thermometer" : undefined,
    } satisfies LaneSeries;
  });

  const flip = events.find((e) => e.kind === "flip_detected");
  const flipAt = flip ? offset(flip.t) : null;
  const latestFrame = frames.length ? frames[frames.length - 1] : null;
  const nearestFrame = useMemo(() => {
    if (!frames.length) return null;
    return frames.reduce((best, f) => (Math.abs(offset(f.t) - cursor) < Math.abs(offset(best.t) - cursor) ? f : best));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frames, cursor, t0]);

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,1fr)]">
        <div className="relative overflow-hidden rounded-xl border border-rule bg-sunken">
          {run.video_url && !live && actionVideo ? (
            <div className="absolute right-3 top-3 z-10 flex overflow-hidden rounded-md border border-white/20 bg-black/60 text-[12px] text-white">
              {(["bench", "action"] as const).map((c) => (
                <button key={c} type="button" onClick={() => setCam(c)} className={clsx("px-2.5 py-1", cam === c ? "bg-white/25 font-medium" : "opacity-80 hover:opacity-100")}>
                  {c === "bench" ? "Bench camera" : "Researcher camera"}
                </button>
              ))}
            </div>
          ) : null}
          {run.video_url && !live ? (
            <video ref={video} src={cam === "action" && actionVideo ? actionVideo : run.video_url} controls playsInline preload="metadata"
              onTimeUpdate={onTime} onSeeked={onTime} onLoadedMetadata={() => seek(cursor)}
              className="aspect-video w-full bg-black" />
          ) : (live ? latestFrame : nearestFrame) ? (
            <div className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={(live ? latestFrame : nearestFrame)!.url} alt="Station camera" className="aspect-video w-full bg-black object-contain" />
              {live ? (
                <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded bg-black/60 px-2 py-0.5 text-[12px] font-medium text-white">
                  <span className="live-dot size-1.5 rounded-full bg-accent" /> Live from the station
                </span>
              ) : null}
            </div>
          ) : (
            <div className="flex aspect-video items-center justify-center text-[14px] text-ink-2">
              {live ? "Waiting for the first frame from the station camera" : "No video was recorded for this run"}
            </div>
          )}
        </div>

        <div className="flex max-h-[min(560px,calc((100vw-400px)*0.32))] min-h-[320px] flex-col rounded-xl border border-rule bg-surface">
          <div className="flex items-baseline justify-between border-b border-rule px-4 py-2.5">
            <h2 className="text-[14px] font-semibold">Commits</h2>
            <span className="text-[12px] text-ink-2">{events.length} in the chain{live ? ", recording" : ""}</span>
          </div>
          <ol ref={list} className="scroll-thin flex-1 overflow-y-auto py-1">
            {timeline.map(({ e, t }) => (
              <li key={e.id} data-id={e.id}>
                <div className={clsx("group grid cursor-pointer grid-cols-[54px_16px_minmax(0,1fr)] items-start gap-2 px-4 py-1.5 text-[13.5px] transition-colors",
                  active === e.id ? "bg-base-soft" : "hover:bg-paper")}
                  onClick={() => seek(t)} role="button" tabIndex={0} onKeyDown={(k) => k.key === "Enter" && seek(t)}>
                  <span className="num pt-[2px] text-[11px] text-ink-3">{fmtOffset(t)}</span>
                  <span className="pt-[3px]"><ProvenanceIcon p={e.provenance} /></span>
                  <span className="min-w-0">
                    <span className={clsx("leading-snug", e.kind === "flip_detected" && "font-semibold text-accent")}>
                      <span className="text-ink-2">{KIND_TEXT[e.kind] ?? e.kind}. </span>{e.summary.replace(/^Step confirmed: /, "")}
                    </span>
                    <span className="mt-0.5 flex items-center gap-2">
                      <span className="num text-[10.5px] text-ink-3">{shortHash(e.hash)}</span>
                      {e.provenance === "inferred" && e.confidence != null && e.confidence < 0.6 ? <span className="text-[11px] text-amber">low confidence</span> : null}
                      <button type="button" onClick={(ev) => { ev.stopPropagation(); open([`evt:${e.id}`], e.summary); }}
                        className="text-[11px] text-base opacity-0 hover:underline focus:opacity-100 group-hover:opacity-100">
                        evidence
                      </button>
                    </span>
                  </span>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <Lanes duration={duration} cursor={cursor} onSeek={seek} events={timeline} strip={strip} series={series} flipAt={flipAt} activeId={active} />

      <p className="flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-ink-2">
        <span className="inline-flex items-center gap-1.5"><ProvenanceIcon p="measured" /> measured by a sensor or the camera</span>
        <span className="inline-flex items-center gap-1.5"><ProvenanceIcon p="reported" /> reported by the researcher</span>
        <span className="inline-flex items-center gap-1.5"><ProvenanceIcon p="inferred" /> inferred by Gemini from video</span>
        <span>Drag across the lanes to scrub the video.</span>
      </p>
    </div>
  );
}
