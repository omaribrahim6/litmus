import { demoMode } from "@/lib/data";
import { normalizeQuestion, snapshotAnalysis, workerPost, WorkerError } from "@/lib/worker";
import type { AskAnswer } from "@/lib/types";

interface AskBody {
  messages: { role: string; text: string }[];
  context?: Record<string, unknown>;
  experiment?: string;
}

async function fromSnapshot(question: string): Promise<AskAnswer | null> {
  const q = normalizeQuestion(question);
  const hit = await snapshotAnalysis((a) => a.kind === "chat" && normalizeQuestion(String((a.content as { question?: string }).question ?? "")) === q);
  return hit ? ({ ...(hit.content as AskAnswer), cached: true }) : null;
}

export async function POST(req: Request) {
  const body = (await req.json()) as AskBody;
  const question = body.messages?.at(-1)?.text ?? "";
  if (!question.trim()) return Response.json({ error: "Ask a question first" }, { status: 400 });

  if (!demoMode()) {
    try {
      return Response.json(await workerPost<AskAnswer>("/api/ask", { messages: body.messages, context: body.context ?? {}, ...(body.experiment ? { experiment: body.experiment } : {}) }));
    } catch (err) {
      const cached = await fromSnapshot(question);
      if (cached) return Response.json(cached);
      const e = err as WorkerError;
      return Response.json({ error: e.message }, { status: e.status ?? 502 });
    }
  }
  const cached = await fromSnapshot(question);
  if (cached) return Response.json(cached);
  return Response.json(
    { error: "Offline mode only replays questions answered before. Try one of the suggested questions" },
    { status: 404 },
  );
}
