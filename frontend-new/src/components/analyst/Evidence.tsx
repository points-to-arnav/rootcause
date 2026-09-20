import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import clsx from 'clsx';
import type { AskResponse } from '../../types';
import { CopyButton } from '../ui/CopyButton';

interface EvidenceProps {
  response: AskResponse;
}

/** Everything behind the answer: the time range it resolved, the assumptions
 *  it made, the SQL it ran, and the plan it compiled. Collapsed by default —
 *  available to anyone who wants to check the work, in the way of nobody who
 *  does not. */
/** One line of provenance for the model call behind this answer: what it cost,
 *  how much of the prompt the cache covered, and whether the answer was replayed
 *  from the server's response cache without a model call at all. */
function CallCost({ response }: { response: AskResponse }) {
  const stats = response.llm_stats;

  if (response.from_cache) {
    return (
      <span className="tnum font-mono text-[12px] text-up">replayed · no model call</span>
    );
  }
  if (!stats || stats.calls === 0) return null;

  const cached = stats.cache_read_tokens;
  const cost = stats.cost_usd;
  const costText = cost < 0.01 ? `$${cost.toFixed(4)}` : `$${cost.toFixed(3)}`;

  return (
    <span className="tnum font-mono text-[12px] text-ink-3">
      {cached > 0 ? (
        <span className="text-up">{cached.toLocaleString('en-US')} cached</span>
      ) : (
        <span>cold</span>
      )}
      {' · '}
      {stats.latency_s.toFixed(1)}s · {costText}
    </span>
  );
}

export function Evidence({ response }: EvidenceProps) {
  const [open, setOpen] = useState(false);
  const hasAssumptions = response.assumptions.length > 0;

  if (!response.sql && !response.plan && !response.resolved_time && !hasAssumptions) {
    return null;
  }

  return (
    <div className="rounded-md border border-line">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] text-ink-2 transition-colors hover:text-ink"
      >
        <ChevronRight
          className={clsx('size-3.5 shrink-0 transition-transform', open && 'rotate-90')}
          aria-hidden="true"
        />
        <span className="font-medium">How this was calculated</span>
        <span className="ml-auto flex items-center gap-2.5">
          <CallCost response={response} />
          {response.result ? (
            <span className="tnum font-mono text-[12px] text-ink-3">
              {response.result.row_count.toLocaleString('en-US')} rows
              {response.result.truncated ? ' (truncated)' : ''}
            </span>
          ) : null}
        </span>
      </button>

      {open ? (
        <div className="space-y-3 border-t border-line p-3">
          {response.resolved_time ? (
            <div>
              <h4 className="mb-1 text-[12px] font-medium text-ink-2">Time range</h4>
              <dl className="space-y-0.5 text-[13px]">
                <div className="flex gap-2">
                  <dt className="w-20 shrink-0 text-ink-3">Current</dt>
                  <dd className="text-ink">
                    {response.resolved_time.label}{' '}
                    <span className="font-mono text-[12px] text-ink-3">
                      {response.resolved_time.start} to {response.resolved_time.end}
                    </span>
                  </dd>
                </div>
                {response.resolved_time.baseline ? (
                  <div className="flex gap-2">
                    <dt className="w-20 shrink-0 text-ink-3">Compared to</dt>
                    <dd className="text-ink">
                      {response.resolved_time.baseline.label}{' '}
                      <span className="font-mono text-[12px] text-ink-3">
                        {response.resolved_time.baseline.start} to{' '}
                        {response.resolved_time.baseline.end}
                      </span>
                    </dd>
                  </div>
                ) : null}
              </dl>
            </div>
          ) : null}

          {hasAssumptions ? (
            <div>
              <h4 className="mb-1 text-[12px] font-medium text-ink-2">Assumptions</h4>
              <ul className="space-y-0.5 text-[13px] text-ink-2">
                {response.assumptions.map((assumption) => (
                  <li key={assumption} className="flex gap-2">
                    <span className="text-ink-3" aria-hidden="true">
                      &middot;
                    </span>
                    <span>{assumption}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {response.sql ? (
            <div>
              <div className="mb-1 flex items-center justify-between">
                <h4 className="text-[12px] font-medium text-ink-2">SQL</h4>
                <CopyButton value={response.sql} label="Copy SQL" />
              </div>
              <pre className="overflow-x-auto rounded-sm border border-line bg-ground p-2.5 font-mono text-[12px] leading-relaxed text-ink">
                {response.sql}
              </pre>
            </div>
          ) : null}

          {response.plan ? (
            <div>
              <div className="mb-1 flex items-center justify-between">
                <h4 className="text-[12px] font-medium text-ink-2">Query plan</h4>
                <CopyButton value={JSON.stringify(response.plan, null, 2)} label="Copy plan" />
              </div>
              <pre className="max-h-48 overflow-auto rounded-sm border border-line bg-ground p-2.5 font-mono text-[12px] leading-relaxed text-ink-2">
                {JSON.stringify(response.plan, null, 2)}
              </pre>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
