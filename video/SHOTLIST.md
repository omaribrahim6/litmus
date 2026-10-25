# Litmus demo: shoot plan

Target length 2:30–2:50. Two phones, both landscape, 4K 30 fps (or 1080p 60), exposure and focus locked (long-press on the subject), and nothing behind the lens that you can't show.

- **Cam A, the station:** mounted on the bench, wide, never moves. This is "what Litmus sees".
- **Cam B, the operator:** handheld or a second tripod, close-ups and reactions, about 1–2 m away.

**Before every take:** start both cameras, then clap once in view of both (this syncs the two cameras in the edit). Hold each action 3–5 s, and pause 1 s before and after any line.

**Run Litmus for real during the shoot.** Have the station (Pi, webcam, kiosk) on the bench, and press Start on the kiosk from a laptop or a third phone at `http://172.20.10.12:8080` at the same moment you tap on camera. The web-app half of the video then shows the actual run from the footage.

---

## Shots (in story order; film in any order)

| # | Cam | Shot | Hold | Notes |
|---|-----|------|------|-------|
| 1 | A | Empty bench, then the two of you walk in from the side | 6 s | Music starts here in the edit |
| 2 | B | Putting on lab coats, buttoning, gloves snap | 2–3 clips × 3 s | Slow and deliberate. Gloves snap = SFX hit |
| 3 | B | Close-up: hand reaches toward the mounted station screen and taps | 3 s | Keep the finger still for 1 s after the tap. The "Start recording" button gets added at the finger in the edit. Don't show the station token or URL |
| 4 | A | Both of you facing the bench, Omar says the intro, looking at the station | 8 s | Line: "Hi, I'm Dr. Omar, and this is my colleague Dr. Lena. Today we're titrating vinegar with phenol red." Name tags appear over your heads, so keep heads in frame with space above |
| 5 | B | Same line from a 3/4 angle (backup) | 8 s | Lets us cut between angles during the tags |
| 6 | A + B | Measuring: pour vinegar into the graduated cylinder | 4 s each | Turn the cylinder graduation toward Cam A |
| 7 | B | Close-up: the scale or thermometer readout | 3 s | Gemini "reads" it, so it must be legible. Fill the frame |
| 8 | A | Adding indicator drops | 4 s | |
| 9 | A + B | Titrating: adding base, swirling the flask | 2 × 5 s | Swirl = the "mixing" detection |
| 10 | B | Lena narrates while working: "That's two mL of base… it's starting to turn pink" | 6 s | Spoken values become data in the record. Speak clearly |
| 11 | B | Close-up of the color change in the flask | 5 s | Hero shot. Use a white sheet behind the flask |
| 12 | A | Omar writes nothing, shrugs at the notebook, smiles | 3 s | The joke: you never have to write it down |
| 13 | B | Tap the station again to stop | 3 s | "Record sealed" stamp goes here |
| 14 | — | Room tone: 10 s of silence with both phones recording | 10 s | For clean audio under cuts |
| 15 | — | Screen recording (later, at the laptop): the web app | 60–90 s | See below |

## Screen recording (after the shoot)

Record at 1440×900 or larger, light theme, browser zoom 100%, cursor moving slowly:

1. The experiment page: scroll the stats, results chart and runs.
2. Open the run from the shoot. Press play, then drag the timeline playhead across the Steps, Speech and Seen-by-Gemini tracks, and click a Gemini pill to show its frame in the inspector.
3. Ask your lab: type "Why was this run different from the control?" Show the answer, click a receipt number, and open **Why this answer?**
4. Switch the Ask page to **Data**, then click **Export CSV**.
5. Optional: run the verdict ("Run the litmus test") for the candidate.

## Edit beats (what gets added in post)

- 0:00 Black. Typed line: "Every experiment generates data. Almost none of it gets written down."
- Walk-in plus coats, with the music building.
- Tap: a ripple and the "Start recording" button at the fingertip, plus a click SFX.
- Intro: "Dr. Omar" and "Dr. Lena" tags pop over your heads with SFX, then "Session titled by Gemini: Titrating vinegar with phenol red" slides in.
- Montage: cut between Cam A and Cam B on every detection. Each detection gets a bracketed box and label (Pouring · Graduated cylinder · 10 mL, Scale reads 2.31 g, Swirling · 6 s, "it's turning pink" → committed). A commit log builds up on the right with hashes.
- Color change: full-width "Color change detected" hit.
- Stop: "Record sealed · 47 commits · SHA-256" stamp.
- Pipeline animation (about 20 s): frames and audio → Gemini → structured JSON → Tiger Data (hypertable, continuous aggregate, hash chain, 768-d embeddings in pgvector, hybrid search).
- Screen recording, with small callouts naming the Gemini model and the Tiger Data feature behind each step.
- End card: "Litmus. Git for research, except you never have to commit." Built with Gemini and Tiger Data. Names.
