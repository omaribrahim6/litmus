import { Suspense } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { getEvents, getExperiment, getFrames, getLatestAnalysisFor, getReadings, getRun, getVerify } from "@/lib/data";
import { RunWorkbench } from "@/components/run/RunWorkbench";
import { ChainBadge } from "@/components/run/ChainBadge";
import { AssumedCauseForm } from "@/components/run/AssumedCauseForm";
import { AskContext } from "@/components/ask/AskProvider";
import { Blame } from "@/components/evidence/Blame";
import { ProvenanceIcon, RoleTag, Skeleton, SyntheticTag } from "@/components/ui";
import { fmtDateTime, fmtNumber, secondsBetween } from "@/lib/format";
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
    <div className="mx-auto max-w-[1280px] px-8 pb-20 pt-7 max-md:px-4">
      <AskContext page="run" run_id={run.id} run_label={run.label ?? undefined} description={`${run.label} (${run.role})`} />
      <nav className="mb-3 text-[13px] text-ink-2">
        <Link href="/" className="hover:text-ink">{experiment?.name ?? "Lab history"}</Link>
        <span className="mx-1.5 text-ink-3">/</span>
        <span>{run.label}</span>
      </nav>

      <header className="mb-6 flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="wide text-[32px] font-semibold leading-tight tracking-[-0.015em]">{run.label}</h1>
            <RoleTag role={run.role} className="text-[15px]" />
            {run.metadata?.synthetic ? <SyntheticTag /> : null}
          </div>
          <p className="mt-1 text-[14px] text-ink-2">
            {fmtDateTime(run.started_at)}
            {duration ? `, ${Math.round(duration)} s` : ""}
            {run.station_id ? `, station ${run.station_id}` : ""}
          </p>
          <div className="mt-3">
            <AssumedCauseForm runId={run.id} current={run.assumed_cause} />
          </div>
        </div>
        <div className="flex flex-col items-end gap-3">
          {result?.value != null ? (
            <div className="text-right">
              <div className="text-[12.5px] text-ink-2">{result.label}</div>
              <Blame ids={result.evidence_ids} title={`How ${result.label.toLowerCase()} was computed: additions up to the detected flip`} quiet>
                <span className="num text-[34px] leading-none">{fmtNumber(result.value)}</span>
                <span className="ml-1.5 text-[15px] text-ink-2">{result.unit}</span>
              </Blame>
              <div className="mt-1 flex justify-end"><ProvenanceIcon p={result.provenance} withText /></div>
            </div>
          ) : (
            <p className="text-[14px] text-ink-2">{run.status === "recording" ? "Waiting for the color flip" : result?.note ?? "No result"}</p>
          )}
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Suspense fallback={<Skeleton className="h-7 w-40 rounded-full" />}>
              <Verify runId={run.id} />
            </Suspense>
            {verdict ? (
              <Link href={`/compare/${verdict.id}`} className="rounded-md border border-rule-strong px-3 py-1.5 text-[13px] font-medium hover:bg-surface">Open verdict</Link>
            ) : run.status === "complete" && run.role !== "reference" ? (
              <Link href={`/compare/start?candidate=${run.id}`} className="rounded-md bg-ink px-3 py-1.5 text-[13px] font-medium text-paper hover:opacity-90">Run the litmus test</Link>
            ) : null}
          </div>
        </div>
      </header>

      <RunWorkbench initialRun={run} initialEvents={events} initialReadings={readings} initialFrames={frames} initialAt={at ?? null} />
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
