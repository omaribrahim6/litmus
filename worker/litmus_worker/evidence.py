"""Evidence IDs: every number and every AI claim points at one or more of these.

    evt:<event uuid>                                  a commit
    frm:<frame uuid>                                  a keyframe image
    ser:<run uuid>:<sensor>:<start ms>:<end ms>       a window of readings
    rdg:<run uuid>:<sensor>:<epoch ms>                a single reading (nearest sample)
    run:<run uuid>                                    the run record (label, role, assumed cause)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import psycopg

from . import store


@dataclass(frozen=True)
class Ref:
    type: str
    id: uuid.UUID
    sensor: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None


def ms(t: datetime | float) -> int:
    if isinstance(t, datetime):
        return int(round(t.timestamp() * 1000))
    return int(round(t * 1000))


def evt(event_id) -> str:
    return f"evt:{event_id}"


def frm(frame_id) -> str:
    return f"frm:{frame_id}"


def run(run_id) -> str:
    return f"run:{run_id}"


def ser(run_id, sensor: str, start, end) -> str:
    return f"ser:{run_id}:{sensor}:{ms(start)}:{ms(end)}"


def rdg(run_id, sensor: str, t) -> str:
    return f"rdg:{run_id}:{sensor}:{ms(t)}"


def parse(eid: str) -> Ref | None:
    try:
        kind, rest = eid.split(":", 1)
        if kind in ("evt", "frm", "run"):
            return Ref(kind, uuid.UUID(rest))
        if kind == "ser":
            rid, sensor, a, b = rest.rsplit(":", 3)
            return Ref(kind, uuid.UUID(rid), sensor, int(a), int(b))
        if kind == "rdg":
            rid, sensor, a = rest.rsplit(":", 2)
            return Ref(kind, uuid.UUID(rid), sensor, int(a), int(a))
    except (ValueError, AttributeError):
        return None
    return None


def _dt(ms_value: int) -> datetime:
    return datetime.fromtimestamp(ms_value / 1000, tz=timezone.utc)


def resolve(conn: psycopg.Connection, eid: str) -> dict | None:
    """Look up the evidence behind an ID. Returns None if it does not exist."""
    ref = parse(eid)
    if ref is None:
        return None
    if ref.type == "evt":
        ev = store.get_event(conn, ref.id)
        if not ev:
            return None
        frames = []
        if ev["frame_ids"]:
            with conn.cursor() as cur:
                cur.execute("select id, t, url, reason from frames where id = any(%s) order by t", (ev["frame_ids"],))
                frames = cur.fetchall()
        return {"id": eid, "type": "event", "run_id": ev["run_id"], "t": ev["t"], "kind": ev["kind"],
                "summary": ev["summary"], "payload": ev["payload"], "provenance": ev["provenance"],
                "confidence": ev["confidence"], "hash": ev["hash"], "seq": ev["seq"], "frames": frames}
    if ref.type == "frm":
        with conn.cursor() as cur:
            cur.execute("select * from frames where id = %s", (ref.id,))
            f = cur.fetchone()
        if not f:
            return None
        return {"id": eid, "type": "frame", "run_id": f["run_id"], "t": f["t"], "url": f["url"],
                "reason": f["reason"], "metrics": f["metrics"], "roi": f["roi"], "provenance": "measured"}
    if ref.type == "run":
        r = store.get_run(conn, ref.id)
        if not r:
            return None
        return {"id": eid, "type": "run", "run_id": r["id"], "label": r["label"], "role": r["role"],
                "assumed_cause": r["assumed_cause"], "result": r["result"], "provenance": "reported"}
    if ref.type in ("ser", "rdg"):
        start, end = _dt(ref.start_ms), _dt(ref.end_ms)
        if ref.type == "rdg":
            start, end = start - timedelta(milliseconds=750), end + timedelta(milliseconds=750)
        rows = store.get_readings(conn, ref.id, [ref.sensor], start, end)
        if not rows:
            return None
        values = [r["value"] for r in rows]
        if ref.type == "rdg":
            target = _dt(ref.start_ms)
            row = min(rows, key=lambda r: abs((r["time"] - target).total_seconds()))
            return {"id": eid, "type": "reading", "run_id": ref.id, "sensor": ref.sensor, "t": row["time"],
                    "value": row["value"], "unit": row["unit"], "provenance": row["provenance"]}
        provs = {r["provenance"] for r in rows}
        return {"id": eid, "type": "series", "run_id": ref.id, "sensor": ref.sensor, "start": start, "end": end,
                "n": len(rows), "mean": sum(values) / len(values), "min": min(values), "max": max(values),
                "unit": rows[0]["unit"], "provenance": "measured" if provs == {"measured"} else sorted(provs)[0],
                "points": [{"t": r["time"], "value": r["value"]} for r in rows[:: max(1, len(rows) // 240)]]}
    return None


def exists(conn: psycopg.Connection, eid: str) -> bool:
    return resolve(conn, eid) is not None
