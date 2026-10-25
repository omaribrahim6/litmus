import { Suspense } from "react";
import { connection } from "next/server";
import Link from "next/link";
import { Download, FlaskConical, Sparkles } from "lucide-react";
import { getExperiments, getLatestAnalysisFor, getRuns, getStrips } from "@/lib/data";
import { CommitLog, type LogRow } from "@/components/history/CommitLog";
import { ResultLine } from "@/components/history/ResultLine";
import { DataTable } from "@/components/history/DataTable";
import { LiveRefresh } from "@/components/LiveRefresh";
import { AskContext } from "@/components/ask/AskProvider";
import { AskButton } from "@/components/ask/AskButton";
import { Skeleton } from "@/components/ui";
import { fmtDateTime, fmtNumber, plural } from "@/lib/format";
import type { VerdictContent } from "@/lib/types";

function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-rule bg-surface px-4 py-3.5">
      <p className="text-[12px] text-ink-2">{label}</p>
      <p className="mt-1 text-[22px] font-semibold tracking-[-0.02em]">{value}</p>
      {hint ? <p className="mt-0.5 truncate text-[12px] text-ink-3">{hint}</p> : null}
    </div>
  );
}

async function History({ searchParams }: { searchParams: Promise<{ experiment?: string }> }) {
  await connection();
  const { experiment: wanted } = await searchParams;
  // "auto" is the placeholder every run starts on before Gemini sets up the real experiment.
  const experiments = (await getExperiments()).filter((e) => e.slug !== "auto");
  if (!experiments.length) {
    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center px-6 text-center">
        <FlaskConical size={28} className="text-ink-3" />
        <h1 className="mt-4 text-[20px] font-semibold">No experiments yet</h1>
        <p className="mt-1 max-w-[46ch] text-ink-2">Press start recording at the station and say what you are doing. Gemini sets the experiment up from that.</p>
      </div>
    );
  }
  const exp = experiments.find((e) => e.slug === wanted || e.id === wanted) ?? experiments[0];
  const runs = await getRuns(exp.id);
  const strips = await getStrips(runs);
  const verdicts = await Promise.all(
    runs.map((r) => (r.role === "candidate" || r.role === "rerun" ? getLatestAnalysisFor<VerdictContent>("verdict", r.id) : Promise.resolve(null))),
  );
  const rows: LogRow[] = runs.map((run, i) => ({
    run,
    strip: strips[run.id],
    verdictId: verdicts[i]?.id ?? null,
    verdictLabel: verdicts[i]?.content.headline ?? null,
  }));
  const recording = runs.some((r) => r.status === "recording");
  const synthetic = runs.some((r) => r.metadata?.synthetic);
  const p = exp.protocol;
  const numeric = runs.map((r) => r.result?.value).filter((v): v is number => typeof v === "number");
  const refVals = runs.filter((r) => r.role === "reference").map((r) => r.result?.value).filter((v): v is number => typeof v === "number");
  const refMean = refVals.length ? refVals.reduce((a, b) => a + b, 0) / refVals.length : null;
  const last = [...runs].sort((a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? ""))[0];
  const tracked = (p.measurements?.length ?? 0) + p.variables.filter((v) => v.type !== "sequence").length;
  const showChart = p.result.kind !== "none" && p.result.type !== "text";

  return (
    <div className="min-h-screen">
      <AskContext page="history" description={`${exp.name}, ${plural(runs.length, "run")}`} experiment={exp.slug} experiment_name={exp.name} result_label={p.result.label} />
      <LiveRefresh active={recording} />

      <div className="flex h-12 items-center gap-2 px-6 text-[13px] text-ink-2 max-md:px-4">
        <FlaskConical size={14} className="text-ink-3" />
        <span>Experiments</span>
        <span className="text-ink-3">/</span>
        <span className="truncate font-medium text-ink">{exp.name}</span>
        <div className="ml-auto flex items-center gap-1.5">
          <Link href={`/worker/api/experiments/${exp.slug}/dataset.csv`} prefetch={false}
            className="hidden h-8 items-center gap-1.5 rounded-lg px-2.5 font-medium text-ink-2 hover:bg-hover hover:text-ink sm:inline-flex">
            <Download size={14} /> Export CSV
          </Link>
          <AskButton />
        </div>
      </div>

      <div className="mx-auto max-w-[1080px] px-8 pb-24 pt-6 max-md:px-4">
        <header className="mb-8">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-[12px]">
            {recording ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-0.5 font-medium text-accent">
                <span className="live-dot inline-block size-1.5 rounded-full bg-accent" /> Recording now
              </span>
            ) : null}
            {"generated" in p && p.generated ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-sunken px-2.5 py-0.5 font-medium text-ink-2">
                <Sparkles size={12} /> Set up by Gemini from the researcher&apos;s intro
              </span>
            ) : null}
            {synthetic ? <span className="rounded-full border border-dashed border-rule-strong px-2.5 py-0.5 text-ink-2">Includes synthetic test runs</span> : null}
          </div>
          <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.025em]">{p.name}</h1>
          {p.description ? <p className="mt-2 max-w-[72ch] text-[14.5px] leading-relaxed text-ink-2">{p.description}</p> : null}
        </header>

        <section className="mb-8 grid grid-cols-4 gap-3 max-lg:grid-cols-2">
          <Stat label="Runs recorded" value={runs.length} hint={last ? `Latest ${fmtDateTime(last.started_at)}` : "None yet"} />
          <Stat label={showChart ? `Typical ${p.result.label.toLowerCase()}` : "Outcome"}
            value={showChart && refMean != null ? <>{fmtNumber(refMean, 2)}<span className="ml-1 text-[13px] font-normal text-ink-2">{p.result.unit}</span></> : showChart ? "—" : "Recorded"}
            hint={showChart ? (refVals.length ? `Mean of ${plural(refVals.length, "reference run")}` : `${numeric.length} runs with a result`) : "No single numeric result"} />
          <Stat label="Tracked per run" value={tracked} hint="Measurements and conditions" />
          <Stat label="Tamper-evident" value={<span className="text-ok">All sealed</span>} hint="SHA-256 hash chain per run" />
        </section>

        {showChart ? (
          <section className="mb-8 rounded-xl border border-rule bg-surface px-5 pb-4 pt-4">
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="text-[14px] font-semibold">{p.result.label}</h2>
              <span className="text-[12px] text-ink-3">Click a run to open it</span>
            </div>
            <ResultLine runs={runs} unit={p.result.unit} label={p.result.label} />
          </section>
        ) : null}

        <section className="mb-10">
          <div className="mb-2 flex items-baseline justify-between gap-4">
            <h2 className="text-[15px] font-semibold">Runs</h2>
            <p className="text-[12.5px] text-ink-3">Newest first. Each run is recorded automatically and sealed.</p>
          </div>
          {runs.length ? (
            <div className="rounded-xl border border-rule bg-surface px-2">
              <CommitLog rows={rows} unit={p.result.unit} />
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-rule-strong px-6 py-12 text-center">
              <p className="font-medium">No runs recorded yet</p>
              <p className="mt-1 text-[13.5px] text-ink-2">Press start on the station, or <Link className="text-base hover:underline" href="/upload">upload a recorded session</Link>.</p>
            </div>
          )}
        </section>

        <Suspense fallback={<Skeleton className="mb-10 h-40 w-full" />}>
          <DataTable slug={exp.slug} />
        </Suspense>
      </div>
    </div>
  );
}

function HistorySkeleton() {
  return (
    <div className="mx-auto max-w-[1080px] px-8 pt-16">
      <Skeleton className="h-8 w-[420px]" />
      <Skeleton className="mt-3 h-4 w-[620px]" />
      <div className="mt-8 grid grid-cols-4 gap-3">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[92px]" />)}</div>
      <Skeleton className="mt-8 h-[140px] w-full" />
    </div>
  );
}

export default function Page(props: PageProps<"/">) {
  return (
    <Suspense fallback={<HistorySkeleton />}>
      <History searchParams={props.searchParams as Promise<{ experiment?: string }>} />
    </Suspense>
  );
}
