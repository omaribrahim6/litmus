import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { hasDatabase, sql } from "./db";
import { labCss, type StripStop } from "./color";
import type {
  Analysis,
  Evidence,
  Experiment,
  Frame,
  LitmusEvent,
  ReadingBucket,
  Run,
  VerifyReport,
} from "./types";

/* ------------------------------------------------------------------ snapshot */

export interface Snapshot {
  generated_at: string;
  experiments: Experiment[];
  runs: Run[];
  events: Record<string, LitmusEvent[]>;
  frames: Record<string, Frame[]>;
  readings_1s: Record<string, ReadingBucket[]>;
  readings: Record<string, [number, string, number, string][]>;
  verify: Record<string, VerifyReport>;
  analyses: Analysis[];
}

let snapshotPromise: Promise<Snapshot | null> | null = null;

export function loadSnapshot(): Promise<Snapshot | null> {
  if (!snapshotPromise) {
    snapshotPromise = readFile(path.join(process.cwd(), "demo-data", "snapshot.json"), "utf8")
      .then((s) => JSON.parse(s) as Snapshot)
      .catch(() => null);
  }
  return snapshotPromise;
}

export function demoMode(): boolean {
  return process.env.LITMUS_DEMO_MODE === "1" || !hasDatabase();
}

/** Prefer the live database; fall back to the bundled snapshot on demo mode or a network failure. */
async function source<T>(live: () => Promise<T>, offline: (s: Snapshot) => T | Promise<T>, empty: T): Promise<T> {
  if (!demoMode()) {
    try {
      return await live();
    } catch (err) {
      console.error("[litmus] database unavailable, using snapshot:", (err as Error).message);
    }
  }
  const snap = await loadSnapshot();
  return snap ? offline(snap) : empty;
}

export async function dataSourceLabel(): Promise<"live" | "snapshot" | "none"> {
  if (!demoMode()) {
    try {
      await sql()`select 1`;
      return "live";
    } catch {
      /* fall through */
    }
  }
  return (await loadSnapshot()) ? "snapshot" : "none";
}

/* ------------------------------------------------------------------ helpers */

function iso(v: unknown): string | null {
  if (v === null || v === undefined) return null;
  return v instanceof Date ? v.toISOString() : String(v);
}

function normalizeRun(r: Record<string, unknown>): Run {
  return {
    ...(r as unknown as Run),
    started_at: iso(r.started_at),
    ended_at: iso(r.ended_at),
    event_count: r.event_count === undefined ? undefined : Number(r.event_count),
  };
}

function normalizeEvent(e: Record<string, unknown>): LitmusEvent {
  return { ...(e as unknown as LitmusEvent), t: iso(e.t)!, frame_ids: ((e.frame_ids as string[]) ?? []).map(String) };
}

/* ------------------------------------------------------------------ queries */

export async function getExperiments(): Promise<Experiment[]> {
  return source(
    async () =>
      (await sql()`select * from experiments order by created_at`).map((e) => ({ ...(e as unknown as Experiment), created_at: iso(e.created_at)! })),
    (s) => s.experiments,
    [],
  );
}

export async function getExperiment(ref: string): Promise<Experiment | null> {
  const all = await getExperiments();
  return all.find((e) => e.id === ref || e.slug === ref) ?? null;
}

export async function getRuns(experimentId?: string): Promise<Run[]> {
  return source(
    async () => {
      const rows = await sql()`
        select r.*,
               (select hash from events ev where ev.run_id = r.id order by seq desc limit 1) as head_hash,
               (select count(*) from events ev where ev.run_id = r.id) as event_count
        from runs r
        where (${experimentId ?? null}::uuid is null or r.experiment_id = ${experimentId ?? null}::uuid)
          and not coalesce((r.metadata->>'smoke')::boolean, false)
        order by r.started_at nulls last`;
      return rows.map(normalizeRun);
    },
    (s) => s.runs.filter((r) => !experimentId || r.experiment_id === experimentId),
    [],
  );
}

export async function getRun(id: string): Promise<Run | null> {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return null;
  return source(
    async () => {
      const [row] = await sql()`
        select r.*,
               (select hash from events ev where ev.run_id = r.id order by seq desc limit 1) as head_hash,
               (select count(*) from events ev where ev.run_id = r.id) as event_count
        from runs r where r.id = ${id}`;
      return row ? normalizeRun(row) : null;
    },
    (s) => s.runs.find((r) => r.id === id) ?? null,
    null,
  );
}

