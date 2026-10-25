"""Check Gemini credentials and model access.

    python -m litmus_worker.ai.check
"""

from __future__ import annotations

from pydantic import BaseModel

from ..config import settings
from .client import client, embed, generate_json


class Ping(BaseModel):
    ok: bool
    model_said: str


def main() -> None:
    mode = "Vertex AI" if settings.use_vertex else "Gemini API (AI Studio key)"
    print(f"mode: {mode}, enabled: {settings.ai_enabled}")
    c = client()
    try:
        names = sorted(m.name for m in c.models.list() if "gemini" in (m.name or ""))
        print(f"{len(names)} Gemini models visible, e.g.:", ", ".join(n.split("/")[-1] for n in names[-12:]))
    except Exception as exc:  # noqa: BLE001 - listing is informational
        print("model listing unavailable:", exc)
    for role, model in (("flash", settings.model_flash), ("pro", settings.model_pro)):
        try:
            out = generate_json(model, ["Reply with ok=true and one word."], Ping, retries=0)
            print(f"{role:5s} {model}: OK ({out.model_said})")
        except Exception as exc:  # noqa: BLE001
            print(f"{role:5s} {model}: FAILED {str(exc)[:200]}")
    try:
        v = embed(["color flip detected"])[0]
        print(f"embed {settings.model_embed}: OK ({len(v)} dims)")
    except Exception as exc:  # noqa: BLE001
        print(f"embed {settings.model_embed}: FAILED {str(exc)[:200]}")


if __name__ == "__main__":
    main()
