import { Database, Gauge, Timer, Zap } from 'lucide-react';

import { useAppStore } from '../../store/useAppStore';
import { formatNumber, formatPercent } from '../../lib/format';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

/** Money here is small by construction — a question costs cents — so the usual
 *  two-decimal currency format would round most of it to $0.00. */
function formatUsd(value: number): string {
  if (value === 0) return '$0';
  if (value < 0.01) return `$${value.toFixed(4)}`;
  if (value < 1) return `$${value.toFixed(3)}`;
  return `$${value.toFixed(2)}`;
}

function Stat({
  icon: Icon,
  label,
  value,
  detail,
  tone = 'neutral',
}: {
  icon: typeof Zap;
  label: string;
  value: string;
  detail?: string;
  tone?: 'neutral' | 'up';
}) {
  return (
    <div className="rounded-md border border-line bg-raised/40 p-3">
      <div className="flex items-center gap-1.5">
        <Icon className="size-3 shrink-0 text-ink-3" aria-hidden="true" />
        <p className="truncate text-[12px] leading-4 text-ink-2">{label}</p>
      </div>
      <p
        className={
          'tnum mt-1.5 font-mono text-[22px] font-semibold leading-none tracking-tight ' +
          (tone === 'up' ? 'text-up' : 'text-ink')
        }
      >
        {value}
      </p>
      {detail ? <p className="mt-1 text-[12px] leading-4 text-ink-3">{detail}</p> : null}
    </div>
  );
}

/** A proportional bar showing how each turn's prompt was paid for: read from
 *  cache, written to it, or billed fresh. The cached share is the whole point,
 *  so it leads and carries the accent. */
