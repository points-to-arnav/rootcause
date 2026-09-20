import React from 'react';
import { useAppStore } from '../store/useAppStore';
import { Database, MessageSquare, LayoutDashboard, Settings as SettingsIcon, RefreshCw, Zap } from 'lucide-react';

export const Navbar: React.FC = () => {
  const {
    currentTab,
    setTab,
    datasetId,
    settings,
    setSettingsOpen,
    resetDataset
  } = useAppStore();

  const providerName = settings?.active_provider === 'openrouter' ? 'OpenRouter' : 'NVIDIA NIM';
  const modelName = settings?.active_provider === 'openrouter'
    ? settings.openrouter_model.split('/').pop()?.split(':')[0]
    : settings?.nvidia_nim_model.split('/').pop();

  return (
    <header className="h-16 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50 px-6 flex items-center justify-between">
      {/* Brand & Dataset */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
              RootCause
            </span>
            <span className="ml-1.5 px-1.5 py-0.5 text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded">
              v1.0
            </span>
          </div>
        </div>

        {datasetId && (
          <div className="hidden md:flex items-center gap-2 pl-4 border-l border-slate-800 text-xs text-slate-400">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-medium text-slate-300 truncate max-w-[140px]">{datasetId}</span>
            <button
              onClick={resetDataset}
              title="Reset Dataset"
              className="p-1 hover:text-slate-200 hover:bg-slate-800 rounded transition"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Center Nav Tabs */}
      <nav className="flex items-center gap-1 bg-slate-900/60 p-1 rounded-xl border border-slate-800/60">
        <button
          onClick={() => setTab('upload')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
            currentTab === 'upload'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          <span>Data & Schema</span>
        </button>

        <button
          onClick={() => setTab('analyst')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
            currentTab === 'analyst'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>AI Analyst</span>
        </button>

        <button
          onClick={() => setTab('dashboard')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
            currentTab === 'dashboard'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
          }`}
        >
          <LayoutDashboard className="w-3.5 h-3.5" />
          <span>Dashboard</span>
        </button>
      </nav>

      {/* Right Model & Settings */}
      <div className="flex items-center gap-3">
        <div
          onClick={() => setSettingsOpen(true)}
          className="cursor-pointer hidden sm:flex items-center gap-2 px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-300 hover:border-slate-700 transition"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
          <span className="font-semibold text-slate-200">{providerName}</span>
          <span className="text-slate-500">/</span>
          <span className="text-slate-400 max-w-[120px] truncate">{modelName || 'free'}</span>
        </div>

        <button
          onClick={() => setSettingsOpen(true)}
          title="Settings & Model Provider"
          className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg border border-slate-800/80 transition"
        >
          <SettingsIcon className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
