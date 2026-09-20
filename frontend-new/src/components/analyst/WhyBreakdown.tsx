import { useState } from 'react';
import clsx from 'clsx';
import { GitCompareArrows } from 'lucide-react';
import type { WhyAnalysisResult, WhyDimensionResult } from '../../types';
import { formatNumber, formatSigned, formatSignedPercent, humanize } from '../../lib/format';
import { Badge } from '../ui/Badge';
import { Delta } from '../ui/Delta';

interface WhyBreakdownProps {
  why: WhyAnalysisResult;
}

/** Dimensions arrive fully qualified (`customers.region`); a reader only needs
 *  the column. */
function dimensionLabel(dimension: string): string {
  return humanize(dimension.includes('.') ? dimension.split('.').slice(1).join('.') : dimension);
}

/** Contribution attribution: which segments moved the metric, and by how much.
 *  Each row carries its share of the total movement as a signed bar measured
 *  from a shared zero, so the largest driver is visible without reading the
 *  numbers. */
export function WhyBreakdown({ why }: WhyBreakdownProps) {
  const dimensions = why.dimensions.filter((d) => d.segments.length > 0);
  const [activeDimension, setActiveDimension] = useState(0);

  if (dimensions.length === 0) return null;

  const current = dimensions[Math.min(activeDimension, dimensions.length - 1)];

  return (
    <div className="overflow-hidden rounded-md border border-line">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 border-b border-line bg-raised/40 px-3 py-2.5">
        <div className="flex items-baseline gap-2">
          <GitCompareArrows className="size-3.5 self-center text-ink-3" aria-hidden="true" />
          <h4 className="text-[13px] font-semibold text-ink">
            What moved {humanize(why.metric).toLowerCase()}
          </h4>
        </div>
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[12px] text-ink-3">
          <span>
            {why.baseline.start} – {why.baseline.end}
            <span className="mx-1.5 text-ink-3">to</span>
            {why.target.start} – {why.target.end}
          </span>
          <Delta
            percent={why.delta_pct}
            label={`(${formatSigned(why.delta)})`}
            inverted={/return|cost|churn|expense|refund|defect/i.test(why.metric)}
          />
        </div>
      </div>

      {dimensions.length > 1 ? (
        <div
          role="tablist"
          aria-label="Breakdown dimension"
          className="flex gap-1 overflow-x-auto border-b border-line px-2 py-1.5"
        >
          {dimensions.map((dimension, index) => (
            <button
              key={dimension.dimension}
              role="tab"
              aria-selected={index === activeDimension}
              onClick={() => setActiveDimension(index)}
              className={clsx(
                'shrink-0 rounded-sm px-2 py-1 text-[12px] font-medium transition-colors',
                index === activeDimension
                  ? 'bg-raised text-ink'
                  : 'text-ink-3 hover:bg-raised/60 hover:text-ink-2',
              )}
            >
              {dimensionLabel(dimension.dimension)}
            </button>
          ))}
        </div>
      ) : null}

      <DimensionTable dimension={current} />
    </div>
  );
}

function DimensionTable({ dimension }: { dimension: WhyDimensionResult }) {
  const segments = [...dimension.segments].sort(
    (a, b) => Math.abs(b.contribution) - Math.abs(a.contribution),
  );
  const largest = Math.max(...segments.map((s) => Math.abs(s.contribution)), 1);

  return (
    <div>
      {dimension.offsetting ? (
        <p className="border-b border-line bg-warn/8 px-3 py-2 text-[12px] leading-5 text-warn">
          Segments move in both directions here, so the net change understates what happened
          inside this dimension.
        </p>
      ) : null}

      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-[12px] text-ink-3">
              <th scope="col" className="px-3 py-1.5 text-left font-medium">
                {dimensionLabel(dimension.dimension)}
              </th>
              <th scope="col" className="px-3 py-1.5 text-right font-medium">
                Baseline
              </th>
              <th scope="col" className="px-3 py-1.5 text-right font-medium">
                Current
              </th>
              <th scope="col" className="px-3 py-1.5 text-right font-medium">
                Change
              </th>
              <th scope="col" className="px-3 py-1.5 text-right font-medium">
                Share of move
              </th>
              <th scope="col" className="w-28 px-3 py-1.5 text-left font-medium">
                <span className="sr-only">Share of move, as a bar</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {segments.map((segment, index) => {
              const negative = segment.delta < 0;
              const width = (Math.abs(segment.contribution) / largest) * 50;
              return (
                <tr
                  key={segment.value}
                  className="reveal-row border-t border-line/60"
                  style={{ '--row': index } as React.CSSProperties}
                >
                  <th
                    scope="row"
                    className="max-w-[14rem] truncate px-3 py-1.5 text-left font-medium text-ink"
                    title={segment.value}
                  >
                    {segment.value}
                  </th>
                  <td className="tnum px-3 py-1.5 text-right font-mono text-ink-2">
                    {formatNumber(segment.baseline)}
                  </td>
                  <td className="tnum px-3 py-1.5 text-right font-mono text-ink-2">
                    {formatNumber(segment.target)}
                  </td>
                  <td
                    className={clsx(
                      'tnum px-3 py-1.5 text-right font-mono font-medium',
                      negative ? 'text-down' : 'text-up',
                    )}
                  >
                    {formatSigned(segment.delta)}
                  </td>
                  <td className="tnum px-3 py-1.5 text-right font-mono text-ink">
                    {formatSignedPercent(segment.contribution * 100)}
                  </td>
                  <td className="px-3 py-1.5">
                    {/* Bars grow outward from a shared centre line at zero. */}
                    <div className="relative h-2 w-24">
                      <span
                        className="absolute inset-y-0 left-1/2 w-px bg-line-strong"
                        aria-hidden="true"
                      />
                      <span
                        className={clsx(
                          'absolute inset-y-0.5 rounded-[1px]',
                          negative ? 'bg-down' : 'bg-up',
                        )}
                        style={
                          negative
                            ? { right: '50%', width: `${width}%` }
                            : { left: '50%', width: `${width}%` }
                        }
                        aria-hidden="true"
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="border-t border-line px-3 py-2 text-[12px] text-ink-3">
        Share of move is each segment&rsquo;s contribution to the total change.{' '}
        <Badge tone="up">Positive</Badge> added to the metric,{' '}
        <Badge tone="down">negative</Badge> subtracted from it.
      </p>
    </div>
  );
}
