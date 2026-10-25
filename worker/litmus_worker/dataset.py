"""Structured data out of the record: what was measured in each run, as a table.

Every run of an experiment becomes a row and every recorded variable a column
(the outcome first, then each measurement, then conditions Litmus tracks).
Each cell keeps its provenance and the evidence IDs it was computed from, so a
spreadsheet or a script gets the same receipts as the web app. Values come
only from measure.py: code aggregates what was recorded and never fills gaps.
"""

from __future__ import annotations

import csv
import io

import psycopg

from . import rundata, store
from .measure import Measure, measure_result, measure_variable, measurement_events


def columns(protocol: dict) -> list[dict]:
    spec = protocol["result"]
    cols = []
    if spec.get("kind", "amount_until_change") != "none":  # older protocols predate result kinds: they are titrations
        cols.append({"key": spec["key"], "label": spec["label"], "unit": spec.get("unit"), "role": "outcome", "result": True})
    for v in protocol.get("variables", []):
        if v["type"] == "sequence" or v["key"] == spec.get("key"):
            continue
        cols.append({"key": v["key"], "label": v["label"], "unit": v.get("unit"), "role": v.get("role", "condition")})
    return cols


def _cell(m: Measure, decimals: int) -> dict:
    return {"value": m.value if m.available else None, "display": m.display(decimals) if m.available else None,
            "provenance": m.provenance, "evidence_ids": m.evidence_ids[:6], "note": m.note}


def row(rd: rundata.RunData, protocol: dict, cols: list[dict]) -> dict:
    by_key = {v["key"]: v for v in protocol.get("variables", [])}
    cells = {}
    for c in cols:
        if c.get("result"):
            m = measure_result(rd, protocol)
            dec = protocol["result"].get("decimals", 2)
        else:
            m = measure_variable(rd, by_key[c["key"]], protocol)
            dec = by_key[c["key"]].get("decimals", 2)
        cells[c["key"]] = _cell(m, dec)
    run = rd.run
    meta = run.get("metadata") or {}
    return {"run_id": str(rd.id), "label": rd.label, "role": run.get("role"), "status": run.get("status"),
            "started_at": run.get("started_at"), "researcher": meta.get("researcher"), "cells": cells}


def readings_log(rd: rundata.RunData) -> list[dict]:
    """Every individual value recorded in one run, in time order, with where it came from."""
    t0 = rd.run.get("started_at")
    out = []
    for e in measurement_events(rd):
        p = e.get("payload") or {}
        out.append({"t_s": round((e["t"] - t0).total_seconds(), 1) if t0 else None, "key": p.get("key"), "label": p.get("label"),
                    "value": p.get("value"), "unit": p.get("unit"), "source": p.get("source"), "read_from": p.get("read_from"),
                    "provenance": e["provenance"], "evidence_id": f"evt:{e['id']}",
                    "frame_ids": [f"frm:{f}" for f in (e.get("frame_ids") or [])]})
    return out


def experiment_table(conn: psycopg.Connection, experiment: dict, include_open: bool = False) -> dict:
    protocol = experiment["protocol"]
    cols = columns(protocol)
    rows = []
    for r in store.list_runs(conn, experiment["id"]):
        if r["status"] != "complete" and not include_open:
            continue
        rows.append(row(rundata.load(conn, r["id"]), protocol, cols))
    return {"experiment": {"slug": experiment["slug"], "name": experiment["name"]}, "columns": cols, "rows": rows,
            "measurements": protocol.get("measurements", [])}


def to_csv(table: dict) -> str:
    """One row per run. Each column has its value and its provenance; evidence IDs let any number be traced back."""
    buf = io.StringIO()
    w = csv.writer(buf)
    head = ["run", "role", "started_at", "researcher"]
    for c in table["columns"]:
        name = f"{c['label']} ({c['unit']})" if c.get("unit") else c["label"]
        head += [name, f"{name} provenance"]
    head.append("evidence")
    w.writerow(head)
    for r in table["rows"]:
        line = [r["label"], r["role"], r["started_at"].isoformat() if r.get("started_at") else "", r.get("researcher") or ""]
        ids: list[str] = []
        for c in table["columns"]:
            cell = r["cells"][c["key"]]
            v = cell["value"]
            line += ["" if v is None else (" → ".join(map(str, v)) if isinstance(v, list) else v), cell["provenance"] or ""]
            ids += cell["evidence_ids"][:2]
        line.append(" ".join(dict.fromkeys(ids)))
        w.writerow(line)
    return buf.getvalue()
