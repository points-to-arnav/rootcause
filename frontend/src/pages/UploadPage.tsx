import React, { useRef, useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import {
  UploadCloud,
  Database,
  ArrowRight,
  AlertTriangle,
  Table as TableIcon,
  Sparkles,
  Link2,
  Loader2,
  Terminal
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
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-8 font-sans">
      {/* Hero Banner / Upload Zone */}
      {!semantic ? (
        <div className="space-y-6">
          <div className="text-center max-w-2xl mx-auto space-y-3">
            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-white font-mono uppercase">
              DATASET INTAKE // <span className="text-cyan-400">SCHEMA INFERENCE</span>
            </h1>
            <p className="text-xs sm:text-sm text-[#888888] font-mono leading-relaxed">
              Upload multi-sheet Excel or CSV files. RootCause automatically infers schemas, detects joins, profiles data quality, and compiles an in-memory DuckDB sandbox.
            </p>
          </div>

          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`dropzone-dashed p-10 text-center transition-all ${
              dragActive ? 'drag-active' : ''
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".xlsx,.xls,.csv,.parquet"
              onChange={handleFileChange}
              className="hidden"
            />

            <div className="flex flex-col items-center justify-center space-y-4 font-mono">
              <div className="w-14 h-14 rounded-2xl bg-[#111111] border border-[#222222] flex items-center justify-center text-cyan-400 shadow-inner">
                {isLoading ? (
                  <Loader2 className="w-7 h-7 animate-spin" />
                ) : (
                  <UploadCloud className="w-7 h-7" />
                )}
              </div>

              <div className="space-y-1">
                <p className="text-sm font-semibold text-white">
                  {isLoading ? 'Ingesting, Profiling & Detecting Schema...' : 'Drag & drop Excel, CSV, or Parquet files'}
                </p>
                <p className="text-xs text-[#71717A]">Supported: .xlsx (multi-sheet), .csv, .parquet</p>
              </div>

              <div className="flex items-center gap-3 pt-2">
                <button
                  type="button"
                  disabled={isLoading}
                  onClick={() => fileInputRef.current?.click()}
                  className="btn-framer-primary px-4 py-2 text-xs font-mono cursor-pointer"
                >
                  Browse Files
                </button>

                <span className="text-xs text-[#52525B]">or</span>

                <button
                  type="button"
                  disabled={isLoading}
                  onClick={loadSample}
                  className="btn-framer-secondary flex items-center gap-2 px-4 py-2 text-xs font-mono cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Load Sample Retail Dataset</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Ingested Overview */
        <div className="space-y-6 font-mono">
          <div className="flex items-center justify-between pb-4 border-b border-[#1E1E1E]">
            <div>
              <h2 className="text-base sm:text-lg font-bold text-white flex items-center gap-2 tracking-tight">
                <Database className="w-4 h-4 text-cyan-400" />
                <span>DATASET INGESTED: {semantic.dataset_id}</span>
              </h2>
              <p className="text-xs text-[#888888] mt-0.5">
                {semantic.tables.length} tables • Anchor Date: {semantic.time?.anchor_date || 'N/A'} • {semantic.relationships.length} joins detected
              </p>
            </div>

            <button
              onClick={() => setTab('dashboard')}
              className="btn-framer-primary flex items-center gap-2 px-4 py-2 text-xs cursor-pointer"
            >
              <span>Launch Bento Dashboard</span>
              <ArrowRight className="w-3.5 h-3.5 text-[#050505]" />
            </button>
          </div>

          {/* Tables & Schema Explorer */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Table Selector Sidebar */}
            <div className="space-y-2">
              <span className="text-[11px] font-semibold text-[#888888] uppercase tracking-wider block mb-2">
                INGESTED TABLES
              </span>
              {semantic.tables.map((tbl) => (
                <button
                  key={tbl.name}
                  onClick={() => setSelectedTable(tbl.name)}
                  className={`w-full p-3 rounded-xl border text-left flex items-center justify-between transition cursor-pointer ${
                    (selectedTable || semantic.tables[0]?.name) === tbl.name
                      ? 'bg-[#141414] border-cyan-500/60 text-white'
                      : 'bg-[#0A0A0A] border-[#1E1E1E] text-[#888888] hover:border-[#2E2E2E]'
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate">
                    <TableIcon className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                    <span className="font-semibold text-xs truncate">{tbl.name}</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      tbl.role === 'fact' ? 'badge-anomaly' : 'bg-[#141414] text-[#888888] border border-[#262626]'
                    }`}>
                      {tbl.role}
                    </span>
                    <span className="text-[10px] text-[#71717A]">{tbl.row_count.toLocaleString()}</span>
                  </div>
                </button>
              ))}

              {/* Data Quality Summary Card */}
              <div className="mt-4 p-4 bento-card space-y-3">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="text-white flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> DATA QUALITY
                  </span>
                  <span className="text-[#888888]">{qualityIssues.length} issues</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="p-2 bg-[#1C080A] border border-[#4C0519] rounded-lg">
                    <span className="block font-bold text-[#FDA4AF]">{semantic.quality_summary?.high ?? 0}</span>
                    <span className="text-[10px] text-[#888888]">High</span>
                  </div>
                  <div className="p-2 bg-amber-950/30 border border-amber-500/30 rounded-lg">
                    <span className="block font-bold text-amber-300">{semantic.quality_summary?.medium ?? 0}</span>
                    <span className="text-[10px] text-[#888888]">Med</span>
                  </div>
                  <div className="p-2 bg-[#141414] border border-[#222222] rounded-lg">
                    <span className="block font-bold text-[#CCCCCC]">{semantic.quality_summary?.low ?? 0}</span>
                    <span className="text-[10px] text-[#888888]">Low</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Column & Details View */}
            <div className="lg:col-span-3 space-y-6">
              {activeTable && (
                <div className="bento-card overflow-hidden">
                  <div className="px-5 py-3 border-b border-[#1E1E1E] flex items-center justify-between bg-[#080808]">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-xs text-white uppercase">{activeTable.name}</span>
                      <span className="text-[11px] text-[#71717A]">({activeTable.row_count.toLocaleString()} rows)</span>
                    </div>
                    <span className="text-[11px] text-[#71717A]">
                      {Object.keys(activeTable.columns).length} columns detected
                    </span>
                  </div>

                  <div className="overflow-x-auto max-h-[380px]">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead className="bg-[#050505] text-[#888888] sticky top-0 border-b border-[#1E1E1E]">
                        <tr>
                          <th className="px-4 py-2 font-medium">Column</th>
                          <th className="px-4 py-2 font-medium">Type</th>
                          <th className="px-4 py-2 font-medium">Role</th>
                          <th className="px-4 py-2 font-medium">Null %</th>
                          <th className="px-4 py-2 font-medium">Sample Values</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#141414] bg-[#0A0A0A]">
                        {Object.values(activeTable.columns).map((col) => (
                          <tr key={col.name} className="hover:bg-[#121212]">
                            <td className="px-4 py-2.5 font-mono text-white font-medium">
                              {col.name}
                            </td>
                            <td className="px-4 py-2.5 text-[#888888] font-mono text-[11px]">
                              {col.dtype}
                            </td>
                            <td className="px-4 py-2.5">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                col.role === 'measure'
                                  ? 'badge-growth'
                                  : col.role === 'time'
                                  ? 'badge-nominal'
                                  : col.role === 'id'
                                  ? 'badge-anomaly'
                                  : 'bg-[#141414] text-[#888888] border border-[#262626]'
                              }`}>
                                {col.role}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-[#888888] font-mono">
                              {col.null_pct > 0 ? (
                                <span className="text-amber-400 font-medium">
                                  {Math.round(col.null_pct * 100)}%
                                </span>
                              ) : (
                                '0%'
                              )}
                            </td>
                            <td className="px-4 py-2.5 text-[#71717A] text-[11px] truncate max-w-xs font-mono">
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
              <div className="bento-card p-5">
                <h3 className="text-xs font-semibold text-[#888888] uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <Link2 className="w-3.5 h-3.5 text-cyan-400" /> INFERRED JOIN GRAPH
                </h3>

                {semantic.relationships.length === 0 ? (
                  <p className="text-xs text-[#71717A]">No multi-table relationships detected.</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {semantic.relationships.map((rel, idx) => (
                      <div
                        key={idx}
                        className="p-3 bg-[#080808] border border-[#1E1E1E] rounded-xl flex items-center justify-between text-xs"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1.5 font-mono text-white">
                            <span className="text-cyan-400 font-semibold">{rel.from}</span>
                            <ArrowRight className="w-3 h-3 text-[#52525B]" />
                            <span className="text-cyan-400 font-semibold">{rel.to}</span>
                          </div>
                          <span className="text-[10px] text-[#71717A] capitalize">{rel.type.replace(/_/g, ' ')}</span>
                        </div>
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold badge-growth font-mono">
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
