import { create } from 'zustand';

import * as api from '../api/client';
import { ApiError } from '../api/client';
import { formatTime } from '../lib/format';
import type {
  AppSettings,
  AskResponse,
  ChatMessage,
  DashboardResponse,
  QualityIssue,
  SemanticResponse,
  StatsSummary,
  TabId,
} from '../types';

const DATASET_KEY = 'rootcause_dataset_id';
const SESSION_KEY = 'rootcause_session_id';

/** sessionStorage throws in some privacy modes; a demo must not die for it. */
function readStored(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key: string, value: string | null): void {
  try {
    if (value === null) sessionStorage.removeItem(key);
    else sessionStorage.setItem(key, value);
  } catch {
    /* no persistence available; the session still works in memory */
  }
}

export interface Toast {
  id: string;
  tone: 'success' | 'error' | 'info';
  title: string;
  body?: string;
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

interface AppState {
  /* Navigation */
  tab: TabId;
  navOpen: boolean;
  settingsOpen: boolean;
  metricsOpen: boolean;

  /* Dataset */
  datasetId: string | null;
  sessionId: string | null;
  semantic: SemanticResponse | null;
  qualityIssues: QualityIssue[];

  /* Work */
  messages: ChatMessage[];
  dashboard: DashboardResponse | null;
  settings: AppSettings | null;
  stats: StatsSummary | null;

  /* Flags */
  asking: boolean;
  ingesting: boolean;
  restoring: boolean;
  dashboardLoading: boolean;

  toasts: Toast[];

  setTab: (tab: TabId) => void;
  setNavOpen: (open: boolean) => void;
  setSettingsOpen: (open: boolean) => void;
  setMetricsOpen: (open: boolean) => void;

  toast: (toast: Omit<Toast, 'id'>) => void;
  dismissToast: (id: string) => void;

  bootstrap: () => Promise<void>;
  saveSettings: (patch: Partial<AppSettings>) => Promise<void>;

  refreshStats: () => Promise<void>;
  resetStats: () => Promise<void>;

