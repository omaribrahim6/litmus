"""Offline-safe uploads: everything goes through a local SQLite outbox first.

If the worker is unreachable (bad Wi-Fi), items wait on disk in order and are
flushed when it comes back. IDs are generated on the station, so retries are
idempotent on the worker side.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path

import requests

log = logging.getLogger("litmus.outbox")


class Outbox:
    def __init__(self, path: Path, worker_url: str, token: str = ""):
        self.worker_url = worker_url
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.execute("pragma journal_mode=wal")
        self._db.execute("""create table if not exists outbox (
            id integer primary key autoincrement, method text, path text, body text, file text, created real)""")
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self.online = False
        self.last_error: str | None = None
        threading.Thread(target=self._loop, daemon=True).start()

    def put(self, path: str, body: dict | None = None, file: str | None = None) -> None:
        with self._lock:
            self._db.execute("insert into outbox (method, path, body, file, created) values ('POST', ?, ?, ?, ?)",
                             (path, json.dumps(body, default=str) if body is not None else None, file, time.time()))
        self._wake.set()

    def pending(self) -> int:
        with self._lock:
            return self._db.execute("select count(*) from outbox").fetchone()[0]

    def _send(self, path: str, body: str | None, file: str | None) -> bool:
        url = f"{self.worker_url}{path}"
        if file:
            meta = json.loads(body) if body else {}
            with open(file, "rb") as fh:
                field = "file"
                mime = {".mp4": "video/mp4", ".wav": "audio/wav"}.get(Path(file).suffix.lower(), "image/jpeg")
                data = {"meta": json.dumps(meta)} if path.endswith(("/frames", "/narration")) else {k: str(v) for k, v in meta.items()}
                res = requests.post(url, files={field: (Path(file).name, fh, mime)}, data=data, headers=self.headers, timeout=120)
        else:
            res = requests.post(url, data=body, headers={**self.headers, "content-type": "application/json"}, timeout=15)
        if res.status_code == 409:
            log.warning("worker refused %s: run already sealed", path)
            return True  # drop: the record is sealed and can no longer change
        res.raise_for_status()
        return True

    def _next_batch(self) -> tuple[list[int], str, str | None, str | None] | None:
        """The oldest item, merged with directly following readings/events batches for the same run.

        Coalescing keeps the station caught up over a slow link: one request
        carries many seconds of readings instead of one request per second.
        """
        with self._lock:
            rows = self._db.execute("select id, path, body, file from outbox order by id limit 40").fetchall()
        if not rows:
            return None
        rid, path, body, file = rows[0]
        key = "readings" if path.endswith("/readings") else "events" if path.endswith("/events") else None
        if key is None or file:
            return [rid], path, body, file
        ids, merged = [rid], json.loads(body)[key]
        for r2, p2, b2, f2 in rows[1:]:
            if p2.endswith("/end"):
                break  # nothing may overtake the end of the run
            if p2 == path and not f2:
                ids.append(r2)
                merged += json.loads(b2)[key]
            elif key == "events" and not p2.endswith("/readings"):
                break  # events never overtake the frames they reference
        return ids, path, json.dumps({key: merged}), None

    def _loop(self) -> None:
        backoff = 1.0
        while True:
            batch = self._next_batch()
            if batch is None:
                self._wake.wait(1.0)
                self._wake.clear()
                continue
            ids, path, body, file = batch
            try:
                self._send(path, body, file)
                with self._lock:
                    self._db.executemany("delete from outbox where id = ?", [(i,) for i in ids])
                self.online, self.last_error, backoff = True, None, 1.0
            except (requests.RequestException, OSError) as exc:
                self.online, self.last_error = False, str(exc)[:200]
                log.info("worker unreachable, %d items buffered: %s", self.pending(), exc)
                time.sleep(backoff)
                backoff = min(backoff * 2, 15.0)

    def flush(self, timeout_s: float = 60.0) -> bool:
        deadline = time.time() + timeout_s
        while self.pending() and time.time() < deadline:
            self._wake.set()
            time.sleep(0.2)
        return self.pending() == 0
