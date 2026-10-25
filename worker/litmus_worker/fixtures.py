"""Synthetic titration runs for development, tests and an offline fallback.

Every run produced here is flagged metadata.synthetic = true and the UI labels
it as such. Real station recordings replace these for the demo.
"""

from __future__ import annotations

import random
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np

YELLOW_BGR = np.array([40, 205, 235], dtype=np.float64)
RED_BGR = np.array([95, 45, 215], dtype=np.float64)


@dataclass
class SynthSpec:
    label: str
    role: str
    start: datetime
    base_needed_ml: float
    water: str = "distilled"
    bottle: str = "Bottle A"
    inversions: list[int] = field(default_factory=list)  # per addition; padded with 3
    temp_c: float | None = 21.5
    air_quality: float = 118.0
    assumed_cause: str | None = None
    seed: int = 0


def demo_specs(day: datetime | None = None) -> list[SynthSpec]:
    day = day or datetime.now(timezone.utc).replace(hour=1, minute=0, second=0, microsecond=0)
    t = lambda m: day + timedelta(minutes=m)  # noqa: E731
    refs = [
        SynthSpec("Reference 1", "reference", t(0), 4.0, inversions=[3, 3, 3, 2, 3, 3, 3, 3], temp_c=21.2, air_quality=121, seed=11),
        SynthSpec("Reference 2", "reference", t(14), 4.5, inversions=[3, 3, 4, 3, 3, 3, 3, 3, 3], temp_c=22.4, air_quality=116, seed=12),
        SynthSpec("Reference 3", "reference", t(27), 4.0, inversions=[3, 2, 3, 3, 3, 3, 3, 3], temp_c=21.8, air_quality=124, seed=13),
        SynthSpec("Reference 4", "reference", t(41), 3.5, inversions=[3, 3, 3, 3, 4, 3, 3], temp_c=20.9, air_quality=113, seed=14),
        SynthSpec("Reference 5", "reference", t(55), 4.0, inversions=[3, 3, 3, 3, 3, 3, 2, 3], temp_c=22.0, air_quality=119, seed=15),
    ]
    control = SynthSpec("Method A", "control", t(80), 4.0, inversions=[3] * 8, temp_c=21.6, air_quality=120, seed=21)
    candidate = SynthSpec(
        "Method B", "candidate", t(96), 2.5, water="tap", inversions=[3, 3, 3, 3, 3], temp_c=22.6, air_quality=122,
        assumed_cause="Method B neutralized with less base because I stirred longer after each addition.", seed=22,
    )
    return refs + [control, candidate]


@dataclass
class Synth:
    run: dict
    readings: list[dict]
    events: list[dict]
    frames: list[dict]          # {"id","t","reason","roi","image": BGR array}
    video_frames: list[np.ndarray]
    fps: int


