"""Hash chain over each run's events (the commits).

hash_n = sha256(hash_{n-1} + canonical_json(event_n)). Computed here, never by
a model. Editing, deleting or reordering any committed event breaks every
hash after it, which /verify/{run_id} reports.

The run_sealed event also commits a digest of every reading and frame in the
run, so tampering with raw sensor rows is detected too.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable

GENESIS = "0" * 64


def iso_utc(t: datetime) -> str:
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def event_body(ev: dict) -> dict:
    """The exact fields covered by the hash. The embedding is a derived index and is excluded."""
    return {
        "run_id": str(ev["run_id"]),
        "seq": int(ev["seq"]),
        "t": iso_utc(ev["t"]),
        "kind": ev["kind"],
        "summary": ev["summary"],
        "payload": ev.get("payload"),
        "provenance": ev["provenance"],
        "confidence": ev.get("confidence"),
        "frame_ids": [str(f) for f in (ev.get("frame_ids") or [])],
    }


def compute_hash(prev_hash: str, ev: dict) -> str:
    return hashlib.sha256((prev_hash + canonical_json(event_body(ev))).encode("utf-8")).hexdigest()


def readings_digest(rows: Iterable[dict]) -> dict:
    """Order-independent digest of reading rows: sorted canonical lines, then sha256."""
    lines = sorted(
        canonical_json([iso_utc(r["time"]), r["sensor"], r["value"], r.get("unit"), r["provenance"]]) for r in rows
    )
    h = hashlib.sha256()
    for line in lines:
        h.update(line.encode("utf-8"))
        h.update(b"\n")
    return {"count": len(lines), "sha256": h.hexdigest()}


def frames_digest(rows: Iterable[dict]) -> dict:
    lines = sorted(canonical_json([str(r["id"]), iso_utc(r["t"]), r["url"]]) for r in rows)
    h = hashlib.sha256()
    for line in lines:
        h.update(line.encode("utf-8"))
        h.update(b"\n")
    return {"count": len(lines), "sha256": h.hexdigest()}


def verify_events(events: list[dict]) -> dict:
    """Recompute the chain. events must be ordered by seq."""
    prev = GENESIS
    for i, ev in enumerate(events):
        if ev["seq"] != i:
            return {"intact": False, "checked": i, "broken_at_seq": i, "reason": f"sequence gap: expected seq {i}, found {ev['seq']}", "event_id": str(ev["id"])}
        if (ev.get("prev_hash") or GENESIS) != prev:
            return {"intact": False, "checked": i, "broken_at_seq": i, "reason": "prev_hash does not match the previous commit", "event_id": str(ev["id"])}
        expected = compute_hash(prev, ev)
        if expected != ev["hash"]:
            return {"intact": False, "checked": i, "broken_at_seq": i, "reason": "event content does not match its hash (edited after commit)", "event_id": str(ev["id"])}
        prev = ev["hash"]
    return {"intact": True, "checked": len(events), "head": prev}
