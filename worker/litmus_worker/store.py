"""Database access for runs, readings, frames, events and analyses."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from . import chain

PROVENANCES = ("measured", "reported", "inferred")


def _clean(obj: Any) -> Any:
    """Make a payload JSON-safe: no NaN/inf, no non-string keys."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, (uuid.UUID, datetime)):
        return chain.iso_utc(obj) if isinstance(obj, datetime) else str(obj)
    return obj


def as_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    s = str(value).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- experiments

def upsert_experiment(conn: psycopg.Connection, protocol: dict) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """insert into experiments (slug, name, protocol) values (%s, %s, %s)
               on conflict (slug) do update set name = excluded.name, protocol = excluded.protocol
               returning *""",
            (protocol["slug"], protocol["name"], Jsonb(protocol)),
        )
        return cur.fetchone()


def get_experiment(conn: psycopg.Connection, ref: str | uuid.UUID) -> dict | None:
    with conn.cursor() as cur:
        try:
            uid = uuid.UUID(str(ref))
            cur.execute("select * from experiments where id = %s", (uid,))
        except ValueError:
            cur.execute("select * from experiments where slug = %s", (str(ref),))
        return cur.fetchone()


def list_experiments(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("select * from experiments order by created_at")
        return cur.fetchall()


# ----------------------------------------------------------------------- runs

def create_run(conn: psycopg.Connection, **fields: Any) -> dict:
    cols = ["id", "experiment_id", "label", "role", "parent_run_id", "station_id", "status",
            "started_at", "ended_at", "video_url", "result", "assumed_cause", "metadata"]
    values = {k: fields.get(k) for k in cols if fields.get(k) is not None}
    values.setdefault("id", uuid.uuid4())
    for k in ("result", "metadata"):
        if k in values:
            values[k] = Jsonb(_clean(values[k]))
    names = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    with conn.cursor() as cur:
        cur.execute(
            f"insert into runs ({names}) values ({marks}) on conflict (id) do nothing returning *",
            list(values.values()),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute("select * from runs where id = %s", (values["id"],))
            row = cur.fetchone()
        return row


def update_run(conn: psycopg.Connection, run_id: uuid.UUID, **fields: Any) -> dict:
    """Update run-level fields (status, result, video). Committed events are never touched."""
    allowed = {"label", "role", "status", "ended_at", "video_url", "result", "assumed_cause", "metadata", "parent_run_id", "experiment_id"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"cannot update {k}")
        if k == "metadata":
            sets.append("metadata = metadata || %s")
            vals.append(Jsonb(_clean(v)))
            continue
        sets.append(f"{k} = %s")
        vals.append(Jsonb(_clean(v)) if k == "result" else v)
    with conn.cursor() as cur:
        cur.execute(f"update runs set {', '.join(sets)} where id = %s returning *", [*vals, run_id])
        return cur.fetchone()


def get_run(conn: psycopg.Connection, run_id: uuid.UUID | str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute("select * from runs where id = %s", (uuid.UUID(str(run_id)),))
        return cur.fetchone()


def list_runs(conn: psycopg.Connection, experiment_id: uuid.UUID | None = None) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """select r.*, e.slug as experiment_slug, e.name as experiment_name,
                      (select hash from events ev where ev.run_id = r.id order by seq desc limit 1) as head_hash,
                      (select count(*) from events ev where ev.run_id = r.id) as event_count
               from runs r left join experiments e on e.id = r.experiment_id
               where (%s::uuid is null or r.experiment_id = %s::uuid)
                 and not coalesce((r.metadata->>'smoke')::boolean, false)
               order by r.started_at nulls last""",
            (experiment_id, experiment_id),
        )
        return cur.fetchall()


# ------------------------------------------------------------------- readings

def insert_readings(conn: psycopg.Connection, run_id: uuid.UUID, readings: list[dict]) -> int:
    rows = []
    for r in readings:
        v = r.get("value")
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            continue  # a missing sensor sends nothing; we never store placeholders
        prov = r.get("provenance", "measured")
        if prov not in PROVENANCES:
            raise ValueError(f"bad provenance {prov}")
        rows.append((as_dt(r["t"]), run_id, r["sensor"], float(v), r.get("unit"), prov))
    if rows:
        # COPY sends the whole batch in one round trip to Tiger Data.
        with conn.cursor() as cur:
            with cur.copy("copy readings (time, run_id, sensor, value, unit, provenance) from stdin") as copy:
                for row in rows:
                    copy.write_row(row)
    return len(rows)


def get_readings(conn: psycopg.Connection, run_id: uuid.UUID, sensors: list[str] | None = None,
                 t_start: datetime | None = None, t_end: datetime | None = None) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """select time, sensor, value, unit, provenance from readings
               where run_id = %s
                 and (%s::text[] is null or sensor = any(%s::text[]))
                 and (%s::timestamptz is null or time >= %s::timestamptz)
                 and (%s::timestamptz is null or time <= %s::timestamptz)
               order by time""",
            (run_id, sensors, sensors, t_start, t_start, t_end, t_end),
        )
        return cur.fetchall()


def get_readings_1s(conn: psycopg.Connection, run_id: uuid.UUID) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "select bucket, sensor, avg, min, max, n from readings_1s where run_id = %s order by bucket",
            (run_id,),
        )
        return cur.fetchall()


