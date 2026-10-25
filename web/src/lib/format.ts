import type { ClaimLabel, Provenance, Role } from "./types";

export function shortHash(hash?: string | null, n = 7): string {
  return hash ? hash.slice(0, n) : "-------";
}

export function fmtNumber(v: number | null | undefined, decimals = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "n/a";
  const s = v.toFixed(decimals);
  return s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") || "0" : s;
}

/** Lab-local time zone, so server-rendered times match the bench clock. */
const TZ = process.env.NEXT_PUBLIC_LAB_TZ || "America/New_York";

export function fmtClock(iso?: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: TZ });
}

export function fmtDateTime(iso?: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: TZ });
}

export function fmtOffset(seconds: number): string {
  const s = Math.max(0, seconds);
  const m = Math.floor(s / 60);
  const rest = s - m * 60;
  return `${m}:${rest.toFixed(1).padStart(4, "0")}`;
}

export function secondsBetween(a?: string | null, b?: string | null): number {
  if (!a || !b) return 0;
  return (new Date(b).getTime() - new Date(a).getTime()) / 1000;
}

export const ROLE_TEXT: Record<Role, string> = {
  reference: "Reference",
  control: "Control",
  candidate: "Candidate",
  rerun: "Rerun",
};

export const LABEL_TEXT: Record<ClaimLabel, string> = {
  observed: "Observed",
  possible_explanation: "Possible explanation",
  contradicted: "Contradicted",
  missing_evidence: "Missing evidence",
};

export const PROVENANCE_TEXT: Record<Provenance, string> = {
  measured: "Measured by a sensor or the camera",
  reported: "Reported by the researcher",
  inferred: "Inferred by Gemini from video",
};

/** A recorded value as stored: numbers formatted, qualitative values (e.g. "cloudy") shown as they are. */
export function fmtValue(v: number | string | null | undefined, decimals = 1): string {
  if (v === null || v === undefined) return "";
  return typeof v === "number" ? fmtNumber(v, decimals) : v;
}

export const KIND_TEXT: Record<string, string> = {
  measurement: "Recorded",
  experiment_setup: "Set up",
  run_started: "Run started",
  step_confirmed: "Step",
  quantity_added: "Added",
  reagent_used: "Reagent",
  mix: "Mixed",
  flip_detected: "Color change",
  flip_crosscheck: "Cross-check",
  reading_reported: "Reading",
  hypothesis_stated: "Hypothesis",
  note: "Note",
  run_ended: "Run ended",
  run_sealed: "Sealed",
  pour: "Pour",
  session_intro: "Intro",
  intro_confirmed: "Confirmed",
  narration: "Said",
};

export function plural(n: number, word: string, pluralWord?: string): string {
  return `${n} ${n === 1 ? word : pluralWord ?? `${word}s`}`;
}
