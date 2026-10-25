"""Researcher narration: anything said about the experiment becomes a commit.

Gemini Flash-Lite (falling back to Flash) transcribes the clip from the
clearest mic and keeps only statements about the experiment. Small talk is
dropped and its audio is deleted, so private conversation never enters the
record. Values the researcher says aloud ("the mass is 2.31 grams", "it
turned cloudy") become measurement commits, and mentions of a tracked
reagent become reagent commits.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field

from ..config import settings
from .client import AIUnavailable, generate_json

log = logging.getLogger("litmus.narration")


class Statement(BaseModel):
    t_offset_s: float = Field(description="seconds from the start of the clip when this statement begins")
    text: str = Field(description="what was said, lightly cleaned (no filler words), in the speaker's words")
    lab_relevant: bool = Field(description="true only if it is about the experiment, procedure, materials, measurements or observations")
    kind: Literal["narration", "observation", "measurement", "reagent", "quantity", "hypothesis", "deviation", "other"]
    variable: str | None = Field(default=None, description="for kind=reagent: the protocol variable key it identifies")
    value: str | None = Field(default=None, description="for kind=reagent: which choice, using the choice key")
    quantity_name: str | None = Field(default=None, description="for kind=quantity: the protocol quantity name being added")
    amount: float | None = Field(default=None, description="for kind=quantity: the amount they said they added")
    unit: str | None = None
    key: str | None = Field(default=None, description="for kind=measurement: a measurement key from the list, or a new snake_case key with unit")
    label: str | None = Field(default=None, description="for kind=measurement with a new key: a short human label")
    reading: str | None = Field(default=None, description="for kind=measurement: the value exactly as said (digits for numbers, a word for qualities)")


class Narration(BaseModel):
    statements: list[Statement]
    clarity: float = Field(description="0-1, how clearly the audio could be understood")


def _prompt(protocol: dict) -> str:
    reagents = {v["key"]: list((v.get("detect") or {}).get("choices", {}).keys())
                for v in protocol["variables"] if v["type"] == "categorical"}
    quantities = {s["quantity"]["name"]: s["quantity"].get("unit") for s in protocol["steps"] if s.get("quantity")}
    wanted = {m["key"]: {"label": m["label"], "unit": m["unit"], "type": m["type"]} for m in protocol.get("measurements", [])}
    return f"""Audio from a lab bench during the experiment "{protocol['name']}". Researchers may narrate what they are doing.
Transcribe each statement with its start time in the clip.
Mark lab_relevant=true only for statements about the experiment: steps, materials, quantities, observations, problems, expectations.
Small talk, personal conversation and anything unrelated must be lab_relevant=false.
Use kind=reagent when they say which container or bottle they are using; variables and choices: {json.dumps(reagents)}.
Use kind=quantity when they say how much they added (e.g. "adding half a mL"), with quantity_name from {json.dumps(quantities)} and the amount in that unit.
Use kind=measurement when they state a value or result (a reading, a count, a length, a color, "it turned cloudy"), with key from
{json.dumps(wanted)} or a new snake_case key for anything else they measured, and the reading exactly as said.
Use kind=hypothesis for what they expect or suspect, kind=deviation for anything done differently from the protocol.
Do not invent statements. If nothing intelligible was said, return an empty list."""


def understand(path: Path, protocol: dict) -> tuple[Narration, str]:
    part = types.Part.from_bytes(data=path.read_bytes(), mime_type="audio/wav")
    last: Exception | None = None
    for model in (settings.model_flash_lite, settings.model_flash):
        try:
            return generate_json(model, [part, _prompt(protocol)], Narration, temperature=0.0, retries=1, thinking="LOW"), model
        except AIUnavailable:
            raise
        except RuntimeError as exc:
            last = exc
            log.info("narration with %s failed: %s", model, exc)
    raise RuntimeError(f"narration failed: {last}")