# --------------------------------------------------------------------- frames

def insert_frame(conn: psycopg.Connection, run_id: uuid.UUID, frame_id: uuid.UUID, t: datetime, url: str,
                 reason: str | None, roi: dict | None, metrics: dict | None) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """insert into frames (id, run_id, t, url, reason, roi, metrics) values (%s, %s, %s, %s, %s, %s, %s)
               on conflict (id) do nothing returning *""",
            (frame_id, run_id, t, url, reason, Jsonb(roi) if roi else None, Jsonb(_clean(metrics)) if metrics else None),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute("select * from frames where id = %s", (frame_id,))
            row = cur.fetchone()
        return row


def get_frames(conn: psycopg.Connection, run_id: uuid.UUID) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("select * from frames where run_id = %s order by t", (run_id,))
        return cur.fetchall()


# --------------------------------------------------------------------- events

def append_events(conn: psycopg.Connection, run_id: uuid.UUID, items: list[dict]) -> list[dict]:
    """Append events to the run's chain. Idempotent on client-supplied ids.

    The hash is computed from the row as Postgres stored it (after jsonb and
    timestamptz normalization) so /verify recomputes exactly the same bytes.
    """
    out: list[dict] = []
    with conn.cursor() as cur:
        cur.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (str(run_id),))
        ids = [uuid.UUID(str(i["id"])) for i in items if i.get("id")]
        existing: set[uuid.UUID] = set()
        if ids:
            cur.execute("select id from events where id = any(%s)", (ids,))
            existing = {r["id"] for r in cur.fetchall()}
        cur.execute("select seq, hash from events where run_id = %s order by seq desc limit 1", (run_id,))
        last = cur.fetchone()
        seq = last["seq"] + 1 if last else 0
        prev = last["hash"] if last else chain.GENESIS

        for item in items:
            eid = uuid.UUID(str(item["id"])) if item.get("id") else uuid.uuid4()
            if eid in existing:
                continue
            prov = item.get("provenance", "measured")
            if prov not in PROVENANCES:
                raise ValueError(f"bad provenance {prov}")
            frame_ids = [uuid.UUID(str(f)) for f in item.get("frame_ids") or []]
            payload = _clean(item.get("payload")) if item.get("payload") is not None else None
            conf = item.get("confidence")
            cur.execute(
                """insert into events (id, run_id, t, seq, kind, summary, payload, provenance, confidence, frame_ids, prev_hash, hash)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                   returning id, run_id, t, seq, kind, summary, payload, provenance, confidence, frame_ids, prev_hash""",
                (eid, run_id, as_dt(item["t"]), seq, item["kind"], item["summary"],
                 Jsonb(payload) if payload is not None else None, prov,
                 float(conf) if conf is not None else None, frame_ids, prev),
            )
            row = cur.fetchone()
            row["hash"] = chain.compute_hash(prev, row)
            cur.execute("update events set hash = %s where id = %s", (row["hash"], eid))
            out.append(row)
            prev = row["hash"]
            seq += 1
    return out


def get_events(conn: psycopg.Connection, run_id: uuid.UUID, order: str = "seq") -> list[dict]:
    col = "seq" if order == "seq" else "t, seq"
    with conn.cursor() as cur:
        cur.execute(
            f"""select id, run_id, t, seq, kind, summary, payload, provenance, confidence, frame_ids, prev_hash, hash
                from events where run_id = %s order by {col}""",
            (run_id,),
        )
        return cur.fetchall()


def get_event(conn: psycopg.Connection, event_id: uuid.UUID) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """select id, run_id, t, seq, kind, summary, payload, provenance, confidence, frame_ids, prev_hash, hash
               from events where id = %s""",
            (event_id,),
        )
        return cur.fetchone()


# ------------------------------------------------------------------- analyses

def insert_analysis(conn: psycopg.Connection, kind: str, run_ids: list, content: dict,
                    cache_key: str | None = None, model: str | None = None) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """insert into analyses (kind, run_ids, cache_key, model, content)
               values (%s, %s, %s, %s, %s) returning *""",
            (kind, [uuid.UUID(str(r)) for r in run_ids], cache_key, model, Jsonb(_clean(content))),
        )
        return cur.fetchone()


def find_analysis(conn: psycopg.Connection, kind: str, cache_key: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            "select * from analyses where kind = %s and cache_key = %s order by created_at desc limit 1",
            (kind, cache_key),
        )
        return cur.fetchone()


def get_analysis(conn: psycopg.Connection, analysis_id: uuid.UUID) -> dict | None:
    with conn.cursor() as cur:
        cur.execute("select * from analyses where id = %s", (analysis_id,))
        return cur.fetchone()


def list_analyses(conn: psycopg.Connection, kind: str | None = None, run_id: uuid.UUID | None = None) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """select * from analyses
               where (%s::text is null or kind = %s::text)
                 and (%s::uuid is null or %s::uuid = any(run_ids))
               order by created_at desc""",
            (kind, kind, run_id, run_id),
        )
        return cur.fetchall()


def to_json(obj: Any) -> Any:
    """Serialize DB rows for API responses."""
    return json.loads(json.dumps(obj, default=lambda o: chain.iso_utc(o) if isinstance(o, datetime) else str(o)))
