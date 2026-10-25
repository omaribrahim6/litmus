"""Deterministic measurement of protocol variables and results for one run.

Every value returned here comes from sensor readings, camera metrics or
committed events, and carries the evidence IDs it was computed from.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime

from litmus_core.signals import MixConfig, summarize_mixing

from . import evidence as ev
from .rundata import RunData

PROVENANCE_RANK = {"measured": 0, "reported": 1, "inferred": 2}


def weakest(provs) -> str:
    provs = [p for p in provs if p]
    return max(provs, key=lambda p: PROVENANCE_RANK[p]) if provs else "measured"


@dataclass
class Measure:
    available: bool
    value: float | str | list | None = None
    unit: str | None = None
    provenance: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    note: str | None = None

    def display(self, decimals: int = 1) -> str:
        if not self.available:
            return "not measured"
        if isinstance(self.value, float):
            text = f"{self.value:.{decimals}f}"
        elif isinstance(self.value, list):
            text = " → ".join(str(v) for v in self.value)
        else:
            text = str(self.value)
        return f"{text} {self.unit}".strip() if self.unit and not isinstance(self.value, list) else text

    def to_dict(self, decimals: int = 1) -> dict:
        return {
            "available": self.available,
            "value": self.value,
            "display": self.display(decimals),
            "unit": self.unit,
            "provenance": self.provenance,
            "evidence_ids": self.evidence_ids,
            "note": self.note,
        }


def _event_ids(events: list[dict], limit: int = 16) -> list[str]:
    out = []
    for e in events[:limit]:
        out.append(ev.evt(e["id"]))
    return out


def _frame_ids(events: list[dict], limit: int = 4) -> list[str]:
    out = []
    for e in events:
        for f in e.get("frame_ids") or []:
            out.append(ev.frm(f))
            if len(out) >= limit:
                return out
    return out


def quantity_events(rd: RunData, name: str, until: datetime | None = None) -> list[dict]:
    out = []
    for e in rd.events_of("quantity_added"):
        p = e.get("payload") or {}
        if p.get("quantity") != name:
            continue
        if until is not None and e["t"] > until:
            continue
        out.append(e)
    return out


def measure_result(rd: RunData, protocol: dict) -> Measure:
    """Result = total of the result quantity added up to the camera-detected flip."""
    spec = protocol["result"]
    flip = rd.flip_event()
    if flip is None:
        return Measure(False, unit=spec.get("unit"), note="no color flip was detected in this run")
    adds = quantity_events(rd, spec["quantity"], until=flip["t"])
    if not adds:
        return Measure(False, unit=spec.get("unit"), note=f"no {spec['quantity']} additions were recorded")
    total = round(sum(float((e["payload"] or {}).get("value", 0)) for e in adds), 6)
    return Measure(
        True,
        total,
        spec.get("unit"),
        weakest([e["provenance"] for e in adds] + [flip["provenance"]]),
        [ev.evt(flip["id"])] + _frame_ids([flip], 2) + _event_ids(adds, 12),
    )


def _series_measure(rd: RunData, sensor: str, agg: str, unit: str | None) -> Measure:
    series = rd.readings.get(sensor)
    if not series:
        return Measure(False, unit=unit, note=f"no {sensor} sensor data (sensor not connected or not recorded)")
    t0, t1 = series[0][0], series[-1][0]
    values = [v for _, v, _ in series]
    if agg == "mean":
        value = statistics.fmean(values)
    elif agg == "max":
        value = max(values)
    elif agg == "min":
        value = min(values)
    elif agg == "last":
        value = values[-1]
    elif agg == "first":
        window = [v for t, v, _ in series if t <= t0 + 3.0]
        value = statistics.fmean(window)
        t1 = min(t1, t0 + 3.0)
    else:
        raise ValueError(f"unknown agg {agg}")
    return Measure(
        True,
        round(float(value), 6),
        unit or rd.units.get(sensor),
        weakest({p for _, _, p in series}),
        [ev.ser(rd.id, sensor, t0, t1)],
    )


def measure_variable(rd: RunData, var: dict, protocol: dict) -> Measure:
    src = var["source"]
    unit = var.get("unit")

    if "event" in src:
        hits = [e for e in rd.events_of(src["event"]) if (e.get("payload") or {}).get("variable") == src["variable"]]
        if not hits:
            return Measure(False, unit=unit, note="not recorded in this run")
        values = [str((e["payload"] or {}).get("value")) for e in hits]
        note = None
        if len(set(values)) > 1:
            note = f"multiple values recorded: {', '.join(sorted(set(values)))}"
        last = hits[-1]
        return Measure(True, values[-1], None, weakest(e["provenance"] for e in hits),
                       _event_ids(hits, 4) + _frame_ids(hits, 4), note)

    if "quantity" in src:
        hits = quantity_events(rd, src["quantity"])
        if not hits:
            return Measure(False, unit=unit, note="no quantity of this kind was recorded")
        if src.get("agg") == "count":
            value = float(len(hits))
        else:
            value = round(sum(float((e["payload"] or {}).get("value", 0)) for e in hits), 6)
        return Measure(True, value, unit, weakest(e["provenance"] for e in hits), _event_ids(hits, 12))

    if "sensor" in src:
        return _series_measure(rd, src["sensor"], src.get("agg", "mean"), unit)

    if "mix" in src:
        # src["mix"]: inversions | active_s, optionally normalized per base addition.
        what = src["mix"]
        per_addition = bool(src.get("per_addition"))
        adds = quantity_events(rd, protocol["result"]["quantity"]) if per_addition else []
        if per_addition and not adds:
            return Measure(False, unit=unit, note="no additions to normalize mixing by")
        mix_cfg = protocol.get("mix", {})
        sensor = mix_cfg.get("sensor", "mix_angle")
        series = rd.readings.get(sensor)
        if series:
            summary = summarize_mixing([(t, v) for t, v, _ in series], MixConfig.from_dict(mix_cfg))
            total = float(summary.inversions) if what == "inversions" else float(summary.active_s)
            ids = [ev.ser(rd.id, sensor, series[0][0], series[-1][0])]
            prov = weakest({p for _, _, p in series})
        else:
            # Without the rotary sensor, fall back to mixing events (camera-inferred or reported).
            mixes = rd.events_of("mix")
            field_name = "inversions" if what == "inversions" else "duration_s"
            vals = [float((e["payload"] or {}).get(field_name)) for e in mixes if (e["payload"] or {}).get(field_name) is not None]
            if not vals:
                return Measure(False, unit=unit, note="mixing was not measured (no rotary sensor data or mixing events)")
            total = sum(vals)
            ids = _event_ids(mixes, 12) + _frame_ids(mixes, 2)
            prov = weakest(e["provenance"] for e in mixes)
        if per_addition:
            total /= len(adds)
            ids = ids + _event_ids(adds, 4)
        return Measure(True, round(total, 6), unit, prov, ids)

    if src.get("derived") == "time_to_flip":
        flip = rd.flip_event()
        adds = quantity_events(rd, protocol["result"]["quantity"])
        if not flip or not adds:
            return Measure(False, unit=unit, note="needs both a first base addition and a detected flip")
        value = (flip["t"] - adds[0]["t"]).total_seconds()
        return Measure(True, round(value, 3), unit, weakest([flip["provenance"], adds[0]["provenance"]]),
                       [ev.evt(adds[0]["id"]), ev.evt(flip["id"])])

    if src.get("steps"):
        steps = rd.events_of("step_confirmed")
        if not steps:
            return Measure(False, note="no protocol steps were confirmed")
        order = [str((e["payload"] or {}).get("step")) for e in steps]
        deduped = [s for i, s in enumerate(order) if i == 0 or s != order[i - 1]]
        return Measure(True, deduped, None, weakest(e["provenance"] for e in steps), _event_ids(steps, 12))

    raise ValueError(f"unsupported variable source {src}")
