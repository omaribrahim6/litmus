"""Validation numbers for the About / Validation page.

    python -m litmus_worker.validate

Every number states its ground truth: manual video review (demo/validation/
manual_flips.csv), the light-sensor colorimeter, planted faults, or the
generator's known flip time for synthetic runs.
"""

from __future__ import annotations

import csv
import itertools
import json
import statistics
import uuid

from . import db, rundata, store
from .config import settings
from .diff import diff
from .measure import measure_result


def _manual_flips() -> dict[str, float]:
    path = settings.demo_dir / "validation" / "manual_flips.csv"
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["run_id"].strip(): float(row["manual_flip_s"]) for row in csv.DictReader(f) if row.get("manual_flip_s")}


def compute(experiment_slug: str = "vinegar-titration") -> dict:
    with db.connect() as conn:
        exp = store.get_experiment(conn, experiment_slug)
        protocol = exp["protocol"]
        runs = [r for r in store.list_runs(conn, exp["id"]) if r["status"] == "complete"]
        data = {r["id"]: rundata.load(conn, r["id"]) for r in runs}
        manual = _manual_flips()

        # 1. Flip timing accuracy against manual review (or synthetic ground truth).
        timing = []
        for r in runs:
            rd = data[r["id"]]
            flip = rd.flip_event()
            if flip is None or r["started_at"] is None:
                continue
            detected = (flip["t"] - r["started_at"]).total_seconds()
            truth, source = None, None
            if str(r["id"]) in manual:
                truth, source = manual[str(r["id"])], "manual video review"
            elif (r["metadata"] or {}).get("ground_truth_flip_s") is not None:
                truth, source = float(r["metadata"]["ground_truth_flip_s"]), "synthetic ground truth"
            if truth is not None:
                timing.append({"run": r["label"], "run_id": str(r["id"]), "detected_s": round(detected, 2),
                               "truth_s": round(truth, 2), "error_s": round(detected - truth, 2), "source": source})
        errors = [abs(t["error_s"]) for t in timing]

        # 2. Camera vs light-sensor colorimeter agreement.
        cross = []
        for r in runs:
            for e in data[r["id"]].events_of("flip_crosscheck"):
                p = e["payload"] or {}
                if p.get("delta_s") is not None:
                    cross.append({"run": r["label"], "delta_s": p["delta_s"], "agree": bool(p.get("agree"))})

        # 3. Hidden-fault test: planted confounds must surface as the top condition difference.
        refs = [data[r["id"]] for r in runs if r["role"] == "reference"]
        controls = [data[r["id"]] for r in runs if r["role"] == "control"]
        faults = []
        for r in runs:
            planted = (r["metadata"] or {}).get("planted_fault")
            if not planted or not controls:
                continue
            d = diff(protocol, data[r["id"]], controls[-1:], refs)
            top = next((i["key"] for i in d["differences"] if i["status"] == "notable" and i.get("role") != "outcome"), None)
            faults.append({"run": r["label"], "planted": planted, "top_difference": top, "found": top == planted})

        # 4. False alarms between reference runs that followed the same protocol.
        pairs = []
        for a, b in itertools.combinations(refs, 2):
            others = [x for x in refs if x.id not in (a.id, b.id)]
            d = diff(protocol, a, [b], others)
            alarms = [i["key"] for i in d["differences"] if i["status"] == "notable" and i.get("role") != "outcome"]
            pairs.append({"a": a.label, "b": b.label, "false_alarms": alarms})

        # 5. Traceability of every AI-written claim and report sentence.
        total = traced = 0
        for row in store.list_analyses(conn, "verdict"):
            for c in row["content"].get("claims", []):
                total += 1
                traced += bool(c.get("evidence_ids"))
        gaps = 0
        for row in store.list_analyses(conn, "report"):
            for sec in row["content"].get("sections", []):
                for s in sec["sentences"]:
                    total += 1
                    if s.get("evidence_ids"):
                        traced += 1
                    else:
                        gaps += 1

        content = {
            "experiment": exp["name"],
            "runs": len(runs),
            "synthetic_runs": sum(1 for r in runs if (r["metadata"] or {}).get("synthetic")),
            "flip_timing": {
                "n": len(timing), "within_1s": sum(1 for e in errors if e <= 1.0),
                "mean_abs_error_s": round(statistics.fmean(errors), 2) if errors else None,
                "max_abs_error_s": round(max(errors), 2) if errors else None,
                "sources": sorted({t["source"] for t in timing}), "rows": timing,
            },
            "probe_agreement": {
                "n": len(cross), "agree": sum(1 for c in cross if c["agree"]),
                "mean_abs_delta_s": round(statistics.fmean(abs(c["delta_s"]) for c in cross), 2) if cross else None,
                "tolerance_s": protocol.get("flip_agreement_s", 1.0), "rows": cross,
            },
            "hidden_faults": {"n": len(faults), "found": sum(1 for f in faults if f["found"]), "rows": faults},
            "false_alarms": {"pairs": len(pairs), "pairs_with_alarm": sum(1 for p in pairs if p["false_alarms"]),
                             "total_alarms": sum(len(p["false_alarms"]) for p in pairs), "rows": pairs},
            "traceability": {"claims": total, "traced": traced, "flagged_gaps": gaps,
                             "percent": round(100 * traced / total, 1) if total else None},
            "results": [{"run": r["label"], "role": r["role"], "value": measure_result(data[r["id"]], protocol).value} for r in runs],
        }
        row = store.insert_analysis(conn, "validation", [r["id"] for r in runs], content, model="deterministic")
    out = settings.cache_dir / "validation"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(content, indent=1, default=str), encoding="utf-8")
    return {"id": str(row["id"]), **content}


if __name__ == "__main__":
    print(json.dumps(compute(), indent=1, default=str)[:3000])
