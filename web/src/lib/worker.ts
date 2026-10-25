import "server-only";
import { demoMode, loadSnapshot, workerUrl } from "./data";
import type { Analysis } from "./types";

export class WorkerError extends Error {
  constructor(message: string, public status = 502) {
    super(message);
  }
}

export async function workerPost<T>(path: string, body: unknown, timeoutMs = 120_000): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${workerUrl()}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (err) {
    throw new WorkerError(`The analysis worker is unreachable (${(err as Error).message})`, 503);
  }
  const text = await res.text();
  if (!res.ok) {
    let detail = text;
    try {
      detail = JSON.parse(text).detail ?? text;
    } catch {
      /* plain text */
    }
    throw new WorkerError(String(detail).slice(0, 300), res.status);
  }
  return JSON.parse(text) as T;
}

export async function workerHealthy(): Promise<boolean> {
  if (demoMode()) return false;
  try {
    const res = await fetch(`${workerUrl()}/health`, { cache: "no-store", signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

/** Offline: find a precomputed analysis in the snapshot. */
export async function snapshotAnalysis(pred: (a: Analysis) => boolean): Promise<Analysis | null> {
  const snap = await loadSnapshot();
  if (!snap) return null;
  return snap.analyses.filter(pred).sort((a, b) => b.created_at.localeCompare(a.created_at))[0] ?? null;
}

export function normalizeQuestion(q: string): string {
  return q.trim().toLowerCase().replace(/[^\w\s]/g, "").replace(/\s+/g, " ");
}
