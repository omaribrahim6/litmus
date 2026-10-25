"""Export an offline snapshot for the web app's demo mode.

    python -m litmus_worker.export [--out ../web] [--runs id,id]

Writes web/demo-data/snapshot.json (runs, commits, readings, analyses,
verification) and copies every referenced frame and video into
web/public/media so the demo needs no database, worker or network.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import db, lifecycle, media, store
from .config import ROOT


def _ms(t) -> int:
    return int(round(t.timestamp() * 1000))


def export(out_root: Path, run_filter: set[str] | None = None, include_media: bool = True) -> dict:
    with db.connect() as conn:
        experiments = store.list_experiments(conn)
        runs = []
        for exp in experiments:
            runs += [r for r in store.list_runs(conn, exp["id"]) if r["status"] == "complete"]
        if run_filter:
            runs = [r for r in runs if str(r["id"]) in run_filter]
        snap = {"generated_at": None, "experiments": experiments, "runs": runs, "events": {}, "frames": {},
                "readings_1s": {}, "readings": {}, "verify": {}, "analyses": []}
        media_urls: set[str] = set()
        for r in runs:
            rid = r["id"]
            key = str(rid)
            snap["events"][key] = store.get_events(conn, rid, order="time")
            snap["frames"][key] = store.get_frames(conn, rid)
            snap["readings_1s"][key] = store.get_readings_1s(conn, rid)
            snap["readings"][key] = [[_ms(x["time"]), x["sensor"], x["value"], x["provenance"]] for x in store.get_readings(conn, rid)]
            snap["verify"][key] = lifecycle.verify(conn, rid)
            media_urls.update(f["url"] for f in snap["frames"][key])
            if r.get("video_url"):
                media_urls.add(r["video_url"])
        run_ids = {str(r["id"]) for r in runs}
        for a in store.list_analyses(conn):
            if a["kind"] == "chat" or not a["run_ids"] or {str(x) for x in a["run_ids"]} <= run_ids:
                snap["analyses"].append(a)
        with conn.cursor() as cur:
            cur.execute("select now() as now")
            snap["generated_at"] = cur.fetchone()["now"]

    data_dir = out_root / "demo-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = store.to_json(snap)
    (data_dir / "snapshot.json").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    copied = 0
    if include_media:
        for url in media_urls:
            src = media.local_path(url)
            if src and src.exists():
                dest = out_root / "public" / url.lstrip("/")
                if not dest.exists() or dest.stat().st_size != src.stat().st_size:
                    media.copy_into(src, dest)
                    copied += 1
    return {"runs": len(runs), "analyses": len(snap["analyses"]), "media": len(media_urls), "copied": copied,
            "bytes": (data_dir / "snapshot.json").stat().st_size}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "web"))
    ap.add_argument("--runs", default="")
    ap.add_argument("--no-media", action="store_true")
    args = ap.parse_args()
    runs = {r.strip() for r in args.runs.split(",") if r.strip()} or None
    print(export(Path(args.out), runs, include_media=not args.no_media))


if __name__ == "__main__":
    main()
