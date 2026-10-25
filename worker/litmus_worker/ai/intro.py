"""Spoken session intro: "I'm Dr. X, this is lab Y, and we're starting Z."

Gemini Flash listens to the clip and extracts who, where and what. The run is
titled from it, and the intro is committed with the transcript as evidence.
The parse is labeled inferred until the researcher confirms it on the kiosk.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field

from ..config import settings
from .client import generate_json

log = logging.getLogger("litmus.intro")

MIME = {".wav": "audio/wav", ".mp3": "audio/mp3", ".webm": "audio/webm", ".ogg": "audio/ogg", ".m4a": "audio/mp4", ".flac": "audio/flac"}


class Intro(BaseModel):
    transcript: str = Field(description="verbatim transcript of what was said")
    researcher: str | None = Field(default=None, description="the speaker's name and title as said, e.g. 'Dr. Lina Chen'")
    lab: str | None = Field(default=None, description="lab or group name as said")
    experiment: str | None = Field(default=None, description="what they are about to do, short, e.g. 'vinegar titration'")
    run_label: str | None = Field(default=None, description="short label for this run, e.g. 'Method B' or 'Reference 3', only if said")
    role: Literal["reference", "control", "candidate", "rerun", "unknown"] = Field(
        default="unknown", description="reference/control/candidate/rerun if the speaker made it clear, otherwise unknown")
    hypothesis: str | None = Field(default=None, description="any stated expectation or suspected cause, in their words")
    title: str = Field(description="a short title for this session, at most 8 words, built only from what was said")
    clarity: float = Field(description="0-1, how clearly the audio could be understood")


PROMPT = """This is the start of a recorded lab session. The researcher introduces themselves at a bench station.
Transcribe it and extract who is speaking, the lab, what they are starting, and any run label, role or hypothesis they state.
Only use what was actually said. Leave a field null if it was not said. Do not invent names."""


def understand(path: Path, experiment_name: str) -> Intro:
    data = path.read_bytes()
    mime = MIME.get(path.suffix.lower(), "audio/wav")
    return generate_json(settings.model_flash,
                         [types.Part.from_bytes(data=data, mime_type=mime), f"{PROMPT}\nStation protocol: {experiment_name}."],
                         Intro, temperature=0.0)
