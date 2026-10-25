import React from "react";
import { Composition } from "remotion";
import { FPS, H, W } from "./theme";
import { Main, MAIN_FRAMES } from "./Main";
import { Pipeline, PIPELINE_FRAMES } from "./Pipeline";
import { Brand, EndCard, Opening } from "./Cards";
import { ColorChange, CommitLog, Detection, NameTags, Sealed, SessionTitle, SpeechCommit, TapStart } from "./Overlays";

/** Every piece renders on its own too (overlays with transparency), for editing in CapCut if preferred. */
export const Root: React.FC = () => (
  <>
    <Composition id="Main" component={Main} durationInFrames={MAIN_FRAMES} fps={FPS} width={W} height={H} defaultProps={{ music: undefined as string | undefined, names: "Omar Ibrahim · Lena · Mark" }} />
    <Composition id="Pipeline" component={Pipeline} durationInFrames={PIPELINE_FRAMES} fps={FPS} width={W} height={H} />
    <Composition id="Opening" component={Opening} durationInFrames={180} fps={FPS} width={W} height={H} />
    <Composition id="Brand" component={Brand} durationInFrames={90} fps={FPS} width={W} height={H} />
    <Composition id="EndCard" component={EndCard} durationInFrames={180} fps={FPS} width={W} height={H} defaultProps={{ names: "Omar Ibrahim · Lena · Mark" }} />
    <Composition id="TapStart" component={TapStart} durationInFrames={80} fps={FPS} width={W} height={H} defaultProps={{ x: 0.5, y: 0.55 }} />
    <Composition id="NameTags" component={NameTags} durationInFrames={150} fps={FPS} width={W} height={H}
      defaultProps={{ out: 130, tags: [
        { name: "Dr. Omar", role: "Researcher · from the spoken intro", x: 0.36, y: 0.2, at: 10 },
        { name: "Dr. Lena", role: "Researcher · from the spoken intro", x: 0.64, y: 0.22, at: 30 },
      ] }} />
    <Composition id="SessionTitle" component={SessionTitle} durationInFrames={130} fps={FPS} width={W} height={H} defaultProps={{ title: "Titrating vinegar with phenol red", people: "Dr. Omar · Dr. Lena", at: 0 }} />
    <Composition id="Detection" component={Detection} durationInFrames={90} fps={FPS} width={W} height={H} defaultProps={{ kind: "reading" as const, box: [0.36, 0.34, 0.28, 0.26] as [number, number, number, number], label: "2.31 g", sub: "read off the scale display", at: 0 }} />
    <Composition id="SpeechCommit" component={SpeechCommit} durationInFrames={110} fps={FPS} width={W} height={H} defaultProps={{ text: "That's two mL of base… it's starting to turn pink", value: "base_ml = 2", at: 0 }} />
    <Composition id="CommitLog" component={CommitLog} durationInFrames={510} fps={FPS} width={W} height={H} defaultProps={{ commits: [
      { at: 15, text: "Step seen: Measure 10 mL vinegar", kind: "step" as const, hash: "a07e91c2" },
      { at: 75, text: "Scale reads 2.31 g", kind: "reading" as const, hash: "b4e1aa02" },
      { at: 150, text: "Swirling · 6 s", kind: "camera" as const, hash: "c41b7e09" },
    ] }} />
    <Composition id="ColorChange" component={ColorChange} durationInFrames={75} fps={FPS} width={W} height={H} />
    <Composition id="Sealed" component={Sealed} durationInFrames={90} fps={FPS} width={W} height={H} defaultProps={{ commits: 47, hash: "sha256 9d2fa6e3…e8b0c5f4" }} />
  </>
);
