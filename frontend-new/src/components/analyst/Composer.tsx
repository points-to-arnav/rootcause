import { useEffect, useRef, useState } from 'react';
import { ArrowUp } from 'lucide-react';
import { Spinner } from '../ui/Spinner';

interface ComposerProps {
  onSubmit: (question: string) => void;
  busy: boolean;
  placeholder?: string;
}

/** A textarea that grows with its content, submits on Enter, and keeps a
 *  newline on Shift+Enter. */
export function Composer({ onSubmit, busy, placeholder }: ComposerProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
  }, [value]);

  function submit() {
    const question = value.trim();
    if (!question || busy) return;
    setValue('');
    onSubmit(question);
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className="flex items-end gap-2 rounded-lg border border-line bg-surface p-2 transition-colors focus-within:border-accent/60"
    >
      <label htmlFor="composer" className="sr-only">
        Ask a question about your data
      </label>
      <textarea
        id="composer"
        ref={textareaRef}
        rows={1}
        value={value}
        disabled={busy}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        placeholder={placeholder ?? 'Ask why a number moved, or for a trend or a breakdown'}
        className="max-h-40 min-h-[2rem] flex-1 resize-none bg-transparent px-1.5 py-1 text-[14px] leading-6 text-ink outline-none disabled:opacity-60"
      />
      <button
        type="submit"
        disabled={!value.trim() || busy}
        aria-label="Send question"
        className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent text-white transition-colors hover:bg-accent-hi disabled:bg-raised disabled:text-ink-3"
      >
        {busy ? <Spinner size={14} /> : <ArrowUp className="size-4" aria-hidden="true" />}
      </button>
    </form>
  );
}
