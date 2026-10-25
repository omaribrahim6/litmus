"""Litmus worker: ingest, hash chain, media, diff engine and Gemini pipeline."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import analysis, charts, db, evidence, lifecycle, media, store
from .ai import chat, intro, narration, perception, video
from .ai.client import AIUnavailable
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
def ingest_events(run_id: str, body: EventsBatch, background: BackgroundTasks) -> dict:
    rid = parse_uuid(run_id)
    with db.connect() as conn:
        _open_run(conn, rid)
        rows = store.append_events(conn, rid, [e.model_dump() for e in body.events])
    for r in rows:
        if r["kind"] == "step_confirmed":
            # Gemini identifies the reagent/container in the keyframes around this step.
            background.add_task(perception.detect_reagents_for_step, rid, r)
    background.add_task(perception.embed_pending)
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
def ingest_video(run_id: str, file: UploadFile = File(...), started_at: str | None = Form(default=None),
                 camera: str = Form(default="bench")) -> dict:
    """The run's video: the bench camera (color of record) or the researcher camera (actions)."""
    rid = parse_uuid(run_id)
    with db.connect() as conn:
        run = store.get_run(conn, rid)
        if run is None:
            raise HTTPException(404, "run not found")
        if camera == "action":
            path, url = media.video_path(rid, "_action.mp4")
            digest = media.save_stream(file.file, path)
            row = store.update_run(conn, rid, metadata={"action_video_url": url, "action_video_sha256": digest})
        else:
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


# ------------------------------------------------------------- analyses

class DiffIn(BaseModel):
    candidate: uuid.UUID
    controls: list[uuid.UUID] | None = None
    references: list[uuid.UUID] | None = None
    exclude: list[uuid.UUID] | None = None


class VerdictIn(BaseModel):
    diff_id: uuid.UUID | None = None
    candidate: uuid.UUID | None = None
    controls: list[uuid.UUID] | None = None
    use_ai: bool = True


class ReportIn(BaseModel):
    verdict_id: uuid.UUID
    use_ai: bool = True


class BranchIn(BaseModel):
    analysis_id: uuid.UUID
    exclude: list[uuid.UUID]
    use_ai: bool = True


def _analysis_or_404(conn, analysis_id: uuid.UUID, kinds: tuple[str, ...]) -> dict:
    row = store.get_analysis(conn, analysis_id)
    if row is None or row["kind"] not in kinds:
        raise HTTPException(404, "analysis not found")
    return row


@app.post("/api/diff")
def diff_endpoint(body: DiffIn) -> dict:
    with db.connect() as conn:
        try:
            row = analysis.run_diff(conn, body.candidate, body.controls, body.references, body.exclude)
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc))
        return store.to_json(row)


@app.post("/api/verdict")
def verdict_endpoint(body: VerdictIn) -> dict:
    with db.connect() as conn:
        if body.diff_id:
            diff_row = _analysis_or_404(conn, body.diff_id, ("diff", "branch"))
        elif body.candidate:
            try:
                diff_row = analysis.run_diff(conn, body.candidate, body.controls)
            except (KeyError, ValueError) as exc:
                raise HTTPException(400, str(exc))
        else:
            raise HTTPException(400, "diff_id or candidate is required")
        conn.commit()
        return store.to_json(analysis.run_verdict(conn, diff_row, use_ai=body.use_ai))


@app.post("/api/report")
def report_endpoint(body: ReportIn) -> dict:
    with db.connect() as conn:
        verdict_row = _analysis_or_404(conn, body.verdict_id, ("verdict",))
        return store.to_json(analysis.run_report(conn, verdict_row, use_ai=body.use_ai))


@app.get("/api/report/{analysis_id}.md", response_class=PlainTextResponse)
def report_markdown(analysis_id: str) -> str:
    with db.connect() as conn:
        row = _analysis_or_404(conn, parse_uuid(analysis_id), ("report",))
    return row["content"].get("markdown", "")


@app.post("/api/branch")
def branch_endpoint(body: BranchIn) -> dict:
    """Reanalysis without some runs. Writes new analyses; never touches the original record."""
    with db.connect() as conn:
        base = _analysis_or_404(conn, body.analysis_id, ("diff", "branch", "verdict"))
        content = base["content"]["diff"] if base["kind"] == "verdict" else base["content"]
        cand = uuid.UUID(content["candidate"]["run_id"])
        controls = [uuid.UUID(c["run_id"]) for c in content["controls"] if uuid.UUID(c["run_id"]) not in body.exclude]
        refs = [uuid.UUID(r["run_id"]) for r in content["references"]]
        try:
            branch = analysis.run_diff(conn, cand, controls or None, refs, body.exclude, kind="branch", parent_id=base["id"])
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, str(exc))
        conn.commit()
        verdict_row = analysis.run_verdict(conn, branch, use_ai=body.use_ai)
        return store.to_json({"branch": branch, "verdict": verdict_row})


