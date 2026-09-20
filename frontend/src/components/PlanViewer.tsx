import React, { useState } from 'react';
import { AskResponse } from '../types';
import { Code, Database, Clock, AlertTriangle, Copy, Check, ChevronDown, ChevronUp } from 'lucide-react';

interface PlanViewerProps {
  response: AskResponse;
}

export const PlanViewer: React.FC<PlanViewerProps> = ({ response }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [copiedSql, setCopiedSql] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);

  const handleCopySql = () => {
    if (response.sql) {
      navigator.clipboard.writeText(response.sql);
      setCopiedSql(true);
      setTimeout(() => setCopiedSql(false), 1500);
    }
  };

  const handleCopyJson = () => {
    if (response.plan) {
      navigator.clipboard.writeText(JSON.stringify(response.plan, null, 2));
      setCopiedJson(true);
      setTimeout(() => setCopiedJson(false), 1500);
    }
  };

  return (
    <div className="mt-3 border border-slate-800/80 rounded-xl bg-slate-950/40 overflow-hidden text-xs">
      {/* Accordion Header */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-2.5 flex items-center justify-between text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 transition"
      >
        <div className="flex items-center gap-2">
          <Code className="w-3.5 h-3.5 text-indigo-400" />
          <span className="font-semibold text-slate-300">Glass-Box Inspection</span>
          <span className="text-[11px] text-slate-500">
            ({response.plan?.intent || 'query'} • {response.result?.row_count ?? 0} rows)
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-slate-500">
          <span>{isOpen ? 'Hide Plan & SQL' : 'View Plan & SQL'}</span>
          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </div>
      </button>

      {/* Accordion Content */}
      {isOpen && (
        <div className="p-4 border-t border-slate-800/80 space-y-4 bg-slate-950/80">
          {/* Resolved Time & Assumptions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {response.resolved_time && (
              <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg">
                <div className="flex items-center gap-1.5 text-slate-300 font-semibold mb-1">
                  <Clock className="w-3 h-3 text-indigo-400" />
                  <span>Time Window</span>
                </div>
                <div className="text-[11px] text-slate-400">
                  <span>Current: </span>
                  <span className="text-slate-200 font-medium">{response.resolved_time.label}</span>
                  <span className="text-slate-500 ml-1">
                    ({response.resolved_time.start} to {response.resolved_time.end})
                  </span>
                </div>
                {response.resolved_time.baseline && (
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    <span>Baseline: </span>
                    <span className="text-slate-200 font-medium">{response.resolved_time.baseline.label}</span>
                    <span className="text-slate-500 ml-1">
                      ({response.resolved_time.baseline.start} to {response.resolved_time.baseline.end})
                    </span>
                  </div>
                )}
              </div>
            )}

            {response.assumptions && response.assumptions.length > 0 && (
              <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg">
                <div className="flex items-center gap-1.5 text-slate-300 font-semibold mb-1">
                  <Database className="w-3 h-3 text-indigo-400" />
                  <span>Planner Assumptions</span>
                </div>
                <ul className="list-disc list-inside space-y-0.5 text-[11px] text-slate-400">
                  {response.assumptions.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* SQL Query */}
          {response.sql && (
            <div>
              <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1.5">
                <span className="font-semibold text-slate-300 flex items-center gap-1.5">
                  <Database className="w-3 h-3 text-indigo-400" /> DuckDB SQL Query
                </span>
                <button
                  type="button"
                  onClick={handleCopySql}
                  className="flex items-center gap-1 px-2 py-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
                >
                  {copiedSql ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedSql ? 'Copied!' : 'Copy SQL'}</span>
                </button>
              </div>
              <pre className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-slate-300 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap leading-relaxed">
                {response.sql}
              </pre>
            </div>
          )}

          {/* JSON Plan */}
          {response.plan && (
            <div>
              <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1.5">
                <span className="font-semibold text-slate-300 flex items-center gap-1.5">
                  <Code className="w-3 h-3 text-indigo-400" /> Structured Execution Plan (JSON)
                </span>
                <button
                  type="button"
                  onClick={handleCopyJson}
                  className="flex items-center gap-1 px-2 py-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
                >
                  {copiedJson ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedJson ? 'Copied!' : 'Copy Plan'}</span>
                </button>
              </div>
              <pre className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-indigo-300/90 font-mono text-[11px] overflow-x-auto max-h-48 overflow-y-auto">
                {JSON.stringify(response.plan, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
