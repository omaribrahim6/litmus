"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { Film } from "lucide-react";

interface Job {
  id: string;
  status: "running" | "done" | "error";
  stage: string;
  run_id: string | null;
  error: string | null;
  events?: number;
}

const STAGES = ["uploading", "watching video with Gemini", "measuring color in the tube", "extracting keyframes", "committing to the record", "detecting color flip and sealing", "done"];

export function UploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [role, setRole] = useState("candidate");
  const [cause, setCause] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!job || job.status !== "running" || job.stage === "uploading") return;
    const id = setInterval(async () => {
      const res = await fetch(`/worker/api/jobs/${job.id}`, { cache: "no-store" });
      if (res.ok) setJob(await res.json());
    }, 1500);
    return () => clearInterval(id);
  }, [job]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !label.trim()) return;
    setError(null);
    setJob({ id: "", status: "running", stage: "uploading", run_id: null, error: null });
    const form = new FormData();
    form.append("file", file);
    form.append("label", label.trim());
    form.append("role", role);
    if (cause.trim()) form.append("assumed_cause", cause.trim());
    try {
      const res = await fetch("/worker/api/upload", { method: "POST", body: form });
      if (!res.ok) throw new Error(`Upload failed (${res.status})`);
      const { job_id } = await res.json();
      setJob({ id: job_id, status: "running", stage: "queued", run_id: null, error: null });
    } catch (err) {
      setJob(null);
      setError(`${(err as Error).message}. Video processing runs on the worker; make sure it is running.`);
    }
  };

  const stageIndex = job ? Math.max(0, STAGES.indexOf(job.stage)) : -1;

  return (
    <form onSubmit={submit} className="space-y-5">
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) setFile(f); }}
        onClick={() => input.current?.click()}
        className={clsx("flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors",
          drag ? "border-base bg-base-soft" : "border-rule-strong hover:border-ink-3")}>
        <Film size={26} className="text-ink-2" />
        <p className="mt-3 text-[15px] font-medium">{file ? file.name : "Drop a recorded lab session here"}</p>
        <p className="mt-1 text-[13px] text-ink-2">{file ? `${(file.size / 1e6).toFixed(1)} MB` : "MP4 from a phone or webcam, up to a few minutes"}</p>
        <input ref={input} type="file" accept="video/mp4,video/quicktime,video/*" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </div>

      <div className="grid gap-4 sm:grid-cols-[1fr_180px]">
        <label className="block">
          <span className="text-[13px] text-ink-2">Run label</span>
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Method C" required
            className="mt-1 w-full rounded-md border border-rule-strong bg-surface px-3 py-2 text-[14px] outline-none focus:border-base" />
        </label>
        <label className="block">
          <span className="text-[13px] text-ink-2">Role</span>
          <select value={role} onChange={(e) => setRole(e.target.value)} className="mt-1 w-full rounded-md border border-rule-strong bg-surface px-3 py-2 text-[14px]">
            <option value="candidate">Candidate</option>
            <option value="control">Control</option>
            <option value="reference">Reference</option>
            <option value="rerun">Rerun</option>
          </select>
        </label>
      </div>
      <label className="block">
        <span className="text-[13px] text-ink-2">What do you think made this run different? (optional)</span>
        <input value={cause} onChange={(e) => setCause(e.target.value)} placeholder="I stirred longer after each addition"
          className="mt-1 w-full rounded-md border border-rule-strong bg-surface px-3 py-2 text-[14px] outline-none focus:border-base" />
      </label>

      <button type="submit" disabled={!file || !label.trim() || job?.status === "running"}
        className="rounded-md bg-ink px-4 py-2 text-[14px] font-medium text-paper disabled:opacity-40">
        Turn this video into commits
      </button>
      {error ? <p className="text-[13.5px] text-accent">{error}</p> : null}

      {job ? (
        <div className="rounded-xl border border-rule bg-surface p-5">
          <ol className="space-y-2">
            {STAGES.slice(0, -1).map((s, i) => (
              <li key={s} className={clsx("flex items-center gap-2.5 text-[14px]", i < stageIndex || job.status === "done" ? "text-ink" : i === stageIndex ? "text-ink" : "text-ink-3")}>
                <span className={clsx("size-2 rounded-full", i < stageIndex || job.status === "done" ? "bg-ok" : i === stageIndex && job.status === "running" ? "live-dot bg-base" : "bg-rule-strong")} />
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </li>
            ))}
          </ol>
          {job.status === "done" && job.run_id ? (
            <p className="mt-4 text-[14px]">
              {job.events ?? 0} commits recorded and sealed. <Link href={`/runs/${job.run_id}`} className="font-medium text-base hover:underline">Open the run</Link>
            </p>
          ) : null}
          {job.status === "error" ? <p className="mt-4 text-[13.5px] text-accent">{job.error}</p> : null}
        </div>
      ) : null}
    </form>
  );
}
