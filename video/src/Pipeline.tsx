import React from "react";
import { AbsoluteFill, Audio, Img, interpolate, Sequence, staticFile, useCurrentFrame } from "remotion";
import { c, ease, mono, sans } from "./theme";
import { Chip, Mono, Orb, Typed, fade, usePop } from "./parts";

const sfx = (name: string) => staticFile(`sfx/${name}.wav`);

const Grid: React.FC = () => (
  <AbsoluteFill style={{
    background: `radial-gradient(1200px 700px at 50% 45%, #1a1a22 0%, ${c.night} 70%)`,
  }}>
    <AbsoluteFill style={{
      backgroundImage: "linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)",
      backgroundSize: "64px 64px", maskImage: "radial-gradient(ellipse at center, black 30%, transparent 75%)",
    }} />
  </AbsoluteFill>
);

const Heading: React.FC<{ kicker: string; title: string; at?: number }> = ({ kicker, title, at = 0 }) => {
  const f = useCurrentFrame();
  const o = fade(f, at, at + 12);
  return (
    <div style={{ position: "absolute", top: 70, left: 0, right: 0, textAlign: "center", fontFamily: sans, color: "#fff", opacity: o, transform: `translateY(${(1 - o) * 12}px)` }}>
      <div style={{ fontSize: 22, letterSpacing: "0.16em", textTransform: "uppercase", opacity: 0.55, fontWeight: 600 }}>{kicker}</div>
      <div style={{ fontSize: 58, fontWeight: 600, letterSpacing: "-0.03em", marginTop: 8 }}>{title}</div>
    </div>
  );
};

const Card: React.FC<{ x: number; y: number; w: number; children: React.ReactNode; p: number; style?: React.CSSProperties }> = ({ x, y, w, children, p, style }) => (
  <div style={{
    position: "absolute", left: x, top: y, width: w, opacity: p, transform: `translateY(${(1 - p) * 24}px) scale(${0.96 + 0.04 * p})`,
    background: "rgba(255,255,255,0.05)", border: `1px solid ${c.nightRule}`, borderRadius: 20, padding: 22, color: "#fff", fontFamily: sans,
    boxShadow: "0 30px 80px rgba(0,0,0,0.45)", ...style,
  }}>{children}</div>
);

/* ------------------------------------------------------------------ 1. inputs into Gemini */

