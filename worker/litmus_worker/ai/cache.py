"""Cache slow AI results on disk (demo/cache) and in the analyses table.

The disk copy keeps the demo alive with no network: a cached verdict, report
or chat answer is replayed exactly as it was first produced.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..chain import canonical_json
from ..config import settings


def key_for(*parts: Any) -> str:
    return hashlib.sha256(canonical_json(parts).encode("utf-8")).hexdigest()[:32]


def _path(kind: str, key: str) -> Path:
    return settings.cache_dir / kind / f"{key}.json"


def read(kind: str, key: str) -> dict | None:
    p = _path(kind, key)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def write(kind: str, key: str, value: dict) -> None:
    p = _path(kind, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
