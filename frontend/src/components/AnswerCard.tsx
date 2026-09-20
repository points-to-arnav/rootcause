import React, { useState } from 'react';
import { AskResponse } from '../types';
import { ChartRenderer } from './ChartRenderer';
import { PlanViewer } from './PlanViewer';
import { SuggestionChips } from './SuggestionChips';
import {
  BarChart2,
  Table as TableIcon,
  ShieldCheck,
  AlertTriangle,
  Info
} from 'lucide-react';

interface AnswerCardProps {
  response: AskResponse;
  onSelectSuggestion: (prompt: string) => void;
}

export const AnswerCard: React.FC<AnswerCardProps> = ({
  response,
  onSelectSuggestion
}) => {
  const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart');
  const hasRows = response.result?.rows && response.result.rows.length > 0;
  const isKpiOnly = response.chart?.type === 'kpi';

  return (
    <div className="w-full bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
      {/* 1. Header with Verification Badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
          <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">
            {response.plan?.intent || 'Analysis'}
          </span>
          {response.resolved_time?.label && (
            <span className="text-xs text-slate-400">
              • {response.resolved_time.label}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>DuckDB Verified</span>
        </div>
      </div>

      {/* 2. Business Narrative */}
      {response.narrative && (
        <div className="text-sm text-slate-200 leading-relaxed font-normal bg-slate-950/40 p-4 rounded-xl border border-slate-800/60">
          {response.narrative}
        </div>
      )}

      {/* 3. Data Quality Warnings */}
      {response.dq_warnings && response.dq_warnings.length > 0 && (
        <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-400">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Data Quality Notice</span>
          </div>
          <div className="space-y-1 text-[11px] text-amber-200/80">
            {response.dq_warnings.map((w, idx) => (
              <div key={idx} className="flex items-start gap-1">
                <span>•</span>
                <span>
                  <strong>{w.table}{w.column ? `.${w.column}` : ''}:</strong> {w.impact || w.description}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Visualization & Table View */}
      {hasRows && (
        <div className="pt-2">
          {!isKpiOnly && (
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium text-slate-400">
                {response.result?.row_count} records returned
              </span>

              <div className="flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800">
                <button
                  type="button"
                  onClick={() => setViewMode('chart')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition ${
                    viewMode === 'chart'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <BarChart2 className="w-3.5 h-3.5" />
                  <span>Chart</span>
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('table')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition ${
                    viewMode === 'table'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <TableIcon className="w-3.5 h-3.5" />
                  <span>Table</span>
                </button>
              </div>
            </div>
          )}

          {viewMode === 'chart' ? (
            <ChartRenderer spec={response.chart} result={response.result} />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-800 max-h-72">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-slate-950 text-slate-400 sticky top-0 border-b border-slate-800">
                  <tr>
                    {response.result?.columns.map((c, i) => (
                      <th key={i} className="px-3 py-2 font-semibold capitalize">
                        {c.replace(/_/g, ' ')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 bg-slate-900/60">
                  {response.result?.rows.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-slate-800/40">
                      {row.map((val, cIdx) => (
                        <td key={cIdx} className="px-3 py-2 text-slate-300 font-mono">
                          {typeof val === 'number'
                            ? val.toLocaleString(undefined, { maximumFractionDigits: 2 })
                            : String(val ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 5. Glass-Box Plan & SQL Inspector */}
      <PlanViewer response={response} />

      {/* 6. Contextual Suggestions */}
      <SuggestionChips
        suggestions={response.suggestions}
        onSelect={onSelectSuggestion}
      />
    </div>
  );
};
