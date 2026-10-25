"""Read a digital thermometer placed in the bench camera's view.

Gemini Flash-Lite reads the display (perception); code converts units and
stores the value as an inferred reading, with the frame it came from.
"""

from __future__ import annotations

from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field

from ..config import settings
from .client import generate_json


class Display(BaseModel):
    visible: bool = Field(description="true only if a thermometer display is clearly readable")
    value: float | None = Field(default=None, description="the number shown on the display")
    unit: Literal["C", "F", "unknown"] = "unknown"


def read(image: bytes) -> float | None:
    """Temperature in degrees C, or None if no readable thermometer is in view."""
    out = generate_json(settings.model_flash_lite,
                        [types.Part.from_bytes(data=image, mime_type="image/jpeg"),
                         "Is there a digital thermometer display in this lab bench photo? If clearly readable, give the number "
                         "and unit exactly as shown. Do not guess."],
                        Display, temperature=0.0, retries=0)
    if not out.visible or out.value is None:
        return None
    c = (out.value - 32) * 5 / 9 if out.unit == "F" or (out.unit == "unknown" and out.value > 60) else out.value
    return round(c, 2) if -30 <= c <= 150 else None
