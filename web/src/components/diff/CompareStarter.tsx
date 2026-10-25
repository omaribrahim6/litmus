"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { Check } from "lucide-react";

const STEPS = [
  "Aligning both runs by protocol step",
  "Measuring every recorded variable",
  "Comparing against reference-run variation",
  "Checking the assumed cause against the measurements",
  "Writing the verdict and validating every claim",
];

/** Runs the diff and verdict, with a designed wait instead of a spinner. */
export function CompareStarter({ candidate, diffId, label }: { candidate?: string; diffId?: string; label?: string }) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const id = setInterval(() => setStep((s) => Math.min(STEPS.length - 1, s + 1)), 900);
    fetch("/api/compare", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(diffId ? { diff_id: diffId } : { candidate }),
    })
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error ?? `Comparison failed (${res.status})`);
        clearInterval(id);
        setStep(STEPS.length);
        router.replace(`/compare/${data.verdict_id}?reveal=1`);
      })
      .catch((err) => {
        clearInterval(id);
        setError((err as Error).message);
      });
    return () => clearInterval(id);
  }, [candidate, diffId, router]);

  return (
    <div className="mx-auto max-w-xl px-6 py-20">
      <h1 className="wide text-[28px] font-semibold tracking-[-0.015em]">Running the litmus test{label ? ` on ${label}` : ""}</h1>
      <p className="mt-2 text-[15px] text-ink-2">Every number comes from the record. Gemini only writes the explanation.</p>
      <ol className="mt-8 space-y-3">
        {STEPS.map((s, i) => (
          <li key={s} className={clsx("flex items-center gap-3 text-[15px] transition-colors", i <= step ? "text-ink" : "text-ink-3")}>
            <span className={clsx("flex size-5 items-center justify-center rounded-full border", i < step ? "border-ok bg-ok text-paper" : i === step && !error ? "border-base" : "border-rule-strong")}>
              {i < step ? <Check size={12} strokeWidth={3} /> : i === step && !error ? <span className="live-dot size-1.5 rounded-full bg-base" /> : null}
            </span>
            {s}
          </li>
        ))}
      </ol>
      {error ? (
        <div className="mt-8 rounded-lg border border-accent/30 bg-accent-soft p-4 text-[14px] text-accent">
          {error}. The worker runs the diff engine; start it with <code className="num text-[12px]">uvicorn litmus_worker.main:app</code> and try again.
        </div>
      ) : null}
    </div>
  );
}
