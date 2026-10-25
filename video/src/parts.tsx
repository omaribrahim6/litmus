import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { c, mono, sans } from "./theme";

/** The assistant's orb, as in the app. */
export const Orb: React.FC<{ size: number; glow?: number; pulse?: boolean }> = ({ size, glow = 0, pulse }) => {
  const f = useCurrentFrame();
  const s = pulse ? 1 + Math.sin(f / 7) * 0.04 : 1;
  return (
    <div style={{ position: "relative", width: size, height: size, transform: `scale(${s})` }}>
      {glow ? <div style={{ position: "absolute", inset: -size * 0.9, borderRadius: "50%", background: c.ai, filter: `blur(${size * 0.55}px)`, opacity: glow }} /> : null}
      <div style={{
        position: "absolute", inset: 0, borderRadius: "50%",
        background: `radial-gradient(circle at 32% 28%, rgba(255,255,255,0.6) 0%, rgba(255,255,255,0) 40%), ${c.ai}`,
        boxShadow: "inset 0 -6px 14px rgba(0,0,0,0.25)",
      }} />
    </div>
  );
};

/** Spring from 0 to 1 starting at `at` frames. */
export const usePop = (at: number, damping = 14) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: f - at, fps, config: { damping, mass: 0.6, stiffness: 140 } });
};

export const Glass: React.FC<{ style?: React.CSSProperties; children: React.ReactNode }> = ({ style, children }) => (
  <div style={{
    background: c.glass, border: `1px solid ${c.glassBorder}`, borderRadius: 18, color: "#fff", fontFamily: sans,
    backdropFilter: "blur(18px) saturate(1.4)", WebkitBackdropFilter: "blur(18px) saturate(1.4)",
    boxShadow: "0 18px 50px rgba(0,0,0,0.35)", ...style,
  }}>{children}</div>
);

export const Chip: React.FC<{ color: string; children: React.ReactNode; style?: React.CSSProperties }> = ({ color, children, style }) => (
  <span style={{
    display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 14px", borderRadius: 999, fontFamily: sans, fontWeight: 600,
    fontSize: 22, color, background: `color-mix(in oklab, ${color} 18%, transparent)`, border: `1px solid color-mix(in oklab, ${color} 35%, transparent)`, ...style,
  }}>{children}</span>
);

export const Mono: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <span style={{ fontFamily: mono, letterSpacing: "-0.02em", ...style }}>{children}</span>
);

/** Text revealed character by character from frame `at`. */
export const Typed: React.FC<{ text: string; at: number; cps?: number; caret?: boolean }> = ({ text, at, cps = 38, caret = true }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = Math.max(0, Math.floor(((f - at) / fps) * cps));
  const done = n >= text.length;
  const blink = Math.floor(f / 15) % 2 === 0;
  return <>{text.slice(0, n)}{caret && (!done || blink) && f >= at ? <span style={{ opacity: 0.7 }}>▍</span> : null}</>;
};

export const fade = (f: number, a: number, b: number) => interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
