"use client";

import { useEffect, useRef, useState } from "react";
import { useEvidence } from "@/components/evidence/EvidenceProvider";

/** Renders a Vega-Lite spec built by the worker. Clicking a point opens its source evidence. */
export function VegaChart({ spec, className }: { spec: Record<string, unknown>; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const { open } = useEvidence();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let finalize: (() => void) | undefined;
    let cancelled = false;
    (async () => {
      try {
        const { default: embed } = await import("vega-embed");
        if (cancelled || !ref.current) return;
        const dark = document.documentElement.dataset.theme === "dark" ||
          (!document.documentElement.dataset.theme && window.matchMedia("(prefers-color-scheme: dark)").matches);
        const paper = (spec.config as { background?: string } | undefined)?.background === "white";
        const themed = paper ? spec : {
          ...spec,
          config: {
            ...(spec.config as object),
            background: null,
            font: "var(--font-archivo), sans-serif",
            axis: { labelColor: dark ? "#93a0aa" : "#5b6873", titleColor: dark ? "#93a0aa" : "#5b6873", gridColor: dark ? "#233039" : "#dce1e5", domainColor: dark ? "#34434e" : "#c3cbd1", tickColor: dark ? "#34434e" : "#c3cbd1", labelFontSize: 11, titleFontSize: 12, titleFontWeight: 500 },
            legend: { labelColor: dark ? "#e4eaee" : "#15202b", titleColor: dark ? "#93a0aa" : "#5b6873" },
            title: { color: dark ? "#e4eaee" : "#15202b", fontSize: 13, fontWeight: 600, anchor: "start" },
            range: { category: ["#8a96a0", "#2c63a8", "#c8264e", "#a8650f"] },
          },
        };
        const result = await embed(ref.current, themed as never, { actions: { export: true, source: false, compiled: false, editor: false }, renderer: "svg" });
        finalize = () => result.finalize();
        result.view.addEventListener("click", (_e, item) => {
          const datum = (item as { datum?: { evidence_id?: string; run?: string } } | null)?.datum;
          if (datum?.evidence_id) open([datum.evidence_id], datum.run ? `Source of this point (${datum.run})` : "Source of this point");
        });
      } catch (err) {
        setError((err as Error).message);
      }
    })();
    return () => {
      cancelled = true;
      finalize?.();
    };
  }, [spec, open]);

  if (error) return <p className="text-[13px] text-accent">This chart could not be drawn: {error}</p>;
  return <div ref={ref} className={className} style={{ width: "100%" }} />;
}
