"""On-the-fly experiment setup: no lab-specific configuration.

The researcher says what they are doing ("titrating vinegar with phenol red",
"iodine clock, method B"), or says nothing. Gemini Flash looks at what was
said and at a frame from the bench camera and proposes the experiment: steps,
what result to watch for, which containers or reagents matter, where the
vessel is, and the colors it expects before and after the change.

Code then builds the protocol: it validates every field, maps the expected
colors to a measurable color channel and threshold (CIE Lab, computed here,
not by the model), turns the vessel box into the measurement region, and adds
the variables Litmus always tracks. If the description matches an experiment
already on record, that experiment is reused so runs stay comparable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Literal

from google.genai import types
from litmus_core.color import rgb_to_lab
from pydantic import BaseModel, Field

from ..config import settings
from .client import generate_json

log = logging.getLogger("litmus.setup")


class StepOut(BaseModel):
    title: str = Field(description="short imperative step, e.g. 'Add 3 drops of indicator'")
    detail: str | None = None
    quantity_name: str | None = Field(default=None, description="snake_case name if this step adds a measured amount, e.g. 'base_ml'")
    quantity_unit: str | None = None
    quantity_step: float | None = Field(default=None, description="typical amount per addition, if repeated")
    expected_amount: float | None = Field(default=None, description="fixed amount for a one-off addition, if stated")
    repeat: bool = Field(default=False, description="true if this step is repeated until the change happens (e.g. titrating)")
    watch_for_change: bool = Field(default=False, description="true for the step during which the visible change is expected")


class ChoiceOut(BaseModel):
    key: str = Field(description="short value, e.g. 'tap' or 'Bottle A'")
    looks_like: str = Field(description="how to recognize it in the camera, e.g. 'jug labeled TAP'")


class ReagentOut(BaseModel):
    key: str = Field(description="snake_case variable name, e.g. 'water_source'")
    label: str
    during_step: int = Field(description="index of the step where it is used")
    question: str = Field(description="what to ask about a camera frame, e.g. 'Which water container is being poured?'")
    choices: list[ChoiceOut]
    expected: str | None = Field(default=None, description="the choice the protocol calls for, if any")


class SetupOut(BaseModel):
    use_existing: str | None = Field(default=None, description="slug of an existing experiment if this is clearly the same experiment")
    name: str = Field(description="short experiment name, e.g. 'Vinegar titration with phenol red'")
    description: str
    result: Literal["amount_until_change", "time_until_change", "none"] = Field(
        description="what the outcome of a run is: total amount added until the visible change, time until the change, or nothing measurable")
    result_label: str | None = Field(default=None, description="e.g. 'Base added at color change' or 'Time to color change'")
    result_unit: str | None = None
    result_quantity: str | None = Field(default=None, description="for amount_until_change: the quantity_name being added")
    change_description: str | None = Field(default=None, description="the visible change, e.g. 'yellow to pink'")
    color_before_hex: str | None = Field(default=None, description="expected liquid color before the change, as #rrggbb")
    color_after_hex: str | None = Field(default=None, description="expected liquid color after the change, as #rrggbb")
    vessel_box: list[int] | None = Field(default=None, description="[ymin, xmin, ymax, xmax] of the liquid in the main vessel, 0-1000, if visible")
    thermometer_visible: bool = False
    steps: list[StepOut]
    reagents: list[ReagentOut] = Field(default_factory=list)


PROMPT = """You are setting up an automatic lab recorder at a bench. Nothing is configured in advance.
From what the researcher said (may be empty) and the bench camera frame (may be missing), propose the experiment.

