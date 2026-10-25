"""Synthesize the demo's sound effects (original, no licensing): python make_sfx.py"""

import wave
from pathlib import Path

import numpy as np

SR = 48000
OUT = Path(__file__).parent / "public" / "sfx"
rng = np.random.default_rng(7)


def t(d):
    return np.arange(int(SR * d)) / SR


def env(n, a=0.002, r=0.2):
    x = np.arange(n) / SR
    return np.minimum(1, x / max(a, 1e-4)) * np.exp(-x / r)


def save(name, x, gain=0.8):
    x = np.asarray(x, dtype=np.float64)
    x = x / (np.max(np.abs(x)) + 1e-9) * gain
    st = np.stack([x, x], 1)
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


def lowpass(x, a):
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += a * (v - acc)
        y[i] = acc
    return y


# pop: a quick pitch-down bubble
tt = t(0.18)
f = 900 * np.exp(-tt * 18) + 260
save("pop", np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(tt), 0.001, 0.05), 0.7)

# tick: tiny glassy click
tt = t(0.07)
save("tick", (np.sin(2 * np.pi * 2400 * tt) + 0.5 * np.sin(2 * np.pi * 3600 * tt)) * env(len(tt), 0.0005, 0.012), 0.45)

# click: UI tap
tt = t(0.09)
save("click", (rng.standard_normal(len(tt)) * 0.4 + np.sin(2 * np.pi * 1500 * tt)) * env(len(tt), 0.0003, 0.01), 0.6)

# blip: two-tone detection ping
tt = t(0.22)
half = len(tt) // 2
tone = np.concatenate([np.sin(2 * np.pi * 1320 * tt[:half]), np.sin(2 * np.pi * 1760 * tt[half:])])
save("blip", tone * env(len(tt), 0.002, 0.09), 0.5)

# whoosh: filtered noise swell
tt = t(0.7)
n = rng.standard_normal(len(tt))
sweep = np.sin(np.pi * tt / tt[-1]) ** 2
save("whoosh", lowpass(n, 0.08) * sweep + 0.3 * lowpass(n, 0.02) * sweep, 0.6)

# riser: rising tone into the pipeline
tt = t(1.6)
f = 120 + 900 * (tt / tt[-1]) ** 2
r = np.sin(2 * np.pi * np.cumsum(f) / SR) * (tt / tt[-1]) ** 1.5
save("riser", r + 0.25 * lowpass(rng.standard_normal(len(tt)), 0.1) * (tt / tt[-1]) ** 2, 0.55)

# hit: low impact for the color change
tt = t(1.2)
f = 90 * np.exp(-tt * 6) + 42
boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(tt), 0.001, 0.35)
crack = lowpass(rng.standard_normal(len(tt)), 0.3) * env(len(tt), 0.0005, 0.04)
save("hit", boom + 0.5 * crack, 0.9)

# stamp: thud plus paper slap
tt = t(0.5)
thud = np.sin(2 * np.pi * (70 + 60 * np.exp(-tt * 30)) * tt) * env(len(tt), 0.0005, 0.09)
slap = lowpass(rng.standard_normal(len(tt)), 0.5) * env(len(tt), 0.0002, 0.025)
save("stamp", thud + 0.7 * slap, 0.9)

# chime: soft bell for answers and the end card
tt = t(1.8)
bell = sum(a * np.sin(2 * np.pi * fr * tt) * np.exp(-tt * d) for fr, a, d in [(880, 1, 2.2), (1320, 0.5, 3), (1760, 0.3, 4), (2637, 0.15, 5)])
save("chime", bell * env(len(tt), 0.003, 10), 0.5)

# type: a few seconds of keyboard ticks for the cold open
dur = 4.0
x = np.zeros(int(SR * dur))
for k in np.cumsum(rng.uniform(0.05, 0.13, 60)):
    i = int(k * SR)
    if i + 2000 >= len(x):
        break
    seg = t(2000 / SR)
    x[i:i + 2000] += (rng.standard_normal(2000) * 0.5 + np.sin(2 * np.pi * rng.uniform(1800, 2600) * seg)) * env(2000, 0.0002, 0.006)
save("type", x, 0.45)
print("wrote", sorted(p.name for p in OUT.glob("*.wav")))
