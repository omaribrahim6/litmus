import { workerPost, WorkerError } from "@/lib/worker";
import type { Analysis } from "@/lib/types";

/** Reanalysis without some runs. Writes new analyses; the original record is never modified. */
export async function POST(req: Request) {
  const body = (await req.json()) as { analysis_id: string; exclude: string[] };
  try {
    const out = await workerPost<{ branch: Analysis; verdict: Analysis }>("/api/branch", body, 180_000);
    return Response.json({ verdict_id: out.verdict.id, branch_id: out.branch.id });
  } catch (err) {
    const e = err as WorkerError;
    return Response.json({ error: e.message }, { status: e.status ?? 502 });
  }
}
