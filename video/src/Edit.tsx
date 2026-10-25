import React from "react";
import { AbsoluteFill, Audio, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";
import { c, sans } from "./theme";
import { EndCard, Opening, Brand } from "./Cards";
import { ColorChange, CommitLog, Detection, NameTags, Sealed, SessionTitle, SpeechCommit, TapStart, type Commit } from "./Overlays";

const s = (x: number) => Math.round(x * 30);
const clip = (name: string) => staticFile(`footage/${name}.mp4`);

/** Landscape footage with a slow push-in so static shots feel alive. */
const Wide: React.FC<{ src: string; zoom?: [number, number]; origin?: string }> = ({ src, zoom = [1.04, 1.12], origin = "50% 50%" }) => {
  const f = useCurrentFrame();
  const k = interpolate(f, [0, 240], zoom, { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#000" }}>
      <OffthreadVideo src={src} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${k})`, transformOrigin: origin, filter: "contrast(1.06) saturate(1.08)" }} />
    </AbsoluteFill>
  );
};

/** The overhead station camera is portrait: show it as a framed monitor over a blurred fill, like the station screen. */
const Overhead: React.FC<{ src: string; label?: string }> = ({ src, label = "Station camera · overhead" }) => {
  const f = useCurrentFrame();
  const k = interpolate(f, [0, 210], [1.0, 1.06], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: c.night, overflow: "hidden" }}>
      <OffthreadVideo src={src} muted style={{ position: "absolute", inset: -80, width: "calc(100% + 160px)", height: "calc(100% + 160px)", objectFit: "cover", filter: "blur(40px) brightness(0.45) saturate(1.2)" }} />
      <div style={{ position: "absolute", left: "50%", top: "50%", width: 560, height: 996, transform: `translate(-50%,-50%) scale(${k})`, borderRadius: 28, overflow: "hidden", boxShadow: "0 40px 120px rgba(0,0,0,0.6)", border: "1px solid rgba(255,255,255,0.14)" }}>
        <OffthreadVideo src={src} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
      <div style={{ position: "absolute", left: "50%", top: 30, transform: "translateX(-50%)", fontFamily: sans, color: "rgba(255,255,255,0.7)", fontSize: 20, letterSpacing: "0.12em", textTransform: "uppercase", display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#e5484d", opacity: 0.5 + 0.5 * Math.sin(f / 5) }} /> {label}
      </div>
    </AbsoluteFill>
  );
};

// Overhead monitor occupies x 0.354–0.646 of the frame; detection boxes sit inside it.
const COMMITS: Commit[] = [
  { at: s(1.0), text: "Step seen: Prepare the water", kind: "step", hash: "a07e91c2" },
  { at: s(2.5), text: "Pouring water into the bowl", kind: "camera", hash: "3f9c0d17" },
  { at: s(7.5), text: "Reagent bottle identified", kind: "camera", hash: "b4e1aa02" },
  { at: s(12.5), text: "Adding the brown reagent", kind: "camera", hash: "77c2d9e0" },
  { at: s(18.5), text: "Stirring · 5 s", kind: "camera", hash: "c41b7e09" },
  { at: s(23.5), text: "Solution turned amber", kind: "reading", hash: "9d2fa6e3" },
];

export const EDIT_FRAMES = s(6) + s(4) + s(8) + s(8) + s(29) + s(5) + s(6);

export const Edit: React.FC = () => {
  const f = useCurrentFrame();
  let t = 0;
  const seg = (len: number) => { const from = t; t += len; return { from, durationInFrames: len }; };
  const S = { open: seg(s(6)), brand: seg(s(4)), tap: seg(s(8)), intro: seg(s(8)), montage: seg(s(29)), sealed: seg(s(5)), end: seg(s(6)) };
  const music = interpolate(f, [S.brand.from, S.brand.from + 20, S.end.from + 90, EDIT_FRAMES], [0, 0.5, 0.5, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: c.night }}>
      <Audio src={staticFile("music.wav")} volume={() => music} />

      <Sequence {...S.open}><Opening /></Sequence>

      <Sequence {...S.brand}><Wide src={clip("b_end")} zoom={[1.15, 1.05]} /><AbsoluteFill style={{ background: "rgba(0,0,0,0.45)" }} /><Brand /></Sequence>

      <Sequence {...S.tap}>
        <Wide src={clip("b_tap")} zoom={[1.0, 1.06]} />
        <Sequence from={s(4.2)}><TapStart x={0.8} y={0.86} /></Sequence>
      </Sequence>

      <Sequence {...S.intro}>
        <Wide src={clip("b_intro")} zoom={[1.0, 1.08]} origin="70% 30%" />
        <NameTags out={s(7.4)} tags={[
          { name: "Dr. Lena", role: "Researcher · from the spoken intro", x: 0.64, y: 0.34, at: s(0.8) },
          { name: "Dr. Omar", role: "Researcher · from the spoken intro", x: 0.86, y: 0.2, at: s(1.6) },
        ]} />
        <SessionTitle title="Iodine dilution at the bench" people="Dr. Omar · Dr. Lena" at={s(3.0)} />
      </Sequence>

      <Sequence {...S.montage}>
        <Sequence durationInFrames={s(6)}><Overhead src={clip("a_pour")} /></Sequence>
        <Sequence from={s(6)} durationInFrames={s(5)}><Wide src={clip("b_bottle")} zoom={[1.1, 1.22]} origin="40% 60%" /></Sequence>
        <Sequence from={s(11)} durationInFrames={s(6)}><Overhead src={clip("a_add")} /></Sequence>
        <Sequence from={s(17)} durationInFrames={s(6)}><Overhead src={clip("a_stir")} /></Sequence>
        <Sequence from={s(23)}><Overhead src={clip("a_result")} /></Sequence>

        <Sequence from={s(1.2)} durationInFrames={s(4.5)}><Detection kind="camera" box={[0.38, 0.12, 0.2, 0.3]} label="Pouring water" sub="into the mixing bowl" /></Sequence>
        <Sequence from={s(6.8)} durationInFrames={s(4)}><Detection kind="camera" box={[0.36, 0.52, 0.1, 0.32]} label="Reagent bottle" sub="amber glass · identified on the bench" /></Sequence>
        <Sequence from={s(11.6)} durationInFrames={s(5)}><Detection kind="camera" box={[0.4, 0.3, 0.2, 0.26]} label="Adding reagent" sub="brown solution · drops" /></Sequence>
        <Sequence from={s(17.5)} durationInFrames={s(5)}><Detection kind="camera" box={[0.4, 0.3, 0.2, 0.26]} label="Stirring" sub="mixing · 5 s from frame timestamps" /></Sequence>
        <Sequence from={s(19.5)} durationInFrames={s(3.4)}><SpeechCommit text="That's mixed in, it's going amber" value="observation" /></Sequence>
        <Sequence from={s(23.6)}><ColorChange /></Sequence>
        <CommitLog commits={COMMITS} />
      </Sequence>

      <Sequence {...S.sealed}><Wide src={clip("b_end")} zoom={[1.0, 1.05]} /><Sealed commits={23} hash="sha256 9d2fa6e3…e8b0c5f4" /></Sequence>
      <Sequence {...S.end}><EndCard names="Omar Ibrahim · Lena · Mark" /></Sequence>
    </AbsoluteFill>
  );
};
