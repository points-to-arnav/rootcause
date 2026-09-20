import { create } from 'zustand';
import {
  AskResponse,
  ChatMessage,
  DashboardResponse,
  QualityIssue,
  SemanticResponse,
  AppSettings
} from '../types';
import * as api from '../api/client';

interface AppState {
  datasetId: string | null;
  sessionId: string | null;
  currentTab: 'upload' | 'analyst' | 'dashboard';
  semantic: SemanticResponse | null;
  qualityIssues: QualityIssue[];
  messages: ChatMessage[];
  dashboard: DashboardResponse | null;
  isLoading: boolean;
  isDashboardLoading: boolean;
  settings: AppSettings | null;
  isSettingsOpen: boolean;

  setTab: (tab: 'upload' | 'analyst' | 'dashboard') => void;
  setSettingsOpen: (open: boolean) => void;
  loadInitialSettings: () => Promise<void>;
  updateSettings: (newSettings: Partial<AppSettings>) => Promise<void>;
  loadSample: () => Promise<void>;
  uploadFiles: (files: File[]) => Promise<void>;
  initSession: (datasetId: string) => Promise<string>;
  sendMessage: (text: string) => Promise<void>;
  loadDashboardData: () => Promise<void>;
  resetDataset: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  datasetId: sessionStorage.getItem('rootcause_dataset_id') || null,
  sessionId: sessionStorage.getItem('rootcause_session_id') || null,
  currentTab: 'dashboard',
  semantic: null,
  qualityIssues: [],
  messages: [],
  dashboard: null,
  isLoading: false,
  isDashboardLoading: false,
  settings: null,
  isSettingsOpen: false,

  setTab: (tab) => set({ currentTab: tab }),
  setSettingsOpen: (open) => set({ isSettingsOpen: open }),

  loadInitialSettings: async () => {
    try {
      const s = await api.getSettings();
      set({ settings: s });
    } catch (e) {
      console.error('Failed to load settings:', e);
    }
  },

  updateSettings: async (newSettings) => {
    try {
      const updated = await api.updateSettings(newSettings);
      set({ settings: updated });
    } catch (e) {
      console.error('Failed to update settings:', e);
      throw e;
    }
  },

  loadSample: async () => {
    set({ isLoading: true });
    try {
      const res = await api.loadSampleDataset();
      const qual = await api.getQualityIssues(res.dataset_id);
      const sess = await api.createSession(res.dataset_id);

      sessionStorage.setItem('rootcause_dataset_id', res.dataset_id);
      sessionStorage.setItem('rootcause_session_id', sess.session_id);

      set({
        datasetId: res.dataset_id,
        sessionId: sess.session_id,
        semantic: res,
        qualityIssues: qual.issues,
        isLoading: false,
        currentTab: 'analyst',
        messages: [
          {
            id: 'welcome',
            sender: 'analyst',
            text: `Welcome! I've loaded the **Retail Demo** dataset (16.6k sales across 2025–Aug 2026). What would you like to analyze?`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            response: {
              status: 'ok',
              assumptions: [],
              suggestions: [
                'What is our total revenue?',
                'Show monthly revenue for 2026',
                'Revenue by region',
                'Why did revenue fall last month?'
              ],
              dq_warnings: []
            }
          }
        ]
      });
    } catch (e) {
      set({ isLoading: false });
      console.error('Failed to load sample dataset:', e);
      throw e;
    }
  },

  uploadFiles: async (files: File[]) => {
    set({ isLoading: true });
    try {
      const res = await api.uploadDataset(files);
      const qual = await api.getQualityIssues(res.dataset_id);
      const sess = await api.createSession(res.dataset_id);

      sessionStorage.setItem('rootcause_dataset_id', res.dataset_id);
      sessionStorage.setItem('rootcause_session_id', sess.session_id);

      set({
        datasetId: res.dataset_id,
        sessionId: sess.session_id,
        semantic: res,
        qualityIssues: qual.issues,
        isLoading: false,
        currentTab: 'analyst',
        messages: [
          {
            id: 'welcome',
            sender: 'analyst',
            text: `Dataset successfully ingested! Identified ${res.tables.length} tables with ${res.relationships.length} joins detected. What question would you like to explore?`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            response: {
              status: 'ok',
              assumptions: [],
              suggestions: [
                'Show total revenue',
                'Monthly trend',
                'Create management dashboard'
              ],
              dq_warnings: []
            }
          }
        ]
      });
    } catch (e) {
      set({ isLoading: false });
      console.error('Failed to upload files:', e);
      throw e;
    }
  },

  initSession: async (datasetId: string) => {
    const sess = await api.createSession(datasetId);
    sessionStorage.setItem('rootcause_session_id', sess.session_id);
    set({ sessionId: sess.session_id });
    return sess.session_id;
  },

  sendMessage: async (text: string) => {
    const { sessionId, datasetId } = get();
    if (!sessionId && datasetId) {
      await get().initSession(datasetId);
    }
    const activeSessionId = get().sessionId;
    if (!activeSessionId) {
      throw new Error('No active session.');
    }

    const userMsg: ChatMessage = {
      id: `u_${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    set((state) => ({
      messages: [...state.messages, userMsg],
      isLoading: true
    }));

    try {
      const res = await api.askQuestion(activeSessionId, text);
      const analystMsg: ChatMessage = {
        id: `a_${Date.now()}`,
        sender: 'analyst',
        text: res.narrative || res.message || '',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        response: res
      };

      set((state) => ({
        messages: [...state.messages, analystMsg],
        isLoading: false
      }));
    } catch (e: any) {
      set({ isLoading: false });
      const errorMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        sender: 'analyst',
        text: `Error analyzing query: ${e.message || 'Server error'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      set((state) => ({ messages: [...state.messages, errorMsg] }));
    }
  },

  loadDashboardData: async () => {
    const { datasetId } = get();
    if (!datasetId) return;

    set({ isDashboardLoading: true });
    try {
      const data = await api.getDashboard(datasetId);
      set({ dashboard: data, isDashboardLoading: false });
    } catch (e) {
      console.error('Failed to load dashboard:', e);
      set({ isDashboardLoading: false });
    }
  },

  resetDataset: () => {
    sessionStorage.removeItem('rootcause_dataset_id');
    sessionStorage.removeItem('rootcause_session_id');
    set({
      datasetId: null,
      sessionId: null,
      semantic: null,
      qualityIssues: [],
      messages: [],
      dashboard: null,
      currentTab: 'upload'
    });
  }
}));
