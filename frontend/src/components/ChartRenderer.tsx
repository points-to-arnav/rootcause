import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { ChartSpec, QueryResult } from '../types';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface ChartRendererProps {
  spec?: ChartSpec;
  result?: QueryResult;
  height?: number | string;
}

export const ChartRenderer: React.FC<ChartRendererProps> = ({
  spec,
  result,
  height = 340
}) => {
  if (!spec && (!result || !result.rows || result.rows.length === 0)) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-500 text-xs">
        No visual data available.
      </div>
    );
  }

  // 1. KPI Card View
  if (spec?.type === 'kpi' && spec.kpi) {
    const { formatted, delta_pct, direction, label } = spec.kpi;
    const isUp = direction === 'up';
    const isDown = direction === 'down';

    return (
      <div className="p-6 bg-slate-900/80 border border-slate-800 rounded-2xl flex flex-col items-center justify-center text-center">
        {label && <span className="text-xs font-medium text-slate-400 mb-2 uppercase tracking-wider">{label}</span>}
        <span className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white mb-3">
          {formatted}
        </span>
        {delta_pct !== undefined && (
          <div
            className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold ${
              isUp
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : isDown
                ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                : 'bg-slate-800 text-slate-400'
            }`}
          >
            {isUp && <TrendingUp className="w-3.5 h-3.5" />}
            {isDown && <TrendingDown className="w-3.5 h-3.5" />}
            {!isUp && !isDown && <Minus className="w-3.5 h-3.5" />}
            <span>{delta_pct > 0 ? `+${delta_pct}%` : `${delta_pct}%`} vs baseline</span>
          </div>
        )}
      </div>
    );
  }

  // 2. Build ECharts Options based on type
  const chartOption = useMemo(() => {
    if (!result || !result.rows || result.rows.length === 0) return null;

    const cols = result.columns;
    const rows = result.rows;

    const darkThemeBase = {
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Inter, sans-serif' },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#0f172a',
        borderColor: '#334155',
        borderWidth: 1,
        textStyle: { color: '#f8fafc', fontSize: 12 },
        padding: [8, 12]
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '8%',
        top: spec?.title ? '18%' : '10%',
        containLabel: true
      }
    };

    // Contribution Bar Chart (Signed divergence for Why root-cause)
    if (spec?.type === 'contribution') {
      const categories = rows.map((r) => String(r[0]));
      const deltas = rows.map((r) => Number(r[1]) || 0);

      return {
        ...darkThemeBase,
        title: spec?.title ? { text: spec.title, textStyle: { color: '#e2e8f0', fontSize: 13 } } : undefined,
        tooltip: {
          trigger: 'axis',
          formatter: (params: any) => {
            const p = params[0];
            const val = p.value;
            const sign = val > 0 ? '+' : '';
            return `<div class="font-semibold text-slate-200 mb-1">${p.name}</div>
                    <div class="text-xs text-slate-400">Delta: <span class="font-mono ${val < 0 ? 'text-rose-400' : 'text-emerald-400'}">${sign}${val.toLocaleString()}</span></div>`;
          }
        },
        xAxis: {
          type: 'value',
          axisLine: { lineStyle: { color: '#334155' } },
          splitLine: { lineStyle: { color: '#1e293b' } },
          axisLabel: { color: '#94a3b8', fontSize: 11 }
        },
        yAxis: {
          type: 'category',
          data: categories.reverse(),
          axisLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#cbd5e1', fontSize: 11, width: 100, overflow: 'truncate' }
        },
        series: [
          {
            type: 'bar',
            data: deltas.reverse().map((v) => ({
              value: v,
              itemStyle: {
                color: v < 0 ? '#f43f5e' : '#10b981',
                borderRadius: [0, 4, 4, 0]
              }
            }))
          }
        ]
      };
    }

    // Line Chart (Trend)
    if (spec?.type === 'line' || (cols.length === 2 && cols[0].toLowerCase().includes('month'))) {
      const xData = rows.map((r) => String(r[0]));
      const yData = rows.map((r) => Number(r[1]) || 0);

      return {
        ...darkThemeBase,
        title: spec?.title ? { text: spec.title, textStyle: { color: '#e2e8f0', fontSize: 13 } } : undefined,
        xAxis: {
          type: 'category',
          data: xData,
          axisLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#94a3b8', fontSize: 11 }
        },
        yAxis: {
          type: 'value',
          axisLine: { lineStyle: { color: '#334155' } },
          splitLine: { lineStyle: { color: '#1e293b' } },
          axisLabel: { color: '#94a3b8', fontSize: 11 }
        },
        series: [
          {
            data: yData,
            type: 'line',
            smooth: true,
            symbolSize: 6,
            itemStyle: { color: '#6366f1' },
            lineStyle: { width: 3, color: '#6366f1' },
            areaStyle: {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: 'rgba(99, 102, 241, 0.35)' },
                  { offset: 1, color: 'rgba(99, 102, 241, 0.0)' }
                ]
              }
            }
          }
        ]
      };
    }

    // Grouped Bar (Comparison)
    if (spec?.type === 'grouped_bar' || (cols.includes('current') && cols.includes('previous'))) {
      const categories = rows.map((r) => String(r[0]));
      const curIdx = cols.indexOf('current');
      const prevIdx = cols.indexOf('previous');

      return {
        ...darkThemeBase,
        legend: { textStyle: { color: '#cbd5e1' }, top: 0 },
        xAxis: {
          type: 'category',
          data: categories,
          axisLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#94a3b8', fontSize: 11, interval: 0, rotate: categories.length > 5 ? 30 : 0 }
        },
        yAxis: {
          type: 'value',
          splitLine: { lineStyle: { color: '#1e293b' } },
          axisLabel: { color: '#94a3b8', fontSize: 11 }
        },
        series: [
          {
            name: 'Current Period',
            type: 'bar',
            data: rows.map((r) => r[curIdx]),
            itemStyle: { color: '#6366f1', borderRadius: [4, 4, 0, 0] }
          },
          {
            name: 'Previous Period',
            type: 'bar',
            data: rows.map((r) => r[prevIdx]),
            itemStyle: { color: '#94a3b8', borderRadius: [4, 4, 0, 0] }
          }
        ]
      };
    }

    // Horizontal Bar (Ranking / large sets)
    if (spec?.type === 'bar_h' || rows.length > 7) {
      const topRows = rows.slice(0, 10).reverse();
      const categories = topRows.map((r) => String(r[0]));
      const values = topRows.map((r) => Number(r[1]) || 0);

      return {
        ...darkThemeBase,
        xAxis: {
          type: 'value',
          splitLine: { lineStyle: { color: '#1e293b' } },
          axisLabel: { color: '#94a3b8', fontSize: 11 }
        },
        yAxis: {
          type: 'category',
          data: categories,
          axisLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#cbd5e1', fontSize: 11, width: 120, overflow: 'truncate' }
        },
        series: [
          {
            type: 'bar',
            data: values,
            itemStyle: {
              color: '#818cf8',
              borderRadius: [0, 4, 4, 0]
            }
          }
        ]
      };
    }

    // Default: Vertical Bar Chart
    const categories = rows.map((r) => String(r[0]));
    const values = rows.map((r) => Number(r[1]) || 0);

    return {
      ...darkThemeBase,
      xAxis: {
        type: 'category',
        data: categories,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8', fontSize: 11, interval: 0, rotate: categories.length > 5 ? 25 : 0 }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8', fontSize: 11 }
      },
      series: [
        {
          type: 'bar',
          data: values,
          itemStyle: {
            color: '#6366f1',
            borderRadius: [4, 4, 0, 0]
          }
        }
      ]
    };
  }, [spec, result]);

  if (!chartOption) return null;

  return (
    <div className="w-full">
      <ReactECharts
        option={chartOption}
        style={{ height, width: '100%' }}
        opts={{ renderer: 'canvas' }}
      />
    </div>
  );
};
