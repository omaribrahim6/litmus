-- Litmus schema for Tiger Data (TimescaleDB + pgvector).
-- Idempotent: safe to re-run against an existing service.

create extension if not exists timescaledb;
create extension if not exists vector;

-- An experiment is a protocol config: steps, tracked variables, ROI, flip rule.
create table if not exists experiments (
  id          uuid primary key default gen_random_uuid(),
  slug        text unique,
  name        text not null,
  protocol    jsonb not null,
  created_at  timestamptz not null default now()
);

create table if not exists runs (
  id             uuid primary key default gen_random_uuid(),
  experiment_id  uuid references experiments(id),
  label          text,
  role           text check (role in ('reference','control','candidate','rerun')),
  parent_run_id  uuid references runs(id),
  station_id     text,
  status         text not null default 'recording' check (status in ('recording','complete','failed')),
  started_at     timestamptz,
  ended_at       timestamptz,
  video_url      text,
  result         jsonb,          -- {"metric":"base_added_ml","value":4.2,"unit":"mL","evidence_ids":[...]}
  assumed_cause  text,           -- the researcher's stated hypothesis, if any
  metadata       jsonb not null default '{}'::jsonb
);
create index if not exists runs_experiment_idx on runs (experiment_id, started_at);

-- Raw sensor and camera-derived readings.
create table if not exists readings (
  time        timestamptz not null,
  run_id      uuid not null references runs(id),
  sensor      text not null,      -- temp_c, light, air_quality, mix_angle, dial, color_darkness, hue, ...
  value       double precision not null,
  unit        text,
  provenance  text not null default 'measured' check (provenance in ('measured','reported','inferred'))
);
select create_hypertable('readings', 'time', if_not_exists => true);
create index if not exists readings_run_sensor_idx on readings (run_id, sensor, time desc);

create materialized view if not exists readings_1s
  with (timescaledb.continuous, timescaledb.materialized_only = false) as
  select time_bucket('1 second', time) as bucket,
         run_id,
         sensor,
         avg(value) as avg,
         min(value) as min,
         max(value) as max,
         count(*)   as n
  from readings
  group by bucket, run_id, sensor
  with no data;

select add_continuous_aggregate_policy('readings_1s',
  start_offset      => interval '1 day',
  end_offset        => interval '1 second',
  schedule_interval => interval '30 seconds',
  if_not_exists     => true);

-- Keyframes kept as evidence.
create table if not exists frames (
  id       uuid primary key default gen_random_uuid(),
  run_id   uuid references runs(id),
  t        timestamptz not null,
  url      text not null,
  reason   text,                 -- periodic | event | flip | upload
  roi      jsonb,                -- ROI rectangle used for color metrics
  metrics  jsonb                 -- color metrics measured inside the ROI at this frame
);
create index if not exists frames_run_idx on frames (run_id, t);

-- Events are the commits: one hash-chained, append-only log per run.
create table if not exists events (
  id          uuid primary key default gen_random_uuid(),
  run_id      uuid not null references runs(id),
  t           timestamptz not null,
  seq         int not null,
  kind        text not null,     -- run_started, step_confirmed, quantity_added, mix, flip_detected, reagent_used, note, run_sealed, ...
  summary     text not null,
  payload     jsonb,
  provenance  text not null check (provenance in ('measured','reported','inferred')),
  confidence  double precision,   -- model-reported, for inferred events only; never shown as a probability
  frame_ids   uuid[],
  prev_hash   text,
  hash        text not null,
  embedding   vector(768),
  search      tsvector generated always as (to_tsvector('english', kind || ' ' || summary)) stored,
  unique (run_id, seq)
);
create index if not exists events_run_t_idx on events (run_id, t);
create index if not exists events_search_idx on events using gin (search);
create index if not exists events_embedding_idx on events using hnsw (embedding vector_cosine_ops);

-- Derived artifacts: diffs, verdicts, reports, branches, chat answers, validation numbers.
-- Rows are never updated in place; a reanalysis is a new row.
create table if not exists analyses (
  id          uuid primary key default gen_random_uuid(),
  kind        text not null check (kind in ('diff','verdict','report','branch','chat','validation')),
  run_ids     uuid[],
  cache_key   text,
  model       text,
  content     jsonb not null,
  created_at  timestamptz not null default now()
);
create index if not exists analyses_kind_runs_idx on analyses using gin (run_ids);
create index if not exists analyses_cache_idx on analyses (kind, cache_key, created_at desc);
