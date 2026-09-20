import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  /** Says what to do next, not only that nothing is here. */
  body: string;
  actions?: ReactNode;
}

export function EmptyState({ icon: Icon, title, body, actions }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <span className="flex size-9 items-center justify-center rounded-md border border-line bg-raised text-ink-2">
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <h3 className="mt-3 text-[15px] font-semibold text-ink">{title}</h3>
      <p className="mt-1 max-w-sm text-[13px] leading-5 text-ink-2">{body}</p>
      {actions ? <div className="mt-4 flex flex-wrap justify-center gap-2">{actions}</div> : null}
    </div>
  );
}
