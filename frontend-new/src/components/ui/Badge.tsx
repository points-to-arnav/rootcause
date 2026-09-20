import clsx from 'clsx';
import type { ReactNode } from 'react';

type Tone = 'neutral' | 'accent' | 'up' | 'down' | 'warn';

const tones: Record<Tone, string> = {
  neutral: 'border-line bg-raised text-ink-2',
  accent: 'border-accent/35 bg-accent/12 text-accent-hi',
  up: 'border-up/30 bg-up/12 text-up',
  down: 'border-down/30 bg-down/12 text-down',
  warn: 'border-warn/30 bg-warn/12 text-warn',
};

interface BadgeProps {
  children: ReactNode;
  tone?: Tone;
  mono?: boolean;
  className?: string;
}

export function Badge({ children, tone = 'neutral', mono = false, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-sm border px-1.5 py-0.5',
        'text-[11px] font-medium leading-4',
        mono && 'tnum font-mono',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
