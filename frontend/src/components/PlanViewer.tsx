import React, { useState } from 'react';
import { AskResponse } from '../types';
import { Code, Database, Clock, Copy, Check, ChevronDown, ChevronUp } from 'lucide-react';

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
    <div className="mt-3 border border-[#1E1E1E] rounded-xl bg-[#080808] overflow-hidden text-xs font-mono">
      {/* Accordion Header */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-2.5 flex items-center justify-between text-[#888888] hover:text-white hover:bg-[#0F0F0F] transition cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <Code className="w-3.5 h-3.5 text-cyan-400" />
          <span className="font-semibold text-[#CCCCCC]">Glass-Box Plan & SQL</span>
          <span className="text-[10px] text-[#71717A]">
            ({response.plan?.intent || 'telemetry'} • {response.result?.row_count ?? 0} rows)
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-[#71717A]">
          <span>{isOpen ? 'Collapse' : 'Inspect'}</span>
          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </div>
      </button>

      {/* Accordion Content */}
      {isOpen && (
        <div className="p-4 border-t border-[#1E1E1E] space-y-4 bg-[#050505]">
          {/* Resolved Time & Assumptions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {response.resolved_time && (
              <div className="p-3 bg-[#0A0A0A] border border-[#1E1E1E] rounded-lg">
                <div className="flex items-center gap-1.5 text-white font-semibold mb-1">
                  <Clock className="w-3 h-3 text-cyan-400" />
                  <span>Time Window</span>
                </div>
                <div className="text-[11px] text-[#888888]">
                  <span>Current: </span>
                  <span className="text-white font-medium">{response.resolved_time.label}</span>
                  <span className="text-[#71717A] ml-1">
                    ({response.resolved_time.start} to {response.resolved_time.end})
                  </span>
                </div>
                {response.resolved_time.baseline && (
                  <div className="text-[11px] text-[#888888] mt-0.5">
                    <span>Baseline: </span>
                    <span className="text-white font-medium">{response.resolved_time.baseline.label}</span>
                    <span className="text-[#71717A] ml-1">
                      ({response.resolved_time.baseline.start} to {response.resolved_time.baseline.end})
                    </span>
                  </div>
                )}
              </div>
            )}

            {response.assumptions && response.assumptions.length > 0 && (
              <div className="p-3 bg-[#0A0A0A] border border-[#1E1E1E] rounded-lg">
                <div className="flex items-center gap-1.5 text-white font-semibold mb-1">
                  <Database className="w-3 h-3 text-cyan-400" />
                  <span>Planner Assumptions</span>
                </div>
                <ul className="list-disc list-inside space-y-0.5 text-[11px] text-[#888888]">
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
              <div className="flex items-center justify-between text-[11px] text-[#888888] mb-1.5">
                <span className="font-semibold text-white flex items-center gap-1.5">
                  <Database className="w-3 h-3 text-cyan-400" /> DuckDB SQL Query
                </span>
                <button
                  type="button"
                  onClick={handleCopySql}
                  className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#111111] hover:bg-[#1A1A1A] border border-[#222222] text-[#CCCCCC] transition cursor-pointer"
                >
                  {copiedSql ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedSql ? 'Copied' : 'Copy SQL'}</span>
                </button>
              </div>
              <pre className="p-3 bg-[#080808] border border-[#1E1E1E] rounded-lg text-cyan-300/90 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap leading-relaxed">
                {response.sql}
              </pre>
            </div>
          )}

          {/* JSON Plan */}
          {response.plan && (
            <div>
              <div className="flex items-center justify-between text-[11px] text-[#888888] mb-1.5">
                <span className="font-semibold text-white flex items-center gap-1.5">
                  <Code className="w-3 h-3 text-cyan-400" /> Structured Execution AST (JSON)
                </span>
                <button
                  type="button"
                  onClick={handleCopyJson}
                  className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#111111] hover:bg-[#1A1A1A] border border-[#222222] text-[#CCCCCC] transition cursor-pointer"
                >
                  {copiedJson ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedJson ? 'Copied' : 'Copy AST'}</span>
                </button>
              </div>
              <pre className="p-3 bg-[#080808] border border-[#1E1E1E] rounded-lg text-[#A1A1AA] font-mono text-[11px] overflow-x-auto max-h-48 overflow-y-auto">
                {JSON.stringify(response.plan, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
