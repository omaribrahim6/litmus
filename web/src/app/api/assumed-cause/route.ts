import { workerPost, WorkerError } from "@/lib/worker";

export async function POST(req: Request) {
  const { run_id, text } = (await req.json()) as { run_id: string; text: string };
  if (!text?.trim()) return Response.json({ error: "Describe the cause you suspect" }, { status: 400 });
  try {
    return Response.json(await workerPost(`/api/runs/${run_id}/assumed-cause`, { text: text.trim() }));
  } catch (err) {
    const e = err as WorkerError;
    return Response.json({ error: e.message }, { status: e.status ?? 502 });
  }
}
