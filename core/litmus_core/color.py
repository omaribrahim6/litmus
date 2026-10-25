"""Color metrics inside a region of interest (ROI) of a camera frame.

Frames are BGR uint8 arrays as returned by OpenCV. The ROI is a normalized
rectangle {"x","y","w","h"} in [0, 1] so a protocol config works at any
camera resolution.
"""

from __future__ import annotations

import math

import numpy as np

METRIC_UNITS = {
    "r": "8bit",
    "g": "8bit",
    "b": "8bit",
    "hue": "deg",
    "saturation": "ratio",
    "lab_l": "L*",
    "lab_a": "a*",
    "lab_b": "b*",
    "darkness": "ratio",
}


def roi_pixels(frame: np.ndarray, roi: dict) -> np.ndarray:
    h, w = frame.shape[:2]
    x0 = int(round(roi["x"] * w))
    y0 = int(round(roi["y"] * h))
    x1 = int(round((roi["x"] + roi["w"]) * w))
    y1 = int(round((roi["y"] + roi["h"]) * h))
    x0, x1 = max(0, x0), min(w, max(x0 + 1, x1))
    y0, y1 = max(0, y0), min(h, max(y0 + 1, y1))
    return frame[y0:y1, x0:x1]


def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _lab_f(t: float) -> float:
    d = 6 / 29
    return t ** (1 / 3) if t > d**3 else t / (3 * d * d) + 4 / 29


def rgb_to_lab(r: float, g: float, b: float) -> tuple[float, float, float]:
    """sRGB (0-255) to CIE L*a*b* with a D65 white point."""
    lin = _srgb_to_linear(np.array([r, g, b], dtype=np.float64) / 255.0)
    x = 0.4124564 * lin[0] + 0.3575761 * lin[1] + 0.1804375 * lin[2]
    y = 0.2126729 * lin[0] + 0.7151522 * lin[1] + 0.0721750 * lin[2]
    z = 0.0193339 * lin[0] + 0.1191920 * lin[1] + 0.9503041 * lin[2]
    fx, fy, fz = _lab_f(x / 0.95047), _lab_f(y / 1.0), _lab_f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def roi_metrics(frame: np.ndarray, roi: dict) -> dict[str, float]:
    """Mean color of the ROI in several spaces.

    Hue is averaged on the circle (degrees, 0-360) so red pixels on both sides
    of 0 degrees do not average to cyan.
    """
    px = roi_pixels(frame, roi).reshape(-1, 3).astype(np.float64)
    b, g, r = px[:, 0], px[:, 1], px[:, 2]
    mr, mg, mb = float(r.mean()), float(g.mean()), float(b.mean())

    mx = np.max(px, axis=1)
    mn = np.min(px, axis=1)
    chroma = mx - mn
    safe = np.where(chroma == 0, 1, chroma)
    hue = np.where(
        mx == r,
        ((g - b) / safe) % 6,
        np.where(mx == g, (b - r) / safe + 2, (r - g) / safe + 4),
    ) * 60.0
    weight = chroma
    if weight.sum() > 0:
        rad = np.deg2rad(hue)
        mean_hue = math.degrees(
            math.atan2(float((np.sin(rad) * weight).sum()), float((np.cos(rad) * weight).sum()))
        ) % 360
    else:
        mean_hue = 0.0
    sat = float(np.where(mx == 0, 0, chroma / np.where(mx == 0, 1, mx)).mean())

    lab_l, lab_a, lab_b = rgb_to_lab(mr, mg, mb)
    return {
        "r": round(mr, 3),
        "g": round(mg, 3),
        "b": round(mb, 3),
        "hue": round(mean_hue, 3),
        "saturation": round(sat, 4),
        "lab_l": round(lab_l, 3),
        "lab_a": round(lab_a, 3),
        "lab_b": round(lab_b, 3),
        "darkness": round(1 - lab_l / 100.0, 4),
    }


def blocked_or_dark(metrics: dict[str, float], min_l: float = 8.0) -> bool:
    """True when the ROI is too dark to read (lens covered, lights off)."""
    return metrics["lab_l"] < min_l
