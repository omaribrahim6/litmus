import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame } from "remotion";
import { c, sans } from "./theme";
import { Orb, Typed, fade } from "./parts";

/** Cold open: typed lines on black. */
export const Opening: React.FC = () => {
  const f = useCurrentFrame();
  const out = 1 - fade(f, 165, 180);
  return (
    <AbsoluteFill style={{ background: c.night, alignItems: "center", justifyContent: "center", fontFamily: sans, color: "#fff", opacity: out }}>
      <Audio src={staticFile("sfx/type.wav")} volume={0.5} />
      <div style={{ fontSize: 60, fontWeight: 500, letterSpacing: "-0.03em", textAlign: "center", lineHeight: 1.3 }}>
        <Typed text="Every experiment generates data." at={8} cps={26} caret={f < 60} />
        <br />
        <span style={{ opacity: 0.55 }}><Typed text="Almost none of it gets written down." at={78} cps={26} /></span>
      </div>
    </AbsoluteFill>
  );
};

/** The product name over the walk-in. */
export const Brand: React.FC = () => {
  const f = useCurrentFrame();
  const o = Math.min(fade(f, 0, 14), 1 - fade(f, 70, 84));
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", fontFamily: sans, color: "#fff", opacity: o }}>
      <Sequence from={0}><Audio src={staticFile("sfx/whoosh.wav")} volume={0.6} /></Sequence>
      <div style={{ display: "flex", alignItems: "center", gap: 26, transform: `scale(${0.94 + 0.06 * fade(f, 0, 20)})`, textShadow: "0 8px 40px rgba(0,0,0,0.5)" }}>
        <div style={{ width: 30, height: 84, borderRadius: 8, background: "linear-gradient(#e8c33a 0 46%, #d0365b 54% 100%)", boxShadow: "0 8px 30px rgba(0,0,0,0.4)" }} />
        <div style={{ fontSize: 150, fontWeight: 700, letterSpacing: "-0.05em" }}>litmus</div>
      </div>
    </AbsoluteFill>
  );
};

export const EndCard: React.FC<{ names: string }> = ({ names }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: c.night, alignItems: "center", justifyContent: "center", fontFamily: sans, color: "#fff" }}>
      <Audio src={staticFile("sfx/chime.wav")} volume={0.5} />
      <div style={{ opacity: fade(f, 0, 16), display: "flex", flexDirection: "column", alignItems: "center", gap: 26 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ width: 22, height: 62, borderRadius: 6, background: "linear-gradient(#e8c33a 0 46%, #d0365b 54% 100%)" }} />
          <div style={{ fontSize: 110, fontWeight: 700, letterSpacing: "-0.05em" }}>litmus</div>
        </div>
        <div style={{ fontSize: 40, opacity: 0.8, letterSpacing: "-0.02em" }}>Git for research, except you never have to commit.</div>
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 30, fontSize: 26, opacity: fade(f, 20, 34) * 0.7 }}>
          <Orb size={26} /> Built with Gemini and Tiger Data
        </div>
        <div style={{ fontSize: 24, opacity: fade(f, 30, 44) * 0.5 }}>{names}</div>
      </div>
    </AbsoluteFill>
  );
};
