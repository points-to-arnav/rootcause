import type { KPICardData } from '../../types';
import { formatValue } from '../../lib/format';
import { Delta } from '../ui/Delta';
import { Sparkline } from '../ui/Sparkline';

/** The period a KPI covers is the same for every tile on the overview, so it is
 *  passed down once rather than repeated in each card's payload. */
export function KpiCard({ kpi, periodLabel }: { kpi: KPICardData; periodLabel?: string }) {
  // Metrics like return rate, costs, etc. are bad when increasing.
  const isInverted =
    /return|cost|churn|expense|refund|defect/i.test(kpi.metric) ||
    /return|cost|churn|expense|refund|defect/i.test(kpi.label);

  // The server sends the change, not a direction; the sign is the direction.
  const trend =
    kpi.delta_pct === null || kpi.delta_pct === undefined || kpi.delta_pct === 0
      ? 'flat'
      : kpi.delta_pct > 0
        ? 'up'
        : 'down';

  const sparklineTone =
    trend === 'flat'
      ? 'flat'
      : isInverted
        ? trend === 'up'
          ? 'down'
          : 'up'
        : trend;

  return (
    <div className="rounded-lg border border-line bg-surface p-3.5">
      <p className="truncate text-[13px] text-ink-2" title={kpi.label}>
        {kpi.label}
      </p>

      <div className="mt-1.5 flex items-end justify-between gap-3">
        <p className="tnum font-mono text-[24px] font-semibold leading-none tracking-tight text-ink">
          {formatValue(kpi.value, kpi.value_format)}
        </p>
        {kpi.sparkline && kpi.sparkline.length > 1 ? (
          <Sparkline values={kpi.sparkline} tone={sparklineTone} />
        ) : null}
      </div>

      <div className="mt-2 flex items-center justify-between gap-2">
        <Delta percent={kpi.delta_pct ?? undefined} inverted={isInverted} />
        {periodLabel ? (
          <span className="truncate text-[12px] text-ink-3">{periodLabel}</span>
        ) : null}
      </div>
    </div>
  );
}
