import clsx from 'clsx';
import { ShieldCheck } from 'lucide-react';
import type { AlertItem, Severity } from '../../types';
import { Button } from '../ui/Button';

interface AlertListProps {
  alerts: AlertItem[];
  onInvestigate: (question: string) => void;
}

const severityDot: Record<Severity, string> = {
  high: 'bg-down',
  medium: 'bg-warn',
  low: 'bg-ink-3',
};

const severityLabel: Record<Severity, string> = {
  high: 'Needs attention',
  medium: 'Worth a look',
  low: 'Minor',
};

/** Alerts ship the query plan that explains them rather than a written prompt,
 *  so the follow-up question is composed from that plan. Alerts with no plan —
 *  data-quality notices — are not investigable and get no button. */
function investigationFor(alert: AlertItem): string | null {
  const plan = alert.plan as { intent?: string; metric?: string } | undefined;
  if (!plan?.intent) return null;

  if (plan.intent === 'why') {
    const metric = (plan.metric ?? 'revenue').replace(/_/g, ' ');
    return `Why did ${metric} fall last month?`;
  }
  if (alert.type === 'low_stock') {
    return 'Show inventory stock levels';
  }
  return null;
}

export function AlertList({ alerts, onInvestigate }: AlertListProps) {
  if (alerts.length === 0) {
    return (
      <div className="flex items-center gap-2.5 px-4 py-6 text-[13px] text-ink-2">
        <ShieldCheck className="size-4 shrink-0 text-up" aria-hidden="true" />
        Nothing stands out in this dataset right now.
      </div>
    );
  }

  const ordered = [...alerts].sort((a, b) => weight(b.severity) - weight(a.severity));

  return (
    <ul className="divide-y divide-line">
      {ordered.map((alert) => (
        <li key={alert.id} className="px-4 py-3">
          <div className="flex items-start gap-2.5">
            <span
              className={clsx('mt-1.5 size-1.5 shrink-0 rounded-full', severityDot[alert.severity])}
              aria-hidden="true"
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <h3 className="text-[13px] font-medium text-ink">{alert.title}</h3>
                <span className="text-[12px] text-ink-3">{severityLabel[alert.severity]}</span>
              </div>
              <p className="mt-0.5 text-[13px] leading-5 text-ink-2">{alert.detail}</p>
              {(() => {
                const question = investigationFor(alert);
                return question ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="-ml-2.5 mt-1.5"
                    onClick={() => onInvestigate(question)}
                  >
                    Investigate
                  </Button>
                ) : null;
              })()}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function weight(severity: Severity): number {
  return severity === 'high' ? 3 : severity === 'medium' ? 2 : 1;
}
