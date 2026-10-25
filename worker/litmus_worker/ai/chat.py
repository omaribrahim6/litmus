"""'Ask your lab': Gemini with function calling over the recorded history.

Tools query SQL, the measurement code and the diff engine. The model never
receives a number it did not get from a tool, charts are built from SQL by
code, and every cited evidence ID is checked before it reaches the UI.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Callable

import psycopg
from google.genai import types

from .. import analysis, charts, evidence as ev, rundata, store
from ..config import settings
from . import cache
from .client import AIUnavailable, embed, generate
from .validator import has_probability_language

log = logging.getLogger("litmus.chat")

CITATION = re.compile(r"\[((?:evt|frm|ser|rdg|run):[^\]]+)\]")
ID_TOKEN = re.compile(r"(?:evt|frm|run):[0-9a-f-]{36}|(?:ser|rdg):[0-9a-f-]{36}:[A-Za-z0-9_]+(?::\d+){1,2}")
MAX_TOOL_ROUNDS = 6


# ------------------------------------------------------------------ helpers

def resolve_run(conn: psycopg.Connection, experiment_id, ref: str | None) -> dict | None:
    """Accept a run UUID, a label ("Method B"), or an ordinal ("trial 4", "run 2")."""
    if not ref:
        return None
    ref = str(ref).strip()
    try:
        return store.get_run(conn, uuid.UUID(ref))
    except ValueError:
        pass
    runs = store.list_runs(conn, experiment_id)
    low = ref.lower()
    for r in runs:
        if (r["label"] or "").lower() == low:
            return r
    m = re.search(r"(\d+)\s*$", low)
    if m:
        n = int(m.group(1))
        for r in runs:
            if re.search(rf"\b{n}\b", (r["label"] or "").lower()):
                return r
        if 1 <= n <= len(runs):
            return runs[n - 1]
    for r in runs:
        if low in (r["label"] or "").lower():
            return r
    words = low.split()
    if words and len(words[-1]) == 1:
        for r in runs:
            if (r["label"] or "").lower().endswith(" " + words[-1]):
                return r
    return None


def _t_s(t: datetime, t0: datetime | None) -> float | None:
    return round((t - t0).total_seconds(), 1) if t0 else None


class Toolbox:
    def __init__(self, conn: psycopg.Connection, experiment: dict):
        self.conn = conn
        self.experiment = experiment
        self.charts: list[dict] = []
        self.analyses: list[str] = []
        self.calls: list[dict] = []
        self.seen_ids: set[str] = set()

    def _note(self, ids: list[str]) -> None:
        self.seen_ids.update(ids)

    def list_runs(self) -> dict:
        out = []
        for r in store.list_runs(self.conn, self.experiment["id"]):
            res = r.get("result") or {}
            ids = (res.get("evidence_ids") or [])[:2] + [ev.run(r["id"])]
            self._note(ids)
            out.append({"run_id": str(r["id"]), "label": r["label"], "role": r["role"], "status": r["status"],
                        "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                        "result": {"value": res.get("value"), "unit": res.get("unit"), "label": res.get("label")},
                        "assumed_cause": r.get("assumed_cause"), "evidence_ids": ids,
                        "synthetic": bool((r.get("metadata") or {}).get("synthetic"))})
        return {"runs": out}

    def get_dataset(self) -> dict:
        """Every completed run as a row, every recorded variable as a column, each value with provenance and evidence."""
        from .. import dataset
        table = dataset.experiment_table(self.conn, self.experiment)
        rows = []
        for r in table["rows"]:
            cells = {}
            for k, c in r["cells"].items():
                if c["value"] is None:
                    cells[k] = {"value": None, "note": c["note"]}
                    continue
                self._note(c["evidence_ids"][:3])
                cells[k] = {"value": c["display"], "provenance": c["provenance"], "evidence_ids": c["evidence_ids"][:3]}
            rows.append({"run": r["label"], "role": r["role"], "cells": cells})
        return store.to_json({"columns": table["columns"], "rows": rows})

    def get_run_timeline(self, run: str) -> dict:
        r = resolve_run(self.conn, self.experiment["id"], run)
        if r is None:
            return {"error": f"no run matches {run!r}"}
        events = store.get_events(self.conn, r["id"], order="time")
        t0 = r["started_at"]
        items = []
        for e in events:
            if e["kind"] == "run_sealed":
                continue
            eid = ev.evt(e["id"])
            frames = [ev.frm(f) for f in (e["frame_ids"] or [])[:1]]
            self._note([eid, *frames])
            items.append({"id": eid, "t_s": _t_s(e["t"], t0), "kind": e["kind"], "summary": e["summary"],
                          "provenance": e["provenance"], "frames": frames})
        return {"run_id": str(r["id"]), "label": r["label"], "role": r["role"], "events": items}

    def query_readings(self, run: str, sensor: str, t_start_s: float | None = None, t_end_s: float | None = None) -> dict:
        r = resolve_run(self.conn, self.experiment["id"], run)
        if r is None:
            return {"error": f"no run matches {run!r}"}
        rows = [b for b in store.get_readings_1s(self.conn, r["id"]) if b["sensor"] == sensor]
        t0 = r["started_at"]
        rows = [b for b in rows if (t_start_s is None or _t_s(b["bucket"], t0) >= t_start_s)
                and (t_end_s is None or _t_s(b["bucket"], t0) <= t_end_s)]
        if not rows:
            return {"run": r["label"], "sensor": sensor, "available": False,
                    "note": "no readings for this sensor in this run (not connected or not recorded)"}
        series_id = ev.ser(r["id"], sensor, rows[0]["bucket"], rows[-1]["bucket"])
        self._note([series_id])
        step = max(1, len(rows) // 60)
        values = [b["avg"] for b in rows]
        return {"run": r["label"], "sensor": sensor, "available": True, "evidence_id": series_id,
                "summary": {"n_seconds": len(rows), "mean": round(sum(values) / len(values), 4),
                            "min": round(min(values), 4), "max": round(max(values), 4)},
                "buckets": [{"t_s": _t_s(b["bucket"], t0), "avg": round(b["avg"], 4)} for b in rows[::step]]}

    def search_events(self, query: str, run: str | None = None, limit: int = 8) -> dict:
        r = resolve_run(self.conn, self.experiment["id"], run) if run else None
        ranked: dict[str, float] = {}
        rows: dict[str, dict] = {}
        with self.conn.cursor() as cur:
            cur.execute(
                """select e.id, e.run_id, e.t, e.kind, e.summary, e.provenance, r.label
                   from events e join runs r on r.id = e.run_id
                   where r.experiment_id = %s and (%s::uuid is null or e.run_id = %s::uuid)
                     and e.search @@ websearch_to_tsquery('english', %s)
                   order by ts_rank(e.search, websearch_to_tsquery('english', %s)) desc limit 20""",
                (self.experiment["id"], r["id"] if r else None, r["id"] if r else None, query, query),
            )
            for i, row in enumerate(cur.fetchall()):
                rows[str(row["id"])] = row
                ranked[str(row["id"])] = ranked.get(str(row["id"]), 0) + 1 / (60 + i)
            if settings.ai_enabled:
                try:
                    [qv] = embed([query], task_type="RETRIEVAL_QUERY")
                    cur.execute(
                        """select e.id, e.run_id, e.t, e.kind, e.summary, e.provenance, r.label
                           from events e join runs r on r.id = e.run_id
                           where r.experiment_id = %s and e.embedding is not null
                             and (%s::uuid is null or e.run_id = %s::uuid)
                           order by e.embedding <=> %s::vector limit 20""",
                        (self.experiment["id"], r["id"] if r else None, r["id"] if r else None, str(qv)),
                    )
                    for i, row in enumerate(cur.fetchall()):
                        rows[str(row["id"])] = row
                        ranked[str(row["id"])] = ranked.get(str(row["id"]), 0) + 1 / (60 + i)
                except Exception as exc:  # noqa: BLE001 - keyword search still answers
                    log.info("vector search skipped: %s", exc)
        top = sorted(ranked, key=ranked.get, reverse=True)[:limit]
        out = []
        for k in top:
            row = rows[k]
            eid = ev.evt(row["id"])
            self._note([eid])
            out.append({"id": eid, "run": row["label"], "kind": row["kind"], "summary": row["summary"],
                        "provenance": row["provenance"]})
        return {"query": query, "matches": out}

    def diff_runs(self, candidate: str, control: str | None = None) -> dict:
        c = resolve_run(self.conn, self.experiment["id"], candidate)
        if c is None:
            return {"error": f"no run matches {candidate!r}"}
        k = resolve_run(self.conn, self.experiment["id"], control) if control else None
        row = analysis.run_diff(self.conn, c["id"], [k["id"]] if k else None)
        self.analyses.append(str(row["id"]))
        d = row["content"]
        def ids(i):  # noqa: E306
            out = i["candidate"]["evidence_ids"][:2] + i["control"]["evidence_ids"][:2]
            self._note(out)
            return out
        return {
            "analysis_id": str(row["id"]),
            "candidate": d["candidate"]["label"], "control": ", ".join(x["label"] for x in d["controls"]),
            "reference_runs": len(d["references"]),
            "result": {"explanation": d["result"].get("explanation"), "headline": d["result"].get("headline"),
                       "evidence_ids": ids(d["result"]) if d["result"]["status"] != "missing_evidence" else []},
            "assumed_cause": {k2: d["assumed_cause"].get(k2) for k2 in ("text", "label", "reason")},
            "notable": [{"variable": i["label"], "role": i.get("role"), "explanation": i["explanation"], "evidence_ids": ids(i)}
                        for i in d["differences"] if i["status"] == "notable"],
            "within_normal_variation": [i["label"] for i in d["differences"] if i["status"] in ("within_normal", "same")],
            "missing_evidence": [i["label"] for i in d["differences"] if i["status"] == "missing_evidence"],
            "follow_up": d["follow_up"],
        }

    def make_chart(self, kind: str, title: str | None = None, variable_key: str | None = None, sensor: str | None = None,
                   runs: list[str] | None = None, style: str = "screen", align: str | None = None) -> dict:
        run_ids = None
        if runs:
            resolved = [resolve_run(self.conn, self.experiment["id"], r) for r in runs]
            run_ids = [str(r["id"]) for r in resolved if r]
        kw: dict[str, Any] = {"title": title, "style": style, "run_ids": run_ids}
        if kind == "variable_by_run":
            kw["variable_key"] = variable_key
        if kind == "sensor_overlay":
            kw["sensor"] = sensor
            kw["align"] = align
        try:
            chart = charts.build(self.conn, self.experiment, kind, **kw)
        except ValueError as exc:
            return {"error": str(exc)}
        self.charts.append(chart)
        for d in chart["data"]:
            self.seen_ids.add(d["evidence_id"])
        preview = [{k: d[k] for k in ("run", "value") if k in d} for d in chart["data"][:30]] if kind != "sensor_overlay" else []
        return {"chart_id": chart["id"], "kind": kind, "points": len(chart["data"]), "data_preview": preview,
                "note": chart.get("note"), "rendered": "The chart is shown to the user; do not describe it point by point."}

    def get_evidence(self, id: str) -> dict:
        found = ev.resolve(self.conn, id)
        if found is None:
            return {"error": "evidence not found"}
        self.seen_ids.add(id)
        return store.to_json({k: v for k, v in found.items() if k != "points"})

    def registry(self) -> dict[str, Callable[..., dict]]:
        return {n: getattr(self, n) for n in ("list_runs", "get_dataset", "get_run_timeline", "query_readings", "search_events",
                                               "diff_runs", "make_chart", "get_evidence")}


def _decl(name: str, desc: str, props: dict, required: list[str] | None = None) -> types.FunctionDeclaration:
    return types.FunctionDeclaration(name=name, description=desc, parameters_json_schema={
        "type": "object", "properties": props, "required": required or []})


DECLARATIONS = [
    _decl("list_runs", "List every run of this experiment with its role, result and evidence IDs.", {}),
    _decl("get_dataset", "The experiment's data table: one row per completed run, one column per recorded measurement and condition "
                         "(values Gemini read off the bench, values said aloud, sensor summaries), each with provenance and evidence IDs.", {}),
    _decl("get_run_timeline", "The ordered commits (events) of one run with evidence IDs and seconds from start.",
          {"run": {"type": "string", "description": "run label (e.g. 'Method B', 'Reference 4'), ordinal ('trial 4') or UUID"}}, ["run"]),
    _decl("query_readings", "Sensor readings for one run from the 1-second continuous aggregate.",
          {"run": {"type": "string"}, "sensor": {"type": "string", "description": "e.g. lab_a, light, air_quality, mix_angle, temp_c, hue"},
           "t_start_s": {"type": "number"}, "t_end_s": {"type": "number"}}, ["run", "sensor"]),
    _decl("search_events", "Hybrid semantic + keyword search over all commits.",
          {"query": {"type": "string"}, "run": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]),
    _decl("diff_runs", "Deterministic diff of a candidate run against a control, judged against reference-run variation. "
                       "Omit control to use the experiment's control run.",
          {"candidate": {"type": "string"}, "control": {"type": "string"}}, ["candidate"]),
    _decl("make_chart", "Render a chart in the UI. kind: results_by_run (the result metric per run), "
                        "variable_by_run (any protocol variable per run; needs variable_key), "
                        "sensor_overlay (a sensor over time per run; needs sensor; align 'start' or 'flip'). "
                        "style 'paper' formats it for publication.",
          {"kind": {"type": "string", "enum": ["results_by_run", "variable_by_run", "sensor_overlay"]},
           "title": {"type": "string"}, "variable_key": {"type": "string"}, "sensor": {"type": "string"},
           "runs": {"type": "array", "items": {"type": "string"}}, "style": {"type": "string", "enum": ["screen", "paper"]},
           "align": {"type": "string", "enum": ["start", "flip"]}}, ["kind"]),
    _decl("get_evidence", "Resolve one evidence ID (evt:, frm:, ser:, rdg:, run:) to its record.",
          {"id": {"type": "string"}}, ["id"]),
]


def _system(experiment: dict, context: dict, runs_overview: dict) -> str:
    p = experiment["protocol"]
    variables = [{"key": v["key"], "label": v["label"], "type": v["type"], "role": v.get("role", "condition")} for v in p["variables"]]
    return f"""You are "Ask your lab" inside Litmus, a system that records every experimental run automatically as a hash-chained history of commits (events), sensor readings and video frames.