export async function getEvents(runId: string, afterSeq = -1): Promise<LitmusEvent[]> {
  return source(
    async () =>
      (
        await sql()`
        select id, run_id, t, seq, kind, summary, payload, provenance, confidence, frame_ids, prev_hash, hash
        from events where run_id = ${runId} and seq > ${afterSeq} order by t, seq`
      ).map(normalizeEvent),
    (s) => (s.events[runId] ?? []).filter((e) => e.seq > afterSeq),
    [],
  );
}

export async function getFrames(runId: string): Promise<Frame[]> {
  return source(
    async () =>
      (await sql()`select id, run_id, t, url, reason, metrics from frames where run_id = ${runId} order by t`).map(
        (f) => ({ ...(f as unknown as Frame), t: iso(f.t)! }),
      ),
    (s) => s.frames[runId] ?? [],
    [],
  );
}

export async function getReadings(runId: string): Promise<ReadingBucket[]> {
  return source(
    async () =>
      (
        await sql()`select bucket, sensor, avg, min, max, n::int as n from readings_1s where run_id = ${runId} order by bucket`
      ).map((b) => ({ ...(b as unknown as ReadingBucket), bucket: iso(b.bucket)! })),
    (s) => s.readings_1s[runId] ?? [],
    [],
  );
}

/** Litmus strips: the tube's measured color over time, from camera Lab readings. */
export async function getStrips(runs: Run[], points = 48): Promise<Record<string, StripStop[]>> {
  const out: Record<string, StripStop[]> = {};
  const ids = runs.map((r) => r.id);
  if (!ids.length) return out;
  const rows = await source(
    async () =>
      (
        await sql()`
        select run_id, bucket, sensor, avg from readings_1s
        where run_id = any(${ids}::uuid[]) and sensor in ('lab_l', 'lab_a', 'lab_b') order by bucket`
      ).map((r) => ({ run_id: String(r.run_id), bucket: iso(r.bucket)!, sensor: String(r.sensor), avg: Number(r.avg) })),
    (s) =>
      ids.flatMap((id) =>
        (s.readings_1s[id] ?? [])
          .filter((b) => b.sensor === "lab_l" || b.sensor === "lab_a" || b.sensor === "lab_b")
          .map((b) => ({ run_id: id, bucket: b.bucket, sensor: b.sensor, avg: b.avg })),
      ),
    [] as { run_id: string; bucket: string; sensor: string; avg: number }[],
  );
  const byRun = new Map<string, Map<string, { l?: number; a?: number; b?: number }>>();
  for (const r of rows) {
    const m = byRun.get(r.run_id) ?? new Map();
    const cell = m.get(r.bucket) ?? {};
    if (r.sensor === "lab_l") cell.l = r.avg;
    if (r.sensor === "lab_a") cell.a = r.avg;
    if (r.sensor === "lab_b") cell.b = r.avg;
    m.set(r.bucket, cell);
    byRun.set(r.run_id, m);
  }
  for (const run of runs) {
    const m = byRun.get(run.id);
    if (!m) continue;
    const t0 = run.started_at ? new Date(run.started_at).getTime() : 0;
    const cells = [...m.entries()]
      .filter(([, c]) => c.l !== undefined && c.a !== undefined && c.b !== undefined)
      .sort(([a], [b]) => a.localeCompare(b));
    const step = Math.max(1, Math.floor(cells.length / points));
    out[run.id] = cells
      .filter((_, i) => i % step === 0)
      .map(([bucket, c]) => ({ t: (new Date(bucket).getTime() - t0) / 1000, color: labCss(c.l!, c.a!, c.b!) }));
  }
  return out;
}

export async function getAnalysis<T>(id: string): Promise<Analysis<T> | null> {
  if (!/^[0-9a-f-]{36}$/i.test(id)) return null;
  return source(
    async () => {
      const [row] = await sql()`select * from analyses where id = ${id}`;
      return row ? ({ ...(row as unknown as Analysis<T>), created_at: iso(row.created_at)! }) : null;
    },
    (s) => (s.analyses.find((a) => a.id === id) as Analysis<T>) ?? null,
    null,
  );
}

