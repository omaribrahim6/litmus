import { connection } from "next/server";
import { getExperiments, getRuns } from "@/lib/data";
import { SidebarNav, type NavExperiment, type NavRun } from "./SidebarNav";

/** Loads what the sidebar lists: every experiment on record and the latest runs. */
export async function Sidebar() {
  await connection();
  const experiments = (await getExperiments()).filter((e) => e.slug !== "auto");
  const runs = await getRuns();
  const byExp = new Map<string, number>();
  for (const r of runs) byExp.set(r.experiment_id, (byExp.get(r.experiment_id) ?? 0) + 1);
  const names = new Map(experiments.map((e) => [e.id, e.name]));
  const navExperiments: NavExperiment[] = experiments
    .map((e) => ({ slug: e.slug, name: e.name, runs: byExp.get(e.id) ?? 0 }))
    .sort((a, b) => b.runs - a.runs);
  const recent: NavRun[] = [...runs]
    .filter((r) => names.has(r.experiment_id))
    .sort((a, b) => (b.started_at ?? "").localeCompare(a.started_at ?? ""))
    .slice(0, 6)
    .map((r) => ({ id: r.id, label: r.label ?? "Untitled run", role: r.role, recording: r.status === "recording", experiment: names.get(r.experiment_id) ?? "" }));
  return <SidebarNav experiments={navExperiments} recent={recent} />;
}
