import { connection, type NextRequest } from "next/server";
import { resolveEvidence } from "@/lib/data";

export async function GET(req: NextRequest) {
  await connection();
  const ids = (req.nextUrl.searchParams.get("ids") ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  if (!ids.length) return Response.json({});
  return Response.json(await resolveEvidence(ids));
}
