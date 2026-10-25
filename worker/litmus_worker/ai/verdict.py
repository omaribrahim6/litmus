"""Verdict: the researcher's assumed cause against the evidence.

Gemini only sees the deterministic diff. It writes the explanation; code
decides the assumed-cause label, validates every claim and fills any gaps
with template claims so the verdict never depends on the model being up.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from .. import diff as diff_engine
from ..config import settings
from . import catalog as catalog_mod
from .client import AIUnavailable, generate_json
from .validator import check_claims, has_probability_language

log = logging.getLogger("litmus.verdict")

LABEL_WORDS = {
    "contradicted": "not supported",
    "possible_explanation": "possible, but not isolated",
    "missing_evidence": "cannot be checked (not measured)",
    "observed": "observed",
}


class CauseMap(BaseModel):
    variable_keys: list[str] = Field(description="protocol variable keys the researcher's stated cause refers to; empty if none")


class ClaimOut(BaseModel):
    text: str
    label: Literal["observed", "possible_explanation", "contradicted", "missing_evidence"]
    evidence: list[str] = Field(description="evidence aliases like E3")
    variable_key: str | None = None
    suggested_check: str | None = None


class OutcomeOut(BaseModel):
    condition: str
    means: Literal["supported", "explained_by_confound", "unresolved"]
    text: str


class VerdictOut(BaseModel):
    headline: str
    assumed_cause_statement: str
    assumed_cause_evidence: list[str]
    claims: list[ClaimOut]
    follow_up_check: str
    follow_up_outcomes: list[OutcomeOut]


SYSTEM = """You write verdicts for Litmus, a lab record system that checks whether a promising experimental result is real.
You receive a deterministic diff between a candidate run and its control, computed by code from sensor readings, camera measurements and logged events, judged against reference-run variation.

