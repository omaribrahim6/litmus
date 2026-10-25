"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { EvidenceDrawer } from "./EvidenceDrawer";
import type { Evidence } from "@/lib/types";

interface EvidenceRequest {
  ids: string[];
  title?: string;
}

interface Ctx {
  open: (ids: string[], title?: string) => void;
  close: () => void;
  highlighted: string[];
  setHighlighted: (ids: string[]) => void;
}

const EvidenceContext = createContext<Ctx | null>(null);

const cache = new Map<string, Evidence | null>();

export async function fetchEvidence(ids: string[]): Promise<Record<string, Evidence | null>> {
  const missing = ids.filter((id) => !cache.has(id));
  if (missing.length) {
    const res = await fetch(`/api/evidence?ids=${encodeURIComponent(missing.join(","))}`);
    if (res.ok) {
      const data = (await res.json()) as Record<string, Evidence | null>;
      for (const id of missing) cache.set(id, data[id] ?? null);
    }
  }
  return Object.fromEntries(ids.map((id) => [id, cache.get(id) ?? null]));
}

export function EvidenceProvider({ children }: { children: React.ReactNode }) {
  const [req, setReq] = useState<EvidenceRequest | null>(null);
  const [highlighted, setHighlighted] = useState<string[]>([]);
  const open = useCallback((ids: string[], title?: string) => setReq({ ids: [...new Set(ids)], title }), []);
  const close = useCallback(() => setReq(null), []);

  useEffect(() => {
    if (!req) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setReq(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [req]);

  const value = useMemo(() => ({ open, close, highlighted, setHighlighted }), [open, close, highlighted]);
  return (
    <EvidenceContext.Provider value={value}>
      {children}
      {req ? <EvidenceDrawer ids={req.ids} title={req.title} onClose={close} /> : null}
    </EvidenceContext.Provider>
  );
}

export function useEvidence(): Ctx {
  const ctx = useContext(EvidenceContext);
  if (!ctx) throw new Error("useEvidence outside EvidenceProvider");
  return ctx;
}
