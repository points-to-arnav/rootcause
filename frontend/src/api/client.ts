import {
  AskResponse,
  DashboardResponse,
  QualityIssue,
  SemanticResponse,
  AppSettings
} from '../types';

const BASE_URL = '/api';

export async function uploadDataset(files: File[]): Promise<SemanticResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));

  const res = await fetch(`${BASE_URL}/datasets`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Failed to upload dataset');
  }
  return res.json();
}

export async function loadSampleDataset(): Promise<SemanticResponse> {
  const res = await fetch(`${BASE_URL}/datasets/sample`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Sample load failed' }));
    throw new Error(err.detail || 'Failed to load sample dataset');
  }
  return res.json();
}

export async function getSemanticLayer(datasetId: string): Promise<SemanticResponse> {
  const res = await fetch(`${BASE_URL}/datasets/${datasetId}/semantic`);
  if (!res.ok) {
    throw new Error('Failed to load semantic layer');
  }
  return res.json();
}

export async function getQualityIssues(datasetId: string): Promise<{ dataset_id: string; issues: QualityIssue[] }> {
  const res = await fetch(`${BASE_URL}/datasets/${datasetId}/quality`);
  if (!res.ok) {
    throw new Error('Failed to load quality issues');
  }
  return res.json();
}

export async function createSession(datasetId: string): Promise<{ session_id: string; dataset_id: string }> {
  const res = await fetch(`${BASE_URL}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId }),
  });
  if (!res.ok) {
    throw new Error('Failed to create session');
  }
  return res.json();
}

export async function askQuestion(sessionId: string, question: string): Promise<AskResponse> {
  const res = await fetch(`${BASE_URL}/sessions/${sessionId}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Analysis failed' }));
    throw new Error(err.detail || 'Analysis request failed');
  }
  return res.json();
}

export async function getDashboard(datasetId: string): Promise<DashboardResponse> {
  const res = await fetch(`${BASE_URL}/datasets/${datasetId}/dashboard`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error('Failed to generate dashboard');
  }
  return res.json();
}

export async function getSettings(): Promise<AppSettings> {
  const res = await fetch(`${BASE_URL}/settings`);
  if (!res.ok) {
    throw new Error('Failed to fetch settings');
  }
  return res.json();
}

export async function updateSettings(settings: Partial<AppSettings>): Promise<AppSettings> {
  const res = await fetch(`${BASE_URL}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!res.ok) {
    throw new Error('Failed to update settings');
  }
  return res.json();
}
