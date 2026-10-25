"""Run the Litmus station.

    python -m litmus_station                 # real hardware (station.json describes the wiring)
    python -m litmus_station --simulate      # laptop development: simulated sensors and camera
    python -m litmus_station --camera demo/runs/live.mp4   # replay a recorded session as the camera
"""

from __future__ import annotations

import argparse
import logging

import uvicorn

from .config import StationConfig
from .kiosk import create_app
from .session import Session


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", action="store_true", help="simulated sensors and camera (runs are flagged synthetic)")
    ap.add_argument("--camera", help="camera index or a video file to replay")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    cfg = StationConfig.load()
    if args.camera is not None:
        cfg.hardware["camera"] = int(args.camera) if args.camera.isdigit() else args.camera
    session = Session(cfg, simulate=args.simulate)

    pin = cfg.hardware.get("confirm_button_pin")
    if pin is not None and not args.simulate:
        try:
            from gpiozero import Button  # type: ignore[import-not-found]
            button = Button(int(pin), bounce_time=0.15)
            button.when_pressed = session.confirm_step
        except Exception as exc:  # noqa: BLE001 - the touchscreen CONFIRM still works
            logging.warning("confirm button unavailable: %s", exc)

    uvicorn.run(create_app(session), host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
