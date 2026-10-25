"""Recorded lab video to commits.

Gemini Flash watches the video and returns timestamped events (perception).
OpenCV measures color in the tube region frame by frame (measurement), the
flip is detected locally, keyframes are extracted at every event, and the
whole run is committed to the hash chain and sealed. Gemini output is cached
by video hash so a re-upload replays instantly and offline.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import cv2
from litmus_core.color import roi_metrics
from pydantic import BaseModel, Field

from .. import db, lifecycle, media, store
from ..config import settings
from . import cache
from .client import AIUnavailable, generate_json, upload_file

log = logging.getLogger("litmus.video")

JOBS: dict[str, dict] = {}
_lock = threading.Lock()


class VideoEvent(BaseModel):
    t_offset_s: float = Field(description="seconds from the start of the video")
    kind: Literal["step_confirmed", "quantity_added", "reagent_used", "mix", "pour", "flip_observed", "note"]
    summary: str = Field(description="short past-tense description, e.g. 'Poured 20 mL from the tap-water jug'")
    step: str | None = Field(default=None, description="protocol step id this belongs to")
    variable: str | None = Field(default=None, description="for reagent_used: the protocol variable key")
    value: str | None = Field(default=None, description="for reagent_used: the observed value, e.g. 'tap'")
    quantity_name: str | None = Field(default=None, description="for quantity_added: protocol quantity name")
    quantity_value: float | None = Field(default=None, description="for quantity_added: amount read from the video")
    unit: str | None = None
    inversions: int | None = Field(default=None, description="for mix: number of inversions seen")
    objects: list[str] = Field(default_factory=list)
    confidence: float = Field(description="0-1, how clearly the video shows this")


class VideoAnalysis(BaseModel):
    events: list[VideoEvent]
    tube_box: list[int] = Field(description="[ymin, xmin, ymax, xmax] of the liquid inside the sample tube, 0-1000 normalized")
    notes: str = ""


def _prompt(protocol: dict) -> str:
    steps = [{"id": s["id"], "title": s["title"], "detail": s.get("detail"), "quantity": s.get("quantity")} for s in protocol["steps"]]
    reagents = [{"variable": v["key"], "label": v["label"], "choices": list((v.get("detect") or {}).get("choices", {}).keys())}
                for v in protocol["variables"] if v["type"] == "categorical"]
    return f"""You are watching a recorded lab session for the experiment "{protocol['name']}".
Protocol steps: {json.dumps(steps)}
Reagent variables to identify (which container or bottle was used): {json.dumps(reagents)}

