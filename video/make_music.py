"""Original music bed for the demo: a tense, driving minor-key pulse (python make_music.py)."""

import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 112
BEAT = 60 / BPM
DUR = 70.0
n = int(SR * DUR)
t = np.arange(n) / SR
out = np.zeros(n)
rng = np.random.default_rng(3)


def note(freq, start, length, kind="saw", amp=0.2, attack=0.005, release=0.15):
    i0, i1 = int(start * SR), min(n, int((start + length + release) * SR))
    if i0 >= n:
        return
    tt = np.arange(i1 - i0) / SR
    if kind == "saw":
        w = 2 * (tt * freq % 1) - 1
    elif kind == "sine":
        w = np.sin(2 * np.pi * freq * tt)
    else:  # square-ish pluck
        w = np.sign(np.sin(2 * np.pi * freq * tt)) * 0.6 + np.sin(2 * np.pi * freq * 2 * tt) * 0.4
    env = np.minimum(1, tt / attack) * np.where(tt < length, 1.0, np.exp(-(tt - length) / release * 4))
    out[i0:i1] += w * env * amp


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


# D minor: i - VI - III - VII  (Dm, Bb, F, C)
prog = [(50, [62, 65, 69]), (46, [58, 62, 65]), (53, [60, 65, 69]), (48, [60, 64, 67])]
bar = 4 * BEAT
nbars = int(DUR / bar) + 1
for b in range(nbars):
    root, chord = prog[b % 4]
    t0 = b * bar
    intensity = min(1.0, 0.35 + b * 0.05)
    # pulsing eighth-note bass
    for k in range(8):
        note(hz(root - 12), t0 + k * BEAT / 2, BEAT / 2 * 0.7, "saw", 0.16 * intensity, release=0.05)
    # pad
    for m in chord:
        note(hz(m - 12), t0, bar, "sine", 0.05, attack=0.4, release=0.6)
    # sixteenth arpeggio after the intro
    if b >= 2:
        pattern = chord + [chord[1] + 12]
        for k in range(16):
            note(hz(pattern[k % 4] + 12), t0 + k * BEAT / 4, BEAT / 4 * 0.5, "pluck", 0.035 * intensity, release=0.08)
    # drums
    for k in range(4):
        bt = t0 + k * BEAT
        if b >= 1:  # kick on every beat
            i0 = int(bt * SR); L = int(0.35 * SR)
            if i0 + L < n:
                tt = np.arange(L) / SR
                out[i0:i0 + L] += np.sin(2 * np.pi * (50 + 90 * np.exp(-tt * 25)) * tt) * np.exp(-tt * 9) * 0.5 * intensity
        if b >= 3 and k in (1, 3):  # snare/clap
            i0 = int(bt * SR); L = int(0.2 * SR)
            if i0 + L < n:
                tt = np.arange(L) / SR
                out[i0:i0 + L] += rng.standard_normal(L) * np.exp(-tt * 22) * 0.18 * intensity
        if b >= 2:  # hats on offbeats
            i0 = int((bt + BEAT / 2) * SR); L = int(0.05 * SR)
            if i0 + L < n:
                hh = rng.standard_normal(L)
                hh = hh - np.convolve(hh, np.ones(4) / 4, mode="same")
                out[i0:i0 + L] += hh * np.exp(-np.arange(L) / SR * 80) * 0.12

# gentle lowpass + soft clip, fade in/out
out = np.convolve(out, np.ones(3) / 3, mode="same")
out = np.tanh(out * 1.4)
fade = np.minimum(1, np.minimum(t / 2.0, (DUR - t) / 3.0))
out *= fade
out /= np.max(np.abs(out)) + 1e-9
st = (np.stack([out, out], 1) * 0.85 * 32767).astype(np.int16)
path = Path(__file__).parent / "public" / "music.wav"
with wave.open(str(path), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
print("wrote", path)
