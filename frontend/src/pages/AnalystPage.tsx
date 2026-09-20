import React, { useState, useRef, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { AnswerCard } from '../components/AnswerCard';
import { Send, Bot, User, Loader2, Sparkles, AlertCircle } from 'lucide-react';

export const AnalystPage: React.FC = () => {
  const { messages, isLoading, sendMessage, datasetId, setTab } = useAppStore();
  const [input, setInput] = useState('');
  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

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
      <div className="max-w-md mx-auto my-24 p-8 bg-slate-900 border border-slate-800 rounded-3xl text-center space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mx-auto">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h3 className="text-lg font-bold text-white">No Dataset Active</h3>
        <p className="text-xs text-slate-400">
          Upload an Excel or CSV file or load the retail demo dataset to begin your analysis.
        </p>
        <button
          onClick={() => setTab('upload')}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-500/25 transition"
        >
          Go to Data Upload
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 flex flex-col h-[calc(100vh-4rem)]">
      {/* Messages Thread */}
      <div className="flex-1 overflow-y-auto space-y-6 pr-2">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start gap-3.5 ${
              msg.sender === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {msg.sender === 'analyst' && (
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-white shrink-0 mt-1 shadow-md shadow-indigo-500/10">
                <Bot className="w-4 h-4" />
              </div>
            )}

            <div
              className={`max-w-3xl ${
                msg.sender === 'user'
                  ? 'bg-indigo-600 text-white px-4 py-2.5 rounded-2xl rounded-tr-sm text-sm shadow-md'
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
                <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl text-sm text-slate-300">
                  {msg.text}
                </div>
              )}
            </div>

            {msg.sender === 'user' && (
              <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0 mt-1">
                <User className="w-4 h-4" />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex items-start gap-3.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-white shrink-0 shadow-md">
              <Bot className="w-4 h-4" />
            </div>
            <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl flex items-center gap-3 text-xs text-slate-300">
              <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
              <span>Analyzing question & executing DuckDB query...</span>
            </div>
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      {/* Input Bar */}
      <div className="pt-4 border-t border-slate-800/80 mt-2">
        <form onSubmit={handleSubmit} className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
            placeholder="Ask a question (e.g. 'Show monthly revenue for 2026', 'Why did revenue fall last month?')..."
            className="w-full bg-slate-900/90 border border-slate-800 focus:border-indigo-500/80 rounded-2xl pl-5 pr-14 py-3.5 text-sm text-white placeholder-slate-500 focus:outline-none shadow-xl transition"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-2 p-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:hover:bg-indigo-600 text-white rounded-xl transition shadow-md shadow-indigo-500/20"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
      </div>
    </div>
  );
};
