import { Suspense } from "react";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { getAnalysis } from "@/lib/data";
import { ReportView } from "@/components/report/ReportView";
import { AskContext } from "@/components/ask/AskProvider";
import { Skeleton } from "@/components/ui";
import type { ReportContent } from "@/lib/types";

async function Report({ params }: { params: Promise<{ id: string }> }) {
  await connection();
  const { id } = await params;
  const report = await getAnalysis<ReportContent>(id);
  if (!report || report.kind !== "report") notFound();
  return (
    <>
      <AskContext page="report" analysis_id={report.id} run_id={report.content.candidate.run_id} run_label={report.content.candidate.label}
        description={`Report: ${report.content.candidate.label}`} />
      <ReportView report={report} />
    </>
  );
}

export default function Page(props: PageProps<"/reports/[id]">) {
  return (
    <Suspense fallback={<div className="mx-auto max-w-[760px] space-y-4 px-8 pt-10"><Skeleton className="h-10 w-3/4" />{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-5 w-full" />)}</div>}>
      <Report params={props.params} />
    </Suspense>
  );
}