def _render(w: int, h: int, color: np.ndarray, t_s: float, overlay: str | None, jug: str | None,
            angle: float, label: str) -> np.ndarray:
    img = np.full((h, w, 3), (38, 36, 34), dtype=np.uint8)
    cv2.rectangle(img, (int(w * 0.30), int(h * 0.12)), (int(w * 0.70), int(h * 0.92)), (58, 56, 54), -1)
    # Tube in a holder; the holder visibly rotates while mixing.
    cx, cy = int(w * 0.5), int(h * 0.53)
    tube = np.zeros_like(img)
    cv2.rectangle(tube, (cx - int(w * 0.07), cy - int(h * 0.26)), (cx + int(w * 0.07), cy + int(h * 0.26)), (230, 230, 230), 3)
    cv2.rectangle(tube, (cx - int(w * 0.065), cy - int(h * 0.16)), (cx + int(w * 0.065), cy + int(h * 0.25)),
                  tuple(int(c) for c in color), -1)
    rot = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    tube = cv2.warpAffine(tube, rot, (w, h))
    mask = tube.any(axis=2)
    img[mask] = tube[mask]
    if jug:
        x0, y0 = int(w * 0.05), int(h * 0.45)
        fill = (205, 190, 150) if jug == "distilled" else (150, 160, 170)
        cv2.rectangle(img, (x0, y0), (x0 + int(w * 0.17), y0 + int(h * 0.42)), fill, -1)
        cv2.rectangle(img, (x0 + 6, y0 + 40), (x0 + int(w * 0.17) - 6, y0 + 80), (250, 250, 250), -1)
        cv2.putText(img, jug.upper(), (x0 + 10, y0 + 68), cv2.FONT_HERSHEY_SIMPLEX, 0.5 if jug == "distilled" else 0.7, (30, 30, 30), 2)
    if overlay:
        cv2.putText(img, overlay, (int(w * 0.74), int(h * 0.6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
    cv2.putText(img, f"SYNTHETIC  {label}  t+{t_s:5.1f}s", (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
    return img


def generate(spec: SynthSpec, protocol: dict, fps: int = 10, width: int = 640, height: int = 360) -> Synth:
    rng = random.Random(spec.seed)
    run_id = uuid.uuid4()
    t0 = spec.start
    T = lambda s: t0 + timedelta(seconds=s)  # noqa: E731

    events: list[dict] = []
    frames: list[dict] = []
    roi = protocol["roi"]

    def event(at: float, kind: str, summary: str, provenance: str, payload: dict | None = None,
              confidence: float | None = None, frame: bool = False) -> dict:
        e = {"id": uuid.uuid4(), "t": T(at), "kind": kind, "summary": summary, "provenance": provenance,
             "payload": payload, "confidence": confidence, "frame_ids": []}
        if frame:
            fid = uuid.uuid4()
            frames.append({"id": fid, "t": T(at), "at": at, "reason": "event", "roi": roi})
            e["frame_ids"] = [fid]
        events.append(e)
        return e

    # Protocol timeline (seconds from start).
    event(2.0, "step_confirmed", "Step confirmed: Measure the vinegar sample", "reported", {"step": "sample"})
    event(3.0, "quantity_added", "Added 10 mL vinegar sample", "reported", {"quantity": "sample_ml", "value": 10.0, "unit": "mL", "step": "sample"})
    event(4.0, "reagent_used", f"Vinegar from {spec.bottle}", "inferred",
          {"variable": "vinegar_bottle", "value": spec.bottle, "label": spec.bottle}, confidence=0.9, frame=True)
    event(8.0, "step_confirmed", "Step confirmed: Dilute with distilled water", "reported", {"step": "dilute"})
    jug_label = "distilled-water jug" if spec.water == "distilled" else "tap-water jug"
    event(9.5, "reagent_used", f"Diluted from the {jug_label}", "inferred",
          {"variable": "water_source", "value": spec.water, "label": jug_label.capitalize()}, confidence=0.92, frame=True)
    event(10.0, "quantity_added", "Added 20 mL water", "reported", {"quantity": "water_ml", "value": 20.0, "unit": "mL", "step": "dilute"})
    event(14.0, "step_confirmed", "Step confirmed: Add the indicator", "reported", {"step": "indicator"})
    event(15.0, "quantity_added", "Added 3 drops phenol red", "reported", {"quantity": "indicator_drops", "value": 3.0, "unit": "drops", "step": "indicator"})
    event(20.0, "step_confirmed", "Step confirmed: Titrate", "reported", {"step": "titrate"})

    n_add = int(round(spec.base_needed_ml / 0.5))
    inv = (spec.inversions + [3] * n_add)[:n_add]
    mix_windows: list[tuple[float, float]] = []
    add_t = 22.0
    total = 0.0
    for i in range(n_add):
        total += 0.5
        event(add_t, "quantity_added", f"Added 0.5 mL base (total {total:.1f} mL)", "reported",
              {"quantity": "base_ml", "value": 0.5, "unit": "mL", "step": "titrate", "total": round(total, 2)})
        mix_start = add_t + 1.0
        mix_end = mix_start + inv[i] * 1.6
        mix_windows.append((mix_start, mix_end))
        add_t = mix_end + rng.uniform(5.0, 7.0)
    flip_at = mix_windows[-1][1] + 0.4 + rng.uniform(0.0, 0.6)
    end_at = flip_at + 9.0
    event(flip_at + 4.0, "step_confirmed", "Step confirmed: Stop at the color flip", "reported", {"step": "endpoint"})

    def angle_at(s: float) -> float:
        for (a, b), n in zip(mix_windows, inv):
            if a <= s < b:
                phase = ((s - a) / 1.6) % 1.0
                return 180.0 * (phase / 0.4) if phase < 0.4 else (180.0 if phase < 0.55 else max(0.0, 180.0 * (1 - (phase - 0.55) / 0.4)))
        return 0.0

    def flip_progress(s: float) -> float:
        return float(np.clip((s - flip_at) / 1.2, 0.0, 1.0))

    readings: list[dict] = []
    s = 0.0
    while s <= end_at:
        p = flip_progress(s)
        # Color metrics follow the flip; small sensor noise throughout.
        lab_a = 4.0 + 30.0 * p + rng.gauss(0, 0.6)
        lab_l = 79.0 - 15.0 * p + rng.gauss(0, 0.4)
        lab_b = 62.0 - 36.0 * p + rng.gauss(0, 0.5)
        hue = (52.0 - 47.0 * p + rng.gauss(0, 0.8)) % 360
        light = 0.82 - 0.26 * float(np.clip((s - flip_at - 0.2) / 1.4, 0, 1)) + rng.gauss(0, 0.006)
        for sensor, value, unit in (
            ("lab_a", lab_a, "a*"), ("lab_l", lab_l, "L*"), ("lab_b", lab_b, "b*"), ("hue", hue, "deg"),
            ("darkness", 1 - lab_l / 100, "ratio"), ("light", light, "ratio"),
            ("air_quality", spec.air_quality + rng.gauss(0, 3), "raw"),
        ):
            readings.append({"t": T(s), "sensor": sensor, "value": round(value, 4), "unit": unit, "provenance": "measured"})
        s = round(s + 0.5, 3)
    s = 0.0
    while s <= end_at:
        readings.append({"t": T(s), "sensor": "mix_angle", "value": round(angle_at(s) + rng.gauss(0, 1.5), 2),
                         "unit": "deg", "provenance": "measured"})
        s = round(s + 0.2, 3)
    if spec.temp_c is not None:
        readings.append({"t": T(5.0), "sensor": "temp_c", "value": spec.temp_c, "unit": "°C", "provenance": "reported"})
        event(5.0, "reading_reported", f"Temperature entered from thermometer: {spec.temp_c:.1f} °C", "reported",
              {"sensor": "temp_c", "value": spec.temp_c, "unit": "°C"})

    for (a, b), n in zip(mix_windows, inv):
        event(b, "mix", f"Mixed: {n} inversions over {b - a:.1f} s", "measured", {"inversions": n, "duration_s": round(b - a, 2)})

    # Periodic keyframes every 4 s.
    k = 0.0
    while k <= end_at:
        frames.append({"id": uuid.uuid4(), "t": T(k), "at": k, "reason": "periodic", "roi": roi})
        k += 4.0

    def overlay_at(sec: float) -> tuple[str | None, str | None]:
        if 3.0 <= sec < 8.0:
            return spec.bottle, None
        if 8.0 <= sec < 13.0:
            return None, spec.water
        return None, None

    def color_at(sec: float) -> np.ndarray:
        p = flip_progress(sec)
        return YELLOW_BGR * (1 - p) + RED_BGR * p

    video_frames = []
    n_frames = int(end_at * fps) + 1
    for i in range(n_frames):
        sec = i / fps
        ov, jug = overlay_at(sec)
        video_frames.append(_render(width, height, color_at(sec), sec, ov, jug, angle_at(sec), spec.label))
    for f in frames:
        ov, jug = overlay_at(f["at"])
        f["image"] = _render(width, height, color_at(f["at"]), f["at"], ov, jug, angle_at(f["at"]), spec.label)

    events.sort(key=lambda e: e["t"])
    events.insert(0, {"id": uuid.uuid4(), "t": T(0.0), "kind": "run_started", "provenance": "measured",
                      "summary": f"Run started: {spec.label} ({spec.role})",
                      "payload": {"label": spec.label, "role": spec.role, "synthetic": True}, "confidence": None, "frame_ids": []})
    run = {"id": run_id, "label": spec.label, "role": spec.role, "started_at": t0, "ended_at": T(end_at),
           "assumed_cause": spec.assumed_cause, "status": "recording",
           "metadata": {"synthetic": True, "video_started_at": t0.isoformat(),
                        "available_sensors": ["light", "air_quality", "mix_angle", "camera"],
                        "missing_sensors": ["temp_probe", "humidity"]}}
    return Synth(run, readings, events, frames, video_frames, fps)


def encode_video(frames: list[np.ndarray], fps: int, dest: Path) -> None:
    """Encode BGR frames to browser-playable H.264 with ffmpeg."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames[0].shape[:2]
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps),
         "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "28",
         "-movflags", "+faststart", str(dest)],
        stdin=subprocess.PIPE,
    )
    assert proc.stdin is not None
    for f in frames:
        proc.stdin.write(f.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode video")
