"""Thin wrapper over google-genai: structured JSON output, files, embeddings."""

from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from ..config import settings

log = logging.getLogger("litmus.ai")
T = TypeVar("T", bound=BaseModel)

_client: genai.Client | None = None


class AIUnavailable(RuntimeError):
    pass


def client() -> genai.Client:
    global _client
    if not settings.ai_enabled:
        raise AIUnavailable("GEMINI_API_KEY is not configured")
    if _client is None:
        _client = genai.Client(vertexai=True) if settings.use_vertex else genai.Client(api_key=settings.gemini_api_key)
    return _client


def generate_json(model: str, contents: list, schema: type[T], system: str | None = None,
                  temperature: float = 0.2, retries: int = 2) -> T:
    """Generate content constrained to a Pydantic schema and parse it."""
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json",
        response_schema=schema,
    )
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = client().models.generate_content(model=model, contents=contents, config=config)
            if resp.parsed is not None:
                return resp.parsed if isinstance(resp.parsed, schema) else schema.model_validate(resp.parsed)
            return schema.model_validate(json.loads(resp.text))
        except AIUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - retried, then surfaced
            last = exc
            log.warning("gemini %s attempt %d failed: %s", model, attempt + 1, exc)
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Gemini call failed: {last}")


def upload_file(path: Path, mime_type: str, timeout_s: float = 300) -> types.File:
    """Upload through the Files API and wait until it is ready for use."""
    f = client().files.upload(file=str(path), config=types.UploadFileConfig(mime_type=mime_type))
    deadline = time.time() + timeout_s
    while f.state and f.state.name == "PROCESSING":
        if time.time() > deadline:
            raise TimeoutError("Gemini file processing timed out")
        time.sleep(2)
        f = client().files.get(name=f.name)
    if f.state and f.state.name == "FAILED":
        raise RuntimeError("Gemini could not process the file")
    return f


def embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT", dims: int = 768) -> list[list[float]]:
    """Gemini embeddings, truncated to `dims` and L2-normalized for cosine search."""
    resp = client().models.embed_content(
        model=settings.model_embed,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=dims),
    )
    out = []
    for e in resp.embeddings:
        v = list(e.values)[:dims]
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


def list_models() -> list[str]:
    return [m.name for m in client().models.list()]
