"""Microphones: every source records continuously; each utterance is taken
from whichever mic heard it most clearly.

Sources (configure "mics" in station.json):
  {"name": "webcam", "device": null}                          sound card via sounddevice (or arecord)
  {"name": "phone",  "url": "http://<phone-ip>:8080/audio.wav"}  phone stream via ffmpeg
  {"name": "usb",    "alsa": "plughw:2,0"}                     ALSA device via ffmpeg

Utterances are cut at natural pauses. The source is chosen by signal-to-noise
(speech peaks against that mic's own noise floor), so a researcher near the
phone is taken from the phone and one near the webcam from the webcam. This
is deterministic; only the chosen clip is sent to Gemini.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger("litmus.audio")

RATE = 16000
BLOCK = 1600          # 0.1 s
KEEP_S = 300          # ring buffer length per source
FRAME = 320           # 20 ms analysis frames


class Source:
    """A microphone feeding int16 mono 16 kHz blocks, each stamped with its wall-clock end time."""

    def __init__(self, name: str):
        self.name = name
        self.available = False
        self.detail = "starting"
        self._buf: deque[tuple[float, np.ndarray]] = deque(maxlen=int(KEEP_S * RATE / BLOCK))
        self._lock = threading.Lock()

    def _push(self, block: np.ndarray) -> None:
        with self._lock:
            self._buf.append((time.time(), block))
        self.available = True

    def window(self, t0: float, t1: float) -> np.ndarray:
        with self._lock:
            blocks = [b for t, b in self._buf if t0 < t <= t1 + 0.05]
        return np.concatenate(blocks) if blocks else np.zeros(0, dtype=np.int16)

    def level(self) -> float:
        x = self.window(time.time() - 0.3, time.time()).astype(np.float32) / 32768.0
        return float(min(1.0, np.sqrt(np.mean(x * x)) * 8)) if x.size else 0.0


class SoundDeviceSource(Source):
    def __init__(self, name: str, device=None):
        super().__init__(name)
        import sounddevice as sd
        def cb(indata, frames, t, status):  # noqa: ARG001
            self._push(indata[:, 0].copy())
        try:
            self._stream = sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=BLOCK, device=device, callback=cb)
            self._stream.start()
            self.detail = f"sound card {device if device is not None else 'default'}"
        except Exception as exc:  # noqa: BLE001 - no such device
            self.detail = f"unavailable: {exc}"
            log.warning("mic %s unavailable: %s", name, exc)


class PipeSource(Source):
    """Raw PCM from a subprocess (ffmpeg for phone streams and ALSA, or arecord); reconnects if it drops."""

    def __init__(self, name: str, cmd: list[str], detail: str):
        super().__init__(name)
        self._cmd, self.detail = cmd, detail
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        while True:
            try:
                proc = subprocess.Popen(self._cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                while True:
                    raw = proc.stdout.read(BLOCK * 2)
                    if not raw:
                        break
                    self._push(np.frombuffer(raw, dtype=np.int16).copy())
            except OSError as exc:
                log.warning("mic %s failed: %s", self.name, exc)
            self.available = False
            time.sleep(2.0)


def build_sources(specs: list[dict] | None) -> list[Source]:
    specs = specs or [{"name": "station mic", "device": None}]
    out: list[Source] = []
    ffmpeg = shutil.which("ffmpeg")
    for s in specs:
        name = s.get("name", "mic")
        pcm = ["-f", "s16le", "-ac", "1", "-ar", str(RATE), "pipe:1"]
        if s.get("url") and ffmpeg:
            out.append(PipeSource(name, [ffmpeg, "-loglevel", "error", "-i", s["url"], *pcm], f"stream {s['url']}"))
        elif s.get("alsa") and ffmpeg:
            out.append(PipeSource(name, [ffmpeg, "-loglevel", "error", "-f", "alsa", "-i", s["alsa"], *pcm], f"ALSA {s['alsa']}"))
        else:
            try:
                out.append(SoundDeviceSource(name, s.get("device")))
            except Exception:  # noqa: BLE001 - PortAudio missing: fall back to arecord
                if shutil.which("arecord"):
                    cmd = ["arecord", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(RATE), "-c", "1"]
                    if s.get("device") is not None:
                        cmd += ["-D", str(s["device"])]
                    out.append(PipeSource(name, cmd, "arecord"))
    return out


def _frame_rms(x: np.ndarray) -> np.ndarray:
    if x.size < FRAME:
        return np.zeros(0)
    x = x.astype(np.float32) / 32768.0
    x = np.append(x[0], x[1:] - 0.97 * x[:-1])  # pre-emphasis: favor speech over hum and rumble
    n = x.size // FRAME
    return np.sqrt(np.mean(x[: n * FRAME].reshape(n, FRAME) ** 2, axis=1))


def speech_score(x: np.ndarray) -> float:
    """Signal-to-noise of speech in a clip: loud frames against this mic's own quiet frames."""
    rms = _frame_rms(x)
    if rms.size < 10:
        return 0.0
    return float(np.percentile(rms, 90) / max(np.percentile(rms, 20), 1e-4))


@dataclass
class Utterance:
    t0: float
    t1: float
    source: str
    scores: dict[str, float]
    samples: np.ndarray

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(self.samples.tobytes())
        return path


class AudioHub:
    SPEECH_SNR = 3.5     # below this, a clip is treated as silence
    PAUSE_S = 0.9        # silence that ends an utterance
    MIN_S, MAX_S = 2.5, 25.0

    def __init__(self, specs: list[dict] | None):
        self.sources = build_sources(specs)
        self.available = bool(self.sources)
        self.active: str | None = None

    def status(self) -> list[dict]:
        return [{"name": s.name, "available": s.available, "level": round(s.level(), 3), "detail": s.detail} for s in self.sources]

    def best(self, t0: float, t1: float) -> Utterance | None:
        clips = {s.name: s.window(t0, t1) for s in self.sources if s.available}
        if not clips:
            return None
        scores = {n: round(speech_score(c), 2) for n, c in clips.items()}
        name = max(scores, key=scores.get)
        self.active = name
        if scores[name] < self.SPEECH_SNR:
            return None
        return Utterance(t0, t1, name, scores, clips[name])

    def _quiet_tail(self, now: float) -> bool:
        for s in self.sources:
            rms = _frame_rms(s.window(now - self.PAUSE_S, now))
            floor = _frame_rms(s.window(now - 8, now))
            if rms.size and floor.size and rms.max() > 3 * max(np.percentile(floor, 20), 1e-4):
                return False
        return True

    def segment_ready(self, t0: float, now: float) -> bool:
        """Cut at a pause once the segment is long enough, or at the maximum length."""
        length = now - t0
        return length >= self.MAX_S or (length >= self.MIN_S and self._quiet_tail(now))
