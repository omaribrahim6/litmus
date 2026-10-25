"""Vega-Lite chart specs built from database rows.

The model asks for a chart by kind; the data always comes from SQL and the
measurement code, and every datum carries the evidence ID behind it so a
click on any point opens its source.
"""

from __future__ import annotations

import statistics
import uuid

import psycopg

from . import evidence as ev
from . import rundata, store
from .measure import measure_result, measure_variable

ROLE_ORDER = ["reference", "control", "candidate", "rerun"]


def _style(style: str) -> dict:
    if style == "paper":
        return {
            "font": "Times New Roman, serif",
            "axis": {"labelFontSize": 12, "titleFontSize": 13, "grid": False, "domainColor": "#111", "tickColor": "#111",
                     "labelColor": "#111", "titleColor": "#111", "titleFontWeight": "normal"},
            "legend": {"labelFontSize": 12, "titleFontSize": 12, "orient": "bottom"},
            "title": {"fontSize": 14, "fontWeight": "normal", "color": "#111", "anchor": "start"},
            "view": {"stroke": None},
            "background": "white",
        }
    return {"view": {"stroke": None}, "axis": {"grid": True, "gridOpacity": 0.15}, "background": None}


def _runs(conn: psycopg.Connection, experiment_id, run_ids: list[str] | None) -> list[dict]:
    rows = [r for r in store.list_runs(conn, experiment_id) if r["status"] == "complete"]
    if run_ids:
        wanted = {str(r) for r in run_ids}
        rows = [r for r in rows if str(r["id"]) in wanted]
    return rows


def results_by_run(conn: psycopg.Connection, experiment: dict, run_ids: list[str] | None = None,
                   title: str | None = None, style: str = "screen") -> dict:
    protocol = experiment["protocol"]
    spec_r = protocol["result"]
    data = []
    for i, r in enumerate(_runs(conn, experiment["id"], run_ids), 1):
        res = r.get("result") or {}
        if not isinstance(res.get("value"), (int, float)):
            continue  # not measured, or a qualitative result that has no place on a numeric axis
        data.append({"run": r["label"], "role": r["role"], "order": i, "value": res["value"],
                     "evidence_id": (res.get("evidence_ids") or [ev.run(r["id"])])[0], "run_id": str(r["id"])})
    refs = [d["value"] for d in data if d["role"] == "reference"]
    layers = []
    if len(refs) >= 2:
        mean = statistics.fmean(refs)
        band = 2 * statistics.stdev(refs) if len(refs) >= 3 else (max(refs) - min(refs)) / 2
        layers.append({"mark": {"type": "rect", "opacity": 0.14, "fillOpacity": 0.14, "strokeOpacity": 0, "color": "#7a8793"},
                       "encoding": {"y": {"datum": mean - band}, "y2": {"datum": mean + band}}})
        layers.append({"mark": {"type": "rule", "strokeDash": [4, 3], "color": "#666"},
                       "encoding": {"y": {"datum": mean}}})
    layers.append({
        "mark": {"type": "point", "filled": True, "size": 110, "cursor": "pointer"},
        "encoding": {
            "x": {"field": "run", "type": "nominal", "sort": {"field": "order"}, "title": None, "axis": {"labelAngle": -30}},
            "y": {"field": "value", "type": "quantitative", "title": f"{spec_r['label']} ({spec_r.get('unit', '')})",
                  "scale": {"zero": False, "padding": 12}},
            "color": {"field": "role", "type": "nominal", "scale": {"domain": [r for r in ROLE_ORDER if any(d["role"] == r for d in data)]},
                      "title": "Role"},
            "shape": {"field": "role", "type": "nominal"},
            "tooltip": [{"field": "run"}, {"field": "role"}, {"field": "value", "title": spec_r["label"]}],
        },
    })
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title or f"{spec_r['label']} across runs",
        "width": "container", "height": 300,
        "data": {"values": data},
        "layer": layers,
        "config": _style(style),
    }
    note = "Shaded band: reference-run mean ± 2 SD." if len(refs) >= 3 else None
    return {"spec": spec, "data": data, "note": note, "kind": "results_by_run"}


