import React, { useState } from 'react';
import { AskResponse } from '../types';
import { ChartRenderer } from './ChartRenderer';
import { PlanViewer } from './PlanViewer';
import { SuggestionChips } from './SuggestionChips';
import {
  BarChart2,
  Table as TableIcon,
  ShieldCheck,
  AlertTriangle
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
    <div className="w-full bento-card p-5 space-y-4">
      {/* 1. Header with Verification Badge */}
      <div className="flex items-center justify-between pb-2 border-b border-[#1A1A1A]">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-white">
            {response.plan?.intent || 'FORENSIC ANALYSIS'}
          </span>
          {response.resolved_time?.label && (
            <span className="text-xs text-[#888888] font-mono">
              • {response.resolved_time.label}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 text-[10px] font-mono font-semibold text-emerald-400 bg-emerald-950/30 border border-emerald-500/30 px-2 py-0.5 rounded">
          <ShieldCheck className="w-3 h-3" />
          <span>DUCKDB VERIFIED</span>
        </div>
      </div>

      {/* 2. Business Narrative */}
      {response.narrative && (
        <div className="text-sm text-[#CCCCCC] leading-relaxed font-mono bg-[#050505] p-3.5 rounded-xl border border-[#1A1A1A]">
          {response.narrative}
        </div>
      )}

      {/* 3. Data Quality Warnings */}
      {response.dq_warnings && response.dq_warnings.length > 0 && (
        <div className="p-3 bg-[#1C080A] border border-[#4C0519] rounded-xl space-y-1.5 font-mono">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[#FDA4AF]">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Integrity Notice</span>
          </div>
          <div className="space-y-1 text-[11px] text-[#FDA4AF]/80">
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
            <div className="flex items-center justify-between mb-3 font-mono">
              <span className="text-xs text-[#71717A]">
                {response.result?.row_count} records returned
              </span>

              <div className="flex items-center bg-[#080808] p-0.5 rounded-md border border-[#1E1E1E]">
                <button
                  type="button"
                  onClick={() => setViewMode('chart')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition ${
                    viewMode === 'chart'
                      ? 'bg-[#222222] text-white'
                      : 'text-[#71717A] hover:text-white'
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
                      ? 'bg-[#222222] text-white'
                      : 'text-[#71717A] hover:text-white'
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
            <div className="overflow-x-auto rounded-xl border border-[#1E1E1E] max-h-72">
              <table className="w-full text-left text-xs border-collapse font-mono">
                <thead className="bg-[#050505] text-[#888888] sticky top-0 border-b border-[#1E1E1E]">
                  <tr>
                    {response.result?.columns.map((c, i) => (
                      <th key={i} className="px-3 py-2 font-medium capitalize">
                        {c.replace(/_/g, ' ')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#141414] bg-[#0A0A0A]">
                  {response.result?.rows.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-[#121212]">
                      {row.map((val, cIdx) => (
                        <td key={cIdx} className="px-3 py-2 text-[#CCCCCC]">
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
