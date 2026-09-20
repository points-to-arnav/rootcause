import React, { useState, useRef, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { AnswerCard } from '../components/AnswerCard';
import { Send, Bot, User, Sparkles, Terminal, Activity, Database } from 'lucide-react';

export const AnalystPage: React.FC = () => {
  const { messages, isLoading, sendMessage, datasetId, loadSample, setTab } = useAppStore();
  const [input, setInput] = useState('');
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const [step, setStep] = useState(0);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    let t1: any, t2: any, t3: any;
    if (isLoading) {
      setStep(1);
      t1 = setTimeout(() => setStep(2), 500);
      t2 = setTimeout(() => setStep(3), 1200);
      t3 = setTimeout(() => setStep(4), 2000);
    } else {
      setStep(0);
    }
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [isLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    const q = input.trim();
    setInput('');
    await sendMessage(q);
  };

  const handleSelectSuggestion = async (prompt: string) => {
    if (isLoading) return;
    await sendMessage(prompt);
  };

  if (!datasetId) {
    return (
      <div className="max-w-md mx-auto my-24 p-8 bento-card text-center space-y-4">
        <div className="w-12 h-12 rounded-xl bg-[#111111] border border-[#222222] flex items-center justify-center text-cyan-400 mx-auto">
          <Terminal className="w-6 h-6" />
        </div>
        <h3 className="text-base font-semibold text-white font-mono">NO ACTIVE FORENSICS SESSION</h3>
        <p className="text-xs text-[#888888] font-mono">
          Ingest a .parquet, .duckdb, or .csv dataset to initiate SQL telemetry and driver attribution.
        </p>
        <div className="flex flex-col gap-2 pt-2">
          <button
            onClick={() => loadSample()}
            className="btn-framer-primary px-4 py-2 text-xs font-mono"
          >
            Load Sample Forensic Dataset
          </button>
          <button
            onClick={() => setTab('upload')}
            className="btn-framer-secondary px-4 py-2 text-xs font-mono"
          >
            Go to Ingest Zone
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Messages Thread */}
      <div className="flex-1 overflow-y-auto space-y-5 pr-2">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start gap-3.5 ${
              msg.sender === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {msg.sender === 'analyst' && (
              <div className="w-8 h-8 rounded-lg bg-[#111111] border border-[#262626] flex items-center justify-center text-cyan-400 shrink-0 mt-1">
                <Terminal className="w-4 h-4" />
              </div>
            )}

            <div
              className={`max-w-3xl ${
                msg.sender === 'user'
                  ? 'bg-[#141414] border border-[#262626] text-white px-4 py-3 rounded-2xl rounded-tr-sm text-sm font-mono'
                  : 'w-full'
              }`}
            >
              {msg.sender === 'user' ? (
                <div className="text-sm font-medium leading-relaxed">{msg.text}</div>
              ) : msg.response ? (
                <AnswerCard
                  response={msg.response}
                  onSelectSuggestion={handleSelectSuggestion}
                />
              ) : (
                <div className="p-4 bento-card text-sm text-[#CCCCCC] font-mono">
                  {msg.text}
                </div>
              )}
            </div>

            {msg.sender === 'user' && (
              <div className="w-8 h-8 rounded-lg bg-[#141414] border border-[#262626] flex items-center justify-center text-[#A1A1AA] shrink-0 mt-1">
                <User className="w-4 h-4" />
              </div>
            )}
          </div>
        ))}

        {/* PROGRESSIVE TELEMETRY LOADING STEPPER */}
        {isLoading && (
          <div className="bento-card p-4 border-cyan-500/30 bg-[#082F49]/10">
            <div className="flex items-center justify-between mb-3 text-xs font-mono">
              <span className="text-cyan-400 flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 animate-pulse" />
                EXECUTING PARALLEL FORENSIC PLAN...
              </span>
              <span className="text-[#888888]">DuckDB ~12ms</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 text-[11px] font-mono">
              <div className={`p-2 rounded border ${step >= 1 ? 'border-cyan-500/50 bg-cyan-950/30 text-cyan-200' : 'border-[#1E1E1E] text-[#52525B]'}`}>
                1. Schema Grounding
              </div>
              <div className={`p-2 rounded border ${step >= 2 ? 'border-cyan-500/50 bg-cyan-950/30 text-cyan-200' : 'border-[#1E1E1E] text-[#52525B]'}`}>
                2. DuckDB Vector Scan
              </div>
              <div className={`p-2 rounded border ${step >= 3 ? 'border-cyan-500/50 bg-cyan-950/30 text-cyan-200' : 'border-[#1E1E1E] text-[#52525B]'}`}>
                3. Variance Attribution
              </div>
              <div className={`p-2 rounded border ${step >= 4 ? 'border-emerald-500/50 bg-emerald-950/30 text-emerald-200' : 'border-[#1E1E1E] text-[#52525B]'}`}>
                4. Narrative Complete
              </div>
            </div>
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      {/* Input Bar */}
      <div className="pt-3 border-t border-[#1A1A1A] mt-2">
        <form onSubmit={handleSubmit} className="glass-search-bar p-1.5 flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
            placeholder="Ask forensic question (e.g., 'What caused revenue to drop last month?', 'Show monthly sales')..."
            className="w-full bg-transparent px-3 py-2 text-sm text-[#EDEDED] placeholder-[#52525B] font-mono focus:outline-none"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="btn-framer-primary px-3.5 py-2 text-xs font-mono flex items-center gap-1.5 shrink-0 disabled:opacity-40 cursor-pointer"
          >
            <span>Query</span>
            <Send className="w-3 h-3" />
          </button>
        </form>
      </div>
    </div>
  );
};
