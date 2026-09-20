import React from 'react';
import { Sparkles } from 'lucide-react';

interface SuggestionChipsProps {
  suggestions: string[];
  onSelect: (prompt: string) => void;
}

export const SuggestionChips: React.FC<SuggestionChipsProps> = ({ suggestions, onSelect }) => {
  if (!suggestions || suggestions.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-3 pt-2">
      <div className="flex items-center gap-1 text-[10px] font-mono text-[#71717A] mr-1">
        <Sparkles className="w-3 h-3 text-cyan-400" />
        <span>SUGGESTED INVESTIGATION:</span>
      </div>
      {suggestions.map((s, idx) => (
        <button
          key={idx}
          onClick={() => onSelect(s)}
          className="px-2.5 py-1 rounded-md text-[11px] font-mono bg-[#0D0D0D] border border-[#1E1E1E] text-[#A1A1AA] hover:text-white hover:border-[#333333] hover:bg-[#141414] transition-all text-left cursor-pointer"
        >
          {s}
        </button>
      ))}
    </div>
  );
};
