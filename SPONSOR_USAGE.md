# Sponsor technology in Litmus

## Google Gemini

Gemini perceives and explains. It never computes a number that Litmus reports; those come from sensors, OpenCV and SQL.

| Where | Model | What it does | Code |
|---|---|---|---|
| Video to commits | Gemini Flash (Files API, video input) | Watches an uploaded lab session and returns timestamped events (steps, additions, containers used, mixing, notes) plus the bounding box of the liquid, with a strict JSON schema | `worker/litmus_worker/ai/video.py` |
| Live reagent identification | Gemini Flash (image input) | When a protocol step is confirmed at the station, labels the keyframe: which water jug or vinegar bottle was used. This is how the hidden confound (tap vs distilled water) gets into the record | `worker/litmus_worker/ai/perception.py` |
| Assumed-cause mapping | Gemini Flash | Maps the researcher's free-text hypothesis ("I stirred longer") onto protocol variables, so code can test it | `worker/litmus_worker/ai/verdict.py` |
| Verdict | Gemini Pro | Writes the verdict from the deterministic diff only, citing evidence aliases. Code decides the labels and validates every claim | `worker/litmus_worker/ai/verdict.py`, `ai/validator.py` |
| Lab report with receipts | Gemini Pro | Writes aim, method as performed, results, deviations and limitations; every sentence carries evidence IDs or is flagged as a gap | `worker/litmus_worker/ai/report.py` |
| Ask your lab | Gemini Pro with function calling | Seven tools over the record: list runs, timelines, readings from the continuous aggregate, hybrid event search, the diff engine, Vega-Lite charts built from SQL, evidence lookup | `worker/litmus_worker/ai/chat.py` |
| Event search | Gemini Embedding (768 dims) | Embeds every commit for semantic search in pgvector, fused with full-text ranking | `worker/litmus_worker/ai/perception.py`, `ai/chat.py` |

Every slow Gemini result is cached (by video hash, or by the chain heads of the runs involved) on disk and in the `analyses` table, so the demo replays instantly and offline.

## Tiger Data

One Tiger Cloud service (`litmus`) holds the entire record.

| Feature | Use | Code |
|---|---|---|
| Hypertable | `readings`: every sensor and camera measurement (light, rotary angle, air quality, temperature, Lab color at 6 Hz) | `db/schema.sql` |
| Continuous aggregate (real-time) | `readings_1s`: 1-second buckets that drive the run-view lanes, the litmus strips and the chat's `query_readings` tool | `db/schema.sql`, `web/src/lib/data.ts` |
| pgvector + HNSW | Commit embeddings for semantic search | `db/schema.sql`, `ai/chat.py` |
| Full-text search | Generated `tsvector` on commits, fused with vector results (reciprocal rank fusion) | `db/schema.sql`, `ai/chat.py` |
| Postgres as the ledger | Hash-chained `events` table with per-run advisory locks; append-only `analyses` table for diffs, verdicts, reports, branches and cached chat answers | `worker/litmus_worker/store.py`, `chain.py` |
| COPY ingest | Station batches stream into the hypertable in one round trip | `worker/litmus_worker/store.py` |
| Tiger CLI | Service creation and connection strings during setup | README |

The web app on Vercel reads Tiger Data directly (server components with the `postgres` driver); the worker writes and computes.
