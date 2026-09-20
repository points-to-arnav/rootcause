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
  height = 300
}) => {
  if (!spec && (!result || !result.rows || result.rows.length === 0)) {
    return (
      <div className="flex items-center justify-center h-48 text-[#52525B] text-xs font-mono">
        NO TELEMETRY STREAM AVAILABLE
      </div>
    );
  }

  // 1. KPI Card View
  if (spec?.type === 'kpi' && spec.kpi) {
    const { formatted, delta_pct, direction, label } = spec.kpi;
    const isUp = direction === 'up';
    const isDown = direction === 'down';

    return (
      <div className="p-5 bento-card flex flex-col items-center justify-center text-center">
        {label && (
          <span className="text-[11px] font-mono text-[#888888] mb-2 uppercase tracking-wider">
            {label}
          </span>
        )}
        <span className="text-4xl sm:text-5xl font-bold tracking-tight text-white mb-2 font-mono">
          {formatted}
        </span>
        {delta_pct !== undefined && (
          <div
            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-mono font-medium ${
              isUp
                ? 'badge-growth'
                : isDown
                ? 'badge-anomaly'
                : 'bg-[#141414] text-[#888888] border border-[#262626]'
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

  // 2. Build High-Precision Minimalist ECharts Option
  const chartOption = useMemo(() => {
    if (!result || !result.rows || result.rows.length === 0) return null;

    const cols = result.columns;
    const rows = result.rows;

    const forensicsThemeBase = {
      backgroundColor: 'transparent',
      textStyle: {
        fontFamily: "'Geist', 'Inter', sans-serif"
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#0C0C0C',
        borderColor: '#262626',
        borderWidth: 1,
        textStyle: { color: '#EDEDED', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" },
        padding: [8, 12]
      },
      grid: {
        left: '2%',
        right: '2%',
        bottom: '8%',
        top: spec?.title ? '16%' : '8%',
        containLabel: true
      }
    };

    // Contribution / Signed Driver Bar Chart (Minimalist Forensics)
    if (spec?.type === 'contribution') {
      const categories = rows.map((r) => String(r[0]));
      const deltas = rows.map((r) => Number(r[1]) || 0);

      return {
        ...forensicsThemeBase,
        title: spec?.title ? { text: spec.title, textStyle: { color: '#A1A1AA', fontSize: 12, fontWeight: '500' } } : undefined,
        tooltip: {
          trigger: 'axis',
          formatter: (params: any) => {
            const p = params[0];
            const val = p.value;
            const sign = val > 0 ? '+' : '';
            return `<div class="font-mono text-xs text-[#A1A1AA] mb-1">${p.name}</div>
                    <div class="text-xs font-mono">Attributed Delta: <span class="${val < 0 ? 'text-[#F43F5E]' : 'text-[#10B981]'} font-semibold">${sign}${val.toLocaleString()}</span></div>`;
          }
        },
        xAxis: {
          type: 'value',
          axisLine: { lineStyle: { color: '#222222' } },
          splitLine: { lineStyle: { color: '#161616', type: 'dashed' } },
          axisLabel: { color: '#71717A', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }
        },
        yAxis: {
          type: 'category',
          data: categories.reverse(),
          axisLine: { lineStyle: { color: '#222222' } },
          axisLabel: { color: '#A1A1AA', fontSize: 10, width: 90, overflow: 'truncate' }
        },
        series: [
          {
            type: 'bar',
            data: deltas.reverse().map((v) => ({
              value: v,
              itemStyle: {
                color: v < 0 ? '#F43F5E' : '#10B981',
                borderRadius: [0, 2, 2, 0]
              }
            }))
          }
        ]
      };
    }

    // Line Chart (Trend / Telemetry Waveform)
    if (spec?.type === 'line' || (cols.length === 2 && cols[0].toLowerCase().includes('month'))) {
      const xData = rows.map((r) => String(r[0]));
      const yData = rows.map((r) => Number(r[1]) || 0);

      return {
        ...forensicsThemeBase,
        title: spec?.title ? { text: spec.title, textStyle: { color: '#A1A1AA', fontSize: 12, fontWeight: '500' } } : undefined,
        xAxis: {
          type: 'category',
          data: xData,
          axisLine: { lineStyle: { color: '#222222' } },
          axisLabel: { color: '#71717A', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }
        },
        yAxis: {
          type: 'value',
          axisLine: { lineStyle: { color: '#222222' } },
          splitLine: { lineStyle: { color: '#161616', type: 'dashed' } },
          axisLabel: { color: '#71717A', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }
        },
        series: [
          {
            data: yData,
            type: 'line',
            smooth: true,
            symbolSize: 4,
            itemStyle: { color: '#06B6D4' },
            lineStyle: { width: 2, color: '#06B6D4' },
            areaStyle: {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: 'rgba(6, 182, 212, 0.28)' },
                  { offset: 1, color: 'rgba(6, 182, 212, 0.0)' }
                ]
              }
            }
          }
        ]
      };
    }

    // Grouped Bar (Comparative Periods)
    if (spec?.type === 'grouped_bar' || (cols.includes('current') && cols.includes('previous'))) {
      const categories = rows.map((r) => String(r[0]));
      const curIdx = cols.indexOf('current');
      const prevIdx = cols.indexOf('previous');

      return {
        ...forensicsThemeBase,
        legend: { textStyle: { color: '#71717A', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }, top: 0 },
        xAxis: {
          type: 'category',
          data: categories,
          axisLine: { lineStyle: { color: '#222222' } },
          axisLabel: { color: '#71717A', fontSize: 10, interval: 0, rotate: categories.length > 5 ? 30 : 0 }
        },
        yAxis: {
          type: 'value',
          splitLine: { lineStyle: { color: '#161616', type: 'dashed' } },
          axisLabel: { color: '#71717A', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }
        },
        series: [
          {
            name: 'Current Period',
            type: 'bar',
            data: rows.map((r) => r[curIdx]),
            itemStyle: { color: '#06B6D4', borderRadius: [2, 2, 0, 0] }
          },
          {
            name: 'Baseline Period',
            type: 'bar',
            data: rows.map((r) => r[prevIdx]),
            itemStyle: { color: '#333333', borderRadius: [2, 2, 0, 0] }
          }
        ]
      };
    }

    // Horizontal Bar (Ranking / Dimension Scan)
    if (spec?.type === 'bar_h' || rows.length > 7) {
      const topRows = rows.slice(0, 10).reverse();
      const categories = topRows.map((r) => String(r[0]));
      const values = topRows.map((r) => Number(r[1]) || 0);

      return {
        ...forensicsThemeBase,
        xAxis: {
          type: 'value',
          splitLine: { lineStyle: { color: '#161616', type: 'dashed' } },
          axisLabel: { color: '#71717A', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }
        },
        yAxis: {
          type: 'category',
          data: categories,
          axisLine: { lineStyle: { color: '#222222' } },
          axisLabel: { color: '#A1A1AA', fontSize: 10, width: 110, overflow: 'truncate' }
        },
        series: [
          {
            type: 'bar',
            data: values,
            itemStyle: {
              color: '#38BDF8',
              borderRadius: [0, 2, 2, 0]
            }
          }
        ]
      };
    }

    // Default: Vertical Forensic Bar Chart
    const categories = rows.map((r) => String(r[0]));
    const values = rows.map((r) => Number(r[1]) || 0);

    return {
      ...forensicsThemeBase,
      xAxis: {
        type: 'category',
        data: categories,
        axisLine: { lineStyle: { color: '#222222' } },
        axisLabel: { color: '#71717A', fontSize: 10, interval: 0, rotate: categories.length > 5 ? 25 : 0 }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#161616', type: 'dashed' } },
        axisLabel: { color: '#71717A', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }
      },
      series: [
        {
          type: 'bar',
          data: values,
          itemStyle: {
            color: '#06B6D4',
            borderRadius: [2, 2, 0, 0]
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
