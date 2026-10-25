import { connection } from "next/server";
import { getEvents, getFrames, getReadings, getRun } from "@/lib/data";

/** Polled by the run view while a run is recording: everything new since the last commit it saw. */
export async function GET(req: Request, ctx: RouteContext<"/api/runs/[id]/live">) {
  await connection();
  const { id } = await ctx.params;
  const after = Number(new URL(req.url).searchParams.get("after") ?? "-1");
  const run = await getRun(id);
  if (!run) return Response.json({ error: "Run not found" }, { status: 404 });
  const [events, readings, frames] = await Promise.all([getEvents(id, after), getReadings(id), getFrames(id)]);
  return Response.json({ run, events, readings, frames });
}
