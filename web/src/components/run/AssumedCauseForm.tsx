"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/** The researcher states what they think caused the result. Stored as a reported commit. */
export function AssumedCauseForm({ runId, current }: { runId: string; current: string | null }) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(current ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  if (!editing) {
    return (
      <div className="text-[14px]">
        {current ? (
          <p><span className="text-ink-2">Your assumed cause: </span>“{current}” <button type="button" onClick={() => setEditing(true)} className="ml-1 text-[13px] text-base hover:underline">Change</button></p>
        ) : (
          <button type="button" onClick={() => setEditing(true)} className="text-[13.5px] font-medium text-base hover:underline">
            State what you think caused this result
          </button>
        )}
      </div>
    );
  }
  return (
    <form className="flex w-full max-w-xl flex-col gap-2" onSubmit={async (e) => {
      e.preventDefault();
      setSaving(true);
      setError(null);
      const res = await fetch("/api/assumed-cause", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ run_id: runId, text }) });
      setSaving(false);
      if (!res.ok) {
        setError((await res.json()).error ?? "Could not save");
        return;
      }
      setEditing(false);
      router.refresh();
    }}>
      <label className="text-[13px] text-ink-2" htmlFor="cause">What do you think caused this result?</label>
      <input id="cause" value={text} onChange={(e) => setText(e.target.value)} autoFocus placeholder="For example: I stirred longer after each addition"
        className="rounded-md border border-rule-strong bg-surface px-3 py-2 text-[14px] outline-none focus:border-base" />
      <div className="flex items-center gap-2">
        <button type="submit" disabled={saving || !text.trim()} className="rounded-md bg-ink px-3 py-1.5 text-[13px] font-medium text-paper disabled:opacity-40">
          {saving ? "Saving" : "Save assumed cause"}
        </button>
        <button type="button" onClick={() => setEditing(false)} className="px-2 text-[13px] text-ink-2 hover:text-ink">Cancel</button>
        {error ? <span className="text-[13px] text-accent">{error}</span> : null}
      </div>
    </form>
  );
}
