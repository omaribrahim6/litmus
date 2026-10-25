import { connection } from "next/server";
import { dataSourceLabel } from "@/lib/data";
import { workerHealthy } from "@/lib/worker";

export async function GET() {
  await connection();
  const [source, worker] = await Promise.all([dataSourceLabel(), workerHealthy()]);
  return Response.json({ source, worker });
}
