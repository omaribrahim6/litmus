"""Precompute everything the demo shows, then export the offline snapshot.

    python -m litmus_worker.prepare_demo

Runs the litmus test on every candidate, writes its report, answers the
suggested Ask questions (cached for offline replay), embeds commits,
computes validation numbers and exports web/demo-data + web/public/media.
"""

from __future__ import annotations

from pathlib import Path

from . import analysis, db, export, store, validate
from .ai import chat, perception
from .config import ROOT

QUESTIONS = [
    "Graph base added across all runs, formatted for a paper.",
    "Why was Method B different?",
    "What did I do differently in trial 4?",
    "Write the methods section as it actually happened.",
]


def main() -> None:
    print("embedded", perception.embed_all(), "commits")
    with db.connect() as conn:
        exp = store.get_experiment(conn, "vinegar-titration")
        for run in store.list_runs(conn, exp["id"]):
            if run["role"] not in ("candidate", "rerun") or run["status"] != "complete":
                continue
            d = analysis.run_diff(conn, run["id"])
            conn.commit()
            v = analysis.run_verdict(conn, d)
            conn.commit()
            r = analysis.run_report(conn, v)
            conn.commit()
            print(f"{run['label']}: verdict {v['id']} ({v['model']}), report {r['id']}")
        for q in QUESTIONS:
            a = chat.ask(conn, exp, [{"role": "user", "text": q}], {"page": "history"})
            conn.commit()
            print(f"asked: {q[:40]}... -> {a['model']}, {len(a['citations'])} citations, {len(a['charts'])} charts")
    v = validate.compute()
    print("validation:", v["flip_timing"]["within_1s"], "/", v["flip_timing"]["n"], "flips within 1 s")
    print(export.export(Path(ROOT / "web")))


if __name__ == "__main__":
    main()