function TokenBar({
  cached,
  written,
  fresh,
}: {
  cached: number;
  written: number;
  fresh: number;
}) {
  const total = cached + written + fresh;
  if (total === 0) return null;

  const pct = (part: number) => (part / total) * 100;
  const segments = [
    { key: 'cached', value: cached, className: 'bg-up', label: 'Read from cache' },
    { key: 'written', value: written, className: 'bg-accent', label: 'Written to cache' },
    { key: 'fresh', value: fresh, className: 'bg-line-strong', label: 'Billed fresh' },
  ].filter((segment) => segment.value > 0);

  return (
    <div>
      <div
        className="flex h-2 overflow-hidden rounded-full bg-raised"
        role="img"
        aria-label={`${formatNumber(cached, 0)} tokens read from cache, ${formatNumber(
          written,
          0,
        )} written, ${formatNumber(fresh, 0)} billed fresh`}
      >
        {segments.map((segment) => (
          <span
            key={segment.key}
            className={segment.className}
            style={{ width: `${pct(segment.value)}%` }}
          />
        ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {segments.map((segment) => (
          <li key={segment.key} className="flex items-center gap-1.5 text-[12px] text-ink-3">
            <span className={`size-1.5 shrink-0 rounded-full ${segment.className}`} aria-hidden="true" />
            {segment.label}
            <span className="tnum font-mono text-ink-2">{formatNumber(segment.value, 0)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CacheMetrics() {
  const stats = useAppStore((state) => state.stats);
  const settings = useAppStore((state) => state.settings);
  const resetStats = useAppStore((state) => state.resetStats);

  const cachingOn = settings?.prompt_caching_enabled ?? false;
  const provider = settings?.providers.find((p) => p.id === settings.active_provider);
  const providerCaches = provider?.supports_caching ?? false;

  if (!stats || stats.calls === 0) {
    return (
      <div className="space-y-3">
        <p className="text-[13px] leading-6 text-ink-2">
          No model calls yet. Ask a question and this fills in — the first question on a dataset
          writes the schema into the cache, and every question after it reads that back instead of
          paying for it again.
        </p>
        {!providerCaches ? (
          <p className="text-[13px] leading-6 text-warn">
            {provider?.label ?? 'The selected provider'} does not support prompt caching. Switch to
            Claude Code or the Anthropic API to see it work.
          </p>
        ) : null}
      </div>
    );
  }

  const latencyGap = stats.avg_latency_uncached_s - stats.avg_latency_cached_s;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={cachingOn && providerCaches ? 'up' : 'neutral'}>
          {cachingOn && providerCaches ? 'Prompt caching on' : 'Prompt caching off'}
        </Badge>
        {stats.providers.map((name) => (
          <Badge key={name} mono>
            {name}
          </Badge>
        ))}
        <span className="text-[12px] text-ink-3">
          over {formatNumber(stats.calls, 0)} model call{stats.calls === 1 ? '' : 's'}
        </span>
      </div>

      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          icon={Gauge}
          label="Cache hit rate"
          value={formatPercent(stats.cache_hit_rate, 0)}
          detail={`${formatNumber(stats.cache_hits, 0)} of ${formatNumber(stats.calls, 0)} calls`}
          tone={stats.cache_hit_rate > 0 ? 'up' : 'neutral'}
        />
        <Stat
          icon={Database}
          label="Prompt served from cache"
          value={formatPercent(stats.cached_share_pct, 0)}
          detail={`${formatNumber(stats.cached_tokens, 0)} tokens`}
          tone={stats.cached_share_pct > 0 ? 'up' : 'neutral'}
        />
        <Stat
          icon={Zap}
          label="Cost saved"
          value={formatPercent(stats.saved_pct, 0)}
          detail={`${formatUsd(stats.cost_usd)} spent vs ${formatUsd(
            stats.uncached_cost_usd,
          )} uncached`}
          tone={stats.saved_pct > 0 ? 'up' : 'neutral'}
        />
        <Stat
          icon={Timer}
          label="Average response"
          value={`${stats.avg_latency_s.toFixed(1)}s`}
          detail={
            stats.avg_latency_cached_s > 0 && stats.avg_latency_uncached_s > 0
              ? `${stats.avg_latency_cached_s.toFixed(1)}s cached vs ${stats.avg_latency_uncached_s.toFixed(
                  1,
                )}s cold`
              : undefined
          }
        />
      </div>

      <div className="rounded-md border border-line bg-surface p-3">
        <div className="mb-2 flex items-baseline justify-between gap-3">
          <h4 className="text-[13px] font-medium text-ink">Where the prompt tokens went</h4>
          <span className="tnum font-mono text-[12px] text-ink-3">
            {formatNumber(stats.total_prompt_tokens, 0)} in · {formatNumber(stats.output_tokens, 0)} out
          </span>
        </div>
        <TokenBar
          cached={stats.cached_tokens}
          written={stats.written_tokens}
          fresh={stats.fresh_tokens}
        />
      </div>

      <p className="max-w-[72ch] text-[12px] leading-5 text-ink-3">
        The planning instructions and the dataset schema are identical on every question, so they
        are sent as one cached prefix and the question is appended after it. Repeat reads bill at a
        tenth of the input rate
        {latencyGap > 0.2 ? ` and return about ${latencyGap.toFixed(1)}s sooner` : ''}. Figures are
        measured from the provider&rsquo;s own usage reports, not estimated.
      </p>

      {stats.recent.length > 0 ? (
        <div className="overflow-hidden rounded-md border border-line">
          <div className="border-b border-line px-3 py-1.5">
            <h4 className="text-[13px] font-medium text-ink">Recent calls</h4>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-[12px] text-ink-3">
                  <th scope="col" className="px-3 py-1.5 text-left font-medium">Stage</th>
                  <th scope="col" className="px-3 py-1.5 text-right font-medium">Cached</th>
                  <th scope="col" className="px-3 py-1.5 text-right font-medium">Written</th>
                  <th scope="col" className="px-3 py-1.5 text-right font-medium">Fresh</th>
                  <th scope="col" className="px-3 py-1.5 text-right font-medium">Time</th>
                  <th scope="col" className="px-3 py-1.5 text-right font-medium">Cost</th>
                </tr>
              </thead>
              <tbody>
                {[...stats.recent].reverse().map((call, index) => (
                  <tr key={`${call.stage}-${index}`} className="border-t border-line/60">
                    <th scope="row" className="px-3 py-1.5 text-left font-medium text-ink">
                      <span className="flex items-center gap-1.5">
                        <span
                          className={`size-1.5 shrink-0 rounded-full ${
                            call.cache_hit ? 'bg-up' : 'bg-line-strong'
                          }`}
                          aria-hidden="true"
                        />
                        {call.stage}
                      </span>
                    </th>
                    <td className="tnum px-3 py-1.5 text-right font-mono text-up">
                      {call.cache_read_tokens ? formatNumber(call.cache_read_tokens, 0) : '—'}
                    </td>
                    <td className="tnum px-3 py-1.5 text-right font-mono text-ink-2">
                      {call.cache_write_tokens ? formatNumber(call.cache_write_tokens, 0) : '—'}
                    </td>
                    <td className="tnum px-3 py-1.5 text-right font-mono text-ink-2">
                      {formatNumber(call.input_tokens, 0)}
                    </td>
                    <td className="tnum px-3 py-1.5 text-right font-mono text-ink-2">
                      {call.latency_s.toFixed(1)}s
                    </td>
                    <td className="tnum px-3 py-1.5 text-right font-mono text-ink-2">
                      {formatUsd(call.cost_usd)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button size="sm" variant="ghost" onClick={() => void resetStats()}>
          Reset counters
        </Button>
      </div>
    </div>
  );
}
