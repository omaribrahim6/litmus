import Link from "next/link";
import { Blame } from "@/components/evidence/Blame";
import { ProvenanceIcon, RoleTag } from "@/components/ui";
import { demoMode, workerUrl } from "@/lib/data";
import { fmtValue } from "@/lib/format";
import type { Provenance, Role } from "@/lib/types";

interface Column { key: string; label: string; unit?: string | null; role?: string; result?: boolean }
interface Cell { value: number | string | string[] | null; display: string | null; provenance: Provenance | null; evidence_ids: string[]; note?: string | null }
interface Table { columns: Column[]; rows: { run_id: string; label: string; role: Role; cells: Record<string, Cell> }[] }

async function load(slug: string): Promise<Table | null> {
  if (demoMode()) return null;
  try {
    const res = await fetch(`${workerUrl()}/api/experiments/${encodeURIComponent(slug)}/dataset`, {
      cache: "no-store", signal: AbortSignal.timeout(8000),
    });
    return res.ok ? ((await res.json()) as Table) : null;
  } catch {
    return null;
  }
}

/** The experiment as a dataset: one row per run, one column per thing recorded, every cell traceable. */
export async function DataTable({ slug, bare }: { slug: string; bare?: boolean }) {
  const table = await load(slug);
  if (!table || !table.rows.length) {
    return bare ? <p className="rounded-xl border border-dashed border-rule-strong px-5 py-10 text-center text-[13.5px] text-ink-2">No completed runs with recorded data yet, or the worker is offline.</p> : null;
  }
  const cols = table.columns.filter((c) => table.rows.some((r) => r.cells[c.key]?.value != null));
  if (!cols.length) return null;

  return (
    <section className="mb-10">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
        {bare ? <span /> : <h2 className="text-[15px] font-semibold">Data</h2>}
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2 text-[13px] text-ink-2">
          <span>One row per run. Empty cells were not recorded.</span>
          <Link href={`/worker/api/experiments/${encodeURIComponent(slug)}/dataset.csv`} prefetch={false}
            className="rounded-md border border-rule-strong px-2.5 py-1 font-medium text-ink hover:bg-surface">
            Download CSV
          </Link>
        </div>
      </div>
      <div className="overflow-x-auto rounded-xl border border-rule">
        <table className="w-full text-[14px]">
          <thead className="bg-surface text-left text-[12.5px] text-ink-2">
            <tr>
              <th className="px-4 py-2 font-medium">Run</th>
              {cols.map((c) => (
                <th key={c.key} className="min-w-[112px] px-4 py-2 text-right align-bottom font-medium leading-snug">
                  {c.label}{c.unit && !c.label.includes("(") ? <span className="text-ink-3"> ({c.unit})</span> : null}
                  {c.result ? <span className="ml-1 text-ink-3">· result</span> : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((r) => (
              <tr key={r.run_id} className="border-t border-rule">
                <td className="whitespace-nowrap px-4 py-2">
                  <Link href={`/runs/${r.run_id}`} className="font-medium hover:underline">{r.label}</Link>
                  <RoleTag role={r.role} className="ml-2 text-[12px]" />
                </td>
                {cols.map((c) => {
                  const cell = r.cells[c.key];
                  if (!cell || cell.value == null) return <td key={c.key} className="px-4 py-2 text-right text-ink-3" title={cell?.note ?? undefined}>·</td>;
                  const v = Array.isArray(cell.value) ? cell.value.join(" → ") : fmtValue(cell.value, 2);
                  return (
                    <td key={c.key} className="whitespace-nowrap px-4 py-2 text-right">
                      <Blame ids={cell.evidence_ids} title={`${c.label} in ${r.label}${cell.note ? ` (${cell.note})` : ""}`} quiet>
                        <span className="num">{v}</span>
                      </Blame>
                      <ProvenanceIcon p={cell.provenance} className="ml-1.5 align-middle" />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
