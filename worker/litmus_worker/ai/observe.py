"""Hands-free recording: Gemini watches recent keyframes and says what it sees.

Every ~12 s the station asks the worker to look at the frames uploaded since
the last look. Gemini Flash (low thinking) describes the scene, labels what
the researcher is doing in each frame, reports the current protocol step, and
reads every value it can actually see: an instrument display, a scale, a
graduation, a ruler, a count, or a qualitative state (color, clarity, a
precipitate, a broken part). Each reading becomes an inferred commit with the
frame it was read from as evidence. Values it cannot read are never guessed.
Code only turns the per-frame labels into durations using the frames' own
timestamps.
"""

from __future__ import annotations

import json
from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field

from ..config import settings
from .client import generate_json

Activity = Literal["mixing", "pouring", "adding", "measuring", "handling", "idle", "nobody", "unclear"]


class Seen(BaseModel):
    frame: int = Field(description="index of the frame (0-based) where this is visible")
    kind: Literal["step", "reagent", "observation"]
    step_id: str | None = Field(default=None, description="for kind=step: the protocol step id that started")
    variable: str | None = Field(default=None, description="for kind=reagent: the reagent variable key")
    value: str | None = Field(default=None, description="for kind=reagent: the choice key")
    summary: str = Field(description="short past-tense description, e.g. 'Poured water from the jug labeled TAP'")


class Reading(BaseModel):
    frame: int = Field(description="index of the frame (0-based) it was read from")
    key: str = Field(description="a measurement key from the list, or a new snake_case key (with unit, e.g. 'mass_g') for something else worth recording")
    label: str | None = Field(default=None, description="for a new key: a short human label")
    value: str = Field(description="exactly what is shown: digits as displayed for numbers, a short word or phrase for qualities")
    unit: str | None = Field(default=None, description="unit as shown or as defined for the measurement")
    read_from: str = Field(description="what it was read from, e.g. 'scale display', 'cylinder graduation', 'counted in frame'")


class Observation(BaseModel):
    scene: str = Field(description="one short sentence: what is in front of the camera right now")
    activity: list[Activity] = Field(description="one label per frame, in order: what the researcher is doing in that frame")
    current_step: str | None = Field(description="protocol step id the researcher is on now, or null if unclear")
    readings: list[Reading] = Field(default_factory=list)
    seen: list[Seen] = Field(default_factory=list)


def look(images: list[bytes], protocol: dict, current_step: str | None, recent: list[str]) -> Observation:
    steps = [{"id": s["id"], "title": s["title"]} for s in protocol["steps"]]
    reagents = [{"variable": v["key"], "label": v["label"], "choices": (v.get("detect") or {}).get("choices", {})}
                for v in protocol["variables"] if v.get("type") == "categorical" and v.get("detect")]
    wanted = [{"key": m["key"], "label": m["label"], "unit": m["unit"], "type": m["type"], "look_for": m.get("look_for")}
              for m in protocol.get("measurements", []) if m.get("read_from") != "speech"]
    prompt = f"""These are {len(images)} consecutive frames (oldest first, a few seconds apart) from a lab bench camera during "{protocol['name']}".
Protocol steps: {json.dumps(steps)}
Measurements to record when visible: {json.dumps(wanted)}
Reagents to identify: {json.dumps(reagents)}
The researcher was last on step: {json.dumps(current_step)}
Already recorded recently (do not repeat unless the value changed): {json.dumps(recent[-10:])}
1. scene: what is in front of the camera now (equipment, materials, instrument displays, people, hands).
2. activity: exactly one label per frame. mixing = swirling, stirring, shaking or inverting; pouring = transferring liquid or material;
   adding = dropping or dispensing a reagent; measuring = reading or using an instrument; handling = hands on equipment otherwise;
   idle = equipment untouched; nobody = no person or hands.
3. readings: every value you can actually read in a frame: displays, scales, meters, timers, graduations, rulers, labels, things you
   can count, and qualities you can see (color, clarity, a precipitate, bubbles, damage). Use the measurement keys above; for anything
   else clearly relevant, add a new key. Read numbers exactly as displayed. If a value is not legible, leave it out. Never estimate.
4. current_step, and in seen only new things: a step starting, which reagent or container is used, anything unexpected.
If nothing new happened, return empty readings and seen lists."""
    parts: list = [types.Part.from_bytes(data=img, mime_type="image/jpeg") for img in images]
    return generate_json(settings.model_flash, [*parts, prompt], Observation, temperature=0.0, retries=1, thinking="LOW")
