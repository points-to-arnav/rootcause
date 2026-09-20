import type {
  AppSettings,
  AskResponse,
  DashboardResponse,
  QualityResponse,
  SemanticResponse,
  StatsResponse,
  StatsSummary,
} from '../types';

const BASE_URL = '/api';

/** An error that carries the HTTP status so callers can tell "not found" from
 *  "the server is down" without parsing strings. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function readError(res: Response, fallback: string): Promise<never> {
  let detail = fallback;
  try {
    const body = (await res.json()) as { detail?: string | { msg?: string }[] };
    if (typeof body.detail === 'string') {
      detail = body.detail;
    } else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      detail = body.detail[0].msg as string;
    }
  } catch {
    /* body was not JSON; keep the fallback */
  }
  throw new ApiError(detail, res.status);
}

async function request<T>(
  path: string,
  init?: RequestInit,
  fallback = 'The request failed.',
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, init);
  } catch {
    throw new ApiError('Cannot reach the RootCause server. Is the backend running?', 0);
  }
  if (!res.ok) return readError(res, fallback);
  return (await res.json()) as T;
}

export function uploadDataset(files: File[]): Promise<SemanticResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  return request<SemanticResponse>(
    '/datasets',
    { method: 'POST', body: formData },
    'The files could not be read.',
  );
}

export function loadSampleDataset(): Promise<SemanticResponse> {
  return request<SemanticResponse>(
    '/datasets/sample',
    { method: 'POST' },
    'The sample dataset could not be loaded.',
  );
}

/** The upload and sample endpoints flatten each table's columns to an array,
 *  while /semantic returns the stored model, where columns are keyed by name.
 *  Normalising here means the rest of the app only ever sees one shape. */
export async function getSemanticLayer(datasetId: string): Promise<SemanticResponse> {
  const raw = await request<SemanticResponse & { tables: unknown }>(
    `/datasets/${datasetId}/semantic`,
    undefined,
    'The dataset schema could not be loaded.',
  );

  const tables = raw.tables as unknown;
  const list = Array.isArray(tables) ? tables : Object.values(tables ?? {});

  return {
    ...raw,
    tables: (list as Record<string, unknown>[]).map((table) => ({
      ...table,
      columns: Array.isArray(table.columns)
        ? table.columns
        : Object.values((table.columns ?? {}) as Record<string, unknown>),
    })),
  } as SemanticResponse;
}

export function getQualityIssues(datasetId: string): Promise<QualityResponse> {
  return request<QualityResponse>(
    `/datasets/${datasetId}/quality`,
    undefined,
    'The data quality report could not be loaded.',
  );
}

export function createSession(
  datasetId: string,
): Promise<{ session_id: string; dataset_id: string }> {
  return request(
    '/sessions',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_id: datasetId }),
    },
    'A new session could not be started.',
  );
}

export function askQuestion(sessionId: string, question: string): Promise<AskResponse> {
  return request<AskResponse>(
    `/sessions/${sessionId}/ask`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    },
    'The question could not be answered.',
  );
}

export function getDashboard(datasetId: string): Promise<DashboardResponse> {
  return request<DashboardResponse>(
    `/datasets/${datasetId}/dashboard`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    },
    'The overview could not be generated.',
  );
}

export function getSettings(): Promise<AppSettings> {
  return request<AppSettings>('/settings', undefined, 'Settings could not be loaded.');
}

export function updateSettings(settings: Partial<AppSettings>): Promise<AppSettings> {
  return request<AppSettings>(
    '/settings',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    },
    'Settings could not be saved.',
  );
}

export function getStats(): Promise<StatsResponse> {
  return request<StatsResponse>('/stats', undefined, 'Live metrics could not be loaded.');
}

export function resetStats(): Promise<{ status: string; summary: StatsSummary }> {
  return request(
    '/stats/reset',
    { method: 'POST' },
    'Metrics could not be reset.',
  );
}
