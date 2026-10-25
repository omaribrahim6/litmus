"""Station configuration: environment variables plus an optional station.json.

station.json maps physical wiring to drivers, for example:

    {
      "adc": "grove",                          # grove | ads1115 | none
      "light":       {"channel": 0},           # analog light sensor on A0
      "mix_angle":   {"channel": 2, "max_deg": 300},
      "air_quality": {"channel": 4},
      "light_rc_pin": null,                    # GPIO pin for an LDR + capacitor when there is no ADC
      "ds18b20": true,                         # 1-Wire probe on GPIO4
      "dht22_pin": null,
      "confirm_button_pin": 17,
      "camera": 0,                             # index, or a path to a recorded video for replay
      "lock_exposure": true
    }
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or "").strip() or default


@dataclass
class StationConfig:
    worker_url: str = field(default_factory=lambda: _env("WORKER_URL", "http://localhost:8000").rstrip("/"))
    worker_token: str = field(default_factory=lambda: _env("WORKER_TOKEN"))
    station_id: str = field(default_factory=lambda: _env("STATION_ID", "bench-1"))
    experiment: str = field(default_factory=lambda: _env("EXPERIMENT_ID", "vinegar-titration"))
    data_dir: Path = field(default_factory=lambda: Path(_env("STATION_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data"))))
    hardware: dict = field(default_factory=dict)
    sensor_hz: float = 2.0
    color_hz: float = 6.0
    keyframe_every_s: float = 2.0
    video_fps: int = 15

    @classmethod
    def load(cls) -> "StationConfig":
        cfg = cls()
        path = Path(_env("STATION_CONFIG", str(Path(__file__).resolve().parents[1] / "station.json")))
        if path.exists():
            cfg.hardware = json.loads(path.read_text(encoding="utf-8"))
        cfg.hardware.setdefault("adc", _env("ADC_DRIVER", "none"))
        cam = _env("CAMERA_INDEX")
        if cam:
            cfg.hardware["camera"] = int(cam) if cam.isdigit() else cam
        cfg.hardware.setdefault("camera", 0)
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        return cfg