List every observable event in time order with its timestamp in seconds from the start of the video:
- step_confirmed when a protocol step begins (set step to the step id)
- quantity_added for every addition, with quantity_name from the protocol and the amount if it can be read
- reagent_used when you can see which container, jug or bottle is used (set variable and value)
- mix for each mixing episode (count inversions or stirs)
- flip_observed when the indicator color changes
- note for anything unexpected (spills, skipped steps, a different container than the protocol says)
Only report what is visible. Use low confidence when unsure. Also return the bounding box of the liquid in the sample tube."""


def _set(job_id: str, **kw) -> None:
    with _lock:
        JOBS[job_id].update(kw)


def start(path: Path, sha256: str, experiment_slug: str, label: str, role: str, assumed_cause: str | None) -> str:
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"id": job_id, "status": "running", "stage": "queued", "run_id": None, "error": None,
                    "label": label, "created_at": datetime.now(timezone.utc).isoformat()}
    threading.Thread(target=_run, args=(job_id, path, sha256, experiment_slug, label, role, assumed_cause), daemon=True).start()
    return job_id


def _analyze(path: Path, sha256: str, protocol: dict) -> dict:
    cached = cache.read("video", sha256)
    if cached:
        return cached
    f = upload_file(path, "video/mp4")
    out = generate_json(settings.model_flash, [f, _prompt(protocol)], VideoAnalysis, temperature=0.1)
    result = out.model_dump()
    result["model"] = settings.model_flash
    cache.write("video", sha256, result)
    return result


def _roi_from_box(box: list[int] | None, fallback: dict) -> dict:
    if not box or len(box) != 4:
        return fallback
    y0, x0, y1, x1 = [max(0, min(1000, v)) / 1000 for v in box]
    if y1 - y0 < 0.02 or x1 - x0 < 0.02:
        return fallback
    # Shrink to the central part of the liquid so glass edges and labels stay out.
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * 0.5, (y1 - y0) * 0.6
    return {"x": round(cx - w / 2, 4), "y": round(cy - h / 2, 4), "w": round(w, 4), "h": round(h, 4)}


def _run(job_id: str, path: Path, sha256: str, slug: str, label: str, role: str, assumed_cause: str | None) -> None:
    try:
        with db.connect() as conn:
            exp = store.get_experiment(conn, slug)
            protocol = exp["protocol"]
        _set(job_id, stage="watching video with Gemini")
        try:
            analysis = _analyze(path, sha256, protocol)
        except AIUnavailable:
            analysis = {"events": [], "tube_box": None, "notes": "Gemini unavailable: color measured, no perceived events.",
                        "model": None}
        roi = _roi_from_box(analysis.get("tube_box"), protocol["roi"])

        _set(job_id, stage="measuring color in the tube")
        cap = cv2.VideoCapture(str(path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = n / fps if n else 0
        started = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=duration)
        T = lambda s: started + timedelta(seconds=s)  # noqa: E731
        readings, step = [], max(1, int(round(fps / 4)))
        i = 0
        while True:
            ok = cap.grab()
            if not ok:
                break
            if i % step == 0:
                ok, frame = cap.retrieve()
                if ok:
                    m = roi_metrics(frame, roi)
                    for sensor, unit in (("lab_a", "a*"), ("lab_l", "L*"), ("lab_b", "b*"), ("hue", "deg"), ("darkness", "ratio")):
                        readings.append({"t": T(i / fps), "sensor": sensor, "value": m[sensor], "unit": unit, "provenance": "measured"})
            i += 1

        _set(job_id, stage="extracting keyframes")
        run_id = uuid.uuid4()
        events, frames = [], []
        for e in sorted(analysis["events"], key=lambda x: x["t_offset_s"]):
            t_off = max(0.0, min(duration, float(e["t_offset_s"])))
            cap.set(cv2.CAP_PROP_POS_MSEC, t_off * 1000)
            ok, frame = cap.read()
            fid = None
            if ok:
                fid = uuid.uuid4()
                fpath, furl = media.frame_path(run_id, fid)
                media.save_bytes(cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes(), fpath)
                frames.append((fid, T(t_off), furl, roi_metrics(frame, roi)))
            payload: dict = {"source": "video", "objects": e.get("objects") or []}
            kind = e["kind"]
            if kind == "step_confirmed":
                payload["step"] = e.get("step")
            elif kind == "quantity_added":
                payload.update(quantity=e.get("quantity_name"), value=e.get("quantity_value"), unit=e.get("unit"))
            elif kind == "reagent_used":
                payload.update(variable=e.get("variable"), value=e.get("value"))
            elif kind == "mix":
                payload.update(inversions=e.get("inversions"))
            elif kind == "flip_observed":
                kind = "note"  # the flip of record is measured locally from color, not taken from the model
                payload["observation"] = "color change seen by Gemini"
            events.append({"t": T(t_off), "kind": kind, "summary": e["summary"], "provenance": "inferred",
                           "confidence": round(float(e.get("confidence", 0.5)), 2), "payload": payload,
                           "frame_ids": [fid] if fid else []})
        cap.release()

        _set(job_id, stage="committing to the record")
        with db.connect() as conn:
            vpath, vurl = media.video_path(run_id)
            media.copy_into(path, vpath)
            store.create_run(conn, id=run_id, experiment_id=exp["id"], label=label, role=role, station_id="upload",
                             status="recording", started_at=started, video_url=vurl, assumed_cause=assumed_cause,
                             metadata={"source": "video_upload", "video_sha256": sha256, "video_started_at": started.isoformat(),
                                       "perception_model": analysis.get("model"), "roi": roi, "notes": analysis.get("notes")})
            store.append_events(conn, run_id, [{"t": started, "kind": "run_started", "provenance": "measured",
                                                "summary": f"Recorded video uploaded: {label} ({role})",
                                                "payload": {"source": "video", "sha256": sha256}}])
            store.insert_readings(conn, run_id, readings)
            for fid, ft, furl, metrics in frames:
                store.insert_frame(conn, run_id, fid, ft, furl, "event", roi, metrics)
            store.append_events(conn, run_id, events)
            conn.commit()
            _set(job_id, stage="detecting color flip and sealing", run_id=str(run_id))
            lifecycle.finalize(conn, run_id, T(duration))
        _set(job_id, status="done", stage="done", run_id=str(run_id), events=len(events))
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI as a job error
        log.exception("video job failed")
        _set(job_id, status="error", error=f"{type(exc).__name__}: {exc}")
