import { Suspense } from "react";
import { connection } from "next/server";
import { getExperiments } from "@/lib/data";
import { AskWorkspace } from "@/components/ask/AskWorkspace";
import { DataTable } from "@/components/history/DataTable";
import { Skeleton } from "@/components/ui";

export const metadata = { title: "Ask your lab" };

async function AskPage({ searchParams }: { searchParams: Promise<{ experiment?: string; session?: string; tab?: string }> }) {
  await connection();
  const { experiment, session, tab } = await searchParams;
  const experiments = (await getExperiments()).filter((e) => e.slug !== "auto");
  const exp = experiments.find((e) => e.slug === experiment) ?? experiments[0];
  const options = experiments.map((e) => ({ slug: e.slug, name: e.name, resultLabel: e.protocol.result?.label ?? "result" }));
  return (
    <AskWorkspace experiments={options} current={exp?.slug ?? ""} sessionId={session ?? null} tab={tab === "data" ? "data" : "chat"}
      data={exp ? (
        <Suspense fallback={<Skeleton className="h-60 w-full" />}>
          <DataTable slug={exp.slug} bare />
        </Suspense>
      ) : null} />
  );
}

export default function Page(props: PageProps<"/ask">) {
  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center"><Skeleton className="h-12 w-[560px]" /></div>}>
      <AskPage searchParams={props.searchParams as Promise<{ experiment?: string; session?: string; tab?: string }>} />
    </Suspense>
  );
}
