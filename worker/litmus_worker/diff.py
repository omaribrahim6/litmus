"""Diff engine: compare a candidate run against control run(s) across every
variable the protocol tracks, judged against reference-run variation.

Entirely deterministic. The verdict model only ever sees this output.
"""

from __future__ import annotations

import math
import re
import statistics
from typing import Iterable

from . import evidence as ev
from .measure import Measure, measure_result, measure_variable
from .rundata import RunData

# Diff item statuses
NOTABLE = "notable"            # outside normal variation, or a categorical/step change
WITHIN = "within_normal"       # differs by no more than reference runs differ from each other
SAME = "same"                  # identical value
MISSING = "missing_evidence"   # not measured on one or both sides


def _fmt(x: float | None, decimals: int = 2) -> str | None:
    if x is None:
        return None
    s = f"{x:.{decimals}f}"
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return "0" if s == "-0" else s


def variation_band(values: list[float], resolution: float) -> tuple[float, str]:
    """How far two runs of the same protocol normally differ.

    With 3+ references: 2 SD of the difference between two runs, which is
    sqrt(2) times the single-run SD (the candidate and the control each vary).
    With 2 references: their range. Otherwise: the measurement resolution.
    """
    if len(values) >= 3:
        band, method = 2 * math.sqrt(2) * statistics.stdev(values), "2sd"
    elif len(values) == 2:
        band, method = abs(values[0] - values[1]), "range"
    else:
        band, method = 0.0, "resolution"
    if band < resolution:
        return resolution, "resolution"
    return band, method


def _numeric_compare(key, label, unit, cand: Measure, ctrls: list[Measure], refs: list[tuple[RunData, Measure]],
                     resolution: float, decimals: int) -> dict:
    ctrl_vals = [float(m.value) for m in ctrls if m.available]
    ref_vals = [(rd, float(m.value), m) for rd, m in refs if m.available]
    out = {
        "key": key, "label": label, "type": "numeric", "unit": unit,
        "candidate": cand.to_dict(decimals),
        "control": _merge_controls(ctrls, decimals, unit),
        "reference": {
            "n": len(ref_vals),
            "values": [{"run_id": str(rd.id), "label": rd.label, "value": v, "evidence_ids": m.evidence_ids} for rd, v, m in ref_vals],
        },
    }
    if not cand.available or not ctrl_vals:
        missing_side = "candidate and control" if not cand.available and not ctrl_vals else ("candidate" if not cand.available else "control")
        out.update(status=MISSING, missing_side=missing_side,
                   explanation=f"{label} was not measured for the {missing_side}" + (f" ({cand.note})" if cand.note and not cand.available else "") + ".")
        return out

    c = float(cand.value)
    k = statistics.fmean(ctrl_vals)
    delta = c - k
    values = [v for _, v, _ in ref_vals]
    band, method = variation_band(values, resolution)
    if values:
        out["reference"].update(mean=statistics.fmean(values), sd=statistics.stdev(values) if len(values) > 1 else 0.0,
                                min=min(values), max=max(values))
    ratio = abs(delta) / band if band > 0 else (0.0 if delta == 0 else None)
    if delta == 0:
        status = SAME
    elif band > 0 and abs(delta) > band:
        status = NOTABLE
    elif band == 0:
        status = NOTABLE
    else:
        status = WITHIN

    dec = decimals
    band_text = {
        "2sd": f"±{_fmt(band, dec)} (how far two runs normally differ, from {len(values)} reference runs)",
        "range": f"±{_fmt(band, dec)} (range of 2 reference runs)",
        "resolution": f"±{_fmt(band, dec)} (measurement resolution; fewer than 2 reference runs)" if len(values) < 2 else f"±{_fmt(band, dec)} (measurement resolution)",
    }[method]
    u = f" {unit}" if unit else ""
    if status == NOTABLE:
        expl = f"{label}: {_fmt(c, dec)}{u} vs {_fmt(k, dec)}{u} in the control, a difference of {_fmt(delta, dec)}{u}. Normal variation is {band_text}, so this is outside normal variation."
    elif status == SAME:
        expl = f"{label}: identical ({_fmt(c, dec)}{u}) in candidate and control."
    else:
        expl = f"{label}: {_fmt(c, dec)}{u} vs {_fmt(k, dec)}{u}, a difference of {_fmt(delta, dec)}{u}, within normal variation {band_text}."
    out.update(status=status, delta=delta, band=band, band_method=method,
               ratio=None if ratio is None else round(ratio, 3), explanation=expl)
    return out


