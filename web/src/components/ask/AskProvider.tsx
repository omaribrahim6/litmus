"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export interface AskContextValue {
  page: string;
  run_id?: string;
  run_label?: string;
  analysis_id?: string;
  description?: string;
  experiment?: string;
  experiment_name?: string;
  result_label?: string;
}

interface Ctx {
  isOpen: boolean;
  setOpen: (v: boolean) => void;
  context: AskContextValue;
  setContext: (c: AskContextValue) => void;
  pending: string | null;
  ask: (question: string) => void;
  takePending: () => string | null;
}

const AskCtx = createContext<Ctx | null>(null);

export function AskProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [context, setContext] = useState<AskContextValue>({ page: "history", description: "Lab history" });
  const [pending, setPending] = useState<string | null>(null);

  useEffect(() => {
    try {
      const v = localStorage.getItem("litmus-ask-open");
      if (v === "1") setIsOpen(true);
    } catch {
      /* storage unavailable */
    }
  }, []);

  const setOpen = useCallback((v: boolean) => {
    setIsOpen(v);
    try {
      localStorage.setItem("litmus-ask-open", v ? "1" : "0");
    } catch {
      /* storage unavailable */
    }
  }, []);

  const ask = useCallback((q: string) => {
    setPending(q);
    setOpen(true);
  }, [setOpen]);

  const takePending = useCallback(() => {
    const p = pending;
    setPending(null);
    return p;
  }, [pending]);

  const value = useMemo(() => ({ isOpen, setOpen, context, setContext, pending, ask, takePending }),
    [isOpen, setOpen, context, pending, ask, takePending]);
  return <AskCtx.Provider value={value}>{children}</AskCtx.Provider>;
}

export function useAsk(): Ctx {
  const ctx = useContext(AskCtx);
  if (!ctx) throw new Error("useAsk outside AskProvider");
  return ctx;
}

/** Drop into a page to tell the Ask panel what the user is looking at. */
export function AskContext(props: AskContextValue) {
  const { setContext } = useAsk();
  const { page, run_id, run_label, analysis_id, description, experiment, experiment_name, result_label } = props;
  useEffect(() => {
    setContext({ page, run_id, run_label, analysis_id, description, experiment, experiment_name, result_label });
  }, [setContext, page, run_id, run_label, analysis_id, description, experiment, experiment_name, result_label]);
  return null;
}
