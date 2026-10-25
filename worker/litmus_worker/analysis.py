"""Orchestrates diff, verdict, report and branch analyses with caching.

Analyses are append-only rows. A cache key covers the inputs (run ids plus
each run's chain head), so a new commit on any run produces a fresh analysis
while repeated requests replay the stored one instantly.
"""

from __future__ import annotations

import uuid

import psycopg

from . import diff as diff_engine
from . import rundata, store
from .ai import cache, report as report_mod, verdict as verdict_mod
from .config import settings


def _heads(conn: psycopg.Connection, run_ids: list[uuid.UUID]) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """select r.id, (select hash from events e where e.run_id = r.id order by seq desc limit 1) as head
               from runs r where r.id = any(%s) order by r.id""",
            (run_ids,),
        )
        return [f"{row['id']}:{row['head']}" for row in cur.fetchall()]


def default_comparison(conn: psycopg.Connection, candidate: dict) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    runs = [r for r in store.list_runs(conn, candidate["experiment_id"]) if r["id"] != candidate["id"] and r["status"] == "complete"]
    controls = [r["id"] for r in runs if r["role"] == "control"][-1:]
    refs = [r["id"] for r in runs if r["role"] == "reference"]
    if not controls and refs:
        controls = refs[-1:]
    return controls, refs


def run_diff(conn: psycopg.Connection, candidate_id: uuid.UUID, control_ids: list[uuid.UUID] | None = None,
             reference_ids: list[uuid.UUID] | None = None, exclude: list[uuid.UUID] | None = None,
             kind: str = "diff", parent_id: uuid.UUID | None = None) -> dict:
    cand_row = store.get_run(conn, candidate_id)
    if cand_row is None:
        raise KeyError("candidate run not found")
    exp = store.get_experiment(conn, cand_row["experiment_id"])
    d_controls, d_refs = default_comparison(conn, cand_row)
    control_ids = control_ids or d_controls
    reference_ids = reference_ids if reference_ids is not None else d_refs
    exclude = exclude or []
    reference_ids = [r for r in reference_ids if r not in exclude]
    if not control_ids:
        raise ValueError("no control run to compare against")

    all_ids = [candidate_id, *control_ids, *reference_ids]
    key = cache.key_for(kind, str(candidate_id), sorted(map(str, control_ids)), sorted(map(str, reference_ids)),
                        _heads(conn, all_ids), cand_row.get("assumed_cause"), exp["protocol"])
    found = store.find_analysis(conn, kind, key)
    if found:
        return found

    cand = rundata.load(conn, candidate_id)
    controls = [rundata.load(conn, r) for r in control_ids]
    refs = [rundata.load(conn, r) for r in reference_ids]
    content = diff_engine.diff(exp["protocol"], cand, controls, refs)
    if kind == "branch":
        content["branch"] = {"parent_analysis_id": str(parent_id) if parent_id else None,
                             "excluded_run_ids": [str(r) for r in exclude],
                             "note": "Reanalysis only. The original runs and analyses are unchanged."}
    return store.insert_analysis(conn, kind, all_ids, content, cache_key=key, model="deterministic")


def run_verdict(conn: psycopg.Connection, diff_row: dict, use_ai: bool = True) -> dict:
    exp_slug = diff_row["content"]["experiment"]["slug"]
    exp = store.get_experiment(conn, exp_slug)
    key = cache.key_for("verdict", str(diff_row["id"]), diff_row["cache_key"], settings.model_pro if use_ai and settings.ai_enabled else "template")
    found = store.find_analysis(conn, "verdict", key)
    if found:
        return found
    cached = cache.read("verdict", key)
    content = cached or verdict_mod.build(diff_row["content"], exp["protocol"], use_ai=use_ai)
    content["diff_analysis_id"] = str(diff_row["id"])
    if not cached and content["model"] != "deterministic-template":
        cache.write("verdict", key, content)
    return store.insert_analysis(conn, "verdict", diff_row["run_ids"], content, cache_key=key, model=content["model"])


def run_report(conn: psycopg.Connection, verdict_row: dict, use_ai: bool = True) -> dict:
    v = verdict_row["content"]
    exp = store.get_experiment(conn, v["diff"]["experiment"]["slug"])
    key = cache.key_for("report", str(verdict_row["id"]), verdict_row["cache_key"], settings.model_pro if use_ai and settings.ai_enabled else "template")
    found = store.find_analysis(conn, "report", key)
    if found:
        return found
    cached = cache.read("report", key)
    if cached:
        content = cached
    else:
        run_ids = [uuid.UUID(v["candidate"]["run_id"])] + [uuid.UUID(c["run_id"]) for c in v["controls"]]
        runs = [rundata.load(conn, r) for r in run_ids]
        content = report_mod.build(v, exp["protocol"], runs, use_ai=use_ai)
        if content["model"] != "deterministic-template":
            cache.write("report", key, content)
    content["verdict_analysis_id"] = str(verdict_row["id"])
    content["markdown"] = report_mod.to_markdown(content)
    return store.insert_analysis(conn, "report", verdict_row["run_ids"], content, cache_key=key, model=content["model"])
