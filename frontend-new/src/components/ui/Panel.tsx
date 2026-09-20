import clsx from 'clsx';
import type { ReactNode } from 'react';

interface PanelProps {
  children: ReactNode;
  className?: string;
  /** Drops the default padding when the panel holds a table or a chart that
   *  should reach its own edges. */
  flush?: boolean;
}

export function Panel({ children, className, flush = false }: PanelProps) {
  return (
    <section
      className={clsx('rounded-lg border border-line bg-surface', !flush && 'p-4', className)}
    >
      {children}
    </section>
  );
}

interface PanelHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function PanelHeader({ title, description, actions, className }: PanelHeaderProps) {
  return (
    <header
      className={clsx(
        'flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3',
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="text-[14px] font-semibold leading-5 text-ink">{title}</h2>
        {description ? (
          <p className="mt-0.5 text-[13px] leading-5 text-ink-2">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </header>
  );
}