  loadSample: () => Promise<void>;
  uploadFiles: (files: File[]) => Promise<void>;
  ask: (question: string) => Promise<void>;
  retryLast: () => Promise<void>;
  loadDashboard: () => Promise<void>;
  clearDataset: () => void;
}


export const useAppStore = create<AppState>((set, get) => ({
  tab: 'analyst',
  navOpen: false,
  settingsOpen: false,
  metricsOpen: false,

  datasetId: readStored(DATASET_KEY),
  sessionId: readStored(SESSION_KEY),
  semantic: null,
  qualityIssues: [],

  messages: [],
  dashboard: null,
  settings: null,
  stats: null,

  asking: false,
  ingesting: false,
  // Starts true when a dataset id survives in sessionStorage: the UI must not
  // flash an empty state before we know whether that dataset is still there.
  restoring: Boolean(readStored(DATASET_KEY)),
  dashboardLoading: false,

  toasts: [],

  setTab: (tab) => set({ tab, navOpen: false }),
  setNavOpen: (navOpen) => set({ navOpen }),
  setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
  setMetricsOpen: (metricsOpen) => set({ metricsOpen }),

  toast: (toast) => {
    const id = `t_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
    const ttl = toast.tone === 'error' ? 8000 : 4000;
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, ttl);
  },

  dismissToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),

  bootstrap: async () => {
    // Settings and stats are independent of the dataset, so never let one
    // failing block the other.
    void get().refreshStats();
    try {
      set({ settings: await api.getSettings() });
    } catch (error) {
      console.error('Settings failed to load', error);
    }

    const storedDataset = get().datasetId;
    if (!storedDataset) {
      set({ restoring: false });
      return;
    }

    try {
      const [semantic, quality] = await Promise.all([
        api.getSemanticLayer(storedDataset),
        api.getQualityIssues(storedDataset),
      ]);
      set({
        semantic,
        qualityIssues: quality.issues,
        restoring: false,
        messages: get().messages,
      });
    } catch {
      // The server was restarted or the dataset was cleared; start clean rather
      // than leaving a dataset id pointing at nothing.
      writeStored(DATASET_KEY, null);
      writeStored(SESSION_KEY, null);
      set({ datasetId: null, sessionId: null, semantic: null, restoring: false });
    }
  },

  saveSettings: async (patch) => {
    const updated = await api.updateSettings(patch);
    set({ settings: updated });
  },

  refreshStats: async () => {
    try {
      const res = await api.getStats();
      set({ stats: res.summary });
    } catch {
      /* metrics are supplementary; a failure here must stay silent */
    }
  },

  resetStats: async () => {
    try {
      const res = await api.resetStats();
      set({ stats: res.summary });
    } catch (error) {
      get().toast({ tone: 'error', title: 'Metrics could not be reset' });
      console.error(error);
    }
  },

  loadSample: async () => {
    set({ ingesting: true });
    try {
      const ingested = await api.loadSampleDataset();
      const [semantic, quality, session] = await Promise.all([
        api.getSemanticLayer(ingested.dataset_id),
        api.getQualityIssues(ingested.dataset_id),
        api.createSession(ingested.dataset_id),
      ]);

      writeStored(DATASET_KEY, semantic.dataset_id);
      writeStored(SESSION_KEY, session.session_id);

      set({
        datasetId: semantic.dataset_id,
        sessionId: session.session_id,
        semantic,
        qualityIssues: quality.issues,
        dashboard: null,
        ingesting: false,
        restoring: false,
        tab: 'analyst',
        messages: [],
      });
      get().toast({ tone: 'success', title: 'Sample retail data loaded' });
      void get().refreshStats();
    } catch (error) {
      set({ ingesting: false });
      get().toast({
        tone: 'error',
        title: 'Sample data could not be loaded',
        body: errorText(error, 'The server did not respond.'),
      });
    }
  },

  uploadFiles: async (files) => {
    if (files.length === 0) return;
    set({ ingesting: true });
    try {
      const ingested = await api.uploadDataset(files);
      const [semantic, quality, session] = await Promise.all([
        api.getSemanticLayer(ingested.dataset_id),
        api.getQualityIssues(ingested.dataset_id),
        api.createSession(ingested.dataset_id),
      ]);

      writeStored(DATASET_KEY, semantic.dataset_id);
      writeStored(SESSION_KEY, session.session_id);

      set({
        datasetId: semantic.dataset_id,
        sessionId: session.session_id,
        semantic,
        qualityIssues: quality.issues,
        dashboard: null,
        ingesting: false,
        restoring: false,
        tab: 'analyst',
        messages: [],
      });
      get().toast({ tone: 'success', title: 'Dataset ready' });
      void get().refreshStats();
    } catch (error) {
      set({ ingesting: false });
      get().toast({
        tone: 'error',
        title: 'The files could not be read',
        body: errorText(error, 'Check that the file is a .csv or .xlsx.'),
      });
    }
  },

  ask: async (question) => {
    const trimmed = question.trim();
    if (!trimmed || get().asking) return;

    const { datasetId } = get();
    let sessionId = get().sessionId;

    if (!sessionId && datasetId) {
      try {
        const session = await api.createSession(datasetId);
        writeStored(SESSION_KEY, session.session_id);
        sessionId = session.session_id;
        set({ sessionId });
      } catch (error) {
        get().toast({
          tone: 'error',
          title: 'A session could not be started',
          body: errorText(error, 'The server did not respond.'),
        });
        return;
      }
    }

    if (!sessionId) {
      get().toast({ tone: 'info', title: 'Load a dataset before asking a question' });
      set({ tab: 'data' });
      return;
    }

    set((state) => ({
      asking: true,
      messages: [
        ...state.messages,
        { id: `u_${Date.now()}`, sender: 'user', text: trimmed, timestamp: formatTime() },
      ],
    }));

    try {
      const response: AskResponse = await api.askQuestion(sessionId, trimmed);
      set((state) => ({
        asking: false,
        messages: [
          ...state.messages,
          {
            id: `a_${Date.now()}`,
            sender: 'analyst',
            text: response.narrative || response.message || 'No answer was produced.',
            timestamp: formatTime(),
            failed: response.status === 'error',
            response,
          },
        ],
        // The answer carries fresh totals, so the metrics panel updates with no poll.
        stats: response.llm_totals ?? state.stats,
      }));
    } catch (error) {
      set((state) => ({
        asking: false,
        messages: [
          ...state.messages,
          {
            id: `e_${Date.now()}`,
            sender: 'analyst',
            text: errorText(error, 'The question could not be answered.'),
            timestamp: formatTime(),
            failed: true,
          },
        ],
      }));
    }
  },

  retryLast: async () => {
    const lastQuestion = [...get().messages]
      .reverse()
      .find((message) => message.sender === 'user');
    if (!lastQuestion) return;

    // Drop the failed exchange so the retry does not stack duplicates.
    set((state) => {
      const index = state.messages.findIndex((m) => m.id === lastQuestion.id);
      return { messages: index === -1 ? state.messages : state.messages.slice(0, index) };
    });
    await get().ask(lastQuestion.text);
  },

  loadDashboard: async () => {
    const { datasetId } = get();
    if (!datasetId) return;
    set({ dashboardLoading: true });
    try {
      const dashboard = await api.getDashboard(datasetId);
      set({ dashboard, dashboardLoading: false });
    } catch (error) {
      set({ dashboardLoading: false });
      get().toast({
        tone: 'error',
        title: 'Overview unavailable',
        body: errorText(error, 'The overview could not be generated.'),
      });
    }
  },

  clearDataset: () => {
    writeStored(DATASET_KEY, null);
    writeStored(SESSION_KEY, null);
    set({
      datasetId: null,
      sessionId: null,
      semantic: null,
      qualityIssues: [],
      messages: [],
      dashboard: null,
      restoring: false,
      tab: 'data',
    });
  },
}));
