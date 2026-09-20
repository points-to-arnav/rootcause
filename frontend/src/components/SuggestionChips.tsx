import React from 'react';
import { Sparkles } from 'lucide-react';

interface SuggestionChipsProps {
  suggestions: string[];
  onSelect: (prompt: string) => void;
}

export const SuggestionChips: React.FC<SuggestionChipsProps> = ({ suggestions, onSelect }) => {
  if (!suggestions || suggestions.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 mt-3 pt-2">
      <div className="flex items-center gap-1 text-[11px] font-medium text-slate-500 mr-1">
        <Sparkles className="w-3 h-3 text-indigo-400" />
        <span>Suggested:</span>
      </div>
      {suggestions.map((s, idx) => (
        <button
          key={idx}
          onClick={() => onSelect(s)}
          className="px-3 py-1.5 rounded-full text-xs bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:border-indigo-500/60 hover:bg-indigo-950/30 transition-all text-left"
        >
          {s}
        </button>
      ))}
    </div>
  );
};
