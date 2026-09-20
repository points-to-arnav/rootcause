import React from 'react';
import { useAppStore } from '../store/useAppStore';
import {
  Database,
  Sparkles,
  LayoutGrid,
  Settings as SettingsIcon,
  RefreshCw,
  Terminal,
  Activity
} from 'lucide-react';

export const Navbar: React.FC = () => {
  const {
    currentTab,
    setTab,
    datasetId,
    semantic,
    settings,
    setSettingsOpen,
    resetDataset
  } = useAppStore();

  const providerName = settings?.active_provider === 'openrouter' ? 'OpenRouter' : 'NVIDIA NIM';
  const modelName = settings?.active_provider === 'openrouter'
    ? settings.openrouter_model.split('/').pop()?.split(':')[0]
    : settings?.nvidia_nim_model.split('/').pop();

  const rowCount = semantic?.tables?.reduce((acc, t) => acc + (t.row_count || 0), 0) || 16640;

  return (
    <header className="h-14 border-b border-[#1E1E1E] bg-[#070707]/90 backdrop-blur-xl sticky top-0 z-50 px-6 flex items-center justify-between">
      {/* Brand & Engine Status */}
      <div className="flex items-center gap-5">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#111111] border border-[#262626] flex items-center justify-center text-cyan-400">
            <Terminal className="w-3.5 h-3.5" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-semibold text-sm tracking-tight text-white font-mono">
              ROOTCAUSE
            </span>
            <span className="text-[10px] text-[#888888] font-mono tracking-widest uppercase">
              // FORENSICS ENGINE
            </span>
          </div>
        </div>

        {/* Operational Indicator */}
        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 bg-[#0A0A0A] border border-[#1E1E1E] rounded-md text-[11px] font-mono text-[#888888]">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-60"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400"></span>
          </span>
          <span className="text-[#A1A1AA]">SYSTEM OPERATIONAL</span>
          <span className="text-[#52525B]">•</span>
          <span className="text-cyan-400/90 font-medium">DuckDB Vector Core</span>
        </div>

        {/* Active Dataset Badge */}
        {datasetId && (
          <div className="hidden md:flex items-center gap-2 pl-3 border-l border-[#1E1E1E] text-xs font-mono text-[#888888]">
            <span className="text-[#A1A1AA] truncate max-w-[150px]">{datasetId}</span>
            <span className="text-[#52525B]">({rowCount.toLocaleString()} rows)</span>
            <button
              onClick={resetDataset}
              title="Unload Dataset"
              className="p-1 hover:text-white hover:bg-[#1A1A1A] rounded transition"
            >
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>

      {/* Center Nav Tabs (Bento Segment Controls) */}
      <nav className="flex items-center gap-1 bg-[#0D0D0D] p-1 rounded-lg border border-[#1E1E1E]">
        <button
          onClick={() => setTab('dashboard')}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
            currentTab === 'dashboard'
              ? 'bg-[#1F1F1F] text-white border border-[#2E2E2E]'
              : 'text-[#888888] hover:text-white hover:bg-[#141414]'
          }`}
        >
          <LayoutGrid className="w-3.5 h-3.5 text-cyan-400" />
          <span>Forensics Bento</span>
        </button>

        <button
          onClick={() => setTab('analyst')}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
            currentTab === 'analyst'
              ? 'bg-[#1F1F1F] text-white border border-[#2E2E2E]'
              : 'text-[#888888] hover:text-white hover:bg-[#141414]'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span>AI Analyst</span>
        </button>

        <button
          onClick={() => setTab('upload')}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
            currentTab === 'upload'
              ? 'bg-[#1F1F1F] text-white border border-[#2E2E2E]'
              : 'text-[#888888] hover:text-white hover:bg-[#141414]'
          }`}
        >
          <Database className="w-3.5 h-3.5 text-emerald-400" />
          <span>Data Ingest</span>
        </button>
      </nav>

      {/* Right Telemetry & Provider Settings */}
      <div className="flex items-center gap-3">
        <div
          onClick={() => setSettingsOpen(true)}
          className="cursor-pointer hidden sm:flex items-center gap-2 px-2.5 py-1 bg-[#0A0A0A] border border-[#1E1E1E] rounded-md text-xs font-mono text-[#888888] hover:border-[#333333] transition"
        >
          <Activity className="w-3 h-3 text-cyan-400" />
          <span className="text-[#CCCCCC]">{providerName}</span>
          <span className="text-[#444444]">/</span>
          <span className="text-[#888888] max-w-[110px] truncate">{modelName || 'free'}</span>
        </div>

        <button
          onClick={() => setSettingsOpen(true)}
          title="Engine Config & API Keys"
          className="p-1.5 text-[#888888] hover:text-white hover:bg-[#141414] rounded-md border border-[#1E1E1E] transition"
        >
          <SettingsIcon className="w-3.5 h-3.5" />
        </button>
      </div>
    </header>
  );
};