def _merge_controls(ctrls: list[Measure], decimals: int, unit: str | None) -> dict:
    avail = [m for m in ctrls if m.available]
    if not avail:
        return {"available": False, "value": None, "display": "not measured", "unit": unit,
                "provenance": None, "evidence_ids": [], "note": ctrls[0].note if ctrls else None}
    if len(avail) == 1:
        return avail[0].to_dict(decimals)
    ids: list[str] = []
    for m in avail:
        ids.extend(m.evidence_ids[:4])
    if all(isinstance(m.value, (int, float)) for m in avail):
        mean = statistics.fmean(float(m.value) for m in avail)
        merged = Measure(True, mean, unit, max((m.provenance for m in avail), key=lambda p: ["measured", "reported", "inferred"].index(p)), ids,
                         note=f"mean of {len(avail)} control runs")
        return merged.to_dict(decimals)
    values = sorted({str(m.value) for m in avail})
    return Measure(True, " / ".join(values), None, avail[0].provenance, ids,
                   note=f"{len(avail)} control runs").to_dict(decimals)


def _categorical_compare(key, label, expected, cand: Measure, ctrls: list[Measure], refs: list[tuple[RunData, Measure]]) -> dict:
    ctrl_vals = sorted({str(m.value) for m in ctrls if m.available})
    ref_vals = [(rd, m) for rd, m in refs if m.available]
    out = {
        "key": key, "label": label, "type": "categorical", "unit": None,
        "candidate": cand.to_dict(), "control": _merge_controls(ctrls, 1, None),
        "reference": {
            "n": len(ref_vals),
            "values": [{"run_id": str(rd.id), "label": rd.label, "value": m.value, "evidence_ids": m.evidence_ids} for rd, m in ref_vals],
            "counts": _counts(str(m.value) for _, m in ref_vals),
        },
        "expected": expected,
    }
    if not cand.available or not ctrl_vals:
        side = "candidate and control" if not cand.available and not ctrl_vals else ("candidate" if not cand.available else "control")
        out.update(status=MISSING, missing_side=side, explanation=f"{label} was not recorded for the {side}.")
        return out
    c = str(cand.value)
    seen = out["reference"]["counts"].get(c, 0)
    if c in ctrl_vals and len(ctrl_vals) == 1:
        out.update(status=SAME, explanation=f"{label}: {c} in both runs.")
    elif c in ctrl_vals:
        out.update(status=WITHIN, explanation=f"{label}: {c}; control runs used {', '.join(ctrl_vals)}.")
    else:
        ref_note = (f" It appears in {seen} of {len(ref_vals)} reference runs." if ref_vals else "")
        if ref_vals and seen == 0:
            ref_note = f" None of the {len(ref_vals)} reference runs used {c}."
        exp_note = f" The protocol specifies {expected}." if expected and c != expected else ""
        out.update(status=NOTABLE,
                   explanation=f"{label}: {c} in the candidate vs {', '.join(ctrl_vals)} in the control.{ref_note}{exp_note}")
    return out


