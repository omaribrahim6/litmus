"""Thin wrapper over google-genai: structured JSON output, files, embeddings."""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from ..config import ROOT, settings

log = logging.getLogger("litmus.ai")
T = TypeVar("T", bound=BaseModel)

_client: genai.Client | None = None


class AIUnavailable(RuntimeError):
    pass


def _vertex_client() -> genai.Client:
    """Vertex AI with a service-account key file; the project defaults to the key's own project."""
    creds_path = settings.gcp_credentials
    project = settings.gcp_project
    if creds_path:
        p = Path(creds_path)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            raise AIUnavailable(f"GOOGLE_APPLICATION_CREDENTIALS points to a missing file: {p}")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(p)
        if not project:
            project = json.loads(p.read_text(encoding="utf-8")).get("project_id", "")
    if not project:
        raise AIUnavailable("Vertex AI needs GOOGLE_CLOUD_PROJECT or a service-account key with a project_id")
    return genai.Client(vertexai=True, project=project, location=settings.gcp_location)


def client() -> genai.Client:
    global _client
    if not settings.ai_enabled:
        raise AIUnavailable("No Gemini credentials: set GEMINI_API_KEY or GOOGLE_GENAI_USE_VERTEXAI with a service-account key")
    if _client is None:
        _client = _vertex_client() if settings.use_vertex else genai.Client(api_key=settings.gemini_api_key)
    return _client


def video_part(path: Path) -> types.Part | types.File:
    """A video Gemini can watch: the Files API on AI Studio, inline bytes on Vertex (which has no Files API).

    Either way the video is first downscaled to 360p; Gemini samples about one
    frame per second, so this keeps uploads small without losing what it can see.
    """
    small = path.with_name(path.stem + "_gemini.mp4")
    if shutil.which("ffmpeg") and not small.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-vf", "scale=-2:360", "-r", "10",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-an", str(small)], check=False)
    src = small if small.exists() and small.stat().st_size > 0 else path
    if settings.use_vertex:
        return types.Part.from_bytes(data=src.read_bytes(), mime_type="video/mp4")
    return upload_file(src, "video/mp4")


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
