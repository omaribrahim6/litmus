# Devpost draft: Litmus

> **For the team, not for pasting.** Sections below map one-to-one to Devpost's form fields. Fill every `[TODO]` before submitting. Before you submit, check:
> - Validation numbers below come from our synthetic test runs. Replace them with the numbers from real station runs (Validation page) or remove them.
> - Only claim what we demo. Voice intro, narration and the phone camera are built but untested on real hardware; keep them in only if they work at the station.
> - Video link, team names, researcher quote.

---

## Project name

Litmus

## Elevator pitch (200 characters max)

Git for research, except you never have to commit. A lab bench that records every run and tells you whether a breakthrough is real, with a receipt for every claim.

*(163 characters)*

## Links

- Live app: https://litmus-rosy.vercel.app
- Code: https://github.com/omaribrahim6/litmus
- Demo video: [TODO]

---

## Inspiration

Before a lab spends months building on a breakthrough, someone should check that it is real. Nobody has time to.

When a result fails to replicate, the reason is usually boring: a different reagent bottle, tap water instead of distilled, a step done slightly differently. Those details almost never make it into the notebook. So when one run looks too good, there is nothing to check it against except memory.

[TODO: one line from the researcher interview, e.g. "We lost two months building on a result that turned out to be a contaminated buffer."]

Software engineers solved this decades ago. Every change is committed, every line can be blamed, and you can diff any two versions. We wanted that for the lab bench, without asking anyone to type a single commit message.

## What it does

Litmus is a bench station plus a pipeline that records every experimental run automatically and turns it into a git-style history.

- **Commits, captured automatically.** Sensors, a camera and the researcher's taps on a touchscreen record every event: steps confirmed, quantities added, which container was used, the moment the indicator changes color. Each event is timestamped and hash-chained to the one before it.
- **Log.** Every run becomes a timeline you can scrub, with video synced to lanes for each sensor and a "litmus strip" of the tube color the camera actually measured.
- **Diff.** Pick the run that looks like a breakthrough. Litmus compares it with the control across every recorded variable and judges each difference against how much identical reference runs normally vary. It also checks the cause the researcher believes in against the measurements.
- **Blame.** Click any number or sentence to see the exact video frame, sensor reading or event behind it.
- **Branch.** Re-run the analysis without a given run. The original record is never modified.
- **A report with receipts.** Litmus writes the lab report as the experiment actually happened. Every sentence links to its evidence, and anything it can't support is flagged instead of stated.

**The demo.** "Method B" neutralizes vinegar with 38% less base than the control. The researcher thinks it's because they stirred longer. Litmus shows two things. Stirring was the same within normal variation, measured by a rotary sensor on the tube holder. The real difference was the water: Method B was diluted from the tap jug instead of distilled, and the camera saw it. Litmus then proposes the one rerun that would settle the question and says what each outcome would mean.

*(Research Track bottleneck: checking whether a promising result is real before expensive follow-on work depends on it.)*

## How we built it

**The station.** A Raspberry Pi 5 with a 7-inch touchscreen runs the bench:
- a webcam watching a clear tube
- a light sensor shining through the tube, an independent colorimeter that cross-checks the camera
- a rotary angle sensor on the mixing holder, which turns "how much did you stir" into a measured number
- an air-quality sensor

