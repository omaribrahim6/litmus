import { Suspense } from "react";
import { connection } from "next/server";
import Link from "next/link";
import { getExperiments, getLatestAnalysisFor, getRuns, getStrips } from "@/lib/data";
import { CommitLog, type LogRow } from "@/components/history/CommitLog";
import { ResultLine } from "@/components/history/ResultLine";
import { LiveRefresh } from "@/components/LiveRefresh";
import { AskContext } from "@/components/ask/AskProvider";
import { Skeleton } from "@/components/ui";
import { plural } from "@/lib/format";
import type { VerdictContent } from "@/lib/types";

async function History({ searchParams }: { searchParams: Promise<{ experiment?: string }> }) {
  await connection();
  const { experiment: wanted } = await searchParams;
  const experiments = await getExperiments();
  if (!experiments.length) {
    return (
      <div className="mx-auto max-w-xl px-6 py-24">
        <h1 className="wide text-2xl font-semibold">No experiments yet</h1>
        <p className="mt-2 text-ink-2">Seed a protocol with <code className="num text-[13px]">python -m litmus_worker.seed</code>, then start a run at the station.</p>
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

  return (
    <div className="mx-auto max-w-[1080px] px-8 pb-24 pt-10 max-md:px-4">
      <AskContext page="history" description={`${exp.name}, ${plural(runs.length, "run")}`} />
      <LiveRefresh active={recording} />

      <section className="mb-10">
        {experiments.length > 1 ? (
          <nav className="mb-4 flex gap-2 text-[13px]">
            {experiments.map((e) => (
              <Link key={e.id} href={`/?experiment=${e.slug}`} className={e.id === exp.id ? "font-semibold" : "text-ink-2 hover:text-ink"}>{e.name}</Link>
            ))}
          </nav>
        ) : null}
        <h1 className="wide text-[34px] font-semibold leading-[1.1] tracking-[-0.015em]">{p.name}</h1>
        <p className="mt-2 max-w-[68ch] text-[15px] text-ink-2">{p.description}</p>
        <div className="mt-8 rounded-xl border border-rule bg-surface px-6 pb-4 pt-5">
          <ResultLine runs={runs} unit={p.result.unit} label={p.result.label} />
        </div>
      </section>

      <section>
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-[17px] font-semibold">Lab history</h2>
          <p className="text-[13px] text-ink-2">
            {plural(runs.length, "run")}, newest first. Every run is recorded automatically and sealed with a hash chain.
          </p>
        </div>
        {synthetic ? (
          <p className="mb-3 text-[13px] text-ink-2">Runs marked synthetic are generated test data, kept until real station recordings replace them.</p>
        ) : null}
        {runs.length ? (
          <CommitLog rows={rows} unit={p.result.unit} />
        ) : (
          <div className="rounded-xl border border-dashed border-rule-strong px-6 py-12 text-center">
            <p className="font-medium">No runs recorded yet</p>
            <p className="mt-1 text-[14px] text-ink-2">Press start on the station, or <Link className="text-base hover:underline" href="/upload">upload a recorded session</Link>.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function HistorySkeleton() {
  return (
    <div className="mx-auto max-w-[1080px] px-8 pt-10">
      <Skeleton className="h-9 w-[440px]" />
      <Skeleton className="mt-3 h-4 w-[620px]" />
      <Skeleton className="mt-8 h-[120px] w-full" />
      <div className="mt-10 space-y-3">
        {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
      </div>
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
