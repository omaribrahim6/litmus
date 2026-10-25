"""Demo helper: edit one committed value directly in the database, then restore it.

    python -m litmus_worker.tamper <run_id>            # change a quantity, as someone fudging a result would
    python -m litmus_worker.tamper <run_id> --restore  # put the original back

Open the run in the web app between the two: the hash badge turns red and
names the commit that no longer matches its hash.
"""

from __future__ import annotations

import argparse
import json
import uuid

from psycopg.types.json import Jsonb

from . import db, lifecycle
from .config import settings

STASH = settings.cache_dir / "tamper.json"


def tamper(run_id: uuid.UUID) -> None:
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            """select id, seq, summary, payload from events
               where run_id = %s and kind = 'quantity_added' and payload->>'quantity' = 'base_ml'
               order by seq limit 1""",
            (run_id,),
        )
        ev = cur.fetchone()
        if ev is None:
            raise SystemExit("no base addition to edit in this run")
        STASH.parent.mkdir(parents=True, exist_ok=True)
        STASH.write_text(json.dumps({"id": str(ev["id"]), "summary": ev["summary"], "payload": ev["payload"]}), encoding="utf-8")
        payload = dict(ev["payload"], value=0.3)
        cur.execute("update events set payload = %s, summary = %s where id = %s",
                    (Jsonb(payload), ev["summary"].replace("0.5 mL", "0.3 mL"), ev["id"]))
        conn.commit()
        print(f"edited commit {ev['seq']}: base addition 0.5 mL -> 0.3 mL")
        print(json.dumps(lifecycle.verify(conn, run_id), default=str, indent=1))


def restore(run_id: uuid.UUID) -> None:
    saved = json.loads(STASH.read_text(encoding="utf-8"))
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("update events set payload = %s, summary = %s where id = %s",
                    (Jsonb(saved["payload"]), saved["summary"], uuid.UUID(saved["id"])))
        conn.commit()
        print(json.dumps(lifecycle.verify(conn, run_id), default=str, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    (restore if a.restore else tamper)(uuid.UUID(a.run_id))
