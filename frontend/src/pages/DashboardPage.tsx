import React, { useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { ChartRenderer } from '../components/ChartRenderer';
import {
  LayoutDashboard,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  ArrowRight,
  Loader2,
  Sparkles,
  Info
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const {
    datasetId,
    dashboard,
    isDashboardLoading,
    loadDashboardData,
    sendMessage,
    setTab
  } = useAppStore();

  useEffect(() => {
    if (datasetId && !dashboard && !isDashboardLoading) {
      loadDashboardData();
    }
  }, [datasetId, dashboard, isDashboardLoading]);

  const handleInvestigateAlert = async (drillQuestion?: string) => {
    if (!drillQuestion) return;
    setTab('analyst');
    await sendMessage(drillQuestion);
  };

  if (!datasetId) {
    return (
      <div className="max-w-md mx-auto my-24 p-8 bg-slate-900 border border-slate-800 rounded-3xl text-center space-y-4">
        <LayoutDashboard className="w-8 h-8 text-indigo-400 mx-auto" />
        <h3 className="text-lg font-bold text-white">No Dataset Selected</h3>
        <p className="text-xs text-slate-400">
          Load or upload a dataset first to generate your executive dashboard.
        </p>
        <button
          onClick={() => setTab('upload')}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-500/25 transition"
        >
          Go to Data Upload
        </button>
      </div>
    );
  }

  if (isDashboardLoading) {
    return (
      <div className="max-w-md mx-auto my-32 text-center space-y-4">
        <Loader2 className="w-10 h-10 text-indigo-400 animate-spin mx-auto" />
        <p className="text-sm font-semibold text-slate-200">
          Compiling executive dashboard & computing KPIs...
        </p>
        <p className="text-xs text-slate-500">
          Scanning trends, breakdowns, and automated anomaly alerts
        </p>
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className="max-w-md mx-auto my-24 text-center space-y-4">
        <p className="text-sm text-slate-400">No dashboard generated yet.</p>
        <button
          onClick={loadDashboardData}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-500/25 transition"
        >
          Generate Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <LayoutDashboard className="w-6 h-6 text-indigo-400" />
            <span>Executive Management Dashboard</span>
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Dataset: {datasetId} • Generated {new Date(dashboard.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </p>
        </div>

        <button
          onClick={loadDashboardData}
          className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-xl text-xs font-medium border border-slate-800 transition"
        >
          Refresh Data
        </button>
      </div>

      {/* Executive Summary Narrative */}
      {dashboard.executive_summary && (
        <div className="p-5 bg-gradient-to-r from-indigo-950/40 via-slate-900/60 to-purple-950/40 border border-indigo-500/20 rounded-2xl shadow-xl flex items-start gap-3.5">
          <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0 mt-0.5">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400 block mb-1">
              Executive Briefing
            </span>
            <p className="text-sm text-slate-200 leading-relaxed font-normal">
              {dashboard.executive_summary}
            </p>
          </div>
        </div>
      )}

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {dashboard.kpis.map((kpi) => {
          const isUp = kpi.direction === 'up';
          const isDown = kpi.direction === 'down';

          return (
            <div
              key={kpi.id}
              className="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl shadow-lg space-y-3"
            >
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-medium truncate">{kpi.title}</span>
                {kpi.period_label && (
                  <span className="text-[10px] text-slate-500 truncate">{kpi.period_label}</span>
                )}
              </div>

              <div className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                {kpi.formatted}
              </div>

              {kpi.delta_pct !== undefined && (
                <div className="flex items-center gap-1.5 text-xs font-semibold">
                  {isUp && (
                    <span className="text-emerald-400 flex items-center gap-0.5">
                      <TrendingUp className="w-3.5 h-3.5" /> +{kpi.delta_pct}%
                    </span>
                  )}
                  {isDown && (
                    <span className="text-rose-400 flex items-center gap-0.5">
                      <TrendingDown className="w-3.5 h-3.5" /> {kpi.delta_pct}%
                    </span>
                  )}
                  {!isUp && !isDown && (
                    <span className="text-slate-400 flex items-center gap-0.5">
                      <Minus className="w-3.5 h-3.5" /> 0%
                    </span>
                  )}
                  <span className="text-[11px] text-slate-500 font-normal">vs prev month</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {dashboard.charts.monthly_trend && (
          <div className="p-6 bg-slate-900/80 border border-slate-800 rounded-2xl shadow-xl space-y-4">
            <h3 className="text-sm font-semibold text-white">
              {dashboard.charts.monthly_trend.title}
            </h3>
            <ChartRenderer
              spec={dashboard.charts.monthly_trend.spec}
              result={dashboard.charts.monthly_trend.result}
              height={280}
            />
          </div>
        )}

        {dashboard.charts.category_breakdown && (
          <div className="p-6 bg-slate-900/80 border border-slate-800 rounded-2xl shadow-xl space-y-4">
            <h3 className="text-sm font-semibold text-white">
              {dashboard.charts.category_breakdown.title}
            </h3>
            <ChartRenderer
              spec={dashboard.charts.category_breakdown.spec}
              result={dashboard.charts.category_breakdown.result}
              height={280}
            />
          </div>
        )}

        {dashboard.charts.entity_ranking && (
          <div className="lg:col-span-2 p-6 bg-slate-900/80 border border-slate-800 rounded-2xl shadow-xl space-y-4">
            <h3 className="text-sm font-semibold text-white">
              {dashboard.charts.entity_ranking.title}
            </h3>
            <ChartRenderer
              spec={dashboard.charts.entity_ranking.spec}
              result={dashboard.charts.entity_ranking.result}
              height={320}
            />
          </div>
        )}
      </div>

      {/* Automated Alerts Feed */}
      {dashboard.alerts && dashboard.alerts.length > 0 && (
        <div className="p-6 bg-slate-900/80 border border-slate-800 rounded-2xl shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-semibold text-white">Automated Anomaly & Root-Cause Alerts</h3>
            </div>
            <span className="text-xs text-slate-500">{dashboard.alerts.length} active alerts</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {dashboard.alerts.map((alert) => (
              <div
                key={alert.id}
                className="p-4 bg-slate-950/60 border border-slate-800/80 rounded-xl space-y-2 flex flex-col justify-between"
              >
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-200">{alert.title}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        alert.severity === 'high'
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : alert.severity === 'medium'
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {alert.severity}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">{alert.description}</p>
                </div>

                {alert.drill_question && (
                  <button
                    onClick={() => handleInvestigateAlert(alert.drill_question)}
                    className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-indigo-400 hover:text-indigo-300 transition self-start"
                  >
                    <span>Investigate Root Cause</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
