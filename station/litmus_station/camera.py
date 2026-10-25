"""Webcam capture: color metrics in the tube ROI, keyframes, and the run video.

Exposure and white balance are locked so color readings stay comparable
across a run (auto-exposure would otherwise "correct" the color flip away).
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from litmus_core.color import blocked_or_dark, roi_metrics

log = logging.getLogger("litmus.camera")


def lock_exposure(index: int) -> None:
    """Disable auto exposure / white balance on a UVC webcam (Linux, v4l2-ctl)."""
    if platform.system() != "Linux" or not shutil.which("v4l2-ctl"):
        return
    dev = f"/dev/video{index}"
    for ctrl in ("auto_exposure=1", "exposure_auto=1", "white_balance_automatic=0", "white_balance_temperature_auto=0", "focus_automatic_continuous=0"):
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", ctrl], capture_output=True)


class Camera:
    def __init__(self, source: int | str, roi: dict, simulate=None, lock: bool = True):
        self.source, self.roi, self.simulate = source, roi, simulate
        self.available = False
        self.detail = "starting"
        self._cap: cv2.VideoCapture | None = None
        self._frame: np.ndarray | None = None
        self._frame_t = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._writer: cv2.VideoWriter | None = None
        self._video_path: Path | None = None
        self.video_started_at: float | None = None
        self.fps = 15
        if simulate is None:
            if lock and isinstance(source, int):
                lock_exposure(source)
            self._cap = cv2.VideoCapture(source)
            if self._cap.isOpened():
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                self.available, self.detail = True, f"camera {source}"
            else:
                self.detail = "camera not found"
        else:
            self.available, self.detail = True, "simulated camera"
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _render_sim(self) -> np.ndarray:
        p = self.simulate.flip_progress()
        color = np.array([40, 205, 235]) * (1 - p) + np.array([95, 45, 215]) * p
        img = np.full((360, 640, 3), (38, 36, 34), dtype=np.uint8)
        cv2.rectangle(img, (275, 105), (365, 300), (230, 230, 230), 3)
        cv2.rectangle(img, (279, 160), (361, 296), tuple(int(c) for c in color), -1)
        cv2.putText(img, f"SIMULATED  base {self.simulate.base_ml:.1f} mL", (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
        return img

    def _loop(self) -> None:
        period = 1 / 30
        while not self._stop.is_set():
            if self.simulate is not None:
                frame = self._render_sim()
                time.sleep(period)
            else:
                ok, frame = self._cap.read() if self._cap else (False, None)
                if not ok:
                    if isinstance(self.source, str):  # replaying a recorded file: loop it
                        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    self.available, self.detail = False, "camera disconnected"
                    time.sleep(0.5)
                    continue
                if isinstance(self.source, str):
                    time.sleep(period)
            with self._lock:
                self._frame, self._frame_t = frame, time.time()
                self.available = True
                if self._writer is not None:
                    # Keep video time locked to wall-clock time: duplicate frames when the camera
                    # is slower than the target fps, skip them when it is faster.
                    due = int((time.time() - self.video_started_at) * self.fps) + 1
                    if due > self._written:
                        small = cv2.resize(frame, self._video_size)
                        for _ in range(due - self._written):
                            self._writer.write(small)
                        self._written = due

    def latest(self) -> tuple[np.ndarray | None, float]:
        with self._lock:
            return (None if self._frame is None else self._frame.copy()), self._frame_t

    def metrics(self) -> dict | None:
        frame, t = self.latest()
        if frame is None or time.time() - t > 2.0:
            return None
        m = roi_metrics(frame, self.roi)
        m["blocked"] = blocked_or_dark(m)
        return m

    def jpeg(self, quality: int = 82) -> tuple[bytes, float] | None:
        frame, t = self.latest()
        if frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return (buf.tobytes(), t) if ok else None

    def start_recording(self, path: Path, fps: int = 15) -> None:
        frame, _ = self.latest()
        h, w = (frame.shape[:2] if frame is not None else (720, 1280))
        scale = min(1.0, 960 / w)
        self._video_size = (int(w * scale) // 2 * 2, int(h * scale) // 2 * 2)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, self._video_size)
            self._video_path = path
            self.video_started_at = time.time()
            self.fps = fps
            self._written = 0

    def stop_recording(self) -> Path | None:
        """Close the raw recording and transcode it to browser-playable H.264."""
        with self._lock:
            writer, path = self._writer, self._video_path
            self._writer = None
        if writer is None or path is None:
            return None
        writer.release()
        if not shutil.which("ffmpeg"):
            return path
        out = path.with_name(path.stem + "_h264.mp4")
        res = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-c:v", "libx264", "-preset", "veryfast",
                              "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], capture_output=True)
        return out if res.returncode == 0 else path

    def close(self) -> None:
        self._stop.set()
        if self._cap:
            self._cap.release()
