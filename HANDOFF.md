# Litmus handoff

Living status for whoever picks this up (Claude, Codex, or a teammate). Read README.md for the product, SPEC.md (local only, gitignored) for the brief, and SPONSOR_USAGE.md for Gemini / Tiger Data usage.

Deadline: Devpost submission Sunday Oct 25, 12:00 PM ET (edits until 1:45 PM).

**The GitHub repo is PRIVATE until submission. Make it public again before 12:00 PM ET** (Devpost requires a public repo): `gh repo edit omaribrahim6/litmus --visibility public --accept-visibility-change-consequences`. While private, deploy the worker with `wsl -e bash deploy/sync-to-vps.sh` (the VPS cannot `git pull`), and copy code to the Pi with scp or `gh repo clone`.

## Where things run

| Piece | Where | How |
|---|---|---|
| Database | Tiger Data service `litmus` (id `wkyqzmagbs`, project `oduirs2xew`) | `DATABASE_URL` in `.env` (gitignored). Tiger CLI at `%LOCALAPPDATA%\Programs\tiger-cli\tiger.exe` |
| Worker (FastAPI) | Laptop: `cd worker; .venv\Scripts\python -m uvicorn litmus_worker.main:app --port 8000 --reload`. VPS: see Deploy below | `.env` at repo root |
| Web (Next.js 16) | Laptop: `npm --prefix web run dev` (port 3000). Vercel project `litmus` (team omar-ibrahims-projects-f536f673) | `web/.env.local` has `DATABASE_URL`, `WORKER_URL` |
| Station (Pi) | `cd station; python -m litmus_station` (kiosk on :8080). Laptop dev: `..\worker\.venv\Scripts\python -m litmus_station --simulate` | `station/.env`, `station/station.json` (see `station/README.md`) |
| Gemini | Vertex AI, project `project-159ede5d-a12e-40b1-a59`, location **global** (us-central1 404s for current models) | `.env`: `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_APPLICATION_CREDENTIALS=C:\Users\omarm\Downloads\model-garden-vertex.json` |

Models (set in `.env`, defaults in `worker/litmus_worker/config.py`): Flash `gemini-3.8-flash`, Flash-Lite `gemini-3.5-flash-lite`, Pro tier `gemini-4-argon` (fast; `gemini-3.1-pro-preview` works but hits 429 quota and takes ~50 s), embeddings `gemini-embedding-001` at 768 dims.

**Credits are limited. Do not spam Gemini.** Every AI result is cached in the `analyses` table (keyed on run chain heads) and on disk in `demo/cache`. Re-rendering pages never calls Gemini. `python -m litmus_worker.ai.check` makes 3 tiny calls; avoid running it repeatedly.

## Commands that matter

```bash
cd worker
.venv\Scripts\python -m pytest -q                       # core + worker tests (fast, no network)
.venv\Scripts\python -m litmus_worker.seed              # upsert protocol JSON into experiments
.venv\Scripts\python -m litmus_worker.seed --synthetic  # wipe + regenerate 7 synthetic runs (flagged synthetic)
.venv\Scripts\python -m litmus_worker.prepare_demo      # verdict + report per candidate, cached Ask answers, embeddings, validation, export snapshot
.venv\Scripts\python -m litmus_worker.validate          # validation numbers only
.venv\Scripts\python -m litmus_worker.export            # web/demo-data/snapshot.json + web/public/media
.venv\Scripts\python -m litmus_worker.tamper <run_id>   # demo: edit a commit in the DB (chain breaks); --restore to undo
```

Demo mode (no network): `LITMUS_DEMO_MODE=1` for the web app, or it falls back automatically when the DB is unreachable. It serves `web/demo-data/snapshot.json` and `web/public/media`.

## State of the build (update as you go)

Done and committed:
- Schema on Tiger Data: readings hypertable, `readings_1s` real-time continuous aggregate, pgvector HNSW, generated tsvector.
- Worker: ingest (runs, readings via COPY, events with hash chain, frames, video incl. researcher camera), finalize (light-sensor flip cross-check, result, seal with readings/frames digest), `/verify`, diff engine (sqrt(2)-corrected normal variation), verdict + validator, report with receipts, Ask chat with tools and Vega-Lite charts, video-to-commits, reagent detection from keyframes, spoken intro titling, narration commits, validation, export, tamper demo.
- Station: sensor drivers (Grove/ADS1115/RC LDR/DS18B20/DHT22, missing never faked), camera with exposure lock + wall-clock-locked video, live flip detector, mixing episodes, coalescing SQLite outbox, kiosk (1024x600 Waveshare 7" C), multi-mic hub picking the clearest mic per utterance, optional phone camera.
- Web: history (commit graph + litmus strips + result line), run view (video synced both ways with lanes, live polling), diff view (verdict reveal), report (hover receipts, Markdown/PDF), Ask panel, upload, validation page, light/dark, offline snapshot fallback.

Deployed:
- Web (production): https://litmus-rosy.vercel.app (Vercel env `DATABASE_URL`, `WORKER_URL`). Redeploy: `cd web; vercel deploy --prod --yes`.
- Worker: https://litmus-worker.23-95-188-69.sslip.io on the VPS (`wsl ssh altair@23.95.188.69`, key auth). Docker container `litmus_worker` on network `webnet` behind nginx-proxy + acme-companion. Redeploy after pushing: `wsl -e ssh altair@23.95.188.69 "bash ~/litmus/deploy/vps-up.sh"`. Server-only files: `~/litmus/deploy/.env.vps`, `~/litmus/deploy/secrets/vertex.json`, media in `~/litmus/data/media`. Sudo needs a password: never type it; ask Omar.
- Station token: `WORKER_TOKEN` in the root `.env` and the VPS `.env.vps`; put the same value in `station/.env` on the Pi with `WORKER_URL=https://litmus-worker.23-95-188-69.sslip.io`.

Next:
1. Real runs: Lina records 5+ reference runs, Method A control, Method B with tap water, at the station. Then `seed --reset-synthetic` (removes synthetic runs only), `prepare_demo` (a few Gemini calls), commit `web/demo-data` + `web/public/media`, redeploy.
2. Fill `demo/validation/manual_flips.csv` (`run_id,manual_flip_s`) from video review of 10 runs, then `validate`.
3. Devpost text (`DEVPOST.md` draft) + demo video.
4. Careful with deletes: analyses list every reference run in `run_ids`; deleting a run cascades to its verdicts. Prefer `seed --reset-synthetic`.

Known gaps / caveats:
- Synthetic runs exist only for development and are labeled "synthetic" in the UI. Replace before judging.
- Gemini's video Files API is not on Vertex; `ai/client.py:video_part` sends downscaled video inline instead.
- `web/demo-data` and `web/public/media` are not committed yet; commit them after the final `prepare_demo`.
- PowerShell gotcha: never post-process files with `.Replace('`n', "`n")`; it corrupts JS template literals that start with `n`.

## Git conventions

Conventional commits (`feat(web): ...`, `fix(worker): ...`), push to `main` on `github.com/omaribrahim6/litmus` as you go. No Co-Authored-By lines.
