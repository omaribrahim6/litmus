"""Apply db/schema.sql to DATABASE_URL and run a smoke test.

Usage: python db/apply.py [--check-only]
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def split_statements(sql: str) -> list[str]:
    statements, buf = [], []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") and not buf:
            continue
        buf.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt and stmt != ";":
                statements.append(stmt)
            buf = []
    if "".join(buf).strip():
        statements.append("\n".join(buf))
    return statements


def smoke_test(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("select hypertable_name from timescaledb_information.hypertables")
        print("hypertables:", [r[0] for r in cur.fetchall()])
        cur.execute("select view_name, materialized_only from timescaledb_information.continuous_aggregates")
        print("continuous aggregates:", cur.fetchall())
        cur.execute("select indexname from pg_indexes where tablename = 'events' and indexdef ilike '%hnsw%'")
        print("vector index:", [r[0] for r in cur.fetchall()])

        run_id = uuid.uuid4()
        cur.execute("insert into runs (id, label, role, status, metadata) values (%s, 'smoke test', 'reference', 'failed', '{\"smoke\": true}')", (run_id,))
        cur.execute("insert into readings (time, run_id, sensor, value, unit) values (now(), %s, 'smoke', 1.5, 'x')", (run_id,))
        cur.execute("select value from readings where run_id = %s", (run_id,))
        assert cur.fetchone()[0] == 1.5
        cur.execute("select count(*) from readings_1s where run_id = %s", (run_id,))
        print("real-time aggregate rows for smoke run:", cur.fetchone()[0])
        conn.rollback()
        print("insert + select OK (rolled back)")


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set")
    with psycopg.connect(url, autocommit=True) as conn:
        if "--check-only" not in sys.argv:
            for stmt in split_statements((ROOT / "db" / "schema.sql").read_text()):
                conn.execute(stmt)
            print("schema applied")
        conn.autocommit = False
        smoke_test(conn)


if __name__ == "__main__":
    main()
