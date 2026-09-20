interface SuggestionsProps {
  suggestions: string[];
  onSelect: (question: string) => void;
  label?: string;
}

export function Suggestions({ suggestions, onSelect, label = 'Ask next' }: SuggestionsProps) {
  if (suggestions.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5 pt-1">
      <span className="text-[12px] text-ink-3">{label}</span>
      {suggestions.map((suggestion) => (
        <button
          key={suggestion}
          onClick={() => onSelect(suggestion)}
          className="rounded-sm border border-line bg-raised px-2 py-1 text-left text-[12px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
        >
          {suggestion}
        </button>
      ))}
    </div>
  );
}