Experiment: {p['name']}. Result metric: {p['result']['label']} ({p['result'].get('unit', '')}).
Protocol steps: {json.dumps([s['title'] for s in p['steps']])}
Tracked variables: {json.dumps(variables)}
Runs (from list_runs): {json.dumps(runs_overview['runs'], default=str)}
The user is currently looking at: {json.dumps(context)}

Rules:
- Answer only from tool results. Call tools whenever you need data. Never invent or compute numbers yourself; quote numbers exactly as tools return them.
- Cite evidence after the sentence it supports, in square brackets, using exact IDs from tool results: [evt:...], [frm:...], [ser:...], [rdg:...], [run:...].
- No probabilities, confidence levels, or words like likely or probably. Say what was measured, what differed, and what was not measured.
- When asked to graph or plot, call make_chart (style "paper" if they mention a paper or publication), then give a one or two sentence caption.
- For questions about the data itself (tables, averages across runs, which run had the highest value), call get_dataset and quote its values; do not do arithmetic beyond what it returns.
- For "why was X different" questions, call diff_runs and explain the notable differences and the verdict on the assumed cause.
- For methods or report writing, use get_run_timeline and write what actually happened, in past tense, with citations.
- Be concise: short paragraphs or a few bullets. Refer to runs by label."""


def _content_from_messages(messages: list[dict]) -> list[types.Content]:
    out = []
    for m in messages[-12:]:
        role = "model" if m.get("role") in ("assistant", "model") else "user"
        out.append(types.Content(role=role, parts=[types.Part(text=m.get("text") or m.get("content") or "")]))
    return out


def finalize_answer(text: str, tb: Toolbox) -> dict:
    """Keep only citations that exist; flag probability language.

    Gemini often groups citations ("[evt:a, frm:b]"); each ID is checked on
    its own and the group is rewritten as one bracket per surviving ID.
    """
    valid, dropped = [], []
    def keep(m: re.Match) -> str:  # noqa: E306
        kept = []
        for eid in ID_TOKEN.findall(m.group(1)):
            if eid in tb.seen_ids or ev.exists(tb.conn, eid):
                kept.append(eid)
                if eid not in valid:
                    valid.append(eid)
            else:
                dropped.append(eid)
        return " ".join(f"[{e}]" for e in kept)
    clean = CITATION.sub(keep, text or "").strip()
    return {"text": clean, "citations": valid, "dropped_citations": dropped,
            "flags": ["probability_language"] if has_probability_language(clean) else []}


def ask(conn: psycopg.Connection, experiment: dict, messages: list[dict], context: dict | None = None) -> dict:
    context = context or {}
    question = (messages[-1].get("text") or messages[-1].get("content") or "") if messages else ""
    key = cache.key_for("chat", experiment["slug"], question.strip().lower(), context, [m.get("text") for m in messages[:-1]][-4:])
    found = store.find_analysis(conn, "chat", key)
    if found:
        return dict(found["content"], cached=True)

    tb = Toolbox(conn, experiment)
    if not settings.ai_enabled:
        content = fallback_answer(conn, experiment, question, context, tb)
    else:
        try:
            content = _ask_gemini(tb, experiment, messages, context)
        except Exception as exc:  # noqa: BLE001 - the demo must still answer
            log.warning("chat fell back to deterministic answer: %s", exc)
            content = fallback_answer(conn, experiment, question, context, Toolbox(conn, experiment))
    store.insert_analysis(conn, "chat", [], dict(content, question=question, context=context), cache_key=key, model=content["model"])
    return content


def _ask_gemini(tb: Toolbox, experiment: dict, messages: list[dict], context: dict) -> dict:
    overview = tb.list_runs()
    config = types.GenerateContentConfig(
        system_instruction=_system(experiment, context, overview),
        tools=[types.Tool(function_declarations=DECLARATIONS)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.2,
    )
    contents = _content_from_messages(messages)
    registry = tb.registry()
    text = ""
    for _ in range(MAX_TOOL_ROUNDS):
        resp = generate(settings.model_pro, contents, config)
        calls = resp.function_calls or []
        if not calls:
            text = resp.text or ""
            break
        contents.append(resp.candidates[0].content)
        parts = []
        for call in calls:
            args = dict(call.args or {})
            try:
                result = registry[call.name](**args) if call.name in registry else {"error": "unknown tool"}
            except Exception as exc:  # noqa: BLE001 - tool errors go back to the model
                result = {"error": f"{type(exc).__name__}: {exc}"}
            tb.calls.append({"name": call.name, "args": args})
            parts.append(types.Part.from_function_response(name=call.name, response=json.loads(json.dumps(result, default=str))))
        contents.append(types.Content(role="user", parts=parts))
    answer = finalize_answer(text, tb)
    return {**answer, "charts": tb.charts, "analyses": tb.analyses, "tool_calls": tb.calls, "model": settings.model_pro}


def fallback_answer(conn: psycopg.Connection, experiment: dict, question: str, context: dict, tb: Toolbox) -> dict:
    """Deterministic answers for the core questions when Gemini is unavailable."""
    q = question.lower()
    lines: list[str] = []
    if any(w in q for w in ("graph", "plot", "chart")):
        style = "paper" if any(w in q for w in ("paper", "publication", "journal")) else "screen"
        tb.make_chart("results_by_run", style=style)
        lines.append(f"{experiment['protocol']['result']['label']} for every completed run, with the reference-run band shaded.")
    elif any(w in q for w in ("methods section", "write the method", "procedure", "as it actually happened")):
        target = context.get("run_label") or context.get("run_id")
        runs = store.list_runs(conn, experiment["id"])
        r = resolve_run(conn, experiment["id"], target) if target else (runs[-1] if runs else None)
        if r:
            tl = tb.get_run_timeline(str(r["id"]))
            for e in tl["events"]:
                if e["kind"] in ("step_confirmed", "quantity_added", "reagent_used", "measurement", "mix", "flip_detected", "reading_reported"):
                    lines.append(f"- {e['summary']}. [{e['id']}]")
    else:
        m = re.search(r"(method\s+\w|reference\s+\d+|trial\s+\d+|run\s+\w+)", q)
        target = m.group(1) if m else context.get("run_id")
        if target is None:
            cands = [r for r in store.list_runs(conn, experiment["id"]) if r["role"] == "candidate"]
            target = str(cands[-1]["id"]) if cands else None
        if target:
            d = tb.diff_runs(target)
            if "error" not in d:
                if d["result"]["explanation"]:
                    lines.append(d["result"]["explanation"] + " " + " ".join(f"[{i}]" for i in d["result"]["evidence_ids"][:2]))
                for n in d["notable"]:
                    if n["role"] != "outcome":
                        lines.append(f"- {n['explanation']} " + " ".join(f"[{i}]" for i in n["evidence_ids"][:2]))
                a = d["assumed_cause"]
                if a.get("text"):
                    lines.append(f"Assumed cause: {a['reason']}")
                if d["missing_evidence"]:
                    lines.append("Not measured: " + ", ".join(d["missing_evidence"]) + ".")
    if not lines:
        lines.append("I can graph results across runs, explain why a run differed, list what changed in a trial, or write the methods as performed.")
    answer = finalize_answer("\n".join(lines), tb)
    return {**answer, "charts": tb.charts, "analyses": tb.analyses, "tool_calls": tb.calls, "model": "deterministic-fallback"}
