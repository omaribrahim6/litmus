"""In-memory view of one run, used by the measurement and diff code.

Kept independent of the database so the same code runs over live rows or an
offline demo snapshot.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

import psycopg

from . import store


@dataclass
class RunData:
    run: dict
    events: list[dict]                                   # ordered by time
    readings: dict[str, list[tuple[float, float, str]]]  # sensor -> [(epoch s, value, provenance)]
    units: dict[str, str | None] = field(default_factory=dict)
    frames: list[dict] = field(default_factory=list)

    @property
    def id(self) -> uuid.UUID:
        return self.run["id"]

    @property
    def label(self) -> str:
        return self.run.get("label") or str(self.run["id"])[:8]

    def events_of(self, kind: str) -> list[dict]:
        return [e for e in self.events if e["kind"] == kind]

    def flip_event(self) -> dict | None:
        flips = [e for e in self.events_of("flip_detected") if (e.get("payload") or {}).get("source", "camera") == "camera"]
        flips = flips or self.events_of("flip_detected")
        return flips[0] if flips else None


def _ts(t: datetime) -> float:
    return t.timestamp()


def from_rows(run: dict, events: list[dict], readings: list[dict], frames: list[dict]) -> RunData:
    by_sensor: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    units: dict[str, str | None] = {}
    for r in readings:
        by_sensor[r["sensor"]].append((_ts(r.get("time") or r["t"]), r["value"], r["provenance"]))
        units.setdefault(r["sensor"], r.get("unit"))
    for s in by_sensor.values():
        s.sort()
    return RunData(
        run=run,
        events=sorted(events, key=lambda e: (e["t"], e["seq"])),
        readings=dict(by_sensor),
        units=units,
        frames=frames,
    )


def load(conn: psycopg.Connection, run_id: uuid.UUID | str) -> RunData:
    rid = uuid.UUID(str(run_id))
    run = store.get_run(conn, rid)
    if run is None:
        raise KeyError(f"run {run_id} not found")
    return from_rows(run, store.get_events(conn, rid), store.get_readings(conn, rid), store.get_frames(conn, rid))
