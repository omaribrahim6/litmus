"""The station's run session: sensors, camera, commits and the flip detector."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from litmus_core.signals import FlipConfig, FlipDetector, MixConfig, summarize_mixing

from .audio import AudioHub
from .camera import Camera
from .config import ROOT, StationConfig
from .outbox import Outbox
from .sensors import SimulatedBench, build_sensors, isfinite

log = logging.getLogger("litmus.session")

COLOR_SENSORS = (("lab_l", "L*"), ("lab_a", "a*"), ("lab_b", "b*"), ("hue", "deg"), ("darkness", "ratio"))


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()


def load_protocol(cfg: StationConfig) -> dict:
    cache = cfg.data_dir / "protocol.json"
    try:
        res = requests.get(f"{cfg.worker_url}/api/experiments", timeout=4)
        res.raise_for_status()
        for exp in res.json():
            if exp["slug"] == cfg.experiment or exp["id"] == cfg.experiment:
                cache.write_text(json.dumps(exp["protocol"]), encoding="utf-8")
                return exp["protocol"]
    except requests.RequestException:
        log.info("worker unreachable; using cached protocol")
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    return json.loads((ROOT / "db" / "experiments" / f"{cfg.experiment}.json").read_text(encoding="utf-8"))


class Session:
    def __init__(self, cfg: StationConfig, simulate: bool = False):
        self.cfg = cfg
        self.protocol = load_protocol(cfg)
        self.bench = SimulatedBench() if simulate else None
        self.sensors = build_sensors(cfg.hardware, self.bench)
        self.camera = Camera(cfg.hardware.get("camera", 0), self.protocol["roi"], simulate=self.bench,
                             lock=cfg.hardware.get("lock_exposure", True))
        # Optional second camera (e.g. a mounted phone streaming MJPEG/RTSP) with a better view
        # of the researcher's hands: a frame at every event, its own video, never used for color.
        action_src = cfg.hardware.get("action_camera")
        self.action_camera = Camera(action_src, self.protocol["roi"], lock=False) if action_src not in (None, "") else None
        self.audio = AudioHub(cfg.hardware.get("mics"))
        self.outbox = Outbox(cfg.data_dir / "outbox.sqlite", cfg.worker_url, cfg.worker_token)
        self.lock = threading.RLock()
        self.latest: dict[str, float | None] = {}
        self.color: dict | None = None
        self._reset()
        threading.Thread(target=self._sensor_loop, daemon=True).start()
        threading.Thread(target=self._color_loop, daemon=True).start()
        threading.Thread(target=self._flush_loop, daemon=True).start()

    # ------------------------------------------------------------ state

    def _reset(self) -> None:
        self.state = "idle"
        self.run_id: str | None = None
        self.label = ""
        self.role = "reference"
        self.started = 0.0
        self.step = 0
        self.totals: dict[str, float] = {}
        self.flip: dict | None = None
        self.flip_detector: FlipDetector | None = None
        self.readings: list[dict] = []
        self.events: list[dict] = []
        self.last_keyframe = 0.0
        self.mix_samples: list[tuple[float, float]] = []
        self.mix_active_since: float | None = None
        self.mix_idle_since: float | None = None
        self.result: dict | None = None
        self.verdict: dict | None = None
        self.message: str | None = None
        self.titrate_started: float | None = None
        self.intro: dict = {"state": None}
        self.title: dict = {}
        self.narration: list[dict] = []

    def snapshot(self) -> dict:
        with self.lock:
            steps = self.protocol["steps"]
            cur = steps[self.step] if self.step < len(steps) else None
            return {
                "state": self.state, "run_id": self.run_id, "label": self.label, "role": self.role,
                "elapsed_s": round(time.time() - self.started, 1) if self.state == "recording" else 0,
                "experiment": self.protocol["name"], "step_index": self.step, "steps": [{"id": s["id"], "title": s["title"], "detail": s.get("detail"), "quantity": s.get("quantity"), "repeat": s.get("repeat", False)} for s in steps],
                "current_step": cur, "totals": self.totals,
                "sensors": {name: {"value": self.latest.get(name), "unit": s.unit, "available": s.available, "detail": s.detail}
                            for name, s in self.sensors.items()},
                "camera": {"available": self.camera.available, "detail": self.camera.detail,
                           "blocked": bool(self.color and self.color.get("blocked")),
                           "rgb": [self.color["r"], self.color["g"], self.color["b"]] if self.color else None},
                "mix_inversions": self._mix_count_live(),
                "flip": self.flip, "result": self.result, "verdict": self.verdict, "message": self.message,
                "no_flip_warning": bool(self.titrate_started and not self.flip and time.time() - self.titrate_started > 600),
                "upload": {"online": self.outbox.online, "pending": self.outbox.pending(), "error": self.outbox.last_error},
                "simulated": self.bench is not None,
                "intro": {k: v for k, v in self.intro.items() if k != "since"},
                "audio": {"available": self.audio.available, "active": self.audio.active, "sources": self.audio.status()},
                "narration": self.narration[-4:],
                "title": self.title,
                "action_camera": {"available": self.action_camera.available, "detail": self.action_camera.detail} if self.action_camera else None,
            }

    # ------------------------------------------------------------ actions

    def start(self, label: str, role: str, assumed_cause: str | None = None, intro: bool = True) -> dict:
        with self.lock:
            if self.state == "recording":
                return self.snapshot()
            self._reset()
            if self.bench:
                self.bench.reset()
            self.run_id = str(uuid.uuid4())
            self.label, self.role, self.started, self.state = label or "Untitled run", role, time.time(), "recording"
            available = [n for n, s in self.sensors.items() if s.available] + (["camera"] if self.camera.available else [])
            if self.action_camera and self.action_camera.available:
                available.append("action_camera")
            missing = [n if n != "temp_c" else "temp_probe" for n, s in self.sensors.items() if not s.available]
            meta = {"available_sensors": available, "missing_sensors": missing, "video_started_at": iso(self.started)}
            if self.bench:
                meta.update(simulated=True, synthetic=True)
            self.outbox.put("/api/runs", {"id": self.run_id, "experiment": self.cfg.experiment, "label": self.label, "role": role,
                                          "station_id": self.cfg.station_id, "started_at": iso(self.started),
                                          "assumed_cause": assumed_cause or None, "metadata": meta})
            run_dir = self.cfg.data_dir / "runs" / self.run_id
            self.camera.start_recording(run_dir / "video.mp4", self.cfg.video_fps)
            self.camera.video_started_at = self.started
            if self.action_camera and self.action_camera.available:
                self.action_camera.start_recording(run_dir / "video_action.mp4", self.cfg.video_fps)
                self.action_camera.video_started_at = self.started
            self._keyframe("start")
            if self.audio.available:
                if intro:
                    max_s = float(self.cfg.hardware.get("intro_seconds", 15))
                    self.intro = {"state": "listening", "since": self.started, "until": self.started + max_s}
                threading.Thread(target=self._listen_loop, args=(self.run_id,), daemon=True).start()
            return self.snapshot()

    # ------------------------------------------------- spoken intro and narration

    def stop_intro(self, skip: bool = False) -> dict:
        with self.lock:
            if self.intro.get("state") == "listening":
                self.intro = {**self.intro, "state": "skipped" if skip else "stopping"}
        return self.snapshot()

    def _listen_loop(self, run_id: str) -> None:
        """While recording: first the intro, then every lab-relevant utterance, from the clearest mic."""
        seg_start = self.seg_start = self.started
        n = 0
        while True:
            time.sleep(0.25)
            now = time.time()
            with self.lock:
                if self.run_id != run_id or self.state != "recording":
                    return
                intro = self.intro.get("state")
            if intro in ("listening", "stopping", "skipped"):
                done = intro != "listening" or now >= self.intro.get("until", now) or \
                    (now - seg_start >= 5 and self.audio.segment_ready(seg_start, now))
                if not done:
                    continue
                utt = self.audio.best(seg_start, now) if intro != "skipped" else None
                seg_start = self.seg_start = now
                with self.lock:
                    if intro == "skipped":
                        self.intro = {"state": "skipped"}
                        continue
                    self.intro = {"state": "processing"} if utt else {"state": "failed", "error": "Didn't hear an introduction"}
                if utt:
                    threading.Thread(target=self._send_intro, args=(run_id, utt), daemon=True).start()
                continue
            if self.audio.segment_ready(seg_start, now):
                utt = self.audio.best(seg_start, now)
                seg_start = self.seg_start = now
                if utt:
                    n += 1
                    threading.Thread(target=self._send_narration, args=(run_id, utt, n), daemon=True).start()

    def _utterance_file(self, run_id: str, utt, name: str) -> Path:
        return utt.write(self.cfg.data_dir / "runs" / run_id / "audio" / f"{name}.wav")

    def _send_intro(self, run_id: str, utt) -> None:
        path = self._utterance_file(run_id, utt, "intro")
        self.outbox.flush(timeout_s=15)  # the run must exist on the worker first
        try:
            with open(path, "rb") as fh:
                res = requests.post(f"{self.cfg.worker_url}/api/runs/{run_id}/intro", files={"file": ("intro.wav", fh, "audio/wav")},
                                    headers=self.outbox.headers, timeout=60)
            res.raise_for_status()
            heard = res.json()
        except requests.RequestException as exc:
            self.outbox.put(f"/api/runs/{run_id}/intro", {}, str(path))
            with self.lock:
                self.intro = {"state": "queued", "error": f"Offline: the run will be titled when the worker is reachable ({exc.__class__.__name__})"}
            return
        with self.lock:
            if self.run_id != run_id:
                return
            if not heard.get("understood"):
                self.intro = {"state": "failed", "error": heard.get("error", "Gemini could not understand the clip")}
                return
            self.intro = {"state": "ready", "result": heard, "mic": utt.source}
            self.title = {k: heard.get(k) for k in ("title", "researcher", "lab", "experiment")}
            if heard.get("run_label"):
                self.label = heard["run_label"]
            if heard.get("role") and heard["role"] != "unknown":
                self.role = heard["role"]

    def _send_narration(self, run_id: str, utt, n: int) -> None:
        path = self._utterance_file(run_id, utt, f"narration_{n:03d}")
        meta = {"t_start": iso(utt.t0), "t_end": iso(utt.t1), "source": utt.source, "scores": utt.scores}
        try:
            with open(path, "rb") as fh:
                res = requests.post(f"{self.cfg.worker_url}/api/runs/{run_id}/narration",
                                    files={"file": (path.name, fh, "audio/wav")}, data={"meta": json.dumps(meta)},
                                    headers=self.outbox.headers, timeout=60)
            res.raise_for_status()
            out = res.json()
        except requests.RequestException:
            self.outbox.put(f"/api/runs/{run_id}/narration", meta, str(path))
            return
        with self.lock:
            for c in out.get("committed", []):
                self.narration.append({"t_s": round(c.get("t_s", 0), 1), "text": c["text"], "mic": utt.source})

    def confirm_intro(self) -> dict:
        with self.lock:
            if self.intro.get("state") == "ready" and self.run_id:
                r = self.intro["result"]
                self.outbox.put(f"/api/runs/{self.run_id}/intro/confirm",
                                {"researcher": r.get("researcher"), "lab": r.get("lab"), "title": r.get("title"), "run_label": r.get("run_label")})
                self.intro = {"state": "confirmed"}
            return self.snapshot()

    def dismiss_intro(self) -> dict:
        with self.lock:
            if self.intro.get("state") in ("ready", "failed", "queued"):
                self.intro = {"state": "dismissed"}
            return self.snapshot()

    def confirm_step(self) -> dict:
        with self.lock:
            if self.state != "recording":
                return self.snapshot()
            steps = self.protocol["steps"]
            if self.step >= len(steps):
                return self.snapshot()
            s = steps[self.step]
            fid = self._keyframe("event")
            self._event("step_confirmed", f"Step confirmed: {s['title']}", "reported", {"step": s["id"]}, [fid] if fid else [])
            if s["id"] == "titrate":
                self.titrate_started = time.time()
                self.flip_detector = FlipDetector(FlipConfig.from_dict(self.protocol.get("flip")))
            q = s.get("quantity")
            if q and q.get("expected") is not None and not s.get("repeat"):
                self._quantity(q, float(q["expected"]), s["id"])
            if not s.get("repeat"):
                self.step += 1
            return self.snapshot()

    def next_step(self) -> dict:
        """Leave a repeating step (titration) and move on."""
        with self.lock:
            if self.state == "recording" and self.step < len(self.protocol["steps"]):
                self.step += 1
            return self.snapshot()

    def add_quantity(self, value: float) -> dict:
        with self.lock:
            if self.state != "recording" or self.step >= len(self.protocol["steps"]):
                return self.snapshot()
            s = self.protocol["steps"][self.step]
            q = s.get("quantity")
            if not q:
                return self.snapshot()
            self._quantity(q, value, s["id"])
            if self.bench and q["name"] == self.protocol["result"]["quantity"]:
                self.bench.add_base(value)
            return self.snapshot()

    def enter_reading(self, sensor: str, value: float, unit: str) -> dict:
        """A value read off an instrument by the researcher (e.g. a kitchen thermometer)."""
        with self.lock:
            if self.state != "recording":
                return self.snapshot()
            t = time.time()
            self.readings.append({"t": iso(t), "sensor": sensor, "value": value, "unit": unit, "provenance": "reported"})
            self.latest[sensor] = value
            self._event("reading_reported", f"Entered from a thermometer: {value:.1f} {unit}" if sensor == "temp_c" else f"Entered {sensor}: {value} {unit}",
                        "reported", {"sensor": sensor, "value": value, "unit": unit})
            return self.snapshot()

    def note(self, text: str) -> dict:
        with self.lock:
            if self.state == "recording" and text.strip():
                fid = self._keyframe("event")
                self._event("note", text.strip(), "reported", {"text": text.strip()}, [fid] if fid else [])
            return self.snapshot()

    def end(self) -> dict:
        with self.lock:
            if self.state != "recording":
                return self.snapshot()
            self._close_mix(time.time(), force=True)
            self._flush_now()
            self.state = "finishing"
            run_id, started, role = self.run_id, self.started, self.role
        # Whatever was said since the last pause is committed before the run ends.
        if self.audio.available and run_id:
            tail = self.audio.best(getattr(self, "seg_start", time.time() - 25), time.time())
            if tail:
                path = self._utterance_file(run_id, tail, "narration_final")
                self.outbox.put(f"/api/runs/{run_id}/narration",
                                {"t_start": iso(tail.t0), "t_end": iso(tail.t1), "source": tail.source, "scores": tail.scores}, str(path))
        video = self.camera.stop_recording()
        if video:
            self.outbox.put(f"/api/runs/{run_id}/video", {"started_at": iso(started)}, str(video))
        if self.action_camera:
            action_video = self.action_camera.stop_recording()
            if action_video:
                self.outbox.put(f"/api/runs/{run_id}/video", {"started_at": iso(started), "camera": "action"}, str(action_video))
        self.outbox.put(f"/api/runs/{run_id}/end", {"ended_at": iso(time.time())})
        threading.Thread(target=self._after_end, args=(run_id, role), daemon=True).start()
        return self.snapshot()

    def _after_end(self, run_id: str, role: str) -> None:
        ok = self.outbox.flush(timeout_s=120)
        with self.lock:
            self.state = "finished"
            if not ok:
                self.message = "Saved on the station. It will upload when the network is back."
                return
        try:
            run = requests.get(f"{self.cfg.worker_url}/api/runs/{run_id}", timeout=10).json()["run"]
            with self.lock:
                self.result = run.get("result")
            if role in ("candidate", "rerun"):
                v = requests.post(f"{self.cfg.worker_url}/api/verdict", json={"candidate": run_id}, timeout=120).json()
                with self.lock:
                    self.verdict = {"summary": v["content"]["station_summary"], "id": v["id"]}
        except (requests.RequestException, KeyError, ValueError) as exc:
            log.warning("could not fetch result: %s", exc)

    # ------------------------------------------------------------ internals

    def _quantity(self, q: dict, value: float, step_id: str) -> None:
        name = q["name"]
        self.totals[name] = round(self.totals.get(name, 0.0) + value, 3)
        unit = q.get("unit", "")
        total = self.totals[name]
        summary = f"Added {value:g} {unit}" + (f" (total {total:g} {unit})" if step_id == "titrate" else "")
        self._event("quantity_added", summary, "reported", {"quantity": name, "value": value, "unit": unit, "step": step_id, "total": total})

    def _event(self, kind: str, summary: str, provenance: str, payload: dict | None = None,
               frame_ids: list[str] | None = None, t: float | None = None) -> None:
        frame_ids = list(frame_ids or [])
        if kind in ("step_confirmed", "quantity_added", "note", "flip_detected"):
            action = self._keyframe("action", camera=self.action_camera)
            if action:
                frame_ids.append(action)
        self.events.append({"id": str(uuid.uuid4()), "t": iso(t or time.time()), "kind": kind, "summary": summary,
                            "provenance": provenance, "payload": payload, "frame_ids": frame_ids})

    def _keyframe(self, reason: str, camera: Camera | None = None) -> str | None:
        cam = camera if camera is not None else (None if reason == "action" else self.camera)
        if self.run_id is None or cam is None:
            return None
        shot = cam.jpeg()
        if shot is None:
            return None
        data, t = shot
        fid = str(uuid.uuid4())
        path = self.cfg.data_dir / "runs" / self.run_id / "frames" / f"{fid}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        metrics = self.color if cam is self.camera else None
        self.outbox.put(f"/api/runs/{self.run_id}/frames",
                        {"id": fid, "t": iso(t), "reason": reason, "roi": self.protocol["roi"] if metrics else None, "metrics": metrics}, str(path))
        if cam is self.camera:
            self.last_keyframe = time.time()
        return fid

    def _mix_count_live(self) -> int:
        cfg = MixConfig.from_dict(self.protocol.get("mix"))
        return summarize_mixing(self.mix_samples, cfg).inversions if self.mix_samples else 0

    def _close_mix(self, now: float, force: bool = False) -> None:
        if self.mix_active_since is None or not self.mix_samples:
            return
        if not force and (self.mix_idle_since is None or now - self.mix_idle_since < 1.5):
            return
        summary = summarize_mixing(self.mix_samples, MixConfig.from_dict(self.protocol.get("mix")))
        if summary.inversions or summary.active_s >= 1.0:
            self._event("mix", f"Mixed: {summary.inversions} inversions over {summary.active_s:.1f} s", "measured",
                        {"inversions": summary.inversions, "duration_s": summary.active_s}, t=summary.last_t or now)
        self.mix_samples, self.mix_active_since, self.mix_idle_since = [], None, None

    def _sensor_loop(self) -> None:
        period = 1.0 / self.cfg.sensor_hz
        last_angle: tuple[float, float] | None = None
        mix_cfg = MixConfig.from_dict(self.protocol.get("mix"))
        while True:
            t = time.time()
            values = {name: s.read() for name, s in self.sensors.items()}
            with self.lock:
                for name, v in values.items():
                    if isfinite(v):
                        self.latest[name] = v
                        if self.state == "recording":
                            self.readings.append({"t": iso(t), "sensor": name, "value": v, "unit": self.sensors[name].unit, "provenance": "measured"})
                    elif not self.sensors[name].available:
                        self.latest.setdefault(name, None)
                angle = values.get("mix_angle")
                if self.state == "recording" and isfinite(angle):
                    speed = abs(angle - last_angle[1]) / (t - last_angle[0]) if last_angle else 0.0
                    last_angle = (t, angle)
                    if speed >= mix_cfg.active_dps:
                        self.mix_active_since = self.mix_active_since or t
                        self.mix_idle_since = None
                    elif self.mix_active_since is not None and self.mix_idle_since is None:
                        self.mix_idle_since = t
                    if self.mix_active_since is not None:
                        self.mix_samples.append((t, angle))
                    self._close_mix(t)
            time.sleep(max(0.0, period - (time.time() - t)))

    def _color_loop(self) -> None:
        period = 1.0 / self.cfg.color_hz
        while True:
            t = time.time()
            m = self.camera.metrics()
            with self.lock:
                self.color = m
                if m and self.state == "recording":
                    if not m.get("blocked"):
                        for sensor, unit in COLOR_SENSORS:
                            self.readings.append({"t": iso(t), "sensor": sensor, "value": m[sensor], "unit": unit, "provenance": "measured"})
                        if self.flip_detector and self.flip is None:
                            metric = self.flip_detector.cfg.metric
                            f = self.flip_detector.feed(t, m[metric])
                            if f:
                                self._on_flip(f, metric)
                    if t - self.last_keyframe >= self.cfg.keyframe_every_s:
                        self._keyframe("periodic")
            time.sleep(max(0.0, period - (time.time() - t)))

    def _on_flip(self, f, metric: str) -> None:
        fid = self._keyframe("flip")
        total = self.totals.get(self.protocol["result"]["quantity"], 0.0)
        self.flip = {"t_s": round(f.t - self.started, 1), "at_total": total, "unit": self.protocol["result"].get("unit")}
        self._event("flip_detected", f"Color flip detected by camera ({metric} changed {f.change:+.1f} from baseline {f.baseline:.1f})",
                    "measured", {"source": "camera", "metric": metric, "baseline": round(f.baseline, 3), "value": round(f.value, 3),
                                 "change": round(f.change, 3), "confirmed_t": iso(f.confirmed_t)}, [fid] if fid else [], t=f.t)

    def _flush_now(self) -> None:
        if not self.run_id:
            return
        if self.readings:
            self.outbox.put(f"/api/runs/{self.run_id}/readings", {"readings": self.readings})
            self.readings = []
        if self.events:
            self.outbox.put(f"/api/runs/{self.run_id}/events", {"events": self.events})
            self.events = []

    def _flush_loop(self) -> None:
        while True:
            time.sleep(1.0)
            with self.lock:
                if self.state == "recording":
                    self._flush_now()

