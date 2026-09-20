import React, { useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { X, Check, Server, Cpu, ShieldCheck } from 'lucide-react';

export const SettingsModal: React.FC = () => {
  const { isSettingsOpen, setSettingsOpen, settings, updateSettings } = useAppStore();
  const [provider, setProvider] = useState<'openrouter' | 'nvidia_nim'>(
    settings?.active_provider || 'openrouter'
  );
  const [openrouterModel, setOpenrouterModel] = useState(
    settings?.openrouter_model || 'nex-agi/nex-n2.5-mini:free'
  );
  const [nvidiaModel, setNvidiaModel] = useState(
    settings?.nvidia_nim_model || 'meta/llama-3.2-11b-vision-instruct'
  );
  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  if (!isSettingsOpen) return null;

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateSettings({
        active_provider: provider,
        openrouter_model: openrouterModel,
        nvidia_nim_model: nvidiaModel
      });
      setSavedSuccess(true);
      setTimeout(() => {
        setSavedSuccess(false);
        setSettingsOpen(false);
      }, 700);
    } catch (e) {
      console.error(e);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl p-6 relative">
        <button
          onClick={() => setSettingsOpen(false)}
          className="absolute top-5 right-5 text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">LLM Provider Configuration</h2>
            <p className="text-xs text-slate-400">
              Configure primary and fallback AI model engines
            </p>
          </div>
        </div>

        <div className="space-y-5">
          {/* Active Provider Selector */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Primary Model Provider
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setProvider('openrouter')}
                className={`flex flex-col items-start p-3.5 rounded-xl border text-left transition ${
                  provider === 'openrouter'
                    ? 'border-indigo-500 bg-indigo-950/40 text-white shadow-sm'
                    : 'border-slate-800 bg-slate-950/50 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <span className="font-semibold text-sm">OpenRouter</span>
                  {provider === 'openrouter' && <Check className="w-4 h-4 text-indigo-400" />}
                </div>
                <span className="text-[11px] text-slate-400 leading-tight">
                  Free models with zero-cost exploration
                </span>
              </button>

              <button
                type="button"
                onClick={() => setProvider('nvidia_nim')}
                className={`flex flex-col items-start p-3.5 rounded-xl border text-left transition ${
                  provider === 'nvidia_nim'
                    ? 'border-indigo-500 bg-indigo-950/40 text-white shadow-sm'
                    : 'border-slate-800 bg-slate-950/50 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <span className="font-semibold text-sm">NVIDIA NIM</span>
                  {provider === 'nvidia_nim' && <Check className="w-4 h-4 text-indigo-400" />}
                </div>
                <span className="text-[11px] text-slate-400 leading-tight">
                  High-throughput Llama 3.2 vision/instruct
                </span>
              </button>
            </div>
          </div>

          {/* Model Specific Settings */}
          <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                OpenRouter Model ID
              </label>
              <input
                type="text"
                value={openrouterModel}
                onChange={(e) => setOpenrouterModel(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
                placeholder="e.g. nex-agi/nex-n2.5-mini:free"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                NVIDIA NIM Model ID
              </label>
              <input
                type="text"
                value={nvidiaModel}
                onChange={(e) => setNvidiaModel(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
                placeholder="e.g. meta/llama-3.2-11b-vision-instruct"
              />
            </div>

            <div className="flex items-start gap-2 pt-2 text-[11px] text-slate-400 border-t border-slate-900">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <span>
                Automatic failover active: If the primary provider hits a 429 rate limit or timeout, the engine automatically routes to the secondary provider.
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              onClick={() => setSettingsOpen(false)}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 transition"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-medium transition shadow-lg shadow-indigo-500/25 flex items-center gap-1.5"
            >
              {savedSuccess ? (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>Saved!</span>
                </>
              ) : (
                <span>Save Changes</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
