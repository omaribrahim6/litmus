import { demoMode } from "@/lib/data";
import { snapshotAnalysis, workerPost, WorkerError } from "@/lib/worker";
import type { Analysis } from "@/lib/types";

export async function POST(req: Request) {
  const { verdict_id } = (await req.json()) as { verdict_id: string };
  const offline = () => snapshotAnalysis((a) => a.kind === "report" && (a.content as { verdict_analysis_id?: string }).verdict_analysis_id === verdict_id);
  if (!demoMode()) {
    try {
      const report = await workerPost<Analysis>("/api/report", { verdict_id }, 180_000);
      return Response.json({ report_id: report.id });
    } catch (err) {
      const hit = await offline();
      if (hit) return Response.json({ report_id: hit.id, offline: true });
      const e = err as WorkerError;
      return Response.json({ error: e.message }, { status: e.status ?? 502 });
    }
  }
  const hit = await offline();
  return hit
    ? Response.json({ report_id: hit.id, offline: true })
    : Response.json({ error: "This report was not prepared for offline mode" }, { status: 404 });
}
