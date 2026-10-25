"""Seed experiments and (optionally) synthetic demo runs.

    python -m litmus_worker.seed                 # upsert experiment protocols from db/experiments
    python -m litmus_worker.seed --synthetic     # also generate 7 synthetic titration runs
    python -m litmus_worker.seed --reset-synthetic
"""

from __future__ import annotations

import argparse
import json
import uuid

import cv2
from litmus_core.color import roi_metrics

from . import db, fixtures, lifecycle, media, store
from .config import settings


def seed_experiments(conn) -> dict[str, dict]:
    out = {}
    for path in sorted(settings.experiments_dir.glob("*.json")):
        protocol = json.loads(path.read_text(encoding="utf-8"))
        out[protocol["slug"]] = store.upsert_experiment(conn, protocol)
        print(f"experiment {protocol['slug']}")
    return out


def reset_synthetic(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("select id from runs where (metadata->>'synthetic')::boolean")
        ids = [r["id"] for r in cur.fetchall()]
        if not ids:
            return
        cur.execute("delete from analyses where run_ids && %s", (ids,))
        cur.execute("delete from events where run_id = any(%s)", (ids,))
        cur.execute("delete from frames where run_id = any(%s)", (ids,))
        cur.execute("delete from readings where run_id = any(%s)", (ids,))
        cur.execute("update runs set parent_run_id = null where parent_run_id = any(%s)", (ids,))
        cur.execute("delete from runs where id = any(%s)", (ids,))
    print(f"removed {len(ids)} synthetic runs")


def seed_synthetic(conn, experiment: dict) -> list[uuid.UUID]:
    protocol = experiment["protocol"]
    created = []
    for spec in fixtures.demo_specs():
        syn = fixtures.generate(spec, protocol)
        r = syn.run
        store.create_run(conn, id=r["id"], experiment_id=experiment["id"], label=r["label"], role=r["role"],
                         station_id="synthetic", status="recording", started_at=r["started_at"],
                         assumed_cause=r["assumed_cause"], metadata=r["metadata"])
        store.insert_readings(conn, r["id"], syn.readings)
        for f in syn.frames:
            path, url = media.frame_path(r["id"], f["id"])
            ok, buf = cv2.imencode(".jpg", f["image"], [cv2.IMWRITE_JPEG_QUALITY, 82])
            media.save_bytes(buf.tobytes(), path)
            store.insert_frame(conn, r["id"], f["id"], f["t"], url, f["reason"], f["roi"], roi_metrics(f["image"], f["roi"]))
        store.append_events(conn, r["id"], syn.events)
        vpath, vurl = media.video_path(r["id"])
        fixtures.encode_video(syn.video_frames, syn.fps, vpath)
        store.update_run(conn, r["id"], video_url=vurl, metadata={"video_sha256": media.file_sha256(vpath)})
        run = lifecycle.finalize(conn, r["id"], r["ended_at"])
        conn.commit()
        print(f"{spec.label:12s} result={run['result'].get('value')} {run['result'].get('unit')}  id={r['id']}")
        created.append(r["id"])
    return created


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--reset-synthetic", action="store_true")
    args = ap.parse_args()
    with db.connect() as conn:
        exps = seed_experiments(conn)
        if args.reset_synthetic or args.synthetic:
            reset_synthetic(conn)
        conn.commit()
        if args.synthetic:
            seed_synthetic(conn, exps["vinegar-titration"])


if __name__ == "__main__":
    main()
