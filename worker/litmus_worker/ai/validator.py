"""Validator for every AI-written claim or sentence. Pure code, no model.

Rules:
  1. A claim must cite at least one evidence ID that exists in its catalog.
  2. Labels are exactly: observed, possible_explanation, contradicted, missing_evidence.
  3. "contradicted" needs a specific measurement among its evidence; if there
     is none, the claim is relabeled "missing_evidence".
  4. No probabilities or likelihood language anywhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .catalog import Catalog

LABELS = ("observed", "possible_explanation", "contradicted", "missing_evidence")

PROBABILITY = re.compile(
    r"\d+(?:\.\d+)?\s*%\s*(?:chance|likel|probab|confiden|certain|sure)"
    r"|\bprobabilit|\bprobabl[ey]\b|\blikelihood\b|\b(?:most |more |less |un)?likely\b|\bodds\b"
    r"|\bp\s*[<=>]\s*0?\.\d|\bconfidence (?:level|interval|score)",
    re.IGNORECASE,
)


@dataclass
class Checked:
    accepted: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    relabeled: int = 0


def has_probability_language(text: str) -> bool:
    return bool(PROBABILITY.search(text or ""))


def resolve_ids(tokens: list[str], cat: Catalog) -> list[str]:
    out: list[str] = []
    for t in tokens or []:
        eid = cat.resolve(str(t))
        if eid and eid not in out:
            out.append(eid)
    return out


def check_claims(claims: list[dict], cat: Catalog) -> Checked:
    result = Checked()
    for c in claims:
        text = (c.get("text") or "").strip()
        ids = resolve_ids(c.get("evidence") or c.get("evidence_ids") or [], cat)
        label = c.get("label")
        if not text:
            continue
        if not ids:
            result.rejected.append({"text": text, "label": label, "reason": "cites no existing evidence"})
            continue
        if label not in LABELS:
            result.rejected.append({"text": text, "label": label, "reason": f"unknown label {label!r}"})
            continue
        if has_probability_language(text):
            result.rejected.append({"text": text, "label": label, "reason": "uses probability or likelihood language"})
            continue
        note = None
        if label == "contradicted":
            measured = [i for i in ids if not i.startswith("run:") and cat.meta.get(i, {}).get("measured")]
            if not measured:
                label = "missing_evidence"
                note = "relabeled: no specific measurement argues against this claim"
                result.relabeled += 1
        out = {"text": text, "label": label, "evidence_ids": ids}
        for k in ("variable_key", "suggested_check"):
            if c.get(k):
                out[k] = c[k]
        if note:
            out["validator_note"] = note
        result.accepted.append(out)
    return result


def check_sentences(sentences: list[dict], cat: Catalog) -> tuple[list[dict], int]:
    """Report sentences: unsupported ones are kept as flagged gaps, never as fact."""
    out, gaps = [], 0
    for s in sentences:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        if has_probability_language(text):
            out.append({"text": text, "evidence_ids": [], "gap": True, "reason": "probability language removed from the record"})
            gaps += 1
            continue
        ids = resolve_ids(s.get("evidence") or [], cat)
        if not ids:
            out.append({"text": text, "evidence_ids": [], "gap": True, "reason": "no supporting evidence in the record"})
            gaps += 1
            continue
        out.append({"text": text, "evidence_ids": ids})
    return out, gaps
