"""Litmus worker: ingest, hash chain, media, diff engine and Gemini pipeline."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db, evidence, lifecycle, media, store
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    media.media_root()
    yield
    db.close()


app = FastAPI(title="litmus-worker", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=str(media.media_root())), name="media")


def require_station(authorization: str | None = Header(default=None)) -> None:
    """Station ingest is authenticated with a shared bearer token when one is configured."""
    if settings.worker_token and authorization != f"Bearer {settings.worker_token}":
        raise HTTPException(401, "invalid station token")


def parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(404, "not found")


# ----------------------------------------------------------------- health

@app.get("/health")
def health() -> dict:
    status: dict[str, Any] = {"ok": True, "service": "litmus-worker", "ai": settings.ai_enabled}
    try:
        with db.connect() as conn:
            conn.execute("select 1")
        status["db"] = True
    except Exception as exc:  # noqa: BLE001 - health must never raise
        status["db"] = False
        status["db_error"] = type(exc).__name__
    return status


# ------------------------------------------------------------ station ingest

class RunIn(BaseModel):
    id: uuid.UUID | None = None
    experiment: str = Field(description="experiment id or slug")
    label: str | None = None
    role: str = "reference"
    station_id: str | None = None
    parent_run_id: uuid.UUID | None = None
    started_at: datetime | None = None
    assumed_cause: str | None = None
    metadata: dict = Field(default_factory=dict)


class ReadingIn(BaseModel):
    t: datetime
    sensor: str
    value: float | None
    unit: str | None = None
    provenance: str = "measured"


class EventIn(BaseModel):
    id: uuid.UUID | None = None
    t: datetime
    kind: str
    summary: str
    payload: dict | None = None
    provenance: str = "measured"
    confidence: float | None = None
    frame_ids: list[uuid.UUID] = Field(default_factory=list)


class ReadingsBatch(BaseModel):
    readings: list[ReadingIn]


class EventsBatch(BaseModel):
    events: list[EventIn]


class EndIn(BaseModel):
    ended_at: datetime | None = None


@app.post("/api/runs", dependencies=[Depends(require_station)])
def create_run(body: RunIn) -> dict:
    with db.connect() as conn:
        exp = store.get_experiment(conn, body.experiment)
        if exp is None:
            raise HTTPException(404, f"unknown experiment {body.experiment}")
        started = body.started_at or datetime.now(timezone.utc)
        run = store.create_run(
            conn, id=body.id, experiment_id=exp["id"], label=body.label, role=body.role,
            station_id=body.station_id, parent_run_id=body.parent_run_id, status="recording",
            started_at=started, assumed_cause=body.assumed_cause, metadata=body.metadata,
        )
        if not store.get_events(conn, run["id"]):
            store.append_events(conn, run["id"], [{
                "t": started, "kind": "run_started", "provenance": "measured",
                "summary": f"Run started{f' at station {body.station_id}' if body.station_id else ''}: {body.label or 'unlabeled'} ({body.role})",
                "payload": {"label": body.label, "role": body.role, "station_id": body.station_id,
                            "experiment": exp["slug"], "available_sensors": body.metadata.get("available_sensors")},
            }])
        return store.to_json(run)


def _open_run(conn, run_id: uuid.UUID) -> dict:
    run = store.get_run(conn, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    if run["status"] != "recording":
        raise HTTPException(409, "run is sealed; its record can no longer change")
    return run


@app.post("/api/runs/{run_id}/readings", dependencies=[Depends(require_station)])
def ingest_readings(run_id: str, body: ReadingsBatch) -> dict:
    rid = parse_uuid(run_id)
    with db.connect() as conn:
        _open_run(conn, rid)
        n = store.insert_readings(conn, rid, [r.model_dump() for r in body.readings])
    return {"inserted": n}


@app.post("/api/runs/{run_id}/events", dependencies=[Depends(require_station)])
def ingest_events(run_id: str, body: EventsBatch) -> dict:
    rid = parse_uuid(run_id)
    with db.connect() as conn:
        _open_run(conn, rid)
        rows = store.append_events(conn, rid, [e.model_dump() for e in body.events])
    return {"committed": [{"id": str(r["id"]), "seq": r["seq"], "hash": r["hash"]} for r in rows]}


@app.post("/api/runs/{run_id}/frames", dependencies=[Depends(require_station)])
def ingest_frame(run_id: str, file: UploadFile = File(...), meta: str = Form(...)) -> dict:
    rid = parse_uuid(run_id)
    info = json.loads(meta)
    frame_id = uuid.UUID(info.get("id") or str(uuid.uuid4()))
    with db.connect() as conn:
        _open_run(conn, rid)
        path, url = media.frame_path(rid, frame_id)
        media.save_stream(file.file, path)
        row = store.insert_frame(conn, rid, frame_id, store.as_dt(info["t"]), url,
                                 info.get("reason"), info.get("roi"), info.get("metrics"))
    return store.to_json(row)


@app.post("/api/runs/{run_id}/video", dependencies=[Depends(require_station)])
def ingest_video(run_id: str, file: UploadFile = File(...), started_at: str | None = Form(default=None)) -> dict:
    rid = parse_uuid(run_id)
    with db.connect() as conn:
        run = store.get_run(conn, rid)
        if run is None:
            raise HTTPException(404, "run not found")
        path, url = media.video_path(rid)
        digest = media.save_stream(file.file, path)
        meta = {"video_sha256": digest, "video_started_at": started_at or (run["started_at"] and run["started_at"].isoformat())}
        row = store.update_run(conn, rid, video_url=url, metadata=meta)
    return store.to_json(row)


@app.post("/api/runs/{run_id}/end", dependencies=[Depends(require_station)])
def end_run(run_id: str, body: EndIn) -> dict:
    rid = parse_uuid(run_id)
    with db.connect() as conn:
        _open_run(conn, rid)
        run = lifecycle.finalize(conn, rid, body.ended_at)
        report = lifecycle.verify(conn, rid)
    return {"run": store.to_json(run), "verify": report}


# --------------------------------------------------------------- reads

@app.get("/verify/{run_id}")
def verify(run_id: str) -> dict:
    rid = parse_uuid(run_id)
    with db.connect() as conn:
        if store.get_run(conn, rid) is None:
            raise HTTPException(404, "run not found")
        return lifecycle.verify(conn, rid)


@app.get("/api/experiments")
def experiments() -> list[dict]:
    with db.connect() as conn:
        return store.to_json(store.list_experiments(conn))


@app.get("/api/runs")
def runs(experiment: str | None = None) -> list[dict]:
    with db.connect() as conn:
        exp_id = None
        if experiment:
            exp = store.get_experiment(conn, experiment)
            if exp is None:
                raise HTTPException(404, "unknown experiment")
            exp_id = exp["id"]
        return store.to_json(store.list_runs(conn, exp_id))


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    rid = parse_uuid(run_id)
    with db.connect() as conn:
        run = store.get_run(conn, rid)
        if run is None:
            raise HTTPException(404, "run not found")
        return store.to_json({
            "run": run,
            "events": store.get_events(conn, rid, order="time"),
            "frames": store.get_frames(conn, rid),
            "readings": store.get_readings_1s(conn, rid),
            "verify": lifecycle.verify(conn, rid),
        })


class AssumedCauseIn(BaseModel):
    text: str


@app.post("/api/runs/{run_id}/assumed-cause")
def set_assumed_cause(run_id: str, body: AssumedCauseIn) -> dict:
    """Record the researcher's hypothesis as a reported commit and on the run."""
    rid = parse_uuid(run_id)
    with db.connect() as conn:
        if store.get_run(conn, rid) is None:
            raise HTTPException(404, "run not found")
        store.append_events(conn, rid, [{
            "t": datetime.now(timezone.utc), "kind": "hypothesis_stated", "provenance": "reported",
            "summary": f"Researcher's assumed cause: {body.text}", "payload": {"text": body.text},
        }])
        return store.to_json(store.update_run(conn, rid, assumed_cause=body.text))


@app.get("/api/evidence/{eid:path}")
def get_evidence(eid: str) -> dict:
    with db.connect() as conn:
        found = evidence.resolve(conn, eid)
    if found is None:
        raise HTTPException(404, "evidence not found")
    return store.to_json(found)


class EvidenceBatch(BaseModel):
    ids: list[str]


@app.post("/api/evidence")
def get_evidence_batch(body: EvidenceBatch) -> dict:
    with db.connect() as conn:
        return store.to_json({eid: evidence.resolve(conn, eid) for eid in body.ids[:64]})
