import { useState } from 'react';
import clsx from 'clsx';
import { AlertTriangle, BarChart3, HelpCircle, Table2 } from 'lucide-react';
import type { AskResponse } from '../../types';
import { ChartView } from '../charts/ChartView';
import { DataTable } from '../ui/DataTable';
import { Delta } from '../ui/Delta';
import { Evidence } from './Evidence';
import { WhyBreakdown } from './WhyBreakdown';
import { Suggestions } from './Suggestions';
import { formatValue, pluralize } from '../../lib/format';

interface AnswerPanelProps {
  response: AskResponse;
  onAsk: (question: string) => void;
}

export function AnswerPanel({ response, onAsk }: AnswerPanelProps) {
  // A question that asked for a table, or a result no chart can carry, opens as one.
  const [view, setView] = useState<'chart' | 'table'>(
    response.chart?.type === 'table' ? 'table' : 'chart',
  );

  const rows = response.result?.rows ?? [];
  const hasRows = rows.length > 0;
  const kpi = response.chart?.type === 'kpi' ? response.chart.kpi : undefined;
  const showViewToggle = hasRows && !kpi;

  if (response.status === 'needs_clarification' || response.status === 'unsupported') {
    return (
      <div className="reveal rounded-lg border border-line bg-surface p-4">
        <div className="flex gap-2.5">
          <HelpCircle className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-[14px] leading-6 text-ink">
              {response.message ?? 'That question needs a little more detail.'}
            </p>
            <Suggestions suggestions={response.suggestions} onSelect={onAsk} />
          </div>
        </div>
      </div>
    );
  }

  const planMetric = typeof response.plan?.metric === 'string' ? response.plan.metric : '';
  const whyMetric = response.why?.metric ?? '';
  const isNegativeMetric =
    /return|cost|churn|expense|refund|defect/i.test(planMetric) ||
    /return|cost|churn|expense|refund|defect/i.test(whyMetric);

  const hasContent = Boolean(
    kpi ||
      response.narrative ||
      response.why ||
      response.dq_warnings.length > 0 ||
      hasRows ||
      response.sql ||
      response.plan ||
      response.resolved_time ||
      response.assumptions.length > 0,
  );

  if (!hasContent) {
    if (response.suggestions && response.suggestions.length > 0) {
      return <Suggestions suggestions={response.suggestions} onSelect={onAsk} />;
    }
    return null;
  }

  return (
    <div className="reveal space-y-3 rounded-lg border border-line bg-surface p-4">
      {kpi ? (
        <div>
          <p className="tnum font-mono text-[32px] font-semibold leading-none tracking-tight text-ink">
            {formatValue(kpi.value ?? 0, response.chart?.value_format)}
          </p>
          {kpi.delta_pct !== null && kpi.delta_pct !== undefined ? (
            <Delta
              className="mt-2"
              percent={kpi.delta_pct}
              label="vs the previous period"
              inverted={isNegativeMetric}
            />
          ) : null}
        </div>
      ) : null}

      {response.narrative ? (
        <p className="max-w-[68ch] text-[14px] leading-6 text-ink">{response.narrative}</p>
      ) : null}

      {response.why ? <WhyBreakdown why={response.why} /> : null}

      {response.dq_warnings.length > 0 ? (
        <div className="rounded-md border border-warn/30 bg-warn/8 p-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-3.5 shrink-0 text-warn" aria-hidden="true" />
            <h4 className="text-[13px] font-medium text-warn">
              Data issues that affect this answer
            </h4>
          </div>
          <ul className="mt-1.5 space-y-1 pl-5.5 text-[13px] leading-5 text-ink-2">
            {response.dq_warnings.map((warning, index) => (
              <li key={`${warning.table}-${warning.column ?? index}`}>
                <span className="font-mono text-[12px] text-ink">
                  {warning.table}
                  {warning.column ? `.${warning.column}` : ''}
                </span>{' '}
                — {warning.impact || warning.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {hasRows && !kpi ? (
        <div className="overflow-hidden rounded-md border border-line">
          <div className="flex items-center justify-between border-b border-line px-3 py-1.5">
            <p className="text-[12px] text-ink-3">
              {pluralize(response.result?.row_count ?? rows.length, 'row')}
            </p>
            {showViewToggle ? (
              <div className="flex gap-0.5 rounded-sm bg-raised p-0.5" role="group">
                <ViewToggle
                  active={view === 'chart'}
                  onClick={() => setView('chart')}
                  icon={<BarChart3 className="size-3.5" aria-hidden="true" />}
                  label="Chart"
                />
                <ViewToggle
                  active={view === 'table'}
                  onClick={() => setView('table')}
                  icon={<Table2 className="size-3.5" aria-hidden="true" />}
                  label="Table"
                />
              </div>
            ) : null}
          </div>

          {view === 'chart' ? (
            <div className="p-3">
              <ChartView spec={response.chart ?? undefined} result={response.result ?? undefined} height={260} />
            </div>
          ) : (
            <DataTable
              columns={response.result?.columns ?? []}
              rows={rows}
              maxHeight={300}
            />
          )}
        </div>
      ) : null}

      <Evidence response={response} />
      <Suggestions suggestions={response.suggestions} onSelect={onAsk} />
    </div>
  );
}

function ViewToggle({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-[3px] px-2 py-1 text-[12px] font-medium transition-colors',
        active ? 'bg-overlay text-ink' : 'text-ink-3 hover:text-ink-2',
      )}
    >
      {icon}
      {label}
    </button>
  );
}