/** Latest analysis of a kind whose first run is the given candidate. */
export async function getLatestAnalysisFor<T>(kind: Analysis["kind"], candidateId: string): Promise<Analysis<T> | null> {
  return source(
    async () => {
      const [row] = await sql()`
        select * from analyses where kind = ${kind} and run_ids[1] = ${candidateId}::uuid
        order by created_at desc limit 1`;
      return row ? ({ ...(row as unknown as Analysis<T>), created_at: iso(row.created_at)! }) : null;
    },
    (s) =>
      (s.analyses
        .filter((a) => a.kind === kind && a.run_ids[0] === candidateId)
        .sort((a, b) => b.created_at.localeCompare(a.created_at))[0] as Analysis<T>) ?? null,
    null,
  );
}

export async function listAnalyses(kind?: Analysis["kind"]): Promise<Analysis[]> {
  return source(
    async () =>
      (
        await sql()`select id, kind, run_ids, model, created_at, content from analyses
                   where (${kind ?? null}::text is null or kind = ${kind ?? null}::text) order by created_at desc limit 200`
      ).map((a) => ({ ...(a as unknown as Analysis), created_at: iso(a.created_at)! })),
    (s) => s.analyses.filter((a) => !kind || a.kind === kind),
    [],
  );
}

/* ----------------------------------------------------------------- evidence */

function parseEvidence(id: string) {
  const [type, ...rest] = id.split(":");
  if (type === "evt" || type === "frm" || type === "run") return { type, id: rest.join(":") };
  if (type === "ser" && rest.length === 4) return { type, run: rest[0], sensor: rest[1], start: Number(rest[2]), end: Number(rest[3]) };
  if (type === "rdg" && rest.length === 3) return { type, run: rest[0], sensor: rest[1], start: Number(rest[2]), end: Number(rest[2]) };
  return null;
}

async function resolveLive(id: string): Promise<Evidence | null> {
  const p = parseEvidence(id);
  if (!p) return null;
  const db = sql();
  const label = async (runId: string) => (await db`select label from runs where id = ${runId}`)[0]?.label ?? null;
  if (p.type === "evt") {
    const [e] = await db`select id, run_id, t, seq, kind, summary, payload, provenance, confidence, frame_ids, hash from events where id = ${p.id!}`;
    if (!e) return null;
    const frames = (e.frame_ids as string[])?.length
      ? (await db`select id, t, url, reason from frames where id = any(${e.frame_ids}::uuid[]) order by t`).map((f) => ({ ...(f as unknown as { id: string; url: string; reason: string | null }), t: iso(f.t)! }))
      : [];
    return { id, type: "event", run_id: String(e.run_id), run_label: await label(String(e.run_id)), t: iso(e.t)!, seq: e.seq, kind: e.kind, summary: e.summary, payload: e.payload, provenance: e.provenance, confidence: e.confidence, hash: e.hash, frames };
  }
  if (p.type === "frm") {
    const [f] = await db`select * from frames where id = ${p.id!}`;
    if (!f) return null;
    return { id, type: "frame", run_id: String(f.run_id), run_label: await label(String(f.run_id)), t: iso(f.t)!, url: f.url, reason: f.reason, metrics: f.metrics, provenance: "measured" };
  }
  if (p.type === "run") {
    const [r] = await db`select id, label, role, assumed_cause, result from runs where id = ${p.id!}`;
    if (!r) return null;
    return { id, type: "run", run_id: String(r.id), run_label: r.label, label: r.label, role: r.role, assumed_cause: r.assumed_cause, result: r.result, provenance: "reported" };
  }
  const pad = p.type === "rdg" ? 750 : 0;
  const rows = await db`
    select time, value, unit, provenance from readings
    where run_id = ${p.run!} and sensor = ${p.sensor!}
      and time >= to_timestamp(${(p.start! - pad) / 1000}) and time <= to_timestamp(${(p.end! + pad) / 1000})
    order by time`;
  if (!rows.length) return null;
  return seriesEvidence(id, p.type as "ser" | "rdg", p.run!, await label(p.run!), p.sensor!, p.start!,
    rows.map((r) => ({ t: (r.time as Date).getTime(), value: Number(r.value), unit: r.unit, provenance: r.provenance })));
}

