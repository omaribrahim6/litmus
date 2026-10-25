"""Re-validate citations in cached Ask answers without calling Gemini.

    python -m litmus_worker.ai.refinalize

Writes a corrected copy of each cached answer as a new analyses row (rows are
never edited in place); lookups return the newest row for a question.
"""

from __future__ import annotations

from .. import db, store
from .chat import Toolbox, finalize_answer


def main() -> None:
    with db.connect() as conn:
        exp = store.get_experiment(conn, "vinegar-titration")
        rows = conn.execute("select * from analyses where kind = 'chat' order by created_at").fetchall()
        latest: dict[str, dict] = {}
        for r in rows:
            latest[r["cache_key"]] = r
        for key, r in latest.items():
            c = r["content"]
            tb = Toolbox(conn, exp)
            for ch in c.get("charts", []):
                tb.seen_ids.update(d["evidence_id"] for d in ch.get("data", []))
            fixed = finalize_answer(c["text"], tb)
            if fixed["citations"] == c.get("citations") and fixed["text"] == c["text"]:
                continue
            store.insert_analysis(conn, "chat", [], {**c, **fixed}, cache_key=key, model=r["model"])
            print(f"{c.get('question', '')[:50]}: {len(c.get('citations', []))} -> {len(fixed['citations'])} citations")


if __name__ == "__main__":
    main()
