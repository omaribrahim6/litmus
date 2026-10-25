import React from "react";
import { AbsoluteFill, Audio, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";
import { c, sans } from "./theme";
import { Brand, EndCard, Opening } from "./Cards";
import { ColorChange, CommitLog, Detection, NameTags, Sealed, SessionTitle, SpeechCommit, TapStart, type Commit } from "./Overlays";
import { Pipeline, PIPELINE_FRAMES } from "./Pipeline";

/**
 * The edit. Drop footage into public/footage/ and fill in FOOTAGE (file name and the second to start from).
 * Until then each shot renders as a labeled placeholder, so timing and overlays can be reviewed now.
 */
export const FOOTAGE: Record<string, { file: string; from?: number } | null> = {
  walkIn: null,      // shot 1, cam A
  coats: null,       // shot 2, cam B
  tap: null,         // shot 3, cam B
  intro: null,       // shot 4, cam A
  introB: null,      // shot 5, cam B
  pour: null,        // shot 6
  readout: null,     // shot 7, cam B close-up
  drops: null,       // shot 8
  swirl: null,       // shot 9
  narrate: null,     // shot 10
  change: null,      // shot 11
  shrug: null,       // shot 12
  stop: null,        // shot 13
  screen: null,      // shot 15, screen recording
};

const Shot: React.FC<{ name: keyof typeof FOOTAGE; label: string }> = ({ name, label }) => {
  const clip = FOOTAGE[name];
  if (clip) {
    return <OffthreadVideo src={staticFile(`footage/${clip.file}`)} startFrom={Math.round((clip.from ?? 0) * 30)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />;
  }
  return (
    <AbsoluteFill style={{ background: "#26262a", alignItems: "center", justifyContent: "center", fontFamily: sans, color: "rgba(255,255,255,0.5)" }}>
      <div style={{ fontSize: 30, letterSpacing: "0.1em" }}>FOOTAGE</div>
      <div style={{ fontSize: 48, color: "rgba(255,255,255,0.85)", marginTop: 8 }}>{label}</div>
    </AbsoluteFill>
  );
};

const at = (s: number) => Math.round(s * 30);

// Commits that appear on the right while the montage plays (frames relative to the montage start).
const COMMITS: Commit[] = [
  { at: at(0.5), text: "Step seen: Measure 10 mL vinegar", kind: "step", hash: "a07e91c2" },
  { at: at(2.5), text: "Graduated cylinder · 10 mL", kind: "camera", hash: "3f9c0d17" },
  { at: at(5.0), text: "Scale reads 2.31 g", kind: "reading", hash: "b4e1aa02" },
  { at: at(7.5), text: "Indicator added · 3 drops", kind: "camera", hash: "77c2d9e0" },
  { at: at(10.0), text: "Swirling · 6 s", kind: "camera", hash: "c41b7e09" },
  { at: at(12.5), text: "“Two mL of base” → base_ml = 2", kind: "speech", hash: "5a8f3c11" },
  { at: at(15.0), text: "Color change detected", kind: "reading", hash: "9d2fa6e3" },
];

export const SCREEN_FRAMES = at(60);
export const MAIN_FRAMES = at(6) + at(6) + at(3) + at(3) + at(8) + at(17) + at(3) + at(3) + PIPELINE_FRAMES + SCREEN_FRAMES + at(6);

export const Main: React.FC<{ music?: string; names?: string }> = ({ music, names = "Omar Ibrahim · Lena · Mark" }) => {
  const f = useCurrentFrame();
  let t = 0;
  const seg = (len: number) => { const from = t; t += len; return { from, durationInFrames: len }; };
  const s = {
    open: seg(at(6)), walk: seg(at(6)), coats: seg(at(3)), tap: seg(at(3)), intro: seg(at(8)),
    montage: seg(at(17)), shrug: seg(at(3)), stop: seg(at(3)), pipeline: seg(PIPELINE_FRAMES), screen: seg(SCREEN_FRAMES), end: seg(at(6)),
  };
  // Music ducks under the pipeline voiceover-free section and fades out on the end card.
  const vol = interpolate(f, [s.walk.from, s.walk.from + 30, s.end.from + 60, s.end.from + s.end.durationInFrames], [0, 0.55, 0.55, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: c.night }}>
      {music ? <Audio src={staticFile(music)} volume={() => vol} /> : null}

      <Sequence {...s.open}><Opening /></Sequence>

      <Sequence {...s.walk}><Shot name="walkIn" label="1 · Walk in" /><Brand /></Sequence>
      <Sequence {...s.coats}><Shot name="coats" label="2 · Lab coats on" /></Sequence>
      <Sequence {...s.tap}><Shot name="tap" label="3 · Tap the station" /><TapStart x={0.52} y={0.5} /></Sequence>

      <Sequence {...s.intro}>
        <Sequence durationInFrames={at(4)}><Shot name="intro" label="4 · Intro (cam A)" /></Sequence>
        <Sequence from={at(4)}><Shot name="introB" label="5 · Intro (cam B)" /></Sequence>
        <NameTags out={at(7)} tags={[
          { name: "Dr. Omar", role: "Researcher · from the spoken intro", x: 0.36, y: 0.2, at: at(1.6) },
          { name: "Dr. Lena", role: "Researcher · from the spoken intro", x: 0.64, y: 0.22, at: at(2.6) },
        ]} />
        <SessionTitle title="Titrating vinegar with phenol red" people="Dr. Omar · Dr. Lena" at={at(4.2)} />
      </Sequence>

      <Sequence {...s.montage}>
        <Sequence durationInFrames={at(2.5)}><Shot name="pour" label="6 · Pour vinegar" /></Sequence>
        <Sequence from={at(2.5)} durationInFrames={at(2.5)}><Shot name="readout" label="7 · Readout close-up" /></Sequence>
        <Sequence from={at(5)} durationInFrames={at(2.5)}><Shot name="drops" label="8 · Indicator drops" /></Sequence>
        <Sequence from={at(7.5)} durationInFrames={at(3.5)}><Shot name="swirl" label="9 · Swirl" /></Sequence>
        <Sequence from={at(11)} durationInFrames={at(3)}><Shot name="narrate" label="10 · Lena narrates" /></Sequence>
        <Sequence from={at(14)}><Shot name="change" label="11 · Color change" /></Sequence>

        <Sequence from={at(0.6)} durationInFrames={at(2)}><Detection kind="camera" box={[0.38, 0.32, 0.16, 0.5]} label="Graduated cylinder" sub="10 mL · pouring" /></Sequence>
        <Sequence from={at(3.0)} durationInFrames={at(2)}><Detection kind="reading" box={[0.36, 0.34, 0.28, 0.26]} label="2.31 g" sub="read off the scale display" /></Sequence>
        <Sequence from={at(5.4)} durationInFrames={at(2)}><Detection kind="camera" box={[0.42, 0.3, 0.18, 0.46]} label="Adding indicator" sub="phenol red · 3 drops" /></Sequence>
        <Sequence from={at(8.0)} durationInFrames={at(3)}><Detection kind="camera" box={[0.34, 0.28, 0.3, 0.56]} label="Swirling" sub="mixing · 6 s from frame timestamps" /></Sequence>
        <Sequence from={at(11.1)} durationInFrames={at(3)}><SpeechCommit text="That's two mL of base… it's starting to turn pink" value="base_ml = 2" /></Sequence>
        <Sequence from={at(14.6)}><ColorChange /></Sequence>
        <CommitLog commits={COMMITS} />
      </Sequence>

      <Sequence {...s.shrug}><Shot name="shrug" label="12 · No notebook needed" /></Sequence>
      <Sequence {...s.stop}><Shot name="stop" label="13 · Tap to stop" /><Sealed commits={47} hash="sha256 9d2fa6e3…e8b0c5f4" /></Sequence>

      <Sequence {...s.pipeline}><Pipeline /></Sequence>
      <Sequence {...s.screen}><Shot name="screen" label="15 · Screen recording: the web app" /></Sequence>
      <Sequence {...s.end}><EndCard names={names} /></Sequence>
    </AbsoluteFill>
  );
};
