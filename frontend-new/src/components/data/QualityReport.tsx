import clsx from 'clsx';
import { ShieldCheck } from 'lucide-react';
import type { QualityIssue, Severity } from '../../types';
import { humanize } from '../../lib/format';

interface QualityReportProps {
  issues: QualityIssue[];
}

const severityDot: Record<Severity, string> = {
  high: 'bg-down',
  medium: 'bg-warn',
  low: 'bg-ink-3',
};

const severityLabel: Record<Severity, string> = {
  high: 'Serious',
  medium: 'Worth a look',
  low: 'Minor',
};

/** Titles for the checks the profiler runs. An unknown type still reads sensibly
 *  through `humanize`, so a new check never renders blank. */
const typeLabel: Record<string, string> = {
  duplicate_rows: 'Duplicate rows',
  duplicate_id: 'Duplicate IDs',
  missing_values: 'Missing values',
  negative_values: 'Negative values',
  outliers: 'Outliers',
  constant_column: 'Constant column',
};

function weight(severity: Severity): number {
  return severity === 'high' ? 3 : severity === 'medium' ? 2 : 1;
}

/** Everything that could make an answer misleading, worst first. Each issue says
 *  what was found and what it does to the numbers — the second half is the part
 *  that matters to someone reading a chart. */
export function QualityReport({ issues }: QualityReportProps) {
  if (issues.length === 0) {
    return (
      <div className="flex items-center gap-2.5 px-4 py-6 text-[13px] text-ink-2">
        <ShieldCheck className="size-4 shrink-0 text-up" aria-hidden="true" />
        No data quality problems were found.
      </div>
    );
  }

  const ordered = [...issues].sort((a, b) => weight(b.severity) - weight(a.severity));

  return (
    <ul className="divide-y divide-line">
      {ordered.map((issue) => (
        <li key={issue.id} className="px-4 py-3">
          <div className="flex items-start gap-2.5">
            <span
              className={clsx('mt-1.5 size-1.5 shrink-0 rounded-full', severityDot[issue.severity])}
              aria-hidden="true"
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <h3 className="text-[13px] font-medium text-ink">
                  {typeLabel[issue.type] ?? humanize(issue.type)}
                </h3>
                <span className="text-[12px] text-ink-3">{severityLabel[issue.severity]}</span>
                <span className="break-all font-mono text-[12px] text-ink-3">
                  {issue.column ? `${issue.table}.${issue.column}` : issue.table}
                </span>
              </div>
              <p className="mt-0.5 text-[13px] leading-5 text-ink">{issue.message}</p>
              <p className="mt-0.5 text-[13px] leading-5 text-ink-2">{issue.impact}</p>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