def _counts(values: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def _sequence_compare(key, label, protocol, cand: Measure, ctrls: list[Measure]) -> dict:
    out = {"key": key, "label": label, "type": "sequence", "unit": None,
           "candidate": cand.to_dict(), "control": ctrls[0].to_dict() if ctrls else Measure(False).to_dict()}
    ctrl = next((m for m in ctrls if m.available), None)
    if not cand.available or ctrl is None:
        out.update(status=MISSING, explanation=f"{label}: steps were not confirmed on one or both runs.")
        return out
    expected = [s["id"] for s in protocol.get("steps", [])]
    cs, ks = list(cand.value), list(ctrl.value)
    skipped = [s for s in expected if s in ks and s not in cs]
    extra = [s for s in cs if s not in ks]
    reordered = [s for s in cs if s in ks] != [s for s in ks if s in cs]
    if not skipped and not extra and not reordered:
        out.update(status=SAME, explanation=f"{label}: same steps in the same order.")
        return out
    parts = []
    if skipped:
        parts.append(f"skipped {', '.join(skipped)}")
    if extra:
        parts.append(f"added {', '.join(extra)}")
    if reordered:
        parts.append("performed steps in a different order")
    out.update(status=NOTABLE, skipped=skipped, extra=extra, reordered=reordered,
               explanation=f"{label}: the candidate {'; '.join(parts)} compared with the control.")
    return out


def map_assumed_cause(text: str | None, protocol: dict) -> list[str]:
    """Keyword fallback for mapping the researcher's stated cause onto variables.

    The verdict step can override this with a model-based mapping; outcome
    variables (time to flip, number of additions) are never treated as causes.
    """
    if not text:
        return []
    t = text.lower()
    keys = []
    for var in protocol.get("variables", []):
        if var.get("role") == "outcome":
            continue
        for alias in var.get("aliases", []):
            if re.search(r"\b" + re.escape(alias.lower()), t):
                keys.append(var["key"])
                break
    return keys


def assess_assumed_cause(text: str | None, keys: list[str], items: dict[str, dict]) -> dict:
    """Label the researcher's assumed cause from the diff alone (no model)."""
    if not text:
        return {"text": None, "variable_keys": [], "label": None, "evidence_ids": [], "reason": "No assumed cause was stated."}
    mapped = [items[k] for k in keys if k in items]
    # Outcomes (time to flip, number of additions) are consequences of the result, never confounds.
    others = [i for i in items.values()
              if i["status"] == NOTABLE and i["key"] not in keys and i.get("role") != "outcome"]
    if not mapped:
        return {"text": text, "variable_keys": [], "label": "missing_evidence", "evidence_ids": [],
                "reason": "The stated cause does not match any variable this protocol records, so it cannot be checked.",
                "confounds": [o["key"] for o in others]}
    measured = [m for m in mapped if m["status"] != MISSING]
    evidence_ids: list[str] = []
    for m in measured:
        for eid in m["candidate"]["evidence_ids"][:3] + m["control"]["evidence_ids"][:3]:
            if eid not in evidence_ids:
                evidence_ids.append(eid)
    if not measured:
        return {"text": text, "variable_keys": keys, "label": "missing_evidence", "evidence_ids": [],
                "reason": f"{', '.join(m['label'] for m in mapped)} was not measured, so the stated cause cannot be checked.",
                "confounds": [o["key"] for o in others]}
    notable = [m for m in measured if m["status"] == NOTABLE]
    if notable:
        reason = " ".join(m["explanation"] for m in notable)
        if others:
            reason += f" Other notable differences ({', '.join(o['label'] for o in others)}) could also explain the result."
        return {"text": text, "variable_keys": keys, "label": "possible_explanation", "evidence_ids": evidence_ids,
                "reason": reason, "confounds": [o["key"] for o in others]}
    reason = " ".join(m["explanation"] for m in measured)
    return {"text": text, "variable_keys": keys, "label": "contradicted", "evidence_ids": evidence_ids,
            "reason": f"Not supported by the evidence. {reason}", "confounds": [o["key"] for o in others]}


def _result_compare(protocol: dict, cand: RunData, ctrls: list[RunData], refs: list[RunData]) -> dict:
    spec = protocol["result"]
    dec = spec.get("decimals", 1)
    cm = measure_result(cand, protocol)
    km = [measure_result(r, protocol) for r in ctrls]
    rm = [(r, measure_result(r, protocol)) for r in refs]
    if spec.get("type") == "text":
        # A qualitative outcome (e.g. "precipitate formed"): compared by value, never turned into a number.
        item = _categorical_compare(spec["key"], spec["label"], None, cm, km, rm)
        if item["status"] == NOTABLE:
            item["headline"] = f"{cand.label}: {spec['label'].lower()} was {cm.value}, not {item['control']['display']}"
        item["result_is_outside_normal_variation"] = item["status"] == NOTABLE
        return item
    item = _numeric_compare(spec["key"], spec["label"], spec.get("unit"), cm, km, rm, spec.get("resolution", 0.0), dec)
    if item["status"] != MISSING:
        k = statistics.fmean(float(m.value) for m in km if m.available)
        if k:
            pct = (float(cm.value) - k) / k * 100
            item["percent_change"] = round(pct, 1)
            other = ctrls[0].label if len(ctrls) == 1 else "the controls"
            if spec.get("kind") == "time_until_change":
                item["headline"] = f"{cand.label} changed {abs(pct):.0f}% {'faster' if pct < 0 else 'slower'} than {other}"
            elif spec.get("kind", "amount_until_change") == "amount_until_change" and spec.get("noun", "base") == "base" and spec.get("quantity") == "base_ml":
                item["headline"] = f"{cand.label} used {abs(pct):.0f}% {'less' if pct < 0 else 'more'} base than {other}"
            else:
                item["headline"] = f"{cand.label}: {spec['label'].lower()} {abs(pct):.0f}% {'lower' if pct < 0 else 'higher'} than {other}"
        item["result_is_outside_normal_variation"] = item["status"] == NOTABLE
    return item


def _follow_up(protocol: dict, result: dict, assumed: dict, ranked: list[dict], cand_label: str) -> dict:
    confound = next((i for i in ranked if i["status"] == NOTABLE and i.get("role") != "outcome"
                     and i["key"] not in assumed.get("variable_keys", [])), None)
    result_label = protocol["result"]["label"].lower()
    if confound is None:
        return {
            "check": f"Repeat {cand_label} with every recorded variable matched to the control.",
            "outcomes": [
                {"if": f"the {result_label} matches the control within normal variation", "means": "explained_by_confound", "text": "The original difference was run-to-run variation or an unrecorded factor."},
                {"if": f"the {result_label} again differs from the control", "means": "supported", "text": "The method difference is reproducible and worth following up."},
            ],
            "variable_key": None,
        }
    ctrl_value = confound["control"]["display"]
    cand_value = confound["candidate"]["display"]
    by_key = {i["key"]: i for i in ranked}
    mapped_labels = [by_key[k]["label"].lower() for k in assumed.get("variable_keys", []) if k in by_key]
    cause_name = (" or ".join(dict.fromkeys(mapped_labels)) if mapped_labels else "the stated cause")
    return {
        "check": f"Matched rerun: repeat {cand_label} exactly, but with {confound['label'].lower()} set to {ctrl_value} (as in the control). Optional swap run: repeat the control with {confound['label'].lower()} set to {cand_value}.",
        "variable_key": confound["key"],
        "outcomes": [
            {"if": f"the {result_label} returns to the control level (within normal variation)", "means": "explained_by_confound",
             "text": f"The difference is explained by {confound['label'].lower()}, not by {cause_name}."},
            {"if": f"the {result_label} stays as far from the control as before", "means": "supported",
             "text": f"{confound['label']} is not the cause; the method difference is reproducible."},
            {"if": "the result lands in between", "means": "unresolved",
             "text": "Both may contribute. Run the swap run to separate them."},
        ],
    }


def diff(protocol: dict, candidate: RunData, controls: list[RunData], references: list[RunData],
         assumed_keys: list[str] | None = None) -> dict:
    refs = [r for r in references if r.id != candidate.id and r.id not in {c.id for c in controls}]
    items: dict[str, dict] = {}
    for var in protocol.get("variables", []):
        cm = measure_variable(candidate, var, protocol)
        km = [measure_variable(r, var, protocol) for r in controls]
        rm = [(r, measure_variable(r, var, protocol)) for r in refs]
        if var["type"] == "numeric":
            item = _numeric_compare(var["key"], var["label"], var.get("unit"), cm, km, rm,
                                    float(var.get("resolution", 0.0)), int(var.get("decimals", 1)))
        elif var["type"] == "categorical":
            item = _categorical_compare(var["key"], var["label"], var.get("expected"), cm, km, rm)
        else:
            item = _sequence_compare(var["key"], var["label"], protocol, cm, km)
        item["role"] = var.get("role", "condition")
        items[var["key"]] = item

    def rank_key(i: dict):
        order = {NOTABLE: 0, WITHIN: 1, SAME: 2, MISSING: 3}[i["status"]]
        exact = 0 if i["type"] in ("categorical", "sequence") else 1
        outcome = 1 if i.get("role") == "outcome" else 0
        return (order, outcome, exact, -(i.get("ratio") or 0))

    ranked = sorted(items.values(), key=rank_key)
    for n, i in enumerate(ranked, 1):
        i["rank"] = n

    result = _result_compare(protocol, candidate, controls, refs)
    keys = assumed_keys if assumed_keys is not None else map_assumed_cause(candidate.run.get("assumed_cause"), protocol)
    assumed = assess_assumed_cause(candidate.run.get("assumed_cause"), keys, items)
    if assumed["text"]:
        assumed["evidence_ids"] = [ev.run(candidate.id)] + assumed["evidence_ids"]

    return {
        "experiment": {"slug": protocol.get("slug"), "name": protocol.get("name")},
        "candidate": {"run_id": str(candidate.id), "label": candidate.label, "role": candidate.run.get("role")},
        "controls": [{"run_id": str(c.id), "label": c.label, "role": c.run.get("role")} for c in controls],
        "references": [{"run_id": str(r.id), "label": r.label} for r in refs],
        "result": result,
        "assumed_cause": assumed,
        "differences": ranked,
        "notable": [i["key"] for i in ranked if i["status"] == NOTABLE],
        "within_normal": [i["key"] for i in ranked if i["status"] in (WITHIN, SAME)],
        "missing_evidence": [i["key"] for i in ranked if i["status"] == MISSING],
        "follow_up": _follow_up(protocol, result, assumed, ranked, candidate.label),
    }


def reassess(content: dict, keys: list[str], protocol: dict, run_text: str | None = None) -> dict:
    """Recompute the assumed-cause label and follow-up for a different variable mapping.

    Used when the verdict step maps the researcher's free text onto variables
    with a model; the label itself is still decided here, from the diff only.
    """
    items = {i["key"]: i for i in content["differences"]}
    text = run_text if run_text is not None else content["assumed_cause"].get("text")
    assumed = assess_assumed_cause(text, [k for k in keys if k in items], items)
    if assumed["text"]:
        assumed["evidence_ids"] = [ev.run(content["candidate"]["run_id"])] + assumed["evidence_ids"]
    out = dict(content)
    out["assumed_cause"] = assumed
    out["follow_up"] = _follow_up(protocol, content["result"], assumed, content["differences"], content["candidate"]["label"])
    return out
