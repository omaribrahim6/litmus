# Litmus

**Git for research, except you never have to commit.**

## Elevator pitch

A lab bench that records every experiment by itself. Gemini watches, listens and reads the instruments; Tiger Data keeps a tamper-evident history you can diff, search and ask questions of, with a receipt for every claim.

## Links

- Live app: https://litmus-rosy.vercel.app
- Code: https://github.com/omaribrahim6/litmus
- Demo video: [paste link]

---

## Inspiration

When a result fails to replicate, the reason is usually boring. Someone used a different reagent bottle, tap water instead of distilled, or skipped a step. Those details almost never make it into the notebook, because writing everything down while your hands are full is impossible. So when one run looks too good, there's nothing to check it against except memory.

Software engineers solved this decades ago. Every change is committed, every line can be blamed, and any two versions can be diffed. We wanted that for the lab bench, without asking a researcher to type a single commit message.

## What it does

You walk up to the bench and press **Start recording**. That's the only button.

- **You say what you're doing, and Litmus sets itself up.** "Hi, I'm Dr. Omar, this is Dr. Lena, we're titrating vinegar with phenol red." Gemini titles the run, tags the researchers, and decides what's worth recording for *this* lab: steps, instrument readings, amounts, counts and qualitative observations, plus which one is the outcome. Nothing is preconfigured for a specific experiment. If you say nothing, it works from what the camera sees.
- **It watches and listens.** Every few seconds Gemini looks at the bench cameras, describes the scene, labels what the researcher is doing (pouring, mixing, measuring), tracks which protocol step they're on, and reads every value it can actually see on a scale, a thermometer or a graduated cylinder. Anything said aloud about the experiment ("that's two mL of base, it's turning pink") is picked up from whichever mic heard it best, and small talk is thrown away.
- **Every observation becomes a commit.** Each event is timestamped, tagged with its provenance (measured, reported or inferred) and the frame or audio it came from, and hash-chained to the one before it. When the run ends, the record is sealed with a digest of every reading and frame. Change one byte and verification fails at that commit.
- **Log.** Every run opens in an editor-style player: video synced to tracks for steps, speech, what Gemini saw, commits and sensors under one playhead.
- **Data.** Each experiment becomes a table with a row per run and a column per measurement. Every cell links to its receipt. One click exports it to CSV.
- **Diff and verdict.** Pick the run that looks like a breakthrough. Litmus compares it with the control across every recorded variable, judges each difference against how much identical reference runs normally vary, and checks the cause the researcher believes in against the measurements.
- **Ask your lab.** A chat built for the record. "Why was Method B different?" "Graph the results for a paper." "Write the methods as they actually happened." Every answer shows how many receipts ground it, numbered evidence cards with the actual frames, and a *Why this answer?* trail of the lookups it ran.

## How we built it

**The station.** A Raspberry Pi 5 with a 7-inch touchscreen kiosk, a USB webcam, a phone as a second camera, every available microphone, and a thermometer placed in camera view. The station streams keyframes, audio and readings through an offline-safe local queue, so a bad Wi-Fi moment never loses a run.

**Google Gemini (on Vertex AI)** does the perceiving and the explaining:
- **Gemini 3.8 Flash** sets the experiment up from the spoken intro and a frame, then watches the bench: it describes the scene, labels activity per frame, tracks steps, and reads values off instruments.
- **Gemini 3.5 Flash-Lite** transcribes narration and keeps only what's about the experiment. It also reads the thermometer.
- **Gemini 4 Argon** writes verdicts and lab reports and powers Ask your lab, with eight function-calling tools over the record.
- **gemini-embedding-001** embeds every commit for semantic search.

**Tiger Data** holds the whole record:
- a hypertable of every reading, COPY-ingested
- a real-time one-second continuous aggregate behind every timeline
- an append-only, hash-chained event ledger with per-run advisory locks
- pgvector (HNSW) and full-text search fused with reciprocal rank fusion for "search by meaning"
- append-only analyses cached against chain heads, so the same question about the same record never costs a second model call

**Web and infrastructure.** Next.js 16 on Vercel (with an offline snapshot fallback), a FastAPI worker in Docker on a VPS, and a Python station service under systemd on the Pi.

### Rules we enforce in code, not in prompts

1. **No model-invented numbers.** Gemini can read a number off a display (stored as *inferred*, with the frame), but every aggregate, difference and normal-variation band is computed by code.
2. **Every claim cites evidence**, and a validator drops any citation that doesn't exist in the record.
3. **Four labels only:** observed, possible explanation, contradicted, missing evidence. No probabilities anywhere.
4. **Provenance on everything:** measured, reported by the researcher, or inferred by AI.
5. **A missing sensor is shown as missing.** It is never estimated.

## Challenges we ran into

- **Our hardware plan fell through on the day.** No ADC and no Grove HAT meant the breadboard sensors weren't happening. We rebuilt around what we had (cameras, mics, a thermometer in view) and moved the perception work to Gemini, which made the product far more general.
- **Not overfitting to one experiment.** Our first version was a great titration recorder and nothing else. We rewrote setup so Gemini declares the measurements for whatever lab you describe, while code still owns every number.
- **Never missing a word.** The spoken intro is processed while the researcher keeps talking, so we serialized setup per run and made narration wait for the right protocol instead of dropping clips.
- **Making "normal variation" honest.** The difference between two runs varies about 1.4 times more than a single run does. Ignoring that tripled false alarms between runs that should look identical.
- **Hackathon networking.** About 80 ms per database round trip meant a backlog. Coalescing the station's queue and bulk-loading readings fixed it.

## Accomplishments that we're proud of

- One button. Walk up, press start, talk, work. The record writes itself.
- It isn't a titration app. Describe any lab and Gemini decides what to watch for.
- Every number and sentence can be clicked back to the frame, audio or reading it came from.
- Editing a single value in the database turns the run's "record intact" badge red and names the exact commit that changed.
- On our validation suite: color changes detected within 1 s, the planted confound surfacing as the top difference, 2 false alarms in 110 same-protocol comparisons, and 100% of AI-written claims traceable to evidence.

## What we learned

- The most valuable thing an AI can say in a lab is often "this wasn't measured."
- Models are great perceivers and bad bookkeepers. Let them see, read and explain, and let code do the arithmetic and the ledger.
- Provenance is a design problem. A value read by a sensor, said by a person and inferred by a model need to look different on screen.

## What's next for litmus

- **Multi-bench labs:** compare runs across stations and researchers, with branches for protocol variants.
- **Live coaching:** Gemini flags a skipped step or the wrong reagent *during* the run, not after.
- **Where confounds cost millions:** cell culture (incubator temperature, reagent lot, passage number) and preclinical work, where a hidden difference surfaces in phase 3 instead of on day one.

## Built with

`google-gemini` `vertex-ai` `tiger-data` `timescaledb` `pgvector` `postgresql` `raspberry-pi` `python` `fastapi` `opencv` `next.js` `react` `typescript` `tailwindcss` `vercel` `docker` `remotion`

## Team

Omar Ibrahim · Lena · Mark
