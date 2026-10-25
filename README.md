# Litmus

**Git for research, except you never have to commit.**

Before a lab spends months building on a breakthrough, someone should check that it is real. Nobody has time to. Litmus does it automatically.

A bench station (Raspberry Pi, webcam, light, rotary and air sensors) records every experimental run without anyone writing anything down. Gemini turns video into a timestamped history of events, sensors and OpenCV measure everything numeric, and every event is committed to a hash-chained record in Tiger Data. When one run looks like a breakthrough, Litmus **diffs** it against the control across every recorded variable, judges each difference against the normal variation of reference runs, checks the researcher's assumed cause against the evidence, and says what actually differed. Every claim links to the exact video frame, sensor series or commit behind it. Then it writes the lab report, with receipts.

> Before you build on a breakthrough, give it the litmus test.

## The git mapping

| Git | Litmus |
|---|---|
| commit | an observed event (step confirmed, quantity added, color flip), captured automatically |
| log | the run timeline and the lab history |
| diff | two runs compared across every variable; only what changed beyond normal variation surfaces |
| blame | click any number or sentence to open the frame or reading it came from |
| branch | a reanalysis ("without reference 3") that never mutates the original record |
| hash chain | every commit is hashed with the previous one; `/verify` detects any edit |

## How it works

```
 station (Pi)                    worker (FastAPI)                         web (Next.js on Vercel)
 sensors 2 Hz, camera 6 Hz  -->  ingest, hash chain, seal         -->     history, run view, diff,
 local flip detection            Gemini: video -> events,                 report, Ask panel
 SQLite outbox (offline-safe)    frame labeling, verdict, report, chat
                                 diff engine (deterministic)
                     \                     |                                /
                      \---------------- Tiger Data (TimescaleDB + pgvector) /
```

**Hard rules the code enforces**

1. Gemini perceives and explains; deterministic code does math, hashing and storage. No number in the UI comes from a model.
2. Every AI claim cites evidence IDs (`evt:`, `frm:`, `ser:`, `rdg:`, `run:`). A validator rejects uncited claims. `contradicted` requires a specific measurement, otherwise the claim is relabeled `missing_evidence`.
3. Four labels only: observed, possible explanation, contradicted, missing evidence. No probabilities anywhere.
4. Provenance on every record: measured (sensor or camera), reported (researcher), inferred (Gemini), each with its own icon.
5. A disconnected sensor shows as missing and becomes missing evidence. Nothing is ever estimated to fill the gap.

## Repository

```
core/      shared, model-free signal processing: ROI color metrics, flip detector, mixing from the rotary angle
station/   Raspberry Pi: sensor drivers (Grove HAT, ADS1115, RC-timing LDR, DS18B20, DHT22), camera, outbox, kiosk
worker/    FastAPI: ingest, hash chain and seal, diff engine, Gemini verdict/report/chat/video, export, validation
web/       Next.js 16 App Router: lab history, run view, diff view, report with receipts, Ask panel
db/        schema.sql (hypertable, continuous aggregate, pgvector), experiment protocols as JSON
demo/      cached Gemini outputs and validation inputs for offline demos
```

## Run it

Requirements: Python 3.11, Node 20+, ffmpeg, a Tiger Data service, a Gemini API key.

```bash
cp .env.example .env            # fill DATABASE_URL, GEMINI_API_KEY, WORKER_TOKEN
python -m venv worker/.venv && worker/.venv/Scripts/pip install -r worker/requirements.txt
worker/.venv/Scripts/python db/apply.py                       # schema + smoke test
cd worker && .venv/Scripts/python -m litmus_worker.seed       # experiment protocols
.venv/Scripts/python -m uvicorn litmus_worker.main:app --port 8000
```

```bash
cd web && npm install && npm run dev                          # http://localhost:3000
```

Station on the Pi (or `--simulate` on a laptop):

```bash
cd station && pip install -r requirements.txt
python -m litmus_station                    # kiosk at http://localhost:8080
python -m litmus_station --simulate         # simulated bench, runs flagged synthetic
python -m litmus_station --camera demo.mp4  # replay a recording as the camera
```

**Demo mode (no network).** `python -m litmus_worker.export` writes `web/demo-data/snapshot.json` and copies media into `web/public/media`. Set `LITMUS_DEMO_MODE=1` (or lose the database connection) and the web app serves everything, including cached verdicts, reports and chat answers, from the snapshot.

**Validation.** Fill `demo/validation/manual_flips.csv` (run id, flip time from video review), then `python -m litmus_worker.validate`. Results appear on the Validation page.

## Built with

Google Gemini (Flash for video and frames, Pro for verdicts, reports and tool-calling chat, Embeddings for search), Tiger Data (TimescaleDB hypertables, continuous aggregates, pgvector), Next.js on Vercel, FastAPI, OpenCV, Raspberry Pi. See [SPONSOR_USAGE.md](SPONSOR_USAGE.md).

Built at HackPSU Fall 2026.
