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


def resolve_device(source: int | str) -> int | str:
    """'auto' (or an index on Linux) -> the webcam's current /dev/video node via its stable USB id.

    USB webcams change /dev/videoN when replugged; /dev/v4l/by-id names do not.
    """
    if platform.system() != "Linux" or not (source == "auto" or isinstance(source, int)):
        return 0 if source == "auto" else source
    ids = sorted(Path("/dev/v4l/by-id").glob("*-video-index0")) if Path("/dev/v4l/by-id").exists() else []
    if ids:
        return str(ids[0].resolve())
    return source if isinstance(source, int) else 0


def lock_exposure(device: int | str) -> None:
    """Disable auto exposure / white balance on a UVC webcam (Linux, v4l2-ctl)."""
    if platform.system() != "Linux" or not shutil.which("v4l2-ctl"):
        return
    dev = device if isinstance(device, str) else f"/dev/video{device}"
    for ctrl in ("auto_exposure=1", "exposure_auto=1", "white_balance_automatic=0", "white_balance_temperature_auto=0", "focus_automatic_continuous=0"):
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", ctrl], capture_output=True)


class Camera:
    def __init__(self, source: int | str, roi: dict, simulate=None, lock: bool = True):
        self.source, self.roi, self.simulate, self.lock = source, roi, simulate, lock
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
        self._stream = isinstance(source, str) and source.startswith(("http://", "https://", "rtsp://"))
        self._usb = source == "auto" or isinstance(source, int) or (isinstance(source, str) and source.startswith("/dev/"))
        self._replay = isinstance(source, str) and not self._stream and not self._usb
        if simulate is None:
            self._open()
            self.detail = f"camera {self._device}" if self._cap.isOpened() else "camera not found"
            self.available = self._cap.isOpened()
        else:
            self.available, self.detail = True, "simulated camera"
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _open(self) -> None:
        """(Re)open the source; USB webcams are re-resolved since their /dev node can change."""
        if self._cap is not None:
            self._cap.release()
        self._device = resolve_device(self.source) if self._usb else self.source
        if self._usb and self.lock:
            lock_exposure(self._device)
        if self._usb and isinstance(self._device, str):
            self._cap = cv2.VideoCapture(self._device, cv2.CAP_V4L2)
        else:
            self._cap = cv2.VideoCapture(self._device)
        if self._cap.isOpened() and not self._stream:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

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
                    if self._replay:  # replaying a recorded file: loop it
                        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    self.available, self.detail = False, "camera disconnected"
                    time.sleep(1.0)
                    # Unplugged USB webcam or dropped phone stream: reopen until it comes back.
                    self._open()
                    continue
                if self._replay:
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

    def motion(self) -> float | None:
        """How much the area around the tube changed since the last call (0-1).

        Used to measure mixing without a rotary sensor: rotating the holder
        moves the tube, so the region around it changes sharply.
        """
        frame, t = self.latest()
        if frame is None or time.time() - t > 2.0:
            return None
        h, w = frame.shape[:2]
        r = self.roi
        cx, cy = (r["x"] + r["w"] / 2) * w, (r["y"] + r["h"] / 2) * h
        hw, hh = r["w"] * w * 1.5, r["h"] * h * 1.2  # a box about 3x the ROI width around the tube
        x0, x1 = int(max(0, cx - hw)), int(min(w, cx + hw))
        y0, y1 = int(max(0, cy - hh)), int(min(h, cy + hh))
        gray = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)
        prev, self._motion_prev = getattr(self, "_motion_prev", None), gray
        if prev is None:
            return 0.0
        return float(np.mean(np.abs(gray - prev)) / 255.0)

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
