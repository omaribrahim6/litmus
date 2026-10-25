import { demoMode } from "@/lib/data";
import { snapshotAnalysis, workerPost, WorkerError } from "@/lib/worker";
import type { Analysis } from "@/lib/types";

/** Start (or replay) the diff + verdict for a candidate run, or for an existing diff. */
export async function POST(req: Request) {
  const body = (await req.json()) as { candidate?: string; controls?: string[]; diff_id?: string };
  const offline = () =>
    snapshotAnalysis((a) => a.kind === "verdict" &&
      (body.diff_id ? (a.content as { diff_analysis_id?: string }).diff_analysis_id === body.diff_id : a.run_ids[0] === body.candidate));

  if (!demoMode()) {
    try {
      const verdict = await workerPost<Analysis>("/api/verdict", body.diff_id ? { diff_id: body.diff_id } : { candidate: body.candidate, controls: body.controls });
      return Response.json({ verdict_id: verdict.id });
    } catch (err) {
      const hit = await offline();
      if (hit) return Response.json({ verdict_id: hit.id, offline: true });
      const e = err as WorkerError;
      return Response.json({ error: e.message }, { status: e.status ?? 502 });
    }
  }
  const hit = await offline();
  return hit
    ? Response.json({ verdict_id: hit.id, offline: true })
    : Response.json({ error: "This comparison was not prepared for offline mode" }, { status: 404 });
}
