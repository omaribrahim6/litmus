"""Run lifecycle: finalize (flip cross-check, result, seal) and verify."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import psycopg

from litmus_core.signals import FlipConfig, detect_flip

from . import chain, evidence as ev, rundata, store
from .measure import measure_result


def _protocol_for(conn: psycopg.Connection, run: dict) -> dict:
    exp = store.get_experiment(conn, run["experiment_id"]) if run.get("experiment_id") else None
    if exp is None:
        raise ValueError("run has no experiment protocol")
    return exp["protocol"]


def _dt(epoch_s: float) -> datetime:
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc)


def detect_flips(conn: psycopg.Connection, rd: rundata.RunData, protocol: dict) -> list[dict]:
    """Recompute the color flip from stored series and cross-check it with the light sensor.

    Adds a camera flip_detected event only if the station did not already
    commit one, and always adds a flip_crosscheck event when both signals exist.
    """
    new_events: list[dict] = []
    if not protocol.get("flip"):
        return new_events  # the experiment has no visible change to detect
    flip_cfg = FlipConfig.from_dict(protocol.get("flip"))
    camera = rd.flip_event()
    series = rd.readings.get(flip_cfg.metric)
    if camera is None and series:
        f = detect_flip([(t, v) for t, v, _ in series], flip_cfg)
        if f:
            near = min(rd.frames, key=lambda fr: abs(fr["t"].timestamp() - f.t), default=None)
            new_events.append({
                "t": _dt(f.t), "kind": "flip_detected", "provenance": "measured",
                "summary": f"Color flip detected by camera ({flip_cfg.metric} changed {f.change:+.1f} from baseline {f.baseline:.1f})",
                "payload": {"source": "camera", "metric": flip_cfg.metric, "baseline": round(f.baseline, 3),
                            "value": round(f.value, 3), "change": round(f.change, 3),
                            "confirmed_t": chain.iso_utc(_dt(f.confirmed_t)),
                            "series_id": ev.ser(rd.id, flip_cfg.metric, series[0][0], series[-1][0])},
                "frame_ids": [near["id"]] if near else [],
            })
            camera_t = f.t
        else:
            camera_t = None
    else:
        camera_t = camera["t"].timestamp() if camera else None

    light_cfg = protocol.get("light_flip")
    light = rd.readings.get(light_cfg["metric"]) if light_cfg else None
    already = rd.events_of("flip_crosscheck")
    if light and not already:
        lf = detect_flip([(t, v) for t, v, _ in light], FlipConfig.from_dict(light_cfg))
        tol = float(protocol.get("flip_agreement_s", 1.0))
        payload = {"camera_t": chain.iso_utc(_dt(camera_t)) if camera_t else None,
                   "light_t": chain.iso_utc(_dt(lf.t)) if lf else None,
                   "tolerance_s": tol,
                   "light_series_id": ev.ser(rd.id, light_cfg["metric"], light[0][0], light[-1][0])}
        if camera_t and lf:
            delta = lf.t - camera_t
            payload.update(delta_s=round(delta, 3), agree=abs(delta) <= tol)
            summary = (f"Light sensor confirms the flip ({delta:+.2f} s from camera)" if abs(delta) <= tol
                       else f"Light sensor and camera disagree on flip time by {delta:+.2f} s")
        elif lf:
            payload.update(agree=False)
            summary = "Light sensor saw a flip the camera did not"
        elif camera_t:
            payload.update(agree=False)
            summary = "Camera saw a flip the light sensor did not confirm"
        else:
            payload = None
        if payload is not None:
            t = _dt(lf.t if lf else camera_t)
            new_events.append({"t": t, "kind": "flip_crosscheck", "provenance": "measured", "summary": summary, "payload": payload})
    return new_events


def finalize(conn: psycopg.Connection, run_id: uuid.UUID, ended_at: datetime | None = None) -> dict:
    run = store.get_run(conn, run_id)
    if run is None:
        raise KeyError("run not found")
    protocol = _protocol_for(conn, run)
    rd = rundata.load(conn, run_id)
    ended_at = ended_at or datetime.now(timezone.utc)

    extra = detect_flips(conn, rd, protocol)
    if extra:
        store.append_events(conn, run_id, extra)
        rd = rundata.load(conn, run_id)

    m = measure_result(rd, protocol)
    spec = protocol["result"]
    result = {"metric": spec["key"], "label": spec["label"], "unit": spec.get("unit"),
              "value": m.value if m.available else None, "available": m.available,
              "provenance": m.provenance, "evidence_ids": m.evidence_ids, "note": m.note}

    if not rd.events_of("run_ended"):
        store.append_events(conn, run_id, [{
            "t": ended_at, "kind": "run_ended", "provenance": "measured",
            "summary": f"Run ended. {spec['label']}: {m.display(spec.get('decimals', 1))}" if m.available else f"Run ended. {m.note}",
            "payload": {"result": result},
        }])
    seal(conn, run_id)
    return store.update_run(conn, run_id, status="complete", ended_at=ended_at, result=result)


def seal(conn: psycopg.Connection, run_id: uuid.UUID) -> dict:
    """Commit a digest of all readings and frames so raw data is tamper-evident too."""
    readings = store.get_readings(conn, run_id)
    frames = store.get_frames(conn, run_id)
    rd_digest = chain.readings_digest(readings)
    fr_digest = chain.frames_digest(frames)
    [event] = store.append_events(conn, run_id, [{
        "t": datetime.now(timezone.utc), "kind": "run_sealed", "provenance": "measured",
        "summary": f"Record sealed: {rd_digest['count']} readings, {fr_digest['count']} frames",
        "payload": {"readings": rd_digest, "frames": fr_digest},
    }])
    return event


def verify(conn: psycopg.Connection, run_id: uuid.UUID) -> dict:
    events = store.get_events(conn, run_id, order="seq")
    report = chain.verify_events(events)
    report["run_id"] = str(run_id)
    report["events"] = len(events)
    seals = [e for e in events if e["kind"] == "run_sealed"]
    if report["intact"] and seals:
        last = seals[-1]
        readings = chain.readings_digest(store.get_readings(conn, run_id))
        frames = chain.frames_digest(store.get_frames(conn, run_id))
        expected = last["payload"] or {}
        if readings != expected.get("readings"):
            report.update(intact=False, reason=f"sensor readings changed after the record was sealed "
                                                 f"({expected.get('readings', {}).get('count')} sealed, {readings['count']} now, or values edited)",
                          broken_at_seq=last["seq"], event_id=str(last["id"]))
        elif frames != expected.get("frames"):
            report.update(intact=False, reason="frames changed after the record was sealed",
                          broken_at_seq=last["seq"], event_id=str(last["id"]))
        report["sealed"] = True
        report["readings"] = readings["count"]
        report["frames"] = frames["count"]
    else:
        report.setdefault("sealed", bool(seals))
    report["checked_at"] = chain.iso_utc(datetime.now(timezone.utc))
    return report