@app.get("/api/analyses")
def analyses_list(kind: str | None = None, run_id: str | None = None) -> list[dict]:
    with db.connect() as conn:
        rows = store.list_analyses(conn, kind, parse_uuid(run_id) if run_id else None)
    return store.to_json([{k: r[k] for k in ("id", "kind", "run_ids", "model", "created_at")} for r in rows])


@app.get("/api/analyses/{analysis_id}")
def analysis_detail(analysis_id: str) -> dict:
    with db.connect() as conn:
        row = store.get_analysis(conn, parse_uuid(analysis_id))
    if row is None:
        raise HTTPException(404, "analysis not found")
    return store.to_json(row)


# ------------------------------------------------------------------ ask

class AskIn(BaseModel):
    messages: list[dict]
    context: dict = Field(default_factory=dict)
    experiment: str = "vinegar-titration"


@app.post("/api/ask")
def ask_endpoint(body: AskIn) -> dict:
    with db.connect() as conn:
        exp = store.get_experiment(conn, body.experiment)
        if exp is None:
            raise HTTPException(404, "unknown experiment")
        return store.to_json(chat.ask(conn, exp, body.messages, body.context))


class ChartIn(BaseModel):
    kind: str
    experiment: str = "vinegar-titration"
    variable_key: str | None = None
    sensor: str | None = None
    run_ids: list[str] | None = None
    style: str = "screen"
    title: str | None = None


@app.post("/api/charts")
def chart_endpoint(body: ChartIn) -> dict:
    with db.connect() as conn:
        exp = store.get_experiment(conn, body.experiment)
        try:
            kw = {"title": body.title, "style": body.style, "run_ids": body.run_ids}
            if body.kind == "variable_by_run":
                kw["variable_key"] = body.variable_key
            if body.kind == "sensor_overlay":
                kw["sensor"] = body.sensor
            return store.to_json(charts.build(conn, exp, body.kind, **kw))
        except ValueError as exc:
            raise HTTPException(400, str(exc))


# --------------------------------------------------------- video upload

@app.post("/api/upload")
def upload_video(file: UploadFile = File(...), experiment: str = Form("vinegar-titration"), label: str = Form(...),
                 role: str = Form("candidate"), assumed_cause: str | None = Form(default=None)) -> dict:
    tmp = media.media_root() / "uploads" / f"{uuid.uuid4().hex}.mp4"
    digest = media.save_stream(file.file, tmp)
    job_id = video.start(tmp, digest, experiment, label, role, assumed_cause or None)
    return {"job_id": job_id, "sha256": digest}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = video.JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


# --------------------------------------------------------- spoken intro

@app.post("/api/runs/{run_id}/intro", dependencies=[Depends(require_station)])
def ingest_intro(run_id: str, file: UploadFile = File(...)) -> dict:
    """The researcher's spoken intro. Gemini titles the run; the clip and transcript stay as evidence."""
    rid = parse_uuid(run_id)
    suffix = Path(file.filename or "intro.wav").suffix.lower() or ".wav"
    with db.connect() as conn:
        run = store.get_run(conn, rid)
        if run is None:
            raise HTTPException(404, "run not found")
        exp = store.get_experiment(conn, run["experiment_id"])
        rel = f"runs/{rid}/intro{suffix}"
        media.save_stream(file.file, media.media_root() / rel)
    url = f"/media/{rel}"
    try:
        heard = intro.understand(media.media_root() / rel, exp["name"])
    except (AIUnavailable, RuntimeError) as exc:
        return {"understood": False, "audio_url": url, "error": str(exc)}
    with db.connect() as conn:
        fields: dict[str, Any] = {"metadata": {"researcher": heard.researcher, "lab": heard.lab, "session_title": heard.title,
                                               "intro_audio_url": url, "intro_experiment": heard.experiment}}
        if heard.run_label:
            fields["label"] = heard.run_label
        if heard.role != "unknown":
            fields["role"] = heard.role
        if heard.hypothesis and not run["assumed_cause"]:
            fields["assumed_cause"] = heard.hypothesis
        store.update_run(conn, rid, **fields)
        events = [{
            "t": run["started_at"] or datetime.now(timezone.utc), "kind": "session_intro", "provenance": "inferred",
            "confidence": round(max(0.0, min(1.0, heard.clarity)), 2),
            "summary": f"Session intro: {heard.title}",
            "payload": {**heard.model_dump(), "audio_url": url, "model": settings.model_flash},
        }]
        if heard.hypothesis:
            events.append({"t": datetime.now(timezone.utc), "kind": "hypothesis_stated", "provenance": "inferred",
                           "summary": f"Stated hypothesis (spoken): {heard.hypothesis}",
                           "payload": {"text": heard.hypothesis, "source": "spoken intro", "audio_url": url}})
        store.append_events(conn, rid, events)
    return {"understood": True, "audio_url": url, **heard.model_dump()}


