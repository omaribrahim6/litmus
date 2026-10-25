import { Blame } from "@/components/evidence/Blame";
import { ProvenanceIcon } from "@/components/ui";
import { fmtOffset, fmtValue } from "@/lib/format";
import type { LitmusEvent, Measurement } from "@/lib/types";

/** Every value recorded in this run: read off the bench by Gemini, said aloud, or measured, each with its receipt. */
export function RecordedData({ events, startedAt, measurements }: {
  events: LitmusEvent[];
  startedAt: string | null;
  measurements: Measurement[];
}) {
  const rows = events.filter((e) => e.kind === "measurement");
  const t0 = startedAt ? new Date(startedAt).getTime() : null;
  const seen = new Set(rows.map((e) => String(e.payload?.key)));
  const watched = measurements.filter((m) => !seen.has(m.key));
  if (!rows.length && !measurements.length) return null;  // nothing was set up to be read as data in this experiment

  return (
    <section className="mt-8">
      <div className="mb-2 flex items-baseline justify-between gap-4">
        <h2 className="text-[17px] font-semibold">Recorded data</h2>
        <p className="text-[13px] text-ink-2">
          Values Gemini read off the bench or heard said aloud. Click a value to see the frame or audio it came from.
        </p>
      </div>
      {rows.length ? (
        <div className="overflow-x-auto rounded-xl border border-rule">
          <table className="w-full min-w-[560px] text-[14px]">
            <thead className="bg-surface text-left text-[12.5px] text-ink-2">
              <tr>
                <th className="px-4 py-2 font-medium">Time</th>
                <th className="px-4 py-2 font-medium">Measurement</th>
                <th className="px-4 py-2 text-right font-medium">Value</th>
                <th className="px-4 py-2 font-medium">From</th>
                <th className="px-4 py-2 font-medium">Provenance</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => {
                const p = e.payload ?? {};
                const value = p.value as number | string | null;
                const ids = [`evt:${e.id}`, ...e.frame_ids.map((f) => `frm:${f}`)];
                return (
                  <tr key={e.id} className="border-t border-rule">
                    <td className="num px-4 py-2 text-[12.5px] text-ink-3">{t0 != null ? fmtOffset((new Date(e.t).getTime() - t0) / 1000) : ""}</td>
                    <td className="px-4 py-2">{String(p.label ?? p.key)}</td>
                    <td className="px-4 py-2 text-right">
                      <Blame ids={ids} title={`${String(p.label ?? p.key)}: where this value came from`} quiet>
                        <span className="num">{fmtValue(value, 2)}</span>
                        {p.unit ? <span className="ml-1 text-[12.5px] text-ink-2">{String(p.unit)}</span> : null}
                      </Blame>
                    </td>
                    <td className="px-4 py-2 text-ink-2">{String(p.read_from ?? (p.source === "speech" ? "said at the bench" : p.source ?? ""))}</td>
                    <td className="px-4 py-2"><ProvenanceIcon p={e.provenance} withText /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-rule-strong px-5 py-6 text-[14px] text-ink-2">
          Nothing was read or said as a value in this run yet.
        </p>
      )}
      {watched.length ? (
        <p className="mt-2 text-[13px] text-ink-3">
          Not recorded in this run: {watched.map((m) => m.label.toLowerCase()).join(", ")}. Missing values are left empty, never estimated.
        </p>
      ) : null}
    </section>
  );
}
