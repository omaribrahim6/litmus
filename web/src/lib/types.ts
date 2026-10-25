export type Provenance = "measured" | "reported" | "inferred";
export type ClaimLabel = "observed" | "possible_explanation" | "contradicted" | "missing_evidence";
export type Role = "reference" | "control" | "candidate" | "rerun";

export interface ProtocolVariable {
  key: string;
  label: string;
  type: "numeric" | "categorical" | "sequence";
  unit?: string;
  role?: "condition" | "outcome";
}

export interface Protocol {
  slug: string;
  name: string;
  description?: string;
  result: { key: string; label: string; unit?: string; quantity: string; decimals?: number };
  steps: { id: string; title: string; detail?: string }[];
  variables: ProtocolVariable[];
  roi: { x: number; y: number; w: number; h: number };
}

export interface Experiment {
  id: string;
  slug: string;
  name: string;
  protocol: Protocol;
  created_at: string;
}

export interface RunResult {
  metric: string;
  label: string;
  unit?: string | null;
  value: number | null;
  available: boolean;
  provenance?: Provenance | null;
  evidence_ids: string[];
  note?: string | null;
}

export interface Run {
  id: string;
  experiment_id: string;
  label: string | null;
  role: Role;
  parent_run_id: string | null;
  station_id: string | null;
  status: "recording" | "complete" | "failed";
  started_at: string | null;
  ended_at: string | null;
  video_url: string | null;
  result: RunResult | null;
  assumed_cause: string | null;
  metadata: Record<string, unknown> & { synthetic?: boolean; video_started_at?: string };
  head_hash?: string | null;
  event_count?: number;
}

export interface LitmusEvent {
  id: string;
  run_id: string;
  t: string;
  seq: number;
  kind: string;
  summary: string;
  payload: Record<string, unknown> | null;
  provenance: Provenance;
  confidence: number | null;
  frame_ids: string[];
  prev_hash: string | null;
  hash: string;
}

export interface Frame {
  id: string;
  run_id: string;
  t: string;
  url: string;
  reason: string | null;
  metrics: Record<string, number> | null;
}

export interface ReadingBucket {
  bucket: string;
  sensor: string;
  avg: number;
  min: number;
  max: number;
  n: number;
}

export interface VerifyReport {
  intact: boolean;
  checked: number;
  events?: number;
  head?: string;
  broken_at_seq?: number;
  reason?: string;
  event_id?: string;
  sealed?: boolean;
  readings?: number;
  frames?: number;
  checked_at?: string;
  unavailable?: boolean;
}

export interface Measure {
  available: boolean;
  value: number | string | string[] | null;
  display: string;
  unit?: string | null;
  provenance?: Provenance | null;
  evidence_ids: string[];
  note?: string | null;
}

export interface DiffItem {
  key: string;
  label: string;
  type: "numeric" | "categorical" | "sequence";
  unit?: string | null;
  role?: "condition" | "outcome";
  status: "notable" | "within_normal" | "same" | "missing_evidence";
  candidate: Measure;
  control: Measure;
  reference?: {
    n: number;
    values: { run_id: string; label: string; value: number | string; evidence_ids: string[] }[];
    mean?: number;
    sd?: number;
    min?: number;
    max?: number;
    counts?: Record<string, number>;
  };
  delta?: number;
  band?: number;
  band_method?: string;
  ratio?: number | null;
  explanation: string;
  rank?: number;
  percent_change?: number;
  headline?: string;
  result_is_outside_normal_variation?: boolean;
  missing_side?: string;
}

export interface FollowUp {
  check: string;
  variable_key?: string | null;
  outcomes: { if: string; means: "supported" | "explained_by_confound" | "unresolved"; text: string }[];
}

export interface DiffContent {
  experiment: { slug: string; name: string };
  candidate: { run_id: string; label: string; role: Role };
  controls: { run_id: string; label: string; role: Role }[];
  references: { run_id: string; label: string }[];
  result: DiffItem;
  assumed_cause: {
    text: string | null;
    variable_keys: string[];
    label: ClaimLabel | null;
    evidence_ids: string[];
    reason: string;
    confounds?: string[];
  };
  differences: DiffItem[];
  notable: string[];
  within_normal: string[];
  missing_evidence: string[];
  follow_up: FollowUp;
  branch?: { parent_analysis_id: string | null; excluded_run_ids: string[]; note: string };
}

export interface Claim {
  text: string;
  label: ClaimLabel;
  evidence_ids: string[];
  variable_key?: string;
  suggested_check?: string;
  validator_note?: string;
}

export interface VerdictContent {
  candidate: DiffContent["candidate"];
  controls: DiffContent["controls"];
  headline: string;
  station_summary: string;
  result: DiffItem;
  assumed_cause: {
    text: string | null;
    label: ClaimLabel | null;
    label_text: string;
    statement: string | null;
    variable_keys: string[];
    evidence_ids: string[];
    confounds: string[];
  };
  claims: Claim[];
  rejected_claims: { text: string; label?: string; reason: string }[];
  follow_up: FollowUp;
  notable: string[];
  missing_evidence: string[];
  model: string;
  validator: { accepted: number; rejected: number; relabeled: number };
  diff: DiffContent;
  diff_analysis_id?: string;
}

export interface ReportSentence {
  text: string;
  evidence_ids: string[];
  gap?: boolean;
  reason?: string;
}

export interface ReportContent {
  title: string;
  sections: { id: string; heading: string; sentences: ReportSentence[] }[];
  model: string;
  candidate: DiffContent["candidate"];
  controls: DiffContent["controls"];
  stats: { sentences: number; gaps: number; traceable: number };
  markdown: string;
  verdict_analysis_id?: string;
}

export interface Analysis<T = unknown> {
  id: string;
  kind: "diff" | "verdict" | "report" | "branch" | "chat" | "validation";
  run_ids: string[];
  model: string | null;
  content: T;
  created_at: string;
}

export interface Evidence {
  id: string;
  type: "event" | "frame" | "series" | "reading" | "run";
  run_id: string;
  run_label?: string | null;
  t?: string;
  start?: string;
  end?: string;
  kind?: string;
  summary?: string;
  payload?: Record<string, unknown> | null;
  provenance?: Provenance;
  confidence?: number | null;
  hash?: string;
  seq?: number;
  frames?: { id: string; t: string; url: string; reason: string | null }[];
  url?: string;
  reason?: string | null;
  metrics?: Record<string, number> | null;
  sensor?: string;
  value?: number;
  unit?: string | null;
  n?: number;
  mean?: number;
  min?: number;
  max?: number;
  points?: { t: string; value: number }[];
  label?: string | null;
  role?: Role;
  assumed_cause?: string | null;
  result?: RunResult | null;
}

export interface ChartBlock {
  id: string;
  kind: string;
  spec: Record<string, unknown>;
  data: { run?: string; value?: number | string; evidence_id: string; run_id?: string }[];
  note?: string | null;
}

export interface AskAnswer {
  text: string;
  citations: string[];
  dropped_citations?: string[];
  charts: ChartBlock[];
  analyses: string[];
  tool_calls: { name: string; args: Record<string, unknown> }[];
  model: string;
  cached?: boolean;
  flags?: string[];
}
