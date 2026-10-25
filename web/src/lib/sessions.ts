"use client";

import type { AskAnswer } from "@/lib/types";

/** Ask-your-lab conversations, kept in this browser only (a per-viewer convenience, never the record). */
export interface Turn {
  role: "user" | "assistant";
  text: string;
  answer?: AskAnswer;
  error?: string;
}

export interface Session {
  id: string;
  title: string;
  experiment: string;
  turns: Turn[];
  updated: number;
}

const KEY = "litmus-sessions";
const EVENT = "litmus-sessions";

export function listSessions(): Session[] {
  try {
    const raw = localStorage.getItem(KEY);
    const all = raw ? (JSON.parse(raw) as Session[]) : [];
    return all.sort((a, b) => b.updated - a.updated);
  } catch {
    return [];
  }
}

export function getSession(id: string): Session | null {
  return listSessions().find((s) => s.id === id) ?? null;
}

export function saveSession(s: Session): void {
  try {
    const rest = listSessions().filter((x) => x.id !== s.id);
    localStorage.setItem(KEY, JSON.stringify([s, ...rest].slice(0, 30)));
    window.dispatchEvent(new Event(EVENT));
  } catch {
    /* storage unavailable: the conversation still works, it just isn't kept */
  }
}

export function onSessionsChange(fn: () => void): () => void {
  window.addEventListener(EVENT, fn);
  window.addEventListener("storage", fn);
  return () => {
    window.removeEventListener(EVENT, fn);
    window.removeEventListener("storage", fn);
  };
}

export function newSessionId(): string {
  return Math.random().toString(36).slice(2, 10);
}