class IntroConfirmIn(BaseModel):
    researcher: str | None = None
    lab: str | None = None
    title: str | None = None
    run_label: str | None = None


@app.post("/api/runs/{run_id}/intro/confirm", dependencies=[Depends(require_station)])
def confirm_intro(run_id: str, body: IntroConfirmIn) -> dict:
    """The researcher confirmed (or corrected) the title on the touchscreen: now it is reported, not inferred."""
    rid = parse_uuid(run_id)
    with db.connect() as conn:
        if store.get_run(conn, rid) is None:
            raise HTTPException(404, "run not found")
        fields: dict[str, Any] = {"metadata": {k: v for k, v in {"researcher": body.researcher, "lab": body.lab,
                                                                  "session_title": body.title, "intro_confirmed": True}.items() if v is not None}}
        if body.run_label:
            fields["label"] = body.run_label
        store.update_run(conn, rid, **fields)
        store.append_events(conn, rid, [{
            "t": datetime.now(timezone.utc), "kind": "intro_confirmed", "provenance": "reported",
            "summary": f"Researcher confirmed the session title: {body.title or body.run_label or 'as heard'}",
            "payload": body.model_dump(),
        }])
        return store.to_json(store.get_run(conn, rid))


@app.post("/api/runs/{run_id}/narration", dependencies=[Depends(require_station)])
def ingest_narration(run_id: str, file: UploadFile = File(...), meta: str = Form("{}")) -> dict:
    """One utterance from the clearest mic. Lab-relevant statements become commits; the rest is discarded."""
    rid = parse_uuid(run_id)
    info = json.loads(meta or "{}")
    with db.connect() as conn:
        run = _open_run(conn, rid)
        exp = store.get_experiment(conn, run["experiment_id"])
    rel = f"runs/{rid}/audio/{uuid.uuid4().hex[:12]}.wav"
    path = media.media_root() / rel
    media.save_stream(file.file, path)
    try:
        heard, model = narration.understand(path, exp["protocol"])
    except (AIUnavailable, RuntimeError) as exc:
        return {"committed": [], "error": str(exc), "audio_url": f"/media/{rel}"}
    relevant = [s for s in heard.statements if s.lab_relevant and s.text.strip()]
    if not relevant:
        path.unlink(missing_ok=True)  # nothing about the lab was said: keep no audio
        return {"committed": [], "dropped": len(heard.statements)}
    t0 = store.as_dt(info["t_start"]) if info.get("t_start") else datetime.now(timezone.utc)
    url = f"/media/{rel}"
    reagent_vars = {v["key"]: v for v in exp["protocol"]["variables"] if v["type"] == "categorical"}
    events, committed = [], []
    for s in relevant:
        t = t0 + timedelta(seconds=max(0.0, s.t_offset_s))
        base = {"audio_url": url, "offset_s": round(s.t_offset_s, 2), "mic": info.get("source"), "mic_scores": info.get("scores"),
                "model": model, "statement_kind": s.kind}
        kind = "hypothesis_stated" if s.kind == "hypothesis" else "narration"
        events.append({"t": t, "kind": kind, "provenance": "inferred", "confidence": round(heard.clarity, 2),
                       "summary": f"Said at the bench: \u201c{s.text}\u201d", "payload": {"text": s.text, **base}})
        if s.kind == "reagent" and s.variable in reagent_vars and s.value:
            label = reagent_vars[s.variable]["label"]
            events.append({"t": t, "kind": "reagent_used", "provenance": "inferred", "confidence": round(heard.clarity, 2),
                           "summary": f"{label}: {s.value} (said at the bench)",
                           "payload": {"variable": s.variable, "value": s.value, "source": "narration", "text": s.text, **base}})
        committed.append({"t_s": (t - run["started_at"]).total_seconds() if run["started_at"] else 0, "text": s.text, "kind": s.kind})
    with db.connect() as conn:
        store.append_events(conn, rid, events)
    return {"committed": committed, "dropped": len(heard.statements) - len(relevant), "audio_url": url}
