import React, { useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { X, Check, Cpu, ShieldCheck } from 'lucide-react';

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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-[#0C0C0C] border border-[#222222] rounded-[16px] w-full max-w-lg p-6 relative font-mono">
        <button
          onClick={() => setSettingsOpen(false)}
          className="absolute top-5 right-5 text-[#71717A] hover:text-white p-1.5 rounded-lg hover:bg-[#1A1A1A] transition cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-3 mb-6">
          <div className="w-9 h-9 rounded-xl bg-[#141414] border border-[#262626] flex items-center justify-center text-cyan-400">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white tracking-wide uppercase">
              LLM ENGINE CONFIGURATION
            </h2>
            <p className="text-xs text-[#888888] mt-0.5">
              Configure primary and fallback AI model inference endpoints
            </p>
          </div>
        </div>

        <div className="space-y-5">
          {/* Active Provider Selector */}
          <div>
            <label className="block text-[11px] font-semibold text-[#888888] uppercase tracking-wider mb-2">
              ACTIVE PROVIDER
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setProvider('openrouter')}
                className={`flex flex-col items-start p-3 rounded-xl border text-left transition cursor-pointer ${
                  provider === 'openrouter'
                    ? 'border-cyan-500/60 bg-cyan-950/20 text-white'
                    : 'border-[#1E1E1E] bg-[#080808] text-[#888888] hover:border-[#2C2C2C]'
                }`}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <span className="font-semibold text-xs text-white">OpenRouter</span>
                  {provider === 'openrouter' && <Check className="w-3.5 h-3.5 text-cyan-400" />}
                </div>
                <span className="text-[10px] text-[#888888] leading-tight">
                  Free community & zero-cost models
                </span>
              </button>

              <button
                type="button"
                onClick={() => setProvider('nvidia_nim')}
                className={`flex flex-col items-start p-3 rounded-xl border text-left transition cursor-pointer ${
                  provider === 'nvidia_nim'
                    ? 'border-cyan-500/60 bg-cyan-950/20 text-white'
                    : 'border-[#1E1E1E] bg-[#080808] text-[#888888] hover:border-[#2C2C2C]'
                }`}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <span className="font-semibold text-xs text-white">NVIDIA NIM</span>
                  {provider === 'nvidia_nim' && <Check className="w-3.5 h-3.5 text-cyan-400" />}
                </div>
                <span className="text-[10px] text-[#888888] leading-tight">
                  High-throughput Llama 3.2 vision/instruct
                </span>
              </button>
            </div>
          </div>

          {/* Model Specific Settings */}
          <div className="p-4 bg-[#080808] rounded-xl border border-[#1E1E1E] space-y-3">
            <div>
              <label className="block text-[11px] text-[#888888] mb-1">
                OpenRouter Model Identifier
              </label>
              <input
                type="text"
                value={openrouterModel}
                onChange={(e) => setOpenrouterModel(e.target.value)}
                className="w-full px-3 py-2 bg-[#050505] border border-[#222222] rounded-lg text-xs text-white focus:outline-none focus:border-cyan-400 font-mono"
                placeholder="e.g. nex-agi/nex-n2.5-mini:free"
              />
            </div>

            <div>
              <label className="block text-[11px] text-[#888888] mb-1">
                NVIDIA NIM Model Identifier
              </label>
              <input
                type="text"
                value={nvidiaModel}
                onChange={(e) => setNvidiaModel(e.target.value)}
                className="w-full px-3 py-2 bg-[#050505] border border-[#222222] rounded-lg text-xs text-white focus:outline-none focus:border-cyan-400 font-mono"
                placeholder="e.g. meta/llama-3.2-11b-vision-instruct"
              />
            </div>

            <div className="flex items-start gap-2 pt-2 text-[11px] text-[#71717A] border-t border-[#161616]">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
              <span>
                Automatic failover active: If primary provider hits 429 rate limit or timeout, the engine dynamically routes to fallback.
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              onClick={() => setSettingsOpen(false)}
              className="btn-framer-secondary px-3.5 py-1.5 text-xs cursor-pointer"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="btn-framer-primary px-4 py-1.5 text-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              {savedSuccess ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Config Saved</span>
                </>
              ) : (
                <span>Save Configuration</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