function seriesEvidence(id: string, type: "ser" | "rdg", runId: string, runLabel: string | null, sensor: string, target: number,
                        rows: { t: number; value: number; unit: string | null; provenance: string }[]): Evidence {
  if (type === "rdg") {
    const near = rows.reduce((best, r) => (Math.abs(r.t - target) < Math.abs(best.t - target) ? r : best));
    return { id, type: "reading", run_id: runId, run_label: runLabel, sensor, t: new Date(near.t).toISOString(), value: near.value, unit: near.unit, provenance: near.provenance as Evidence["provenance"] };
  }
  const values = rows.map((r) => r.value);
  const step = Math.max(1, Math.floor(rows.length / 240));
  const provs = new Set(rows.map((r) => r.provenance));
  return {
    id, type: "series", run_id: runId, run_label: runLabel, sensor,
    start: new Date(rows[0].t).toISOString(), end: new Date(rows[rows.length - 1].t).toISOString(),
    n: rows.length, mean: values.reduce((a, b) => a + b, 0) / values.length, min: Math.min(...values), max: Math.max(...values),
    unit: rows[0].unit, provenance: (provs.size === 1 ? [...provs][0] : "reported") as Evidence["provenance"],
    points: rows.filter((_, i) => i % step === 0).map((r) => ({ t: new Date(r.t).toISOString(), value: r.value })),
  };
}

function resolveSnapshot(s: Snapshot, id: string): Evidence | null {
  const p = parseEvidence(id);
  if (!p) return null;
  const runLabel = (runId: string) => s.runs.find((r) => r.id === runId)?.label ?? null;
  if (p.type === "evt") {
    for (const [runId, events] of Object.entries(s.events)) {
      const e = events.find((x) => x.id === p.id);
      if (e) {
        const frames = (s.frames[runId] ?? []).filter((f) => e.frame_ids.includes(f.id)).map((f) => ({ id: f.id, t: f.t, url: f.url, reason: f.reason }));
        return { id, type: "event", run_id: runId, run_label: runLabel(runId), t: e.t, seq: e.seq, kind: e.kind, summary: e.summary, payload: e.payload, provenance: e.provenance, confidence: e.confidence, hash: e.hash, frames };
      }
    }
    return null;
  }
  if (p.type === "frm") {
    for (const [runId, frames] of Object.entries(s.frames)) {
      const f = frames.find((x) => x.id === p.id);
      if (f) return { id, type: "frame", run_id: runId, run_label: runLabel(runId), t: f.t, url: f.url, reason: f.reason, metrics: f.metrics, provenance: "measured" };
    }
    return null;
  }
  if (p.type === "run") {
    const r = s.runs.find((x) => x.id === p.id);
    return r ? { id, type: "run", run_id: r.id, run_label: r.label, label: r.label, role: r.role, assumed_cause: r.assumed_cause, result: r.result, provenance: "reported" } : null;
  }
  const pad = p.type === "rdg" ? 750 : 0;
  const rows = (s.readings[p.run!] ?? [])
    .filter(([t, sensor]) => sensor === p.sensor && t >= p.start! - pad && t <= p.end! + pad)
    .map(([t, , value, provenance]) => ({ t, value, unit: null, provenance }));
  return rows.length ? seriesEvidence(id, p.type as "ser" | "rdg", p.run!, runLabel(p.run!), p.sensor!, p.start!, rows) : null;
}

export async function resolveEvidence(ids: string[]): Promise<Record<string, Evidence | null>> {
  const unique = [...new Set(ids)].slice(0, 64);
  return source(
    async () => Object.fromEntries(await Promise.all(unique.map(async (id) => [id, await resolveLive(id)] as const))),
    (s) => Object.fromEntries(unique.map((id) => [id, resolveSnapshot(s, id)])),
    {},
  );
}

/* ------------------------------------------------------------- verification */

export async function getVerify(runId: string): Promise<VerifyReport> {
  const offline = async () => (await loadSnapshot())?.verify[runId] ?? { intact: false, checked: 0, unavailable: true };
  if (demoMode()) return offline();
  try {
    const res = await fetch(`${workerUrl()}/verify/${runId}`, { cache: "no-store", signal: AbortSignal.timeout(6000) });
    if (!res.ok) throw new Error(`worker ${res.status}`);
    return (await res.json()) as VerifyReport;
  } catch {
    return offline();
  }
}

export function workerUrl(): string {
  return (process.env.WORKER_URL || "http://localhost:8000").replace(/\/$/, "");
}
