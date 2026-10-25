import { Suspense } from "react";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { getAnalysis } from "@/lib/data";
import { DiffView } from "@/components/diff/DiffView";
import { CompareStarter } from "@/components/diff/CompareStarter";
import { AskContext } from "@/components/ask/AskProvider";
import { Skeleton } from "@/components/ui";
import type { DiffContent, VerdictContent } from "@/lib/types";

async function Compare({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ reveal?: string }> }) {
  await connection();
  const { id } = await params;
  const { reveal } = await searchParams;
  const analysis = await getAnalysis<VerdictContent | DiffContent>(id);
  if (!analysis) notFound();
  if (analysis.kind === "diff" || analysis.kind === "branch") {
    const d = analysis.content as DiffContent;
    return <CompareStarter diffId={analysis.id} label={d.candidate.label} />;
  }
  if (analysis.kind !== "verdict") notFound();
  const v = analysis.content as VerdictContent;
  return (
    <>
      <AskContext page="diff" analysis_id={analysis.id} run_id={v.candidate.run_id} run_label={v.candidate.label}
        description={`${v.candidate.label} vs ${v.controls.map((c) => c.label).join(", ")}`} />
      <DiffView verdict={analysis as never} reveal={reveal === "1"} />
    </>
  );
}

export default function Page(props: PageProps<"/compare/[id]">) {
  return (
    <Suspense fallback={
      <div className="mx-auto max-w-[1180px] px-8 pt-8">
        <Skeleton className="h-11 w-[420px]" />
        <div className="mt-8 grid gap-5 lg:grid-cols-2"><Skeleton className="h-64" /><Skeleton className="h-64" /></div>
        <Skeleton className="mt-8 h-80" />
      </div>
    }>
      <Compare params={props.params} searchParams={props.searchParams as Promise<{ reveal?: string }>} />
    </Suspense>
  );
}
