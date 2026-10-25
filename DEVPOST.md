# Litmus: Git for research, except you never have to commit

**Live demo:** https://litmus-rosy.vercel.app · **Code:** https://github.com/omaribrahim6/litmus

## Inspiration

Before a lab spends months building on a breakthrough, someone should check that it is real. Nobody has time to. Results that fail to replicate usually fail for boring reasons: a different reagent lot, warmer water, a step done slightly differently. Those details almost never make it into the notebook, so when a run looks too good, there is nothing to check it against.

## What it does

Litmus is a bench station plus a pipeline that records every experimental run automatically and turns it into a git-like history.

- **Commit:** every event (step confirmed, quantity added, container used, color flip) is captured by sensors, the camera, the researcher's voice or a tap on the touchscreen, timestamped and hash-chained.
- **Log:** each run is a timeline you can scrub: video synced with lanes for every sensor, with a "litmus strip" of the tube color the camera actually measured.
- **Diff:** pick the run that looks like a breakthrough. Litmus compares it with the control across every recorded variable, judges each difference against how much identical reference runs normally vary, and checks the researcher's stated cause against the evidence.
- **Blame:** click any number or sentence and see the exact video frame, sensor series or commit behind it.
- **Branch:** reanalyze without a run without touching the original record.
- **Report with receipts:** Gemini writes the lab report as the experiment actually happened; every sentence links to its evidence or is flagged as unsupported.

In our demo, "Method B" neutralizes vinegar with 38% less base. The researcher believes it is because they stirred longer. Litmus shows that stirring was the same within normal variation (measured by a rotary sensor on the tube holder) and that the real difference was the water: Method B was diluted from the tap jug, not distilled, which the camera saw. It then proposes the matched rerun that would settle it, and what each outcome would mean.

## How we built it

- **Station:** Raspberry Pi 5 with a Logitech webcam, a light sensor shining through the tube (an independent colorimeter that cross-checks the camera), a rotary angle sensor on the mixing holder, an air-quality sensor and a 7" touchscreen kiosk. A second phone camera and every available mic feed it too. Each utterance is taken from whichever mic heard it most clearly. An offline-safe SQLite outbox survives bad Wi-Fi.
- **Measurement is never AI:** ROI color in CIE Lab, flip detection with baseline, persistence and onset back-tracking, inversion counting from the rotary angle, and the diff engine are deterministic Python.
- **Google Gemini perceives and explains:** Flash watches uploaded videos and labels which jug or bottle appears in keyframes; it also titles each run from the researcher's spoken intro ("I'm Dr. Chen, this is the Rivera lab...") and turns narration into commits. The Pro-tier model writes the verdict, the report, and powers "Ask your lab" with seven function-calling tools over the record. Gemini Embeddings power semantic search over every commit.
- **Tiger Data** holds the whole record: sensor readings in a TimescaleDB hypertable, a real-time 1-second continuous aggregate behind every chart, pgvector plus full-text search over commits, and a hash-chained, append-only event ledger.
- **Web:** Next.js 16 on Vercel; the worker (FastAPI) runs in Docker on a VPS.

## Rules we enforced in code

1. No number comes from a model. Numbers come from sensors, OpenCV or SQL.
2. Every AI claim cites evidence IDs; a validator rejects uncited claims.
3. Four labels only (observed, possible explanation, contradicted, missing evidence), and no probabilities anywhere. "Contradicted" requires a specific measurement or it is relabeled "missing evidence".
4. Every record carries its provenance: measured, reported, or inferred.
5. A missing sensor is shown as missing, never estimated.

## How we know it works

From the Validation page: color flips detected within 1 s of ground truth, the light-sensor colorimeter agreeing with the camera on every run, the planted confound surfacing as the top difference, 2 false alarms in 110 comparisons between runs that followed the same protocol, and 100% of AI-written claims traceable to the record. Editing a single value in the database turns the run's hash badge red and names the commit.

## Challenges

- Making "normal variation" statistically honest: the difference between two runs varies about 1.4 times more than a single run, and ignoring that tripled our false alarms.
- Keeping a live station in sync over high-latency Wi-Fi without losing order: coalescing the outbox and ingesting readings with COPY.
- Getting a language model to be useful without letting it be the source of truth.

## What's next

The same pattern applies where confounds cost millions: cell cultures where incubator temperature, reagent lot or passage number silently differ, and preclinical results that fail in phase 3. A second protocol (the iodine clock) runs on the same pipeline, because experiments are configuration, not code.

## Built with

Google Gemini (Vertex AI), Tiger Data (TimescaleDB, pgvector), Raspberry Pi, OpenCV, Python, FastAPI, Next.js, Vercel, Docker.
