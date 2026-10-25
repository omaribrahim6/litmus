import React from "react";
import { AbsoluteFill, interpolate, Sequence, staticFile, useCurrentFrame, Audio } from "remotion";
import { c, mono, sans } from "./theme";
import { Chip, Glass, Mono, Orb, Typed, fade, usePop } from "./parts";

const sfx = (name: string) => staticFile(`sfx/${name}.wav`);

/* --------------------------------------------------------------- tap to start */

/** A ripple at the fingertip and the station's Start recording button popping out of it. x, y are 0-1 of the frame. */
export const TapStart: React.FC<{ x: number; y: number }> = ({ x, y }) => {
  const f = useCurrentFrame();
  const pop = usePop(4);
  const toRec = fade(f, 26, 32);
  const out = 1 - fade(f, 62, 72);
  return (
    <AbsoluteFill>
      <Audio src={sfx("click")} />
      <Sequence from={26}><Audio src={sfx("blip")} volume={0.7} /></Sequence>
      {[0, 6, 12].map((d) => {
        const t = Math.max(0, f - d) / 24;
        return <div key={d} style={{
          position: "absolute", left: `${x * 100}%`, top: `${y * 100}%`, width: 40 + t * 260, height: 40 + t * 260,
          transform: "translate(-50%,-50%)", borderRadius: "50%", border: "3px solid rgba(255,255,255,0.9)", opacity: Math.max(0, 0.9 - t),
        }} />;
      })}
      <div style={{ position: "absolute", left: `${x * 100}%`, top: `${y * 100}%`, transform: `translate(-50%, -150%) scale(${pop})`, opacity: out }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 18, padding: "22px 40px", borderRadius: 999, fontFamily: sans, fontWeight: 600, fontSize: 40,
          color: toRec ? "#fff" : c.ink, background: toRec ? "#e5484d" : "#fff", boxShadow: "0 24px 60px rgba(0,0,0,0.4)", whiteSpace: "nowrap",
        }}>
          <span style={{ width: 22, height: 22, borderRadius: "50%", background: toRec ? "#fff" : "#e5484d", opacity: toRec ? 0.5 + 0.5 * Math.sin(f / 4) : 1 }} />
          {toRec ? "Recording" : "Start recording"}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* --------------------------------------------------------------- name tags */

export interface Tag { name: string; role: string; x: number; y: number; at: number }

/** Name tags over each head, from the spoken intro. x, y = the top of the head (0-1). */
export const NameTags: React.FC<{ tags: Tag[]; out?: number }> = ({ tags, out = 999 }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      {tags.map((t) => {
        const p = usePop(t.at);
        const o = Math.min(fade(f, t.at, t.at + 4), 1 - fade(f, out, out + 8));
        return (
          <React.Fragment key={t.name}>
            <Sequence from={t.at}><Audio src={sfx("pop")} /></Sequence>
            <div style={{ position: "absolute", left: `${t.x * 100}%`, top: `${t.y * 100}%`, transform: `translate(-50%, -100%) translateY(${-24 * p}px) scale(${0.6 + 0.4 * p})`, transformOrigin: "50% 100%", opacity: o }}>
              <Glass style={{ padding: "14px 22px 14px 16px", display: "flex", alignItems: "center", gap: 14, whiteSpace: "nowrap" }}>
                <Orb size={30} />
                <div>
                  <div style={{ fontSize: 34, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.1 }}>{t.name}</div>
                  <div style={{ fontSize: 20, opacity: 0.7, marginTop: 2 }}>{t.role}</div>
                </div>
              </Glass>
              <div style={{ width: 2, height: 34 * p, margin: "0 auto", background: "linear-gradient(rgba(255,255,255,0.8), rgba(255,255,255,0))" }} />
            </div>
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};

/* --------------------------------------------------------------- session title */

export const SessionTitle: React.FC<{ title: string; people: string; at?: number }> = ({ title, people, at = 0 }) => {
  const f = useCurrentFrame();
  const p = usePop(at, 18);
  const out = 1 - fade(f, 110, 122);
  return (
    <AbsoluteFill>
      <Sequence from={at}><Audio src={sfx("whoosh")} volume={0.6} /></Sequence>
      <div style={{ position: "absolute", left: 80, bottom: 90, transform: `translateX(${(1 - p) * -60}px)`, opacity: Math.min(p, out) }}>
        <Glass style={{ padding: "24px 30px", minWidth: 760 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 21, opacity: 0.75 }}>
            <Orb size={20} /> Session titled by Gemini from the spoken intro
          </div>
          <div style={{ fontSize: 50, fontWeight: 600, letterSpacing: "-0.025em", marginTop: 10, lineHeight: 1.1 }}>
            <Typed text={title} at={at + 8} cps={34} />
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
            <Chip color={c.blue}>{people}</Chip>
            <Chip color={c.green}>Experiment set up · 6 steps</Chip>
          </div>
        </Glass>
      </div>
    </AbsoluteFill>
  );
};

/* --------------------------------------------------------------- detections */

export type DetKind = "camera" | "speech" | "reading" | "step";
const KIND_COLOR: Record<DetKind, string> = { camera: c.amber, speech: c.blue, reading: c.green, step: c.violet };
const KIND_LABEL: Record<DetKind, string> = { camera: "Seen by Gemini", speech: "Heard", reading: "Read off the bench", step: "Step" };

/** Corner brackets drawing in around what Gemini detected, with a label. Box in 0-1 frame units. */
export const Detection: React.FC<{ box: [number, number, number, number]; label: string; sub?: string; kind: DetKind; at?: number }> = ({ box, label, sub, kind, at = 0 }) => {
  const f = useCurrentFrame();
  const [x, y, w, h] = box;
  const draw = fade(f, at, at + 10);
  const p = usePop(at + 6);
  const out = 1 - fade(f, at + 75, at + 85);
  const col = KIND_COLOR[kind];
  const L = 46 * draw;
  const corner = (s: React.CSSProperties) => <div style={{ position: "absolute", width: L, height: L, borderColor: col, borderStyle: "solid", ...s }} />;
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <Sequence from={at}><Audio src={sfx("blip")} volume={0.55} /></Sequence>
      <div style={{ position: "absolute", left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%`,
        background: `color-mix(in oklab, ${col} ${8 * draw}%, transparent)`, borderRadius: 10 }}>
        {corner({ left: 0, top: 0, borderWidth: "5px 0 0 5px", borderTopLeftRadius: 10 })}
        {corner({ right: 0, top: 0, borderWidth: "5px 5px 0 0", borderTopRightRadius: 10 })}
        {corner({ left: 0, bottom: 0, borderWidth: "0 0 5px 5px", borderBottomLeftRadius: 10 })}
        {corner({ right: 0, bottom: 0, borderWidth: "0 5px 5px 0", borderBottomRightRadius: 10 })}
        <div style={{ position: "absolute", left: 0, top: -14, transform: `translateY(-100%) scale(${p})`, transformOrigin: "0 100%" }}>
          <Glass style={{ padding: "10px 18px", borderRadius: 14, whiteSpace: "nowrap" }}>
            <div style={{ fontSize: 17, color: col, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>{KIND_LABEL[kind]}</div>
            <div style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.02em" }}>{label}</div>
            {sub ? <div style={{ fontSize: 19, opacity: 0.7 }}>{sub}</div> : null}
          </Glass>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** A spoken line becoming a commit: caption-style quote with a "committed" tick. */
export const SpeechCommit: React.FC<{ text: string; value?: string; at?: number }> = ({ text, value, at = 0 }) => {
  const f = useCurrentFrame();
  const p = usePop(at, 16);
  const tick = usePop(at + 34);
  const out = 1 - fade(f, at + 95, at + 105);
  return (
    <AbsoluteFill>
      <Sequence from={at + 34}><Audio src={sfx("tick")} /></Sequence>
      <div style={{ position: "absolute", left: "50%", bottom: 110, transform: `translate(-50%, ${(1 - p) * 30}px)`, opacity: Math.min(p, out) }}>
        <Glass style={{ padding: "18px 26px", display: "flex", alignItems: "center", gap: 18, whiteSpace: "nowrap" }}>
          <span style={{ fontSize: 22, color: c.blue, fontWeight: 600 }}>HEARD</span>
          <span style={{ fontSize: 36, fontWeight: 500 }}>“<Typed text={text} at={at + 4} cps={30} caret={false} />”</span>
          <span style={{ transform: `scale(${tick})`, display: "inline-flex" }}>
            <Chip color={c.green}>{value ? `${value} · committed` : "committed"}</Chip>
          </span>
        </Glass>
      </div>
    </AbsoluteFill>
  );
};

/* --------------------------------------------------------------- commit log */

export interface Commit { at: number; text: string; kind: DetKind; hash: string }

/** The record building up on the right edge as things happen. */
export const CommitLog: React.FC<{ commits: Commit[]; title?: string }> = ({ commits, title = "Litmus · recording" }) => {
  const f = useCurrentFrame();
  const shown = commits.filter((cm) => f >= cm.at);
  const enter = fade(f, 0, 10);
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", right: 48, top: 48, width: 520, opacity: enter, transform: `translateX(${(1 - enter) * 40}px)` }}>
        <Glass style={{ padding: "18px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 20, fontWeight: 600 }}>
            <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#e5484d", opacity: 0.5 + 0.5 * Math.sin(f / 5) }} />
            {title}
            <Mono style={{ marginLeft: "auto", fontSize: 18, opacity: 0.6 }}>{shown.length} commits</Mono>
          </div>
          <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
            {shown.slice(-6).map((cm) => {
              const p = Math.min(1, (f - cm.at) / 8);
              return (
                <div key={cm.hash} style={{ display: "flex", alignItems: "center", gap: 12, opacity: p, transform: `translateY(${(1 - p) * 12}px)` }}>
                  <span style={{ width: 10, height: 10, borderRadius: 3, transform: "rotate(45deg)", background: KIND_COLOR[cm.kind], flexShrink: 0 }} />
                  <span style={{ fontSize: 21, flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{cm.text}</span>
                  <Mono style={{ fontSize: 16, opacity: 0.5 }}>{cm.hash}</Mono>
                </div>
              );
            })}
          </div>
        </Glass>
      </div>
      {commits.map((cm) => <Sequence key={cm.hash} from={cm.at}><Audio src={sfx("tick")} volume={0.35} /></Sequence>)}
    </AbsoluteFill>
  );
};

/* --------------------------------------------------------------- moments */

export const ColorChange: React.FC = () => {
  const f = useCurrentFrame();
  const p = usePop(0, 12);
  const out = 1 - fade(f, 60, 72);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <Audio src={sfx("hit")} />
      <AbsoluteFill style={{ background: "#ff6d8c", opacity: interpolate(f, [0, 3, 14], [0, 0.35, 0], { extrapolateRight: "clamp" }) }} />
      <div style={{ transform: `scale(${0.7 + 0.3 * p})`, opacity: Math.min(p, out) }}>
        <Glass style={{ padding: "26px 44px", display: "flex", alignItems: "center", gap: 22 }}>
          <div style={{ width: 26, height: 70, borderRadius: 6, background: "linear-gradient(#e8c33a 0 48%, #d0365b 52% 100%)" }} />
          <div>
            <div style={{ fontSize: 56, fontWeight: 700, letterSpacing: "-0.03em" }}>Color change detected</div>
            <div style={{ fontSize: 24, opacity: 0.75 }}>Measured by the camera · a* +29.8 from baseline · frame saved</div>
          </div>
        </Glass>
      </div>
    </AbsoluteFill>
  );
};

export const Sealed: React.FC<{ commits: number; hash: string }> = ({ commits, hash }) => {
  const f = useCurrentFrame();
  const p = usePop(4, 10);
  const out = 1 - fade(f, 80, 90);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", background: `rgba(0,0,0,${0.35 * Math.min(fade(f, 0, 8), out)})` }}>
      <Sequence from={4}><Audio src={sfx("stamp")} /></Sequence>
      <div style={{ transform: `scale(${2 - p}) rotate(${-4 * p}deg)`, opacity: Math.min(p, out) }}>
        <div style={{ border: "6px solid #5fd29b", color: "#5fd29b", borderRadius: 22, padding: "26px 46px", fontFamily: sans, textAlign: "center", background: "rgba(10,20,14,0.55)" }}>
          <div style={{ fontSize: 72, fontWeight: 800, letterSpacing: "-0.02em" }}>RECORD SEALED</div>
          <div style={{ fontSize: 28, fontWeight: 600, marginTop: 6 }}>{commits} commits · SHA-256 hash chain</div>
          <div style={{ fontFamily: mono, fontSize: 24, opacity: 0.8, marginTop: 6 }}>{hash}</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
