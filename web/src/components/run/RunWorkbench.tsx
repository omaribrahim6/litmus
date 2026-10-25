"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { Pause, Play, Receipt } from "lucide-react";
import { labCss, type StripStop } from "@/lib/color";
import type { Frame, LitmusEvent, ReadingBucket, Run } from "@/lib/types";
import { fmtOffset, KIND_TEXT, shortHash } from "@/lib/format";
import { ProvenanceIcon } from "@/components/ui";
import { useEvidence } from "@/components/evidence/EvidenceProvider";
import type { LaneSeries } from "./Lanes";
import { Timeline, type Mark } from "./Timeline";

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

  // Play / pause: drives the video when there is one, otherwise walks the keyframes in real time.
  const [playing, setPlaying] = useState(false);
  const toggle = () => {
    const v = video.current;
    if (v) {
      if (v.paused) v.play(); else v.pause();
      return;
    }
    setPlaying((p) => !p);
  };
  useEffect(() => {
    if (!playing || video.current) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      setCursor((c) => {
        const next = c + (now - last) / 1000;
        if (next >= duration) { setPlaying(false); return duration; }
        return next;
      });
      last = now;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, duration]);
  const [selected, setSelected] = useState<string | null>(null);

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

  const shown = (selected && timeline.find((x) => x.e.id === selected)) || timeline.find((x) => x.e.id === active) || null;
  const frameById = new Map(frames.map((f) => [f.id, f]));
  const shownFrame = shown?.e.frame_ids?.map((id) => frameById.get(id)).find(Boolean) ?? null;
  const still = live ? latestFrame : nearestFrame;
  const hasVideo = Boolean(run.video_url && !live);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,1fr)]">
        {/* player */}
        <div className="overflow-hidden rounded-xl bg-[#0e0e0e] ring-1 ring-black/10">
          <div className="relative">
            {hasVideo ? (
              <video ref={video} src={cam === "action" && actionVideo ? actionVideo : run.video_url!} playsInline preload="metadata"
                onTimeUpdate={onTime} onSeeked={onTime} onLoadedMetadata={() => seek(cursor)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
                onClick={toggle} className="aspect-video w-full cursor-pointer bg-black object-contain" />
            ) : still ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={still.url} alt="Station camera" className="aspect-video w-full bg-black object-contain" />
            ) : (
              <div className="flex aspect-video items-center justify-center text-[13.5px] text-white/50">
                {live ? "Waiting for the first frame from the station camera" : "No video was recorded for this run"}
              </div>
            )}
            {live ? (
              <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-[12px] font-medium text-white backdrop-blur">
                <span className="live-dot size-1.5 rounded-full bg-accent" /> Live from the station
              </span>
            ) : null}
            {hasVideo && actionVideo ? (
              <div className="absolute right-3 top-3 flex rounded-lg bg-black/55 p-0.5 text-[12px] text-white backdrop-blur">
                {(["bench", "action"] as const).map((c) => (
                  <button key={c} type="button" onClick={() => setCam(c)} className={clsx("rounded-md px-2.5 py-1", cam === c ? "bg-white/20 font-medium" : "opacity-70 hover:opacity-100")}>
                    {c === "bench" ? "Bench" : "Researcher"}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          {!live ? (
            <div className="flex h-11 items-center gap-3 border-t border-white/10 px-3 text-white">
              <button type="button" onClick={toggle} aria-label={playing ? "Pause" : "Play"}
                className="flex size-7 items-center justify-center rounded-full bg-white text-black transition hover:scale-105">
                {playing ? <Pause size={13} fill="currentColor" /> : <Play size={13} fill="currentColor" className="translate-x-[1px]" />}
              </button>
              <span className="num text-[12px] text-white/80">{fmtOffset(cursor)} <span className="text-white/40">/ {fmtOffset(duration)}</span></span>
              <span className="ml-auto truncate text-[12px] text-white/50">{hasVideo ? (cam === "action" ? "Researcher camera" : "Bench camera") : `${frames.length} keyframes`}</span>
            </div>
          ) : null}
        </div>

        {/* inspector: whatever is under the playhead */}
        <div className="flex max-h-[min(600px,calc((100vw-300px)*0.36))] min-h-[340px] flex-col overflow-hidden rounded-xl border border-rule bg-surface">
          {shown ? (
            <div className="border-b border-rule p-4">
              <div className="flex items-center gap-2 text-[12px]">
                <span className="rounded-full bg-sunken px-2 py-0.5 font-medium text-ink-2">{KIND_TEXT[shown.e.kind] ?? shown.e.kind}</span>
                <span className="num text-ink-3">{fmtOffset(shown.t)}</span>
                <span className="ml-auto"><ProvenanceIcon p={shown.e.provenance} withText /></span>
              </div>
              <p className={clsx("mt-2 text-[15px] font-medium leading-snug", shown.e.kind === "flip_detected" && "text-accent")}>{shown.e.summary}</p>
              {shownFrame ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={shownFrame.url} alt="" className="mt-3 aspect-video w-full rounded-lg object-cover ring-1 ring-rule" />
              ) : null}
              <div className="mt-3 flex items-center gap-2">
                <span className="num truncate text-[11px] text-ink-3" title={shown.e.hash}>#{shortHash(shown.e.hash, 12)}</span>
                <button type="button" onClick={() => open([`evt:${shown.e.id}`], shown.e.summary)}
                  className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-rule px-2.5 py-1 text-[12px] font-medium hover:border-rule-strong">
                  <Receipt size={12} /> Receipt
                </button>
              </div>
            </div>
          ) : null}
          <div className="flex items-baseline justify-between px-4 pb-1 pt-3">
            <h2 className="text-[12px] font-semibold text-ink-2">Commits</h2>
            <span className="text-[11.5px] text-ink-3">{events.length} in the chain{live ? ", recording" : ""}</span>
          </div>
          <ol ref={list} className="scroll-thin flex-1 overflow-y-auto px-2 pb-2">
            {timeline.map(({ e, t }) => (
              <li key={e.id} data-id={e.id}>
                <button type="button" onClick={() => { setSelected(e.id); seek(t); }}
                  className={clsx("grid w-full grid-cols-[44px_14px_minmax(0,1fr)] items-start gap-2 rounded-lg px-2 py-1.5 text-left text-[13px] transition-colors",
                    (shown?.e.id ?? active) === e.id ? "bg-hover" : "hover:bg-side")}>
                  <span className="num pt-[2px] text-[10.5px] text-ink-3">{fmtOffset(t)}</span>
                  <span className="pt-[3px]"><ProvenanceIcon p={e.provenance} /></span>
                  <span className={clsx("min-w-0 leading-snug", e.kind === "flip_detected" && "font-semibold text-accent")}>
                    <span className="text-ink-3">{KIND_TEXT[e.kind] ?? e.kind} · </span>{e.summary.replace(/^Step (confirmed|seen): /, "")}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <Timeline duration={duration} cursor={cursor} onSeek={(t) => { setSelected(null); seek(t); }} marks={timeline as Mark[]}
        frames={frames} frameT={(f) => offset(f.t)} strip={strip} series={series} activeId={shown?.e.id ?? active}
        onSelect={(m) => { setSelected(m.e.id); seek(m.t); }} />

      <p className="flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-ink-3">
        <span className="inline-flex items-center gap-1.5"><ProvenanceIcon p="measured" /> measured by a sensor or the camera</span>
        <span className="inline-flex items-center gap-1.5"><ProvenanceIcon p="reported" /> reported by the researcher</span>
        <span className="inline-flex items-center gap-1.5"><ProvenanceIcon p="inferred" /> inferred by Gemini</span>
        <span>Drag the timeline to scrub.</span>
      </p>
    </div>
  );
}