Rules you must follow:
1. Use only facts in the diff. Never compute or estimate a new number; you may only repeat numbers that appear in the diff.
2. Every claim cites evidence aliases (E1, E2, ...) from the evidence catalog that directly support it.
3. Labels: "observed" = a measured difference or sameness; "possible_explanation" = a recorded difference that could explain the result; "contradicted" = a specific measurement argues against the claim; "missing_evidence" = the measurement needed does not exist.
4. No probabilities, confidence levels, or words like likely, probably, odds, chance.
5. The assumed-cause label is decided by code and given to you. Write one sentence consistent with that label, naming the measurement that decides it.
6. Outcome variables (role "outcome", e.g. time to flip, number of additions) are consequences of the result, never causes.
7. Short, plain sentences a scientist would write in a lab notebook. Name the variable and both values.
8. Include one claim per notable condition difference, one for the result, and one per missing_evidence variable."""


def map_cause(text: str, protocol: dict) -> list[str] | None:
    """Map free-text cause onto protocol variables with Gemini Flash (perception of language, not math)."""
    if not text or not settings.ai_enabled:
        return None
    options = [{"key": v["key"], "label": v["label"]} for v in protocol["variables"] if v.get("role") != "outcome"]
    prompt = (f"Researcher's stated cause: {text!r}\n\nProtocol variables:\n{json.dumps(options)}\n\n"
              "Return the keys of the variables this stated cause is about. Only use keys from the list.")
    try:
        out = generate_json(settings.model_flash, [prompt], CauseMap, temperature=0.0)
    except (AIUnavailable, RuntimeError) as exc:
        log.info("cause mapping fell back to aliases: %s", exc)
        return None
    valid = {o["key"] for o in options}
    return [k for k in out.variable_keys if k in valid]


def _alias(ids: list[str], cat: catalog_mod.Catalog) -> list[str]:
    return [cat.by_id[i] for i in ids if i in cat.by_id]


def _prompt_payload(d: dict, cat: catalog_mod.Catalog, protocol: dict) -> dict:
    a = d["assumed_cause"]
    return {
        "experiment": protocol["name"],
        "result_metric": protocol["result"]["label"],
        "candidate": d["candidate"]["label"],
        "control": ", ".join(c["label"] for c in d["controls"]),
        "reference_runs": len(d["references"]),
        "result": {
            "explanation": d["result"].get("explanation"),
            "headline": d["result"].get("headline"),
            "outside_normal_variation": d["result"].get("result_is_outside_normal_variation"),
            "evidence": _alias(d["result"]["candidate"]["evidence_ids"][:4] + d["result"]["control"]["evidence_ids"][:4], cat),
        },
        "assumed_cause": {
            "researcher_text": a.get("text"),
            "maps_to_variables": a.get("variable_keys"),
            "label_decided_by_code": a.get("label"),
            "reason": a.get("reason"),
            "evidence": _alias(a.get("evidence_ids", []), cat),
        },
        "differences": [
            {
                "key": i["key"], "label": i["label"], "role": i.get("role"), "status": i["status"],
                "candidate": i["candidate"]["display"], "control": i["control"]["display"],
                "candidate_provenance": i["candidate"].get("provenance"),
                "explanation": i["explanation"],
                "evidence": _alias(i["candidate"]["evidence_ids"][:4] + i["control"]["evidence_ids"][:4], cat),
            }
            for i in d["differences"]
        ],
        "follow_up_template": d["follow_up"],
        "evidence_catalog": cat.listing(),
    }


def template_claims(d: dict) -> list[dict]:
    """Deterministic claims straight from the diff; also the fallback when Gemini is down."""
    claims: list[dict] = []
    cand, ctrl = d["candidate"], d["controls"][0] if d["controls"] else None
    run_ids = [f"run:{cand['run_id']}"] + ([f"run:{ctrl['run_id']}"] if ctrl else [])
    r = d["result"]
    if r["status"] != "missing_evidence":
        claims.append({"text": r["explanation"], "label": "observed", "variable_key": r["key"],
                       "evidence_ids": r["candidate"]["evidence_ids"][:4] + r["control"]["evidence_ids"][:4]})
    for i in d["differences"]:
        ev = i["candidate"]["evidence_ids"][:4] + i["control"]["evidence_ids"][:4]
        if i["status"] == "notable" and i.get("role") != "outcome":
            claims.append({"text": i["explanation"], "label": "observed", "variable_key": i["key"], "evidence_ids": ev})
            claims.append({"text": f"{i['label']} differed between the runs and could explain the difference in result.",
                           "label": "possible_explanation", "variable_key": i["key"], "evidence_ids": ev,
                           "suggested_check": d["follow_up"]["check"] if d["follow_up"].get("variable_key") == i["key"] else None})
        elif i["status"] == "missing_evidence":
            claims.append({"text": f"{i['label']} was not measured, so it cannot be ruled out as a factor.",
                           "label": "missing_evidence", "variable_key": i["key"], "evidence_ids": run_ids})
    return claims


def station_summary(d: dict) -> str:
    """One glanceable line for the station screen and spoken verdict."""
    parts = []
    a = d["assumed_cause"]
    if a.get("text"):
        names = [i["label"].lower() for i in d["differences"] if i["key"] in a.get("variable_keys", [])]
        subject = names[0].split(" (")[0] if names else "stated cause"
        parts.append(f"Assumed cause ({subject}): {LABEL_WORDS.get(a['label'], a['label'])}.")
    notable = [i for i in d["differences"] if i["status"] == "notable" and i.get("role") != "outcome"
               and i["key"] not in a.get("variable_keys", [])]
    if notable:
        parts.append("Notable difference: " + ", ".join(i["label"].lower() for i in notable[:2]) + ".")
    temp = next((i for i in d["differences"] if i["key"] == "temp_c"), None)
    if temp:
        parts.append({"within_normal": "Temperature: within normal variation.", "same": "Temperature: same.",
                      "notable": "Temperature: outside normal variation.",
                      "missing_evidence": "Temperature: not measured."}[temp["status"]])
    return " ".join(parts)


def build(diff_content: dict, protocol: dict, use_ai: bool = True) -> dict:
    d = diff_content
    model = "deterministic-template"
    if use_ai and d["assumed_cause"].get("text"):
        keys = map_cause(d["assumed_cause"]["text"], protocol)
        if keys is not None and set(keys) != set(d["assumed_cause"].get("variable_keys", [])):
            d = diff_engine.reassess(d, keys, protocol)

    cat = catalog_mod.from_diff(d)
    a = d["assumed_cause"]
    template = template_claims(d)
    statement = a.get("reason") if a.get("text") else None
    headline = station_summary(d)
    follow_up = d["follow_up"]
    claims = template
    rejected: list[dict] = []
    relabeled = 0

    if use_ai and settings.ai_enabled:
        try:
            out = generate_json(settings.model_pro, [json.dumps(_prompt_payload(d, cat, protocol), ensure_ascii=False)],
                                VerdictOut, system=SYSTEM, temperature=0.2)
            checked = check_claims([c.model_dump() for c in out.claims], cat)
            rejected, relabeled = checked.rejected, checked.relabeled
            claims = checked.accepted
            covered = {c.get("variable_key") for c in claims}
            for t in template:  # guarantee coverage of every notable and missing variable
                if t.get("variable_key") not in covered:
                    claims.append(t)
                    covered.add(t.get("variable_key"))
            if out.assumed_cause_statement and not has_probability_language(out.assumed_cause_statement):
                statement = out.assumed_cause_statement
            if out.headline and not has_probability_language(out.headline):
                headline = out.headline
            outcomes = [o for o in out.follow_up_outcomes if not has_probability_language(o.text)]
            if out.follow_up_check and outcomes:
                follow_up = {"check": out.follow_up_check, "variable_key": d["follow_up"].get("variable_key"),
                             "outcomes": [{"if": o.condition, "means": o.means, "text": o.text} for o in outcomes]}
            model = settings.model_pro
        except (AIUnavailable, RuntimeError) as exc:
            log.info("verdict used template: %s", exc)

    # Template claims carry real IDs already; make sure every claim still validates.
    final = check_claims([dict(c, evidence=c.get("evidence_ids")) for c in claims], cat)
    return {
        "candidate": d["candidate"],
        "controls": d["controls"],
        "headline": headline,
        "station_summary": station_summary(d),
        "result": d["result"],
        "assumed_cause": {
            "text": a.get("text"),
            "label": a.get("label"),
            "label_text": LABEL_WORDS.get(a.get("label"), a.get("label")),
            "statement": statement,
            "variable_keys": a.get("variable_keys", []),
            "evidence_ids": a.get("evidence_ids", []),
            "confounds": a.get("confounds", []),
        },
        "claims": final.accepted,
        "rejected_claims": rejected + final.rejected,
        "follow_up": follow_up,
        "notable": d["notable"],
        "missing_evidence": d["missing_evidence"],
        "model": model,
        "validator": {"accepted": len(final.accepted), "rejected": len(rejected) + len(final.rejected),
                      "relabeled": relabeled + final.relabeled},
        "diff": d,
    }
