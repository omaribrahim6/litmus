"""Lab report with receipts: every sentence carries evidence IDs or is flagged as a gap."""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from .. import evidence as ev
from ..config import settings
from ..rundata import RunData
from . import catalog as catalog_mod
from .client import AIUnavailable, generate_json
from .validator import check_sentences

log = logging.getLogger("litmus.report")

SECTIONS = [("aim", "Aim"), ("method", "Method as performed"), ("results", "Results"),
            ("deviations", "Notable deviations"), ("limitations", "Limitations")]


class SentenceOut(BaseModel):
    text: str
    evidence: list[str] = Field(description="evidence aliases like E3 that support this sentence")


class SectionOut(BaseModel):
    id: Literal["aim", "method", "results", "deviations", "limitations"]
    sentences: list[SentenceOut]


class ReportOut(BaseModel):
    title: str
    sections: list[SectionOut]


SYSTEM = """You write lab reports for Litmus from an automatically recorded, hash-chained lab history.
Write the report as the experiment actually happened, not as the protocol says it should have.

Rules:
1. Every sentence cites evidence aliases (E1, E2, ...) from the catalog that support it. A sentence you cannot support must not be written.
2. Never compute or estimate numbers. Only repeat numbers that appear in the commits, results or verdict.
3. No probabilities, confidence levels, or words like likely, probably.
4. Past tense, plain scientific English, short sentences.
5. Sections: aim (1-2 sentences), method (what was actually done, in order, for each run), results, deviations (differences from protocol or between runs, including the verdict), limitations (unmeasured variables, low-confidence camera inferences)."""


def _event_line(e: dict, t0) -> dict:
    return {"t_s": round((e["t"] - t0).total_seconds(), 1), "kind": e["kind"], "summary": e["summary"],
            "provenance": e["provenance"]}


def _add_run(cat: catalog_mod.Catalog, rd: RunData, limit: int = 60) -> list[dict]:
    t0 = rd.run.get("started_at") or rd.events[0]["t"]
    lines = []
    for e in rd.events:
        if e["kind"] in ("run_sealed",):
            continue
        line = _event_line(e, t0)
        line["evidence"] = [cat.add(ev.evt(e["id"]), f"commit: {e['summary']}", measured=e["provenance"] != "inferred")]
        for fid in (e.get("frame_ids") or [])[:1]:
            line["evidence"].append(cat.add(ev.frm(fid), f"video frame at: {e['summary']}", measured=True))
        lines.append(line)
    return lines[:limit]


def template_report(verdict: dict, protocol: dict, runs: list[RunData]) -> dict:
    """Deterministic report used when Gemini is unavailable."""
    cand = verdict["candidate"]
    sections: dict[str, list[dict]] = {k: [] for k, _ in SECTIONS}
    cand_run = f"run:{cand['run_id']}"
    sections["aim"].append({"text": f"Test whether {cand['label']} changes the {protocol['result']['label'].lower()} "
                                    f"relative to {', '.join(c['label'] for c in verdict['controls'])}.",
                            "evidence_ids": [cand_run]})
    for rd in runs:
        steps = [e for e in rd.events if e["kind"] in ("step_confirmed", "reagent_used", "quantity_added")][:8]
        for e in steps:
            sections["method"].append({"text": f"{rd.label}: {e['summary']}.", "evidence_ids": [ev.evt(e["id"])]})
    r = verdict["result"]
    if r.get("explanation"):
        sections["results"].append({"text": r["explanation"],
                                    "evidence_ids": r["candidate"]["evidence_ids"][:3] + r["control"]["evidence_ids"][:3]})
    for c in verdict["claims"]:
        if c["label"] in ("observed", "possible_explanation", "contradicted") and c.get("variable_key") != r.get("key"):
            sections["deviations"].append({"text": c["text"], "evidence_ids": c["evidence_ids"]})
        elif c["label"] == "missing_evidence":
            sections["limitations"].append({"text": c["text"], "evidence_ids": c["evidence_ids"]})
    if verdict["assumed_cause"].get("statement"):
        sections["deviations"].insert(0, {"text": verdict["assumed_cause"]["statement"],
                                          "evidence_ids": verdict["assumed_cause"]["evidence_ids"]})
    return {"title": f"{protocol['name']}: {cand['label']} vs control",
            "sections": [{"id": k, "heading": h, "sentences": sections[k]} for k, h in SECTIONS]}


def build(verdict: dict, protocol: dict, runs: list[RunData], use_ai: bool = True) -> dict:
    cat = catalog_mod.from_diff(verdict["diff"])
    for c in verdict["claims"]:
        for eid in c["evidence_ids"]:
            cat.add(eid, f"verdict claim: {c['text'][:80]}", measured=c["label"] != "missing_evidence")
    timelines = {rd.label: _add_run(cat, rd) for rd in runs}
    model = "deterministic-template"
    report = template_report(verdict, protocol, runs)
    gaps = 0
    if use_ai and settings.ai_enabled:
        payload = {
            "experiment": protocol["name"],
            "protocol_steps": [{"id": s["id"], "title": s["title"], "detail": s.get("detail")} for s in protocol["steps"]],
            "result_metric": protocol["result"]["label"],
            "runs": timelines,
            "verdict": {
                "headline": verdict["headline"],
                "assumed_cause": {k: verdict["assumed_cause"][k] for k in ("text", "label", "statement")},
                "claims": [{"text": c["text"], "label": c["label"], "evidence": [cat.by_id[i] for i in c["evidence_ids"] if i in cat.by_id]}
                           for c in verdict["claims"]],
                "follow_up": verdict["follow_up"],
            },
            "evidence_catalog": cat.listing(),
        }
        try:
            out = generate_json(settings.model_pro, [json.dumps(payload, ensure_ascii=False, default=str)],
                                ReportOut, system=SYSTEM, temperature=0.3)
            sections = []
            for sid, heading in SECTIONS:
                sec = next((s for s in out.sections if s.id == sid), None)
                sentences, g = check_sentences([s.model_dump() for s in sec.sentences] if sec else [], cat)
                gaps += g
                sections.append({"id": sid, "heading": heading, "sentences": sentences})
            report = {"title": out.title, "sections": sections}
            model = settings.model_pro
        except (AIUnavailable, RuntimeError) as exc:
            log.info("report used template: %s", exc)
    total = sum(len(s["sentences"]) for s in report["sections"])
    report.update(model=model, candidate=verdict["candidate"], controls=verdict["controls"],
                  stats={"sentences": total, "gaps": gaps, "traceable": total - gaps})
    return report


def to_markdown(report: dict) -> str:
    """Markdown export with numbered receipts after each sentence."""
    lines = [f"# {report['title']}", ""]
    receipts: list[str] = []
    for sec in report["sections"]:
        if not sec["sentences"]:
            continue
        lines += [f"## {sec['heading']}", ""]
        para = []
        for s in sec["sentences"]:
            if s.get("gap"):
                para.append(f"*[unsupported: {s['text']}]*")
                continue
            refs = []
            for eid in s["evidence_ids"]:
                if eid not in receipts:
                    receipts.append(eid)
                refs.append(str(receipts.index(eid) + 1))
            para.append(f"{s['text']} [{', '.join(refs)}]")
        lines += [" ".join(para), ""]
    lines += ["## Receipts", ""]
    lines += [f"{n}. `{eid}`" for n, eid in enumerate(receipts, 1)]
    lines += ["", f"_Generated by Litmus ({report.get('model')}). Every bracketed number resolves to a commit, frame or sensor series in the hash-chained record._"]
    return "\n".join(lines)