[TODO if demoed: a second phone camera with a better view of the researcher's hands, plus every available mic. Each spoken comment is taken from whichever mic heard it most clearly.] An offline-safe local queue means a run is never lost to bad Wi-Fi.

**Measurement is never AI.** Color in the tube is measured in CIE Lab from a fixed region of the frame. The flip is detected with a baseline, a persistence check and onset back-tracking. Mixing is counted from the rotary angle. All of this, and the diff engine itself, is deterministic Python.

**Google Gemini perceives and explains.**
- **Flash** labels which jug or bottle appears in the keyframe at each step, turns uploaded lab videos into timestamped events, and [TODO if demoed: titles each run from the researcher's spoken intro and turns narration into events].
- **The Pro-tier model** writes the verdict and the lab report, and powers "Ask your lab": a chat with seven function-calling tools over the record that can answer "Graph base added across all runs, formatted for a paper."
- **Gemini Embeddings** power semantic search over every event.

**Tiger Data** holds the entire record:
- sensor readings in a TimescaleDB hypertable
- a real-time one-second continuous aggregate behind every chart
- pgvector plus full-text search over events
- a hash-chained, append-only event ledger

**Web and infrastructure.** The web app is Next.js on Vercel. The analysis worker is FastAPI in Docker on a VPS.

### Rules we enforced in code, not in prompts

1. No number comes from a model. Numbers come from sensors, OpenCV or SQL.
2. Every AI claim cites evidence IDs, and a validator rejects claims that don't.
3. Four labels only: observed, possible explanation, contradicted, missing evidence. No probabilities anywhere. A claim can only be "contradicted" if a specific measurement argues against it; otherwise it is relabeled "missing evidence."
4. Every record shows its provenance: measured, reported by the researcher, or inferred by AI.
5. A missing sensor is shown as missing. It is never estimated.

## Challenges we ran into

- **Making "normal variation" honest.** The difference between two runs varies about 1.4 times more than a single run does. Our first version ignored that and raised three times as many false alarms between runs that should have looked identical.
- **Keeping a live station in sync over hackathon Wi-Fi.** Every database round trip cost about 80 ms. We fixed it by coalescing the station's upload queue and bulk-loading readings.
- **Getting a language model to be useful without letting it be the source of truth.** Gemini groups and paraphrases citations, so every evidence ID is checked by code before it reaches the screen.
- [TODO: hardware challenge from Lina, e.g. no ADC, mounting the light sensor, steady lighting for the camera]

## Accomplishments that we're proud of

- The station measures how much you stirred. It's the kind of confound a spreadsheet never records.
- Editing a single value in the database turns the run's "record intact" badge red and names the exact event that was changed.
- Every sentence in a generated lab report can be clicked back to a video frame or sensor reading.
- Validation, measured by the system on itself [TODO: replace with real-run numbers]:
  - detected color flips within 1 second of ground truth
  - the light-sensor colorimeter agreeing with the camera on every run
  - the planted confound surfacing as the top difference
  - 2 false alarms in 110 comparisons between runs that followed the same protocol
  - 100% of AI-written claims traceable to evidence

## What we learned

- The most valuable thing an AI can say in a lab is often "this wasn't measured."
- Provenance is a design problem as much as a data problem. A reading typed by a person, a reading from a sensor, and a guess from a model need to look different on screen.
- Hardware forces honesty. When a sensor is unplugged, the software has to say so.

## What's next for litmus

- **Any protocol.** Experiments are configuration, not code: steps, tracked variables and the color-change rule live in a JSON file. Next, a researcher pastes a written protocol and Gemini drafts the configuration for them to review. A second experiment, the iodine clock, needs only a "time until the flip" result type.
- **Where confounds cost millions.** The same pattern applies to cell cultures, where incubator temperature, reagent lot or passage number silently differ, and to preclinical results that fail in phase 3.

## Built with

`google-gemini` `vertex-ai` `tiger-data` `timescaledb` `pgvector` `postgresql` `raspberry-pi` `opencv` `python` `fastapi` `next.js` `typescript` `tailwindcss` `vercel` `docker` `vega-lite`

## Team

[TODO: names and roles, e.g. Omar: software and design; Lina: hardware]

---

## Sponsor prize notes (optional field or judge conversation)

**Google Gemini.** Four models, each with a real job:
- Flash: video-to-events, keyframe labeling, [spoken intro and narration]
- Pro tier: verdict, lab report, tool-calling chat
- Embeddings: event search

Gemini never computes a number we report. Every claim it writes is validated against the record. Details in `SPONSOR_USAGE.md`.

**Tiger Data.**
- a hypertable for every sensor reading
- a real-time continuous aggregate behind every chart
- pgvector with full-text search fused for event search
- Postgres as a tamper-evident, hash-chained ledger
