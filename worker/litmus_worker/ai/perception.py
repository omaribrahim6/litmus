"""Gemini perception: keyframe reagent identification and event embeddings."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta

from google.genai import types
from pydantic import BaseModel, Field

from .. import db, media, store
from ..config import settings
from .client import AIUnavailable, embed, generate_json

log = logging.getLogger("litmus.perception")


class FrameLabel(BaseModel):
    choice: str | None = Field(description="one of the choice keys, or null if it cannot be seen")
    observation: str = Field(description="what in the image shows this, in a few words")
    confidence: float = Field(description="0 to 1, how clearly the image shows it")


def label_frame(image: bytes, question: str, choices: dict[str, str]) -> FrameLabel:
    prompt = (f"Lab station camera frame. {question}\nChoices (key: what it looks like):\n"
              + "\n".join(f"- {k}: {v}" for k, v in choices.items())
              + "\nAnswer with the choice key only if the image clearly shows it; otherwise null.")
    return generate_json(settings.model_flash, [types.Part.from_bytes(data=image, mime_type="image/jpeg"), prompt],
                         FrameLabel, temperature=0.0)


def detect_reagents_for_step(run_id: uuid.UUID, step_event: dict, wait_s: float = 4.0) -> list[dict]:
    """After a protocol step is confirmed, identify reagents the protocol asks to watch for.

    Produces reagent_used commits with provenance 'inferred' and the frame as evidence.
    Without Gemini nothing is written and the variable stays missing evidence.
    """
    if not settings.ai_enabled:
        return []
    time.sleep(wait_s)  # let the station upload the frames around the step
    committed: list[dict] = []
    with db.connect() as conn:
        run = store.get_run(conn, run_id)
        exp = store.get_experiment(conn, run["experiment_id"])
        step = (step_event.get("payload") or {}).get("step")
        targets = [v for v in exp["protocol"]["variables"] if (v.get("detect") or {}).get("step") == step]
        if not targets:
            return []
        frames = store.get_frames(conn, run_id)
        t = step_event["t"]
        window = [f for f in frames if t - timedelta(seconds=2) <= f["t"] <= t + timedelta(seconds=8)]
        window.sort(key=lambda f: abs((f["t"] - (t + timedelta(seconds=2))).total_seconds()))
        for var in targets:
            det = var["detect"]
            for f in window[:3]:
                path = media.local_path(f["url"])
                if not path or not path.exists():
                    continue
                try:
                    lab = label_frame(path.read_bytes(), det["question"], det["choices"])
                except (AIUnavailable, RuntimeError) as exc:
                    log.info("frame labeling failed: %s", exc)
                    break
                if lab.choice in det["choices"]:
                    rows = store.append_events(conn, run_id, [{
                        "t": f["t"], "kind": "reagent_used", "provenance": "inferred",
                        "confidence": round(max(0.0, min(1.0, lab.confidence)), 2),
                        "summary": f"{var['label']}: {lab.choice} (camera: {lab.observation})",
                        "payload": {"variable": var["key"], "value": lab.choice, "label": det["choices"][lab.choice],
                                    "observation": lab.observation, "model": settings.model_flash},
                        "frame_ids": [f["id"]],
                    }])
                    committed += rows
                    break
    return committed


def embed_pending(limit: int = 96) -> int:
    """Embed commits that do not have an embedding yet (a derived search index, not part of the hash)."""
    if not settings.ai_enabled:
        return 0
    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """select e.id, e.kind, e.summary, r.label from events e join runs r on r.id = e.run_id
                   where e.embedding is null order by e.t limit %s""",
                (limit,),
            )
            rows = cur.fetchall()
        if not rows:
            return 0
        texts = [f"{r['label']}: {r['kind'].replace('_', ' ')}. {r['summary']}" for r in rows]
        try:
            vectors = embed(texts)
        except Exception as exc:  # noqa: BLE001 - search falls back to keywords
            log.info("embedding failed: %s", exc)
            return 0
        with conn.cursor() as cur:
            cur.executemany("update events set embedding = %s::vector where id = %s",
                            [(str(v), r["id"]) for v, r in zip(vectors, rows)])
        return len(rows)


def embed_all() -> int:
    total = 0
    while (n := embed_pending()) > 0:
        total += n
    return total
