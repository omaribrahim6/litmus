"""Evidence catalogs: short aliases (E1, E2, ...) for the evidence a prompt may cite.

Models copy short tokens reliably; long UUIDs get mangled. The validator maps
aliases back to real evidence IDs and rejects anything not in the catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Catalog:
    by_alias: dict[str, str] = field(default_factory=dict)
    by_id: dict[str, str] = field(default_factory=dict)
    meta: dict[str, dict] = field(default_factory=dict)  # real id -> {"item": key, "measured": bool, "desc": str}

    def add(self, eid: str, desc: str = "", item: str | None = None, measured: bool = False) -> str:
        if eid in self.by_id:
            m = self.meta[eid]
            m["measured"] = m["measured"] or measured
            if item and item not in m["items"]:
                m["items"].append(item)
            return self.by_id[eid]
        alias = f"E{len(self.by_alias) + 1}"
        self.by_alias[alias] = eid
        self.by_id[eid] = alias
        self.meta[eid] = {"items": [item] if item else [], "measured": measured, "desc": desc}
        return alias

    def resolve(self, token: str) -> str | None:
        token = token.strip().strip("[]")
        if token in self.by_alias:
            return self.by_alias[token]
        if token in self.by_id:
            return token
        return None

    def listing(self) -> list[dict]:
        return [{"alias": a, "id_type": eid.split(":", 1)[0], "describes": self.meta[eid]["desc"]}
                for a, eid in self.by_alias.items()]


def _desc(eid: str, what: str) -> str:
    kind = eid.split(":", 1)[0]
    noun = {"evt": "commit", "frm": "video frame", "ser": "sensor series", "rdg": "sensor reading", "run": "run record"}.get(kind, kind)
    return f"{noun}: {what}"


def from_diff(diff: dict) -> Catalog:
    cat = Catalog()
    res = diff["result"]
    for side in ("candidate", "control"):
        for eid in res[side]["evidence_ids"]:
            cat.add(eid, _desc(eid, f"{res['label']} ({side})"), res["key"], measured=True)
    a = diff.get("assumed_cause") or {}
    for eid in a.get("evidence_ids", []):
        cat.add(eid, _desc(eid, "assumed cause / related measurement"), None, measured=not eid.startswith("run:"))
    for item in diff["differences"]:
        measured = item["status"] != "missing_evidence"
        for side in ("candidate", "control"):
            for eid in item[side]["evidence_ids"]:
                cat.add(eid, _desc(eid, f"{item['label']} ({side})"), item["key"], measured=measured)
    cat.add(f"run:{diff['candidate']['run_id']}", _desc("run:", f"{diff['candidate']['label']} run record"))
    for c in diff["controls"]:
        cat.add(f"run:{c['run_id']}", _desc("run:", f"{c['label']} run record"))
    return cat
