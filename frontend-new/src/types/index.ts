/* Wire types. These mirror the FastAPI responses in backend/app/api exactly —
   change them only when the backend contract changes.

   Verified against the running backend. Note the shapes that are easy to get
   wrong: quality issues use `message`/`count` (not description/row_count), a
   chart carries a prebuilt `echarts_option` (the backend decides the chart, the
   UI only renders it), and the why result nests its windows under
   `target`/`baseline` rather than flat *_window fields. */

export type Scalar = string | number | boolean | null;

export type ColumnRole = 'id' | 'time' | 'measure' | 'dimension' | 'text';

export interface ColumnMeta {
  name: string;
  display_name: string;
  dtype: string;
  role: ColumnRole;
  entity?: boolean;
  description?: string | null;
  null_pct: number;
  distinct?: number;
  min?: string | null;
  max?: string | null;
  samples?: Scalar[];
}

/** The upload/sample endpoints flatten columns to an array; the /semantic
 *  endpoint returns the raw model, where columns is a keyed record. */
export interface TableSummary {
  name: string;
  display_name: string;
  role: 'fact' | 'dimension' | 'mapping';
  row_count: number;
  columns: ColumnMeta[];
}

/** The /semantic endpoint returns the stored model, where a table's columns are
 *  keyed by name rather than listed. */
export interface TableMeta extends Omit<TableSummary, 'columns'> {
  columns: Record<string, ColumnMeta>;
}

export interface Relationship {
  from: string;
  to: string;
  type: 'many_to_one' | 'one_to_one';
  confidence: number;
  containment?: number;
  parent_unique?: boolean;
  confirmed?: boolean;
}

export type Severity = 'high' | 'medium' | 'low';

export interface QualityIssue {
  id: string;
  type: string;
  severity: Severity;
  table: string;
  column?: string | null;
  count?: number;
  pct?: number;
  message: string;
  impact: string;
}

export interface QualitySummary {
  high: number;
  medium: number;
  low: number;
  total: number;
}

/** GET /api/datasets/{id}/quality — note there is no dataset_id in the body. */
export interface QualityResponse {
  issues: QualityIssue[];
  summary: QualitySummary;
}

export interface SemanticTime {
  primary_column?: string | null;
  min?: string | null;
  max?: string | null;
  anchor_date?: string | null;
}

export interface SemanticResponse {
  status: string;
  dataset_id: string;
  tables: TableSummary[];
  relationships: Relationship[];
  time: SemanticTime;
  quality_summary: QualitySummary;
}

export interface QueryResult {
  columns: string[];
  rows: Scalar[][];
  row_count: number;
  truncated: boolean;
}

export type ChartType =
  | 'kpi'
  | 'line'
  | 'bar'
  | 'bar_h'
  | 'grouped_bar'
  | 'contribution'
  | 'table';

export type ValueFormat = 'currency' | 'count' | 'percent' | 'number';

export interface KpiPayload {
  value: number | null;
  previous: number | null;
  delta: number | null;
  delta_pct: number | null;
}

/** The backend picks the chart and hands over a ready ECharts option object.
 *  `echarts_option` is null for `kpi`, `table`, and `contribution` — the last
 *  is built in the UI from the `why` payload. */
export interface ChartSpec {
  type: ChartType;
  value_format: ValueFormat;
  echarts_option: Record<string, unknown> | null;
  kpi: KpiPayload | null;
}

export interface WhySegment {
  value: string;
  target: number;
  baseline: number;
  delta: number;
  contribution: number;
  baseline_share: number;
  lift: number;
}

export interface WhyDimensionResult {
  dimension: string;
  is_driver: boolean;
  c_top: number;
  lift: number;
  offsetting: boolean;
  segments: WhySegment[];
}

export interface WhyWindow {
  start: string;
  end: string;
  value: number;
}

export interface WhyDrillStep {
  dimension: string;
  value: string;
  delta: number;
  share_of_parent: number;
  cumulative_share: number;
}

export interface WhyContributorRow {
  value: string;
  delta: number;
  cumulative_share: number;
}

export interface WhyAnalysisResult {
  metric: string;
  direction: 'increase' | 'decrease' | 'flat';
  target: WhyWindow;
  baseline: WhyWindow;
  delta: number;
  delta_pct: number;
  broad_based: boolean;
  offsetting: boolean;
  dimensions: WhyDimensionResult[];
  drill_path: WhyDrillStep[];
  top_contributors?: { dimension: string; rows: WhyContributorRow[] } | null;
}

