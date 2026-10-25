import math

import numpy as np

from litmus_core.color import rgb_to_lab, roi_metrics
from litmus_core.signals import FlipConfig, detect_flip, summarize_mixing


def series(fn, seconds=60.0, hz=2.0):
    n = int(seconds * hz)
    return [(i / hz, fn(i / hz)) for i in range(n)]


def test_flip_onset_within_one_sample():
    flip_at = 31.0
    rng = np.random.default_rng(1)
    noise = rng.normal(0, 0.8, 200)
    samples = series(lambda t: (5.0 if t < flip_at else 30.0) + noise[int(t * 2)], seconds=60)
    flip = detect_flip(samples, {"metric": "lab_a", "direction": "rise", "delta": 12, "hold_s": 2})
    assert flip is not None
    assert abs(flip.t - flip_at) <= 0.5
    assert flip.confirmed_t >= flip.t + 2


def test_brief_spike_is_not_a_flip():
    samples = series(lambda t: 30.0 if 20 <= t < 21 else 5.0, seconds=60)
    assert detect_flip(samples, {"delta": 12, "hold_s": 2}) is None


def test_fall_direction_and_circular_hue():
    # Hue moving from 20 deg (yellow-orange) to 350 deg (red) is a 30 deg fall
    # across the wrap, not a 330 deg rise.
    samples = series(lambda t: 20.0 if t < 25 else 350.0, seconds=50)
    flip = detect_flip(samples, {"metric": "hue", "direction": "fall", "delta": 20, "hold_s": 1.5})
    assert flip is not None
    assert abs(flip.t - 25.0) <= 0.5
    assert math.isclose(flip.change, -30.0, abs_tol=1e-6)


def test_mixing_counts_inversions_with_hysteresis():
    # Two full inversions, plus jitter around the middle that must not count.
    angles = [0, 0, 90, 180, 180, 90, 0, 0, 100, 110, 100, 0, 90, 180, 170, 180, 90, 0]
    samples = [(i * 0.5, float(a)) for i, a in enumerate(angles)]
    summary = summarize_mixing(samples, {"low_deg": 60, "high_deg": 150})
    assert summary.inversions == 2
    assert summary.active_s > 0


def test_lab_and_roi_metrics():
    l, a, b = rgb_to_lab(255, 255, 255)
    assert math.isclose(l, 100, abs_tol=0.01) and abs(a) < 0.01 and abs(b) < 0.01
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[:, :] = (40, 40, 220)  # BGR red
    m = roi_metrics(frame, {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5})
    assert m["lab_a"] > 50
    assert m["hue"] < 5 or m["hue"] > 355
