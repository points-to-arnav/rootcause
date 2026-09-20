export type ColumnRole = 'id' | 'time' | 'measure' | 'dimension' | 'text';

export interface ColumnMeta {
  name: string;
  display_name: string;
  dtype: string;
  role: ColumnRole;
  entity?: boolean;
  description?: string;
  null_pct: number;
  distinct?: number;
  min?: string;
  max?: string;
  samples?: any[];
}

export interface TableMeta {
  name: string;
  display_name: string;
  row_count: number;
  role: 'fact' | 'dimension' | 'mapping';
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

export interface QualityIssue {
  type: string;
  severity: 'high' | 'medium' | 'low';
  table: string;
  column?: string;
  row_count?: number;
  pct?: number;
  description: string;
  impact: string;
}

export interface QualitySummary {
  high: number;
  medium: number;
  low: number;
  total: number;
}

export interface SemanticTime {
  primary_column?: string;
  min?: string;
  max?: string;
  anchor_date?: string;
}

export interface MetricMeta {
  name: string;
  label: string;
  table: string;
  expr: string;
  additive: boolean;
  format: 'currency' | 'count' | 'percent' | 'number';
  time_behavior: 'flow' | 'snapshot';
  synonyms: string[];
}

export interface SemanticResponse {
  status: string;
  dataset_id: string;
  tables: TableMeta[];
  relationships: Relationship[];
  time: SemanticTime;
  quality_summary: QualitySummary;
}

export interface QueryResult {
  columns: string[];
  rows: any[][];
  row_count: number;
  truncated: boolean;
}

export interface ChartSpec {
  type: 'kpi' | 'line' | 'bar' | 'bar_h' | 'grouped_bar' | 'contribution' | 'table';
  title?: string;
  x?: string;
  y?: string | string[];
  series?: any[];
  kpi?: {
    value: number;
    formatted: string;
    delta?: number;
    delta_pct?: number;
    direction?: 'up' | 'down' | 'flat';
    label?: string;
  };
  options?: Record<string, any>;
}

export interface WhySegment {
  value: string;
  baseline: number;
  target: number;
  delta: number;
  contribution: number;
  lift: number;
  drill_down?: any[];
}

export interface WhyDimensionResult {
  dimension: string;
  label: string;
  segments: WhySegment[];
  offsetting_detected: boolean;
}

export interface WhyAnalysisResult {
  metric: string;
  target_window: [string, string];
  baseline_window: [string, string];
  baseline_total: number;
  target_total: number;
  delta: number;
  delta_pct: number;
  direction: 'increase' | 'decrease' | 'flat';
  dimensions: WhyDimensionResult[];
  executive_summary?: string;
}

export interface AskResponse {
  status: 'ok' | 'clarification' | 'unsupported' | 'error';
  message?: string;
  plan?: Record<string, any>;
  assumptions: string[];
  resolved_time?: {
    start: string;
    end: string;
    label: string;
    baseline?: {
      start: string;
      end: string;
      label: string;
    };
  };
  sql?: string;
  result?: QueryResult;
  chart?: ChartSpec;
  narrative?: string;
  dq_warnings: QualityIssue[];
  why?: WhyAnalysisResult;
  suggestions: string[];
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'analyst';
  text: string;
  timestamp: string;
  response?: AskResponse;
}

export interface KPICardData {
  id: string;
  title: string;
  value: number;
  formatted: string;
  delta?: number;
  delta_pct?: number;
  direction?: 'up' | 'down' | 'flat';
  sparkline?: number[];
  period_label?: string;
}

export interface AlertItem {
  id: string;
  type: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  suggested_action?: string;
  drill_question?: string;
}

export interface DashboardResponse {
  status: string;
  dataset_id: string;
  generated_at: string;
  executive_summary: string;
  kpis: KPICardData[];
  charts: {
    monthly_trend?: {
      title: string;
      spec: ChartSpec;
      result: QueryResult;
    };
    category_breakdown?: {
      title: string;
      spec: ChartSpec;
      result: QueryResult;
    };
    entity_ranking?: {
      title: string;
      spec: ChartSpec;
      result: QueryResult;
    };
  };
  alerts: AlertItem[];
}

export interface AppSettings {
  active_provider: 'openrouter' | 'nvidia_nim';
  openrouter_model: string;
  nvidia_nim_model: string;
}
