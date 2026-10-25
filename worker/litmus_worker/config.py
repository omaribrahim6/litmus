from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    return value or default


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL"))
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    model_flash: str = field(default_factory=lambda: _env("GEMINI_MODEL_FLASH", "gemini-2.5-flash"))
    model_flash_lite: str = field(default_factory=lambda: _env("GEMINI_MODEL_FLASH_LITE", "gemini-2.5-flash-lite"))
    model_pro: str = field(default_factory=lambda: _env("GEMINI_MODEL_PRO", "gemini-2.5-pro"))
    model_embed: str = field(default_factory=lambda: _env("GEMINI_MODEL_EMBED", "gemini-embedding-001"))
    model_tts: str = field(default_factory=lambda: _env("GEMINI_MODEL_TTS", "gemini-2.5-flash-preview-tts"))
    use_vertex: bool = field(default_factory=lambda: _env("GOOGLE_GENAI_USE_VERTEXAI").lower() in ("1", "true"))
    worker_token: str = field(default_factory=lambda: _env("WORKER_TOKEN"))
    media_dir: Path = field(default_factory=lambda: Path(_env("MEDIA_DIR", str(ROOT / "worker" / "media"))))
    public_url: str = field(default_factory=lambda: _env("PUBLIC_WORKER_URL", "http://localhost:8000").rstrip("/"))
    cors_origins: list[str] = field(
        default_factory=lambda: [o.strip() for o in _env("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    )
    demo_dir: Path = ROOT / "demo"
    experiments_dir: Path = ROOT / "db" / "experiments"

    @property
    def cache_dir(self) -> Path:
        return self.demo_dir / "cache"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key) or self.use_vertex


settings = Settings()
