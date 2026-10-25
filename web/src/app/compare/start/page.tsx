import { Suspense } from "react";
import { connection } from "next/server";
import { getRun } from "@/lib/data";
import { CompareStarter } from "@/components/diff/CompareStarter";

async function Start({ searchParams }: { searchParams: Promise<{ candidate?: string }> }) {
  await connection();
  const { candidate } = await searchParams;
  const run = candidate ? await getRun(candidate) : null;
  if (!run) {
    return <p className="mx-auto max-w-xl px-6 py-20 text-ink-2">Pick a candidate run from the lab history to test it.</p>;
  }
  return <CompareStarter candidate={run.id} label={run.label ?? undefined} />;
}

export default function Page(props: PageProps<"/compare/start">) {
  return (
    <Suspense fallback={null}>
      <Start searchParams={props.searchParams as Promise<{ candidate?: string }>} />
    </Suspense>
  );
}
