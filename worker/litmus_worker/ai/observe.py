"""Hands-free step tracking: Gemini watches recent keyframes and says where the researcher is.

No buttons: every ~12 s the station asks the worker to look at the frames
uploaded since the last look. Gemini Flash (low thinking) reports the
current protocol step and anything it saw happen: a step starting, which
container or reagent was used, an addition, or something unexpected. Each
becomes an inferred commit with the frame it was seen in as evidence.
"""

from __future__ import annotations

import json
from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field

from ..config import settings
from .client import generate_json


class Seen(BaseModel):
    frame: int = Field(description="index of the frame (0-based) where this is visible")
    kind: Literal["step", "reagent", "addition", "observation"]
    step_id: str | None = Field(default=None, description="for kind=step: the protocol step id that started")
    variable: str | None = Field(default=None, description="for kind=reagent: the reagent variable key")
    value: str | None = Field(default=None, description="for kind=reagent: the choice key")
    summary: str = Field(description="short past-tense description, e.g. 'Poured water from the jug labeled TAP'")


class Observation(BaseModel):
    current_step: str | None = Field(description="protocol step id the researcher is on now, or null if unclear")
    seen: list[Seen] = Field(default_factory=list)


def look(images: list[bytes], protocol: dict, current_step: str | None, recent: list[str]) -> Observation:
    steps = [{"id": s["id"], "title": s["title"], "detail": s.get("detail")} for s in protocol["steps"]]
    reagents = [{"variable": v["key"], "label": v["label"], "choices": (v.get("detect") or {}).get("choices", {})}
                for v in protocol["variables"] if v.get("type") == "categorical"]
    prompt = f"""These are consecutive frames (oldest first, a few seconds apart) from a lab bench camera during "{protocol['name']}".
Protocol steps: {json.dumps(steps)}
Reagents to identify: {json.dumps(reagents)}
The researcher was last on step: {json.dumps(current_step)}
Already recorded recently (do not repeat): {json.dumps(recent[-8:])}
Report the step the researcher is on now, and only new things clearly visible in these frames: a new step starting,
which container or reagent is being used, an addition being made, or anything unexpected. Do not guess amounts.
If nothing new happened, return an empty list."""
    parts: list = [types.Part.from_bytes(data=img, mime_type="image/jpeg") for img in images]
    return generate_json(settings.model_flash, [*parts, prompt], Observation, temperature=0.0, retries=1, thinking="LOW")