- If what they described clearly matches one of the existing experiments, set use_existing to its slug and still fill the other fields.
- Steps: the protocol as it will actually be done, in order, short and imperative. Mark the step that is repeated until a change (if any) and the step during which the visible change is expected.
- Result: if they add something until a visible change (titration), result=amount_until_change with the quantity being added; if they wait for a change (clock reactions), result=time_until_change; otherwise none.
- Expected colors before and after the change, as hex, from chemistry knowledge (e.g. phenol red: yellow #e8c33a to pink-red #d6336c).
- Reagents: only containers or materials whose identity matters and that the camera could tell apart (e.g. which water jug, which bottle). Give recognizable choices.
- vessel_box: where the liquid being watched is in the frame.
If nothing was said and the frame is unclear, propose a generic 'Bench observation' with one step 'Observe the sample' and result=none.
Existing experiments: {existing}
What the researcher said: {said}"""


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "experiment"
    return f"{s}-{hashlib.sha1(name.encode()).hexdigest()[:4]}"


def _snake(s: str, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:32]
    return s or fallback


def _hex_rgb(h: str | None) -> tuple[float, float, float] | None:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (h or "").strip())
    if not m:
        return None
    v = m.group(1)
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def flip_rule(before_hex: str | None, after_hex: str | None) -> dict | None:
    """Pick the Lab channel that separates the expected colors most, and a threshold at 40% of the gap."""
    a, b = _hex_rgb(before_hex), _hex_rgb(after_hex)
    if not a or not b:
        return None
    la, lb = rgb_to_lab(*a), rgb_to_lab(*b)
    gaps = {"lab_l": lb[0] - la[0], "lab_a": lb[1] - la[1], "lab_b": lb[2] - la[2]}
    metric = max(gaps, key=lambda k: abs(gaps[k]))
    gap = gaps[metric]
    if abs(gap) < 8:
        return None
    return {"metric": metric, "direction": "rise" if gap > 0 else "fall",
            "delta": round(min(25.0, max(6.0, abs(gap) * 0.4)), 1), "hold_s": 2, "baseline_s": 3, "smooth": 5}


def roi_from_box(box: list[int] | None) -> dict:
    default = {"x": 0.4, "y": 0.35, "w": 0.2, "h": 0.3}
    if not box or len(box) != 4:
        return default
    y0, x0, y1, x1 = [max(0, min(1000, v)) / 1000 for v in box]
    if y1 - y0 < 0.03 or x1 - x0 < 0.03:
        return default
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * 0.5, (y1 - y0) * 0.5
    return {"x": round(cx - w / 2, 4), "y": round(cy - h / 2, 4), "w": round(w, 4), "h": round(h, 4)}


def build_protocol(out: SetupOut) -> dict:
    """Validated protocol from Gemini's proposal. Unknown or unsafe fields are dropped, never trusted."""
    steps, used = [], set()
    for i, s in enumerate(out.steps[:12] or [StepOut(title="Observe the sample")]):
        sid = _snake(s.title, f"step_{i + 1}")
        while sid in used:
            sid += "_2"
        used.add(sid)
        step = {"id": sid, "title": s.title.strip()[:80], "detail": (s.detail or "").strip()[:160] or None}
        if s.quantity_name:
            q = {"name": _snake(s.quantity_name, f"amount_{i + 1}"), "unit": (s.quantity_unit or "")[:12]}
            if s.repeat and s.quantity_step:
                q["step"] = float(s.quantity_step)
            if not s.repeat and s.expected_amount is not None:
                q["expected"] = float(s.expected_amount)
            step["quantity"] = q
        if s.repeat:
            step["repeat"] = True
        if s.watch_for_change:
            step["arm_flip"] = True
        steps.append(step)
    if not any(st.get("arm_flip") for st in steps):
        target = next((st for st in steps if st.get("repeat")), steps[-1])
        target["arm_flip"] = True

    quantities = {st["quantity"]["name"]: st for st in steps if st.get("quantity")}
    flip = flip_rule(out.color_before_hex, out.color_after_hex)
    result_kind = out.result if flip or out.result == "none" else "none"
    rq = _snake(out.result_quantity or "", "")
    if result_kind == "amount_until_change" and rq not in quantities:
        rq = next((n for n, st in quantities.items() if st.get("repeat")), None) or next(iter(quantities), None)
        if rq is None:
            result_kind = "time_until_change"
    result = {"kind": result_kind, "key": "result", "label": (out.result_label or "Result").strip()[:60],
              "unit": (out.result_unit or "").strip()[:12] or None, "decimals": 1}
    if result_kind == "amount_until_change":
        result.update(key=f"{rq}_at_change", quantity=rq, unit=quantities[rq]["quantity"]["unit"] or result["unit"])
    elif result_kind == "time_until_change":
        result.update(key="time_to_change_s", unit="s", label=out.result_label or "Time to color change")

    variables = []
    for r in out.reagents[:5]:
        key = _snake(r.key, "reagent")
        choices = {c.key.strip()[:24]: c.looks_like.strip()[:80] for c in r.choices[:6] if c.key.strip()}
        if len(choices) < 2:
            continue
        step_idx = min(max(r.during_step, 0), len(steps) - 1)
        variables.append({"key": key, "label": r.label.strip()[:40], "type": "categorical",
                          "source": {"event": "reagent_used", "variable": key},
                          "expected": r.expected if r.expected in choices else None,
                          "detect": {"step": steps[step_idx]["id"], "question": r.question.strip()[:160], "choices": choices},
                          "aliases": [key.replace("_", " ")] + [k.lower() for k in choices]})
    for name, st in quantities.items():
        if st.get("repeat"):
            continue
        variables.append({"key": name, "label": st["title"][:40], "type": "numeric", "unit": st["quantity"]["unit"],
                          "source": {"quantity": name, "agg": "sum"}, "resolution": 0.0,
                          "aliases": [name.replace("_", " ")]})
    # Always tracked, whatever the experiment.
    variables += [
        {"key": "mix_active_s", "label": "Mixing time", "type": "numeric", "unit": "s", "source": {"mix": "active_s"},
         "resolution": 1, "aliases": ["stir", "mix", "shak", "swirl", "agitat"]},
        {"key": "temp_c", "label": "Temperature", "type": "numeric", "unit": "°C", "source": {"sensor": "temp_c", "agg": "mean"},
         "resolution": 0.3, "aliases": ["temp", "heat", "warm", "cold", "hot"]},
        {"key": "start_color", "label": "Starting color", "type": "numeric", "unit": flip["metric"].replace("lab_", "") + "*" if flip else "a*",
         "source": {"sensor": flip["metric"] if flip else "lab_a", "agg": "first"}, "resolution": 2, "aliases": ["color", "colour"]},
        {"key": "step_order", "label": "Steps performed", "type": "sequence", "source": {"steps": True}, "aliases": ["skip", "order", "step"]},
    ]
    if result_kind != "none":
        variables.append({"key": "time_to_flip_s", "label": "Time to change", "type": "numeric", "unit": "s",
                          "source": {"derived": "time_to_flip"}, "role": "outcome"})
    protocol = {
        "slug": _slug(out.name), "name": out.name.strip()[:80], "description": out.description.strip()[:400],
        "generated": True, "change": out.change_description, "result": result, "roi": roi_from_box(out.vessel_box),
        "steps": steps, "variables": variables, "mix": {"source": "camera"},
    }
    if flip:
        protocol["flip"] = flip
        protocol["light_flip"] = None
    return protocol


def propose(said: str | None, image: bytes | None, existing: list[dict]) -> tuple[SetupOut, dict]:
    catalog = json.dumps([{"slug": e["slug"], "name": e["name"], "description": e.get("protocol", {}).get("description", "")[:160]}
                          for e in existing if e["slug"] != "auto"])
    contents: list = [PROMPT.format(existing=catalog, said=json.dumps(said or ""))]
    if image:
        contents.insert(0, types.Part.from_bytes(data=image, mime_type="image/jpeg"))
    out = generate_json(settings.model_flash, contents, SetupOut, temperature=0.1)
    return out, build_protocol(out)
