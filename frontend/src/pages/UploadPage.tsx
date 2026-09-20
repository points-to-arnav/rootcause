import React, { useRef, useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import {
  UploadCloud,
  FileSpreadsheet,
  Database,
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  Table as TableIcon,
  Sparkles,
  Link2,
  Loader2
} from 'lucide-react';

export const UploadPage: React.FC = () => {
  const {
    semantic,
    qualityIssues,
    isLoading,
    loadSample,
    uploadFiles,
    setTab
  } = useAppStore();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const files = Array.from(e.dataTransfer.files);
      await uploadFiles(files);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      await uploadFiles(files);
    }
  };

  const activeTable = semantic?.tables?.find(
    (t) => t.name === (selectedTable || semantic.tables[0]?.name)
  );

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">
      {/* Hero Banner / Upload Zone */}
      {!semantic ? (
        <div className="space-y-6">
          <div className="text-center max-w-2xl mx-auto space-y-3">
            <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
              Turn Business Data into <span className="bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">Instant Answers</span>
            </h1>
            <p className="text-sm text-slate-400">
              Upload multi-sheet Excel or CSV files. RootCause automatically infers schemas, detects relationships, profiles data quality, and builds an AI analyst sandbox with zero manual setup.
            </p>
          </div>

          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-3xl p-10 text-center transition-all ${
              dragActive
                ? 'border-indigo-500 bg-indigo-950/20'
                : 'border-slate-800 bg-slate-900/40 hover:border-slate-700'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".xlsx,.xls,.csv"
              onChange={handleFileChange}
              className="hidden"
            />

            <div className="flex flex-col items-center justify-center space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shadow-xl shadow-indigo-500/10">
                {isLoading ? (
                  <Loader2 className="w-8 h-8 animate-spin" />
                ) : (
                  <UploadCloud className="w-8 h-8" />
                )}
              </div>

              <div className="space-y-1">
                <p className="text-base font-medium text-slate-200">
                  {isLoading ? 'Ingesting, Profiling & Detecting Schema...' : 'Drag & drop Excel or CSV files here'}
                </p>
                <p className="text-xs text-slate-500">Supports .xlsx (all sheets), .csv, .tsv</p>
              </div>

              <div className="flex items-center gap-3 pt-2">
                <button
                  type="button"
                  disabled={isLoading}
                  onClick={() => fileInputRef.current?.click()}
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-500/25 transition"
                >
                  Browse Files
                </button>

                <span className="text-xs text-slate-500">or</span>

                <button
                  type="button"
                  disabled={isLoading}
                  onClick={loadSample}
                  className="flex items-center gap-2 px-5 py-2.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 rounded-xl text-xs font-semibold border border-slate-700 transition"
                >
                  <Sparkles className="w-4 h-4 text-violet-400" />
                  <span>Load Retail Demo Dataset</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Ingested Overview */
        <div className="space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Database className="w-5 h-5 text-indigo-400" />
                <span>Dataset Overview: {semantic.dataset_id}</span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                {semantic.tables.length} tables • Anchor Date: {semantic.time?.anchor_date || 'N/A'} • {semantic.relationships.length} joins detected
              </p>
            </div>

            <button
              onClick={() => setTab('analyst')}
              className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-500/25 transition"
            >
              <span>Ask AI Analyst</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>

          {/* Tables & Schema Explorer */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Table Selector Sidebar */}
            <div className="space-y-2">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                Ingested Tables
              </span>
              {semantic.tables.map((tbl) => (
                <button
                  key={tbl.name}
                  onClick={() => setSelectedTable(tbl.name)}
                  className={`w-full p-3 rounded-xl border text-left flex items-center justify-between transition ${
                    (selectedTable || semantic.tables[0]?.name) === tbl.name
                      ? 'bg-indigo-950/40 border-indigo-500/80 text-white shadow-sm'
                      : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate">
                    <TableIcon className="w-4 h-4 text-indigo-400 shrink-0" />
                    <span className="font-semibold text-xs truncate">{tbl.name}</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      tbl.role === 'fact' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-slate-800 text-slate-400'
                    }`}>
                      {tbl.role}
                    </span>
                    <span className="text-[11px] text-slate-500">{tbl.row_count.toLocaleString()} rows</span>
                  </div>
                </button>
              ))}

              {/* Data Quality Summary Card */}
              <div className="mt-4 p-4 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-3">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="text-slate-300 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-400" /> Data Quality
                  </span>
                  <span className="text-slate-500">{qualityIssues.length} issues</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="p-2 bg-rose-500/10 border border-rose-500/20 rounded-lg">
                    <span className="block font-bold text-rose-400">{semantic.quality_summary?.high ?? 0}</span>
                    <span className="text-[10px] text-slate-400">High</span>
                  </div>
                  <div className="p-2 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                    <span className="block font-bold text-amber-400">{semantic.quality_summary?.medium ?? 0}</span>
                    <span className="text-[10px] text-slate-400">Med</span>
                  </div>
                  <div className="p-2 bg-slate-800/60 border border-slate-700/40 rounded-lg">
                    <span className="block font-bold text-slate-300">{semantic.quality_summary?.low ?? 0}</span>
                    <span className="text-[10px] text-slate-400">Low</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Column & Details View */}
            <div className="lg:col-span-3 space-y-6">
              {activeTable && (
                <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
                  <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-white">{activeTable.name}</span>
                      <span className="text-xs text-slate-400">({activeTable.row_count.toLocaleString()} rows)</span>
                    </div>
                    <span className="text-xs text-slate-500">
                      {Object.keys(activeTable.columns).length} columns detected
                    </span>
                  </div>

                  <div className="overflow-x-auto max-h-[380px]">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-950 text-slate-400 sticky top-0 border-b border-slate-800">
                        <tr>
                          <th className="px-4 py-2.5 font-semibold">Column</th>
                          <th className="px-4 py-2.5 font-semibold">Type</th>
                          <th className="px-4 py-2.5 font-semibold">Role</th>
                          <th className="px-4 py-2.5 font-semibold">Null %</th>
                          <th className="px-4 py-2.5 font-semibold">Sample Values</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {Object.values(activeTable.columns).map((col) => (
                          <tr key={col.name} className="hover:bg-slate-800/30">
                            <td className="px-4 py-2.5 font-mono text-slate-200 font-medium">
                              {col.name}
                            </td>
                            <td className="px-4 py-2.5 text-slate-400 font-mono text-[11px]">
                              {col.dtype}
                            </td>
                            <td className="px-4 py-2.5">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                col.role === 'measure'
                                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                  : col.role === 'time'
                                  ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                                  : col.role === 'id'
                                  ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                                  : 'bg-slate-800 text-slate-300'
                              }`}>
                                {col.role}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-slate-400 font-mono">
                              {col.null_pct > 0 ? (
                                <span className="text-amber-400 font-medium">
                                  {Math.round(col.null_pct * 100)}%
                                </span>
                              ) : (
                                '0%'
                              )}
                            </td>
                            <td className="px-4 py-2.5 text-slate-400 text-[11px] truncate max-w-xs font-mono">
                              {col.samples && col.samples.length > 0
                                ? col.samples.join(', ')
                                : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Inferred Relationships & Joins */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <Link2 className="w-3.5 h-3.5 text-indigo-400" /> Inferred Join Graph
                </h3>

                {semantic.relationships.length === 0 ? (
                  <p className="text-xs text-slate-500">No multi-table relationships detected.</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {semantic.relationships.map((rel, idx) => (
                      <div
                        key={idx}
                        className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl flex items-center justify-between text-xs"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1.5 font-mono text-slate-200">
                            <span className="text-indigo-400 font-semibold">{rel.from}</span>
                            <ArrowRight className="w-3 h-3 text-slate-500" />
                            <span className="text-indigo-400 font-semibold">{rel.to}</span>
                          </div>
                          <span className="text-[11px] text-slate-500 capitalize">{rel.type.replace(/_/g, ' ')}</span>
                        </div>
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                          {Math.round(rel.confidence * 100)}% match
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
