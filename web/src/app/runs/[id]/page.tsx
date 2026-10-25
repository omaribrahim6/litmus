import { Suspense } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { getEvents, getExperiment, getFrames, getLatestAnalysisFor, getReadings, getRun, getVerify } from "@/lib/data";
import { RunWorkbench } from "@/components/run/RunWorkbench";
import { ChainBadge } from "@/components/run/ChainBadge";
import { AssumedCauseForm } from "@/components/run/AssumedCauseForm";
import { AskContext } from "@/components/ask/AskProvider";
import { AskButton } from "@/components/ask/AskButton";
import { Blame } from "@/components/evidence/Blame";
import { ProvenanceIcon, RoleTag, Skeleton, SyntheticTag } from "@/components/ui";
import { fmtDateTime, fmtValue, secondsBetween } from "@/lib/format";
import { RecordedData } from "@/components/run/RecordedData";
import type { VerdictContent } from "@/lib/types";

async function Verify({ runId }: { runId: string }) {
  return <ChainBadge report={await getVerify(runId)} />;
}

async function RunPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ at?: string }> }) {
  await connection();
  const { id } = await params;
  const { at } = await searchParams;
  const run = await getRun(id);
  if (!run) notFound();
  const [events, readings, frames, experiment, verdict] = await Promise.all([
    getEvents(id), getReadings(id), getFrames(id), getExperiment(run.experiment_id), getLatestAnalysisFor<VerdictContent>("verdict", id),
  ]);
  const result = run.result;
  const duration = secondsBetween(run.started_at, run.ended_at);

  return (
    <div className="min-h-screen">
      <AskContext page="run" run_id={run.id} run_label={run.label ?? undefined} description={`${run.label} (${run.role})`} experiment={experiment?.slug} experiment_name={experiment?.name} result_label={experiment?.protocol.result.label} />
      <div className="flex h-12 items-center gap-2 px-6 text-[13px] text-ink-2 max-md:px-4">
        <Link href={experiment ? `/?experiment=${experiment.slug}` : "/"} className="truncate hover:text-ink">{experiment?.name ?? "Lab history"}</Link>
        <span className="text-ink-3">/</span>
        <span className="truncate font-medium text-ink">{run.label}</span>
        <div className="ml-auto flex items-center gap-1.5">
          <Suspense fallback={<Skeleton className="h-7 w-36 rounded-full" />}>
            <Verify runId={run.id} />
          </Suspense>
          <AskButton />
        </div>
      </div>

      <div className="mx-auto max-w-[1320px] px-6 pb-20 pt-4 max-md:px-4">
      <header className="mb-5 flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.025em]">{run.label}</h1>
            <RoleTag role={run.role} className="rounded-full bg-sunken px-2 py-0.5 text-[12px]" />
            {run.metadata?.synthetic ? <SyntheticTag /> : null}
            {run.status === "recording" ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2 py-0.5 text-[12px] font-medium text-accent"><span className="live-dot size-1.5 rounded-full bg-accent" /> Recording</span>
            ) : null}
          </div>
          <p className="mt-1 text-[13.5px] text-ink-2">
            {run.metadata?.session_title ? <>{String(run.metadata.session_title)}{run.metadata.researcher ? `, ${String(run.metadata.researcher)}` : ""}{run.metadata.lab ? `, ${String(run.metadata.lab)}` : ""} · </> : null}
            {fmtDateTime(run.started_at)}{duration ? ` · ${Math.round(duration)} s` : ""}{run.station_id ? ` · station ${run.station_id}` : ""}
          </p>
          <div className="mt-3">
            <AssumedCauseForm runId={run.id} current={run.assumed_cause} />
          </div>
        </div>
        <div className="flex items-stretch gap-3">
          <div className="min-w-[180px] rounded-xl border border-rule bg-surface px-4 py-3">
            <p className="text-[12px] text-ink-2">{result?.label ?? "Result"}</p>
            {result?.value != null ? (
              <>
                <Blame ids={result.evidence_ids} title={`Where ${result.label.toLowerCase()} came from`} quiet>
                  <span className="num text-[26px] font-medium leading-tight">{fmtValue(result.value)}</span>
                  <span className="ml-1 text-[13px] text-ink-2">{typeof result.value === "number" ? result.unit : ""}</span>
                </Blame>
                <div className="mt-0.5"><ProvenanceIcon p={result.provenance} withText /></div>
              </>
            ) : (
              <p className="mt-1 max-w-[26ch] text-[13.5px] text-ink-2">{run.status === "recording" ? "Recording" : result?.recorded ? `${result.recorded} values recorded` : result?.note ?? "Recorded"}</p>
            )}
          </div>
          <div className="flex flex-col justify-center gap-2">
            {verdict ? (
              <Link href={`/compare/${verdict.id}`} className="rounded-lg border border-rule bg-surface px-3 py-2 text-[13px] font-medium hover:border-rule-strong">Open verdict</Link>
            ) : run.status === "complete" && run.role !== "reference" ? (
              <Link href={`/compare/start?candidate=${run.id}`} className="rounded-lg bg-ink px-3 py-2 text-[13px] font-medium text-paper hover:opacity-90">Run the litmus test</Link>
            ) : null}
          </div>
        </div>
      </header>

      <RunWorkbench initialRun={run} initialEvents={events} initialReadings={readings} initialFrames={frames} initialAt={at ?? null} />
      <RecordedData events={events} startedAt={run.started_at} measurements={experiment?.protocol.measurements ?? []} />
      </div>
    </div>
  );
}

export default function Page(props: PageProps<"/runs/[id]">) {
  return (
    <Suspense fallback={
      <div className="mx-auto max-w-[1280px] px-8 pt-8">
        <Skeleton className="h-9 w-72" />
        <div className="mt-8 grid gap-5 xl:grid-cols-[1.45fr_1fr]"><Skeleton className="aspect-video" /><Skeleton className="h-full min-h-80" /></div>
        <Skeleton className="mt-5 h-72" />
      </div>
    }>
      <RunPage params={props.params} searchParams={props.searchParams as Promise<{ at?: string }>} />
    </Suspense>
  );
}
