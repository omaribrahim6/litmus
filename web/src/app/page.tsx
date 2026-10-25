import { Suspense } from "react";
import { connection } from "next/server";
import { sql, hasDatabase } from "@/lib/db";

async function LatestRun() {
  await connection();
  if (!hasDatabase()) {
    return <p className="text-sm opacity-60">Database not configured.</p>;
  }
  const [row] = await sql()`
    select label, role, started_at, (select count(*)::int from runs) as total
    from runs order by started_at desc nulls last limit 1`;
  if (!row) {
    return <p className="text-sm opacity-60">Connected to Tiger Data. No runs recorded yet.</p>;
  }
  return (
    <p className="font-mono text-sm">
      {row.total} runs on record. Latest: {row.label} ({row.role})
    </p>
  );
}

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-4 px-6">
      <h1 className="text-4xl font-semibold tracking-tight">Litmus</h1>
      <p className="opacity-70">Git for research, except you never have to commit.</p>
      <Suspense fallback={<p className="text-sm opacity-40">Reading from Tiger Data…</p>}>
        <LatestRun />
      </Suspense>
    </main>
  );
}