export interface ResolvedWindow {
  start: string;
  end: string;
  label: string;
}

export interface ResolvedTime extends ResolvedWindow {
  baseline?: ResolvedWindow | null;
}

/* ---------------------------------------------------------------------------
   LLM telemetry — what the cache panel reads.
--------------------------------------------------------------------------- */

export interface TurnStats {
  calls: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  input_tokens: number;
  output_tokens: number;
  cache_hit: boolean;
  latency_s: number;
  cost_usd: number;
  uncached_cost_usd: number;
  saved_usd: number;
  provider: string | null;
  model: string | null;
}

export interface RecentCall {
  provider: string;
  model: string;
  stage: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cache_hit: boolean;
  latency_s: number;
  cost_usd: number;
  uncached_cost_usd: number;
  saved_usd: number;
  ok: boolean;
}

export interface StatsSummary {
  calls: number;
  cache_hits: number;
  cache_hit_rate: number;
  cached_tokens: number;
  written_tokens: number;
  fresh_tokens: number;
  output_tokens: number;
  total_prompt_tokens: number;
  cached_share_pct: number;
  cost_usd: number;
  uncached_cost_usd: number;
  saved_usd: number;
  saved_pct: number;
  avg_latency_s: number;
  avg_latency_cached_s: number;
  avg_latency_uncached_s: number;
  providers: string[];
  recent: RecentCall[];
}

export interface StatsResponse {
  status: string;
  provider: string;
  prompt_caching_enabled: boolean;
  summary: StatsSummary;
}

export interface AskResponse {
  status: 'ok' | 'needs_clarification' | 'unsupported' | 'error';
  message?: string | null;
  plan?: Record<string, unknown> | null;
  assumptions: string[];
  resolved_time?: ResolvedTime | null;
  sql?: string | null;
  result?: QueryResult | null;
  chart?: ChartSpec | null;
  narrative?: string | null;
  dq_warnings: QualityIssue[];
  why?: WhyAnalysisResult | null;
  suggestions: string[];
  mode?: string;
  from_cache?: boolean;
  llm_stats?: TurnStats | null;
  llm_totals?: StatsSummary | null;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'analyst';
  text: string;
  timestamp: string;
  pending?: boolean;
  failed?: boolean;
  response?: AskResponse;
}

/* ---------------------------------------------------------------------------
   Dashboard
--------------------------------------------------------------------------- */

export interface KPICardData {
  metric: string;
  label: string;
  value: number;
  previous?: number | null;
  delta?: number | null;
  delta_pct?: number | null;
  /** The server's field name for how the value should be read. */
  value_format?: ValueFormat;
  sparkline?: number[];
}

export interface AlertItem {
  id: string;
  type: string;
  severity: Severity;
  title: string;
  detail: string;
  plan?: Record<string, unknown>;
}

export interface DashboardPanel {
  id: string;
  title: string;
  plan?: Record<string, unknown>;
  sql?: string;
  result: QueryResult;
  chart?: ChartSpec;
  insight?: string | null;
}

export interface DashboardPeriod {
  label: string;
  baseline_label?: string;
}

export interface DashboardResponse {
  status: string;
  summary: string;
  period: DashboardPeriod;
  kpis: KPICardData[];
  panels: DashboardPanel[];
  alerts: AlertItem[];
  dq_warnings: QualityIssue[];
}

/* ---------------------------------------------------------------------------
   Settings
--------------------------------------------------------------------------- */

export type Provider = 'openrouter' | 'nvidia_nim' | 'claude_code' | 'anthropic';

/** Each provider keeps its model name under its own settings key, so a settings
 *  form needs to know which field a given provider writes to. */
export const providerModelField = {
  openrouter: 'openrouter_model',
  nvidia_nim: 'nvidia_nim_model',
  claude_code: 'claude_code_model',
  anthropic: 'anthropic_model',
} as const satisfies Record<Provider, string>;

export interface ProviderInfo {
  id: Provider;
  label: string;
  model: string;
  available: boolean;
  supports_caching: boolean;
  requires: string;
}

export interface AppSettings {
  active_provider: Provider;
  openrouter_model: string;
  nvidia_nim_model: string;
  claude_code_model: string;
  anthropic_model: string;
  prompt_caching_enabled: boolean;
  max_result_rows: number;
  query_timeout_s: number;
  providers: ProviderInfo[];
}

export type TabId = 'overview' | 'analyst' | 'data';
