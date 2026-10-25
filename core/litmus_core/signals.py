"""Time-series detectors: color flip onset and mixing from a rotary angle.

Samples are (t, value) pairs with t in seconds (float, monotonic). The same
code runs live on the station (streaming) and offline in the worker (batch),
so a flip found on the Pi and a flip recomputed later agree by construction.
"""

from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass, field


@dataclass
class FlipConfig:
    metric: str = "lab_a"
    direction: str = "rise"   # rise | fall | either
    delta: float = 12.0       # change from baseline, in metric units
    hold_s: float = 2.0       # the change must persist this long
    baseline_s: float = 3.0   # window after arming used as the baseline
    smooth: int = 5           # trailing median window, in samples
    circular: bool = False    # hue in degrees wraps at 360
    onset_fraction: float = 0.3  # the reported flip time is where the change first passed this share of delta
    relative: bool = False    # delta is a fraction of the baseline (for sensors in arbitrary units)

    @classmethod
    def from_dict(cls, d: dict | None) -> "FlipConfig":
        d = dict(d or {})
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        if "circular" not in known and known.get("metric") == "hue":
            known["circular"] = True
        return cls(**known)


@dataclass
class Flip:
    t: float              # onset time of the persistent change
    confirmed_t: float    # time the detector was sure (onset + hold)
    baseline: float
    value: float          # smoothed value at confirmation
    change: float         # signed change from baseline at confirmation


def _diff(a: float, b: float, circular: bool) -> float:
    if not circular:
        return a - b
    return (a - b + 180.0) % 360.0 - 180.0


def _circular_median(values: list[float]) -> float:
    ref = values[len(values) // 2]
    return (ref + statistics.median(_diff(v, ref, True) for v in values)) % 360.0


class FlipDetector:
    """Streaming flip detector: baseline, trailing median, threshold, persistence."""

    def __init__(self, cfg: FlipConfig):
        self.cfg = cfg
        self.start_t: float | None = None
        self.baseline: float | None = None
        self._baseline_samples: list[float] = []
        self._window: deque[float] = deque(maxlen=max(1, cfg.smooth))
        self._raw: deque[tuple[float, float]] = deque(maxlen=4096)
        self._streak_start: float | None = None
        self.flip: Flip | None = None

    def _median(self, values) -> float:
        values = list(values)
        return _circular_median(values) if self.cfg.circular else statistics.median(values)

    def _exceeds(self, value: float, fraction: float = 1.0) -> bool:
        d = _diff(value, self.baseline, self.cfg.circular)
        if self.cfg.relative:
            d = d / max(abs(self.baseline), 1e-9)
        threshold = self.cfg.delta * fraction
        if self.cfg.direction == "rise":
            return d >= threshold
        if self.cfg.direction == "fall":
            return -d >= threshold
        return abs(d) >= threshold

    def feed(self, t: float, value: float) -> Flip | None:
        """Add one sample. Returns the Flip the first time it is confirmed."""
        if self.flip is not None or value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        if self.start_t is None:
            self.start_t = t
        self._raw.append((t, value))
        if self.baseline is None:
            self._baseline_samples.append(value)
            if t - self.start_t >= self.cfg.baseline_s and len(self._baseline_samples) >= 3:
                self.baseline = self._median(self._baseline_samples)
            return None

        self._window.append(value)
        smoothed = self._median(self._window)
        if not self._exceeds(smoothed):
            self._streak_start = None
            return None
        if self._streak_start is None:
            self._streak_start = t
        if t - self._streak_start < self.cfg.hold_s:
            return None

        # Confirmed. The trailing median lags and the threshold is crossed partway
        # through the change, so walk back through raw samples to where the
        # change began (the first of the unbroken run past onset_fraction of delta).
        onset = t
        for rt, rv in reversed(self._raw):
            if not self._exceeds(rv, self.cfg.onset_fraction):
                break
            onset = rt
        self.flip = Flip(
            t=onset,
            confirmed_t=t,
            baseline=self.baseline,
            value=smoothed,
            change=_diff(smoothed, self.baseline, self.cfg.circular),
        )
        return self.flip


def detect_flip(samples: list[tuple[float, float]], cfg: FlipConfig | dict) -> Flip | None:
    """Batch flip detection over a full series."""
    if isinstance(cfg, dict):
        cfg = FlipConfig.from_dict(cfg)
    det = FlipDetector(cfg)
    for t, v in sorted(samples):
        if det.feed(t, v):
            break
    return det.flip


@dataclass
class MixConfig:
    low_deg: float = 60.0      # holder counts as "upright" below this angle
    high_deg: float = 150.0    # and "inverted" above this angle
    active_dps: float = 30.0   # angular speed that counts as mixing
    max_gap_s: float = 2.0     # ignore speed across gaps in the data

    @classmethod
    def from_dict(cls, d: dict | None) -> "MixConfig":
        d = dict(d or {})
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class MixSummary:
    inversions: int
    active_s: float
    first_t: float | None
    last_t: float | None
    crossings: list[float] = field(default_factory=list)


def summarize_mixing(samples: list[tuple[float, float]], cfg: MixConfig | dict | None = None) -> MixSummary:
    """Count inversions (upright to inverted, with hysteresis) and active mixing time."""
    if not isinstance(cfg, MixConfig):
        cfg = MixConfig.from_dict(cfg)
    samples = sorted(samples)
    state: str | None = None
    crossings: list[float] = []
    active = 0.0
    first_t = last_t = None
    for i, (t, angle) in enumerate(samples):
        if angle <= cfg.low_deg:
            zone = "up"
        elif angle >= cfg.high_deg:
            zone = "down"
        else:
            zone = None
        if zone is not None:
            if state is not None and zone != state and zone == "down":
                crossings.append(t)
            state = zone
        if i:
            pt, pa = samples[i - 1]
            dt = t - pt
            if 0 < dt <= cfg.max_gap_s and abs(angle - pa) / dt >= cfg.active_dps:
                active += dt
                first_t = pt if first_t is None else first_t
                last_t = t
    return MixSummary(
        inversions=len(crossings),
        active_s=round(active, 3),
        first_t=first_t,
        last_t=last_t,
        crossings=crossings,
    )