def variable_by_run(conn: psycopg.Connection, experiment: dict, variable_key: str, run_ids: list[str] | None = None,
                    title: str | None = None, style: str = "screen") -> dict:
    protocol = experiment["protocol"]
    var = next((v for v in protocol["variables"] if v["key"] == variable_key), None)
    if var is None:
        raise ValueError(f"unknown variable {variable_key}")
    data = []
    for i, r in enumerate(_runs(conn, experiment["id"], run_ids), 1):
        m = measure_variable(rundata.load(conn, r["id"]), var, protocol)
        if not m.available:
            continue
        data.append({"run": r["label"], "role": r["role"], "order": i, "value": m.value,
                     "evidence_id": m.evidence_ids[0] if m.evidence_ids else ev.run(r["id"]), "run_id": str(r["id"]),
                     "provenance": m.provenance})
    numeric = var["type"] == "numeric"
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title or f"{var['label']} across runs",
        "width": "container", "height": 280,
        "data": {"values": data},
        "mark": {"type": "point" if numeric else "square", "filled": True, "size": 110, "cursor": "pointer"},
        "encoding": {
            "x": {"field": "run", "type": "nominal", "sort": {"field": "order"}, "title": None, "axis": {"labelAngle": -30}},
            "y": {"field": "value", "type": "quantitative" if numeric else "nominal",
                  "title": f"{var['label']}{' (' + var['unit'] + ')' if var.get('unit') else ''}", "scale": {"zero": False} if numeric else {}},
            "color": {"field": "role", "type": "nominal", "title": "Role"},
            "tooltip": [{"field": "run"}, {"field": "value"}, {"field": "provenance"}],
        },
        "config": _style(style),
    }
    return {"spec": spec, "data": data, "kind": "variable_by_run"}


def sensor_overlay(conn: psycopg.Connection, experiment: dict, sensor: str, run_ids: list[str] | None = None,
                   align: str = "start", title: str | None = None, style: str = "screen") -> dict:
    data = []
    for r in _runs(conn, experiment["id"], run_ids)[:8]:
        rd = rundata.load(conn, r["id"])
        series = rd.readings.get(sensor)
        if not series:
            continue
        t0 = series[0][0]
        if align == "flip":
            flip = rd.flip_event()
            if flip is None:
                continue
            t0 = flip["t"].timestamp()
        step = max(1, len(series) // 300)
        for t, v, _ in series[::step]:
            data.append({"run": r["label"], "role": r["role"], "t": round(t - t0, 2), "value": v,
                         "evidence_id": ev.rdg(r["id"], sensor, t), "run_id": str(r["id"])})
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title or f"{sensor} over time",
        "width": "container", "height": 280,
        "data": {"values": data},
        "mark": {"type": "line", "strokeWidth": 1.6, "interpolate": "monotone", "point": False},
        "encoding": {
            "x": {"field": "t", "type": "quantitative", "title": "seconds from flip" if align == "flip" else "seconds from start"},
            "y": {"field": "value", "type": "quantitative", "title": sensor, "scale": {"zero": False}},
            "color": {"field": "run", "type": "nominal", "title": "Run"},
            "tooltip": [{"field": "run"}, {"field": "t"}, {"field": "value"}],
        },
        "config": _style(style),
    }
    return {"spec": spec, "data": data[:2000], "kind": "sensor_overlay"}


def build(conn: psycopg.Connection, experiment: dict, kind: str, **kw) -> dict:
    fn = {"results_by_run": results_by_run, "variable_by_run": variable_by_run, "sensor_overlay": sensor_overlay}.get(kind)
    if fn is None:
        raise ValueError(f"unknown chart kind {kind}")
    chart = fn(conn, experiment, **{k: v for k, v in kw.items() if v is not None})
    chart["id"] = f"chart_{uuid.uuid4().hex[:10]}"
    return chart