const Inputs: React.FC<{ frames: string[] }> = ({ frames }) => {
  const f = useCurrentFrame();
  const p = [usePop(6), usePop(14), usePop(22)];
  const orb = usePop(30, 12);
  const models = [
    { at: 52, name: "Gemini 3.8 Flash", role: "watches every frame", col: c.amber, y: 330 },
    { at: 62, name: "Gemini 3.5 Flash-Lite", role: "listens to the bench", col: c.blue, y: 470 },
    { at: 72, name: "Gemini 4 Argon", role: "reasons over the record", col: c.violet, y: 610 },
  ];
  const flow = (i: number) => (f * 6 + i * 40) % 160;
  return (
    <AbsoluteFill>
      <Heading kicker="Step 1" title="Gemini sees and hears the bench" />
      <Sequence from={30}><Audio src={sfx("riser")} volume={0.5} /></Sequence>
      {/* camera */}
      <Card x={120} y={290} w={430} p={p[0]}>
        <div style={{ fontSize: 20, opacity: 0.6, marginBottom: 12 }}>Two cameras · a keyframe every 2 s</div>
        <div style={{ display: "flex", gap: 8 }}>
          {frames.slice(0, 3).map((src, i) => <Img key={i} src={src} style={{ width: 122, height: 80, objectFit: "cover", borderRadius: 8, opacity: fade(f, 10 + i * 5, 16 + i * 5) }} />)}
        </div>
      </Card>
      {/* audio */}
      <Card x={120} y={480} w={430} p={p[1]}>
        <div style={{ fontSize: 20, opacity: 0.6, marginBottom: 12 }}>Best of two microphones</div>
        <div style={{ display: "flex", alignItems: "center", gap: 5, height: 60 }}>
          {Array.from({ length: 44 }).map((_, i) => (
            <div key={i} style={{ width: 5, borderRadius: 3, background: c.blue, height: 8 + Math.abs(Math.sin(i * 0.7 + f / 4)) * 44 * (0.4 + 0.6 * Math.abs(Math.sin(i * 0.31))) }} />
          ))}
        </div>
      </Card>
      {/* instruments */}
      <Card x={120} y={670} w={430} p={p[2]}>
        <div style={{ fontSize: 20, opacity: 0.6, marginBottom: 8 }}>Instruments in view</div>
        <div style={{ display: "flex", gap: 14, alignItems: "baseline" }}>
          <Mono style={{ fontSize: 46, color: c.green }}>22.6 °C</Mono>
          <Mono style={{ fontSize: 46, color: c.green }}>2.31 g</Mono>
        </div>
      </Card>
      {/* flow lines */}
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {[360, 540, 720].map((y, i) => (
          <path key={y} d={`M 560 ${y} C 760 ${y}, 760 540, 900 540`} fill="none" stroke="url(#g)" strokeWidth={3}
            strokeDasharray="8 152" strokeDashoffset={-flow(i)} opacity={fade(f, 34, 44)} />
        ))}
        <defs><linearGradient id="g"><stop offset="0" stopColor="#fff" stopOpacity="0.2" /><stop offset="1" stopColor="#ff8fa8" /></linearGradient></defs>
      </svg>
      <div style={{ position: "absolute", left: 960 - 80, top: 540 - 80, transform: `scale(${orb})` }}><Orb size={160} glow={0.45} pulse /></div>
      {models.map((m) => {
        const q = usePop(m.at, 16);
        return (
          <div key={m.name} style={{ position: "absolute", left: 1160, top: m.y, opacity: q, transform: `translateX(${(1 - q) * 30}px)`, fontFamily: sans, color: "#fff" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <span style={{ width: 12, height: 12, borderRadius: "50%", background: m.col }} />
              <span style={{ fontSize: 40, fontWeight: 600, letterSpacing: "-0.02em" }}>{m.name}</span>
            </div>
            <div style={{ fontSize: 26, opacity: 0.6, marginLeft: 26 }}>{m.role}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ 2. structured output */

const JSON_CARDS = [
  { col: c.green, lines: [["kind", '"measurement"'], ["key", '"mass_g"'], ["value", "2.31"], ["unit", '"g"'], ["provenance", '"inferred"'], ["evidence", '"frm:3f9c…"']] },
  { col: c.blue, lines: [["kind", '"narration"'], ["text", '"turning pink"'], ["provenance", '"inferred"'], ["evidence", '"audio 0:41"']] },
  { col: c.violet, lines: [["kind", '"step_confirmed"'], ["step", '"titrate"'], ["provenance", '"inferred"'], ["evidence", '"frm:a07e…"']] },
];

const Structured: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Heading kicker="Step 2" title="Turned into structured data, with receipts" />
      <div style={{ position: "absolute", left: 960 - 50, top: 250 }}><Orb size={100} glow={0.35} pulse /></div>
      {JSON_CARDS.map((card, i) => {
        const at = 10 + i * 16;
        const p = usePop(at, 15);
        const x = 220 + i * 520;
        return (
          <React.Fragment key={i}>
            <Sequence from={at}><Audio src={sfx("pop")} volume={0.5} /></Sequence>
            <Card x={x} y={420} w={480} p={p} style={{ borderColor: `color-mix(in oklab, ${card.col} 40%, transparent)` }}>
              <Mono style={{ fontSize: 24, lineHeight: 1.6, display: "block" }}>
                <span style={{ opacity: 0.5 }}>{"{"}</span>
                {card.lines.map(([k, v], j) => (
                  <div key={k} style={{ paddingLeft: 24, opacity: fade(f, at + 6 + j * 4, at + 10 + j * 4) }}>
                    <span style={{ color: "#9aa0ff" }}>&quot;{k}&quot;</span><span style={{ opacity: 0.5 }}>: </span>
                    <span style={{ color: k === "provenance" ? c.amber : k === "evidence" ? c.green : "#fff" }}>{v}</span>
                  </div>
                ))}
                <span style={{ opacity: 0.5 }}>{"}"}</span>
              </Mono>
            </Card>
          </React.Fragment>
        );
      })}
      <div style={{ position: "absolute", bottom: 120, left: 0, right: 0, display: "flex", justifyContent: "center", gap: 14, opacity: fade(f, 70, 82) }}>
        <Chip color={c.green}>Numbers read exactly as shown, never estimated</Chip>
        <Chip color={c.amber}>Every value tagged measured, reported or inferred</Chip>
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ 3. Tiger Data */

const ROWS = [
  ["10:42:03.120", "step_confirmed", "inferred", "a07e91c2"],
  ["10:42:09.884", "measurement", "inferred", "3f9c0d17"],
  ["10:42:16.402", "narration", "inferred", "c41b7e09"],
  ["10:42:21.951", "flip_detected", "measured", "9d2fa6e3"],
  ["10:42:30.000", "run_sealed", "measured", "e8b0c5f4"],
];

const Tiger: React.FC = () => {
  const f = useCurrentFrame();
  const tbl = usePop(4, 16);
  const chunks = usePop(30, 16);
  return (
    <AbsoluteFill>
      <Heading kicker="Step 3" title="Stored in Tiger Data, tamper-evident" />
      {/* events hypertable */}
      <Card x={120} y={250} w={1000} p={tbl} style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "16px 22px", borderBottom: `1px solid ${c.nightRule}` }}>
          <span style={{ fontSize: 24, fontWeight: 600 }}>events</span>
          <Chip color={c.amber} style={{ fontSize: 17, padding: "3px 10px" }}>hypertable</Chip>
          <Mono style={{ marginLeft: "auto", fontSize: 18, opacity: 0.5 }}>append-only · per-run advisory lock</Mono>
        </div>
        <div style={{ padding: "8px 22px 16px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "230px 230px 160px 1fr", fontSize: 17, opacity: 0.45, padding: "6px 0" }}>
            <span>time</span><span>kind</span><span>provenance</span><span>hash = sha256(prev_hash ‖ event)</span>
          </div>
          {ROWS.map((r, i) => {
            const at = 14 + i * 9;
            const o = fade(f, at, at + 6);
            return (
              <React.Fragment key={r[3]}>
                <Sequence from={at}><Audio src={sfx("tick")} volume={0.35} /></Sequence>
                <div style={{ display: "grid", gridTemplateColumns: "230px 230px 160px 1fr", alignItems: "center", padding: "9px 0", borderTop: `1px solid ${c.nightRule}`, opacity: o, transform: `translateX(${(1 - o) * -20}px)` }}>
                  <Mono style={{ fontSize: 21, opacity: 0.8 }}>{r[0]}</Mono>
                  <Mono style={{ fontSize: 21 }}>{r[1]}</Mono>
                  <Mono style={{ fontSize: 21, color: r[2] === "measured" ? "#ddd" : c.amber }}>{r[2]}</Mono>
                  <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    {i > 0 ? <Mono style={{ fontSize: 19, opacity: 0.4 }}>{ROWS[i - 1][3]} →</Mono> : <Mono style={{ fontSize: 19, opacity: 0.4 }}>genesis →</Mono>}
                    <Mono style={{ fontSize: 21, color: c.green }}>{r[3]}</Mono>
                  </span>
                </div>
              </React.Fragment>
            );
          })}
        </div>
      </Card>
      {/* readings hypertable chunks + continuous aggregate */}
      <Card x={1170} y={250} w={630} p={chunks}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 24, fontWeight: 600 }}>readings</span>
          <Chip color={c.amber} style={{ fontSize: 17, padding: "3px 10px" }}>hypertable</Chip>
        </div>
        <div style={{ fontSize: 18, opacity: 0.5, marginTop: 6 }}>Sensor and camera values, COPY-ingested, chunked by time</div>
        <div style={{ display: "flex", gap: 10, marginTop: 18, alignItems: "flex-end", height: 150 }}>
          {Array.from({ length: 8 }).map((_, i) => {
            const fill = interpolate(f, [34 + i * 5, 54 + i * 5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={i} style={{ flex: 1, height: 150, borderRadius: 8, border: `1px solid ${c.nightRule}`, position: "relative", overflow: "hidden" }}>
                <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: `${fill * 100}%`, background: "linear-gradient(#f0b25e55, #f0b25e22)" }} />
                <Mono style={{ position: "absolute", bottom: 6, left: 0, right: 0, textAlign: "center", fontSize: 14, opacity: 0.55 }}>chunk {i + 1}</Mono>
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 20, display: "flex", alignItems: "center", gap: 12, opacity: fade(f, 80, 92) }}>
          <span style={{ fontSize: 30 }}>↓</span>
          <div>
            <div style={{ fontSize: 24, fontWeight: 600 }}>readings_1s</div>
            <div style={{ fontSize: 18, opacity: 0.55 }}>real-time continuous aggregate, powers every timeline</div>
          </div>
        </div>
      </Card>
      <div style={{ position: "absolute", left: 120, top: 790, display: "flex", gap: 14, opacity: fade(f, 70, 82) }}>
        <Chip color={c.green}>Change one byte and verification fails at that commit</Chip>
        <Chip color={c.blue}>Run sealed with a digest of every reading and frame</Chip>
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ 4. vectors + hybrid search */

const rnd = (i: number) => {
  const x = Math.sin(i * 12.9898) * 43758.5453;
  return x - Math.floor(x);
};
const POINTS = Array.from({ length: 64 }, (_, i) => ({ x: 1080 + rnd(i) * 700, y: 300 + rnd(i + 99) * 420, near: false }))
  .map((p, i) => ({ ...p, near: [7, 19, 33, 41, 52].includes(i) }));
const Q = { x: 1420, y: 500 };

const Vectors: React.FC = () => {
  const f = useCurrentFrame();
  const bars = usePop(16, 18);
  const answer = usePop(150, 16);
  return (
    <AbsoluteFill>
      <Heading kicker="Step 4" title="Searchable by meaning, answered with citations" />
      <Card x={120} y={260} w={820} p={usePop(2, 16)}>
        <div style={{ fontSize: 18, opacity: 0.55 }}>commit</div>
        <div style={{ fontSize: 28, marginTop: 4 }}>“Diluted from the tap-water jug”</div>
        <div style={{ fontSize: 18, opacity: 0.55, marginTop: 20 }}>gemini-embedding-001 · 768 dimensions</div>
        <div style={{ display: "flex", gap: 2, height: 70, alignItems: "center", marginTop: 8 }}>
          {Array.from({ length: 96 }).map((_, i) => {
            const v = Math.sin(i * 1.7) * Math.cos(i * 0.37);
            return <div key={i} style={{ flex: 1, height: `${(10 + Math.abs(v) * 90) * bars}%`, borderRadius: 2, background: v > 0 ? c.violet : c.rose, opacity: 0.85 }} />;
          })}
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 18, opacity: fade(f, 40, 50) }}>
          <Chip color={c.violet} style={{ fontSize: 18 }}>pgvector · HNSW index</Chip>
          <Chip color={c.amber} style={{ fontSize: 18 }}>tsvector · full-text</Chip>
        </div>
      </Card>
      {/* embedding space */}
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {POINTS.map((p, i) => POINTS.slice(i + 1, i + 3).map((q, j) => (
          <line key={`${i}-${j}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y} stroke="#fff" strokeOpacity={0.07 * fade(f, 30 + i * 0.6, 40 + i * 0.6)} />
        )))}
        {POINTS.map((p, i) => {
          const hit = p.near && f > 96;
          return <circle key={i} cx={p.x} cy={p.y} r={hit ? 9 : 5} fill={hit ? c.green : "#fff"} opacity={fade(f, 24 + i * 0.6, 32 + i * 0.6) * (hit ? 1 : 0.45)} />;
        })}
        {f > 80 ? POINTS.filter((p) => p.near).map((p, i) => (
          <line key={i} x1={Q.x} y1={Q.y} x2={p.x} y2={p.y} stroke={c.green} strokeWidth={2} strokeDasharray="6 6" opacity={fade(f, 90 + i * 3, 98 + i * 3)} />
        )) : null}
        <circle cx={Q.x} cy={Q.y} r={14 * ease((f - 76) / 12)} fill={c.rose} />
      </svg>
      <div style={{ position: "absolute", left: Q.x - 250, top: Q.y + 40, width: 500, display: "flex", justifyContent: "center", opacity: fade(f, 78, 88) }}>
        <div style={{ fontFamily: sans, color: "#fff", textAlign: "center", padding: "12px 22px", borderRadius: 16, background: "rgba(13,13,15,0.92)", border: `1px solid color-mix(in oklab, ${c.rose} 45%, transparent)` }}>
          <div style={{ fontSize: 19, opacity: 0.6 }}>question</div>
          <div style={{ fontSize: 30, fontWeight: 600, whiteSpace: "nowrap" }}>“Why was Method B different?”</div>
        </div>
      </div>
      <Sequence from={76}><Audio src={sfx("whoosh")} volume={0.5} /></Sequence>
      <div style={{ position: "absolute", left: 120, top: 640, fontFamily: sans, color: "#fff", opacity: fade(f, 112, 124) }}>
        <div style={{ fontSize: 22, opacity: 0.55 }}>Hybrid search · reciprocal rank fusion of vector and keyword matches</div>
      </div>
      {/* answer */}
      <Sequence from={150}><Audio src={sfx("chime")} volume={0.6} /></Sequence>
      <Card x={120} y={700} w={820} p={answer}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 20 }}>
          <Orb size={24} /> <b>Litmus</b> <span style={{ opacity: 0.55 }}>Gemini 4 Argon</span>
          <Chip color={c.green} style={{ marginLeft: "auto", fontSize: 17, padding: "3px 10px" }}>Grounded in 6 receipts</Chip>
        </div>
        <div style={{ fontSize: 27, lineHeight: 1.45, marginTop: 12 }}>
          <Typed text="Method B was diluted with tap water instead of distilled" at={158} cps={42} caret={false} />
          {f > 196 ? <Mono style={{ fontSize: 17, color: c.blue, border: `1px solid ${c.blue}`, borderRadius: 6, padding: "1px 6px", marginLeft: 6 }}>1,2</Mono> : null}
          {f > 200 ? <> <Typed text="; stirring time matched the control" at={200} cps={42} caret={false} /></> : null}
          {f > 222 ? <Mono style={{ fontSize: 17, color: c.blue, border: `1px solid ${c.blue}`, borderRadius: 6, padding: "1px 6px", marginLeft: 6 }}>3</Mono> : null}
        </div>
      </Card>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ assembled */

export const PIPELINE_FRAMES = 150 + 120 + 130 + 260 + 80;

export const Pipeline: React.FC<{ frames?: string[] }> = ({ frames = [staticFile("frames/f1.jpg"), staticFile("frames/f2.jpg"), staticFile("frames/f3.jpg")] }) => {
  const f = useCurrentFrame();
  const scenes = [
    { from: 0, len: 150, el: <Inputs frames={frames} /> },
    { from: 150, len: 120, el: <Structured /> },
    { from: 270, len: 130, el: <Tiger /> },
    { from: 400, len: 260, el: <Vectors /> },
  ];
  return (
    <AbsoluteFill style={{ fontFamily: sans }}>
      <Grid />
      {scenes.map((s) => (
        <Sequence key={s.from} from={s.from} durationInFrames={s.len}>
          <AbsoluteFill style={{ opacity: Math.min(fade(f, s.from, s.from + 10), 1 - fade(f, s.from + s.len - 10, s.from + s.len)) }}>{s.el}</AbsoluteFill>
        </Sequence>
      ))}
      <Sequence from={660}>
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", color: "#fff", textAlign: "center", opacity: fade(f, 662, 676) }}>
          <div style={{ fontSize: 76, fontWeight: 600, letterSpacing: "-0.035em", lineHeight: 1.15 }}>
            Gemini sees it.<br />Tiger Data remembers it.<br /><span style={{ background: c.ai, WebkitBackgroundClip: "text", color: "transparent" }}>You never have to commit.</span>
          </div>
        </AbsoluteFill>
      </Sequence>
    </AbsoluteFill>
  );
};
