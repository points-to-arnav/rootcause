import { Gauge } from 'lucide-react';

import { useAppStore } from '../../store/useAppStore';
import { formatPercent } from '../../lib/format';

/** The always-visible version of the cache panel: one figure, live, clickable.
 *  Stays mounted with a placeholder rather than disappearing before the first
 *  question, so the layout does not jump the moment a demo starts. */
export function CacheBadge({ className }: { className?: string }) {
  const stats = useAppStore((state) => state.stats);
  const setMetricsOpen = useAppStore((state) => state.setMetricsOpen);

  const hasData = Boolean(stats && stats.calls > 0);
  const saved = stats?.saved_pct ?? 0;

  return (
    <button
      onClick={() => setMetricsOpen(true)}
      title="Prompt cache and token usage"
      className={
        'flex items-center gap-2 rounded-md border border-line bg-raised/50 px-2 py-1 ' +
        'text-left transition-colors hover:border-line-strong hover:bg-raised ' +
        (className ?? '')
      }
    >
      <Gauge
        className={`size-3.5 shrink-0 ${hasData && saved > 0 ? 'text-up' : 'text-ink-3'}`}
        aria-hidden="true"
      />
      <span className="min-w-0">
        <span className="block text-[11px] leading-3 text-ink-3">Prompt cache</span>
        <span className="tnum block font-mono text-[12px] leading-4 text-ink">
          {hasData ? `${formatPercent(saved, 0)} saved` : 'idle'}
        </span>
      </span>
    </button>
  );
}
