import { useMemo } from 'react';
import type { EChartsOption } from 'echarts';
import type { ChartSpec, QueryResult, Scalar } from '../../types';
import { LazyChart } from './LazyChart';
import {
  baseOption,
  categorical,
  categoryAxis,
  chartColors,
  escapeHtml,
  pointTooltip,
  valueAxis,
} from '../../lib/chartTheme';
import { formatNumber, humanize } from '../../lib/format';

interface ChartViewProps {
  spec?: ChartSpec;
  result?: QueryResult;
  height?: number;
}

function toNumber(value: Scalar): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function seriesLabel(_spec: ChartSpec | undefined, result: QueryResult): string {
  // The server names no series; the second result column is always the measure.
  return humanize(result.columns[1] ?? 'value');
}

/** Picks a chart shape from the plan's `type`, falling back to the shape of the
 *  result when the planner did not name one. Kept as a pure function so the
 *  component below never branches before its hooks run. */
function buildOption(spec: ChartSpec | undefined, result: QueryResult): EChartsOption | null {
  const { columns, rows } = result;
  if (rows.length === 0 || columns.length < 2) return null;

  const names = rows.map((row) => String(row[0] ?? ''));
  const values = rows.map((row) => toNumber(row[1]));
  const unit = seriesLabel(spec, result);

  /* Signed contribution: each segment's share of the total movement. Zero sits
     on a marked line so a reader can see which side of it a bar falls. */
  if (spec?.type === 'contribution') {
    const ordered = [...rows].sort((a, b) => Math.abs(toNumber(b[1])) - Math.abs(toNumber(a[1])));
    const labels = ordered.map((row) => String(row[0] ?? '')).reverse();
    const deltas = ordered.map((row) => toNumber(row[1])).reverse();

    return baseOption({
      grid: { left: 8, right: 24, top: 8, bottom: 4, containLabel: true },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1a1e24',
        borderColor: '#343a44',
        borderWidth: 1,
        padding: [8, 10],
        textStyle: { color: '#e6e8eb', fontSize: 12 },
        formatter: (params: unknown) => {
          const first = Array.isArray(params) ? params[0] : params;
          const point = first as { name: string; value: number };
          const sign = point.value > 0 ? '+' : '';
          const colour = point.value < 0 ? chartColors.down : chartColors.up;
          return [
            `<div style="color:#9ba3ae;font-size:11px;margin-bottom:2px">${escapeHtml(point.name)}</div>`,
            `<div style="font-variant-numeric:tabular-nums">Contribution `,
            `<strong style="color:${colour}">${sign}${formatNumber(point.value)}</strong></div>`,
          ].join('');
        },
      },
      xAxis: valueAxis,
      yAxis: {
        ...categoryAxis,
        data: labels,
        axisLabel: { ...categoryAxis.axisLabel, width: 120, overflow: 'truncate' },
      },
      series: [
        {
          type: 'bar',
          barMaxWidth: 18,
          data: deltas.map((value) => ({
            value,
            itemStyle: {
              color: value < 0 ? chartColors.down : chartColors.up,
              borderRadius: value < 0 ? [2, 0, 0, 2] : [0, 2, 2, 0],
            },
          })),
          markLine: {
            silent: true,
            symbol: 'none',
            data: [{ xAxis: 0 }],
            lineStyle: { color: chartColors.axis, width: 1, type: 'solid' },
            label: { show: false },
          },
        },
      ],
    });
  }

  /* Two measure columns against one category: current versus baseline. */
  const isGrouped = spec?.type === 'grouped_bar' || columns.length >= 3;
  if (isGrouped) {
    // Exclude computed delta/delta_pct columns from sharing the absolute value axis
    const filtered = columns.slice(1).filter(
      (col) => col.toLowerCase() !== 'delta' && col.toLowerCase() !== 'delta_pct',
    );
    const measureColumns = filtered.length > 0 ? filtered : columns.slice(1);

    return baseOption({
      grid: { left: 8, right: 16, top: 32, bottom: 4, containLabel: true },
      legend: {
        top: 0,
        left: 0,
        icon: 'roundRect',
        itemWidth: 8,
        itemHeight: 8,
        itemGap: 16,
        textStyle: { color: chartColors.labelStrong, fontSize: 11 },
      },
      xAxis: {
        ...categoryAxis,
        data: names,
        axisLabel: {
          ...categoryAxis.axisLabel,
          interval: 0,
          rotate: names.length > 6 ? 30 : 0,
        },
      },
      yAxis: valueAxis,
      series: measureColumns.map((column, index) => {
        const colIdx = columns.indexOf(column);
        return {
          name: humanize(column),
          type: 'bar' as const,
          barMaxWidth: 22,
          data: rows.map((row) => toNumber(row[colIdx])),
          itemStyle: {
            color: categorical[index % categorical.length],
            borderRadius: [2, 2, 0, 0],
          },
        };
      }),
    });
  }

  /* A time axis reads as a line; everything else reads as bars. */
  const firstColumn = columns[0]?.toLowerCase() ?? '';
  const looksTemporal =
    spec?.type === 'line' ||
    /month|date|day|week|quarter|year|period|time/.test(firstColumn);

  if (looksTemporal) {
    return baseOption({
      xAxis: { ...categoryAxis, data: names, boundaryGap: false },
      yAxis: valueAxis,
      tooltip: {
        ...baseOption().tooltip,
        formatter: (params: unknown) => {
          const first = Array.isArray(params) ? params[0] : params;
          const point = first as { name: string; value: number };
          return pointTooltip(point.name, point.value, unit);
        },
      },
      series: [
        {
          type: 'line',
          data: values,
          smooth: false,
          symbol: 'circle',
          symbolSize: 5,
          showSymbol: values.length <= 24,
          itemStyle: { color: chartColors.series },
          lineStyle: { width: 1.75, color: chartColors.series },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(91,141,239,0.20)' },
                { offset: 1, color: 'rgba(91,141,239,0)' },
              ],
            },
          },
        },
      ],
    });
  }

  /* Rankings go horizontal once the labels stop fitting under a vertical axis. */
  const horizontal = spec?.type === 'bar_h' || names.length > 7;
  const tooltip = {
    ...baseOption().tooltip,
    formatter: (params: unknown) => {
      const first = Array.isArray(params) ? params[0] : params;
      const point = first as { name: string; value: number };
      return pointTooltip(point.name, point.value, unit);
    },
  };

  if (horizontal) {
    const top = rows.slice(0, 12);
    return baseOption({
      grid: { left: 8, right: 24, top: 8, bottom: 4, containLabel: true },
      tooltip,
      xAxis: valueAxis,
      yAxis: {
        ...categoryAxis,
        data: top.map((row) => String(row[0] ?? '')).reverse(),
        axisLabel: { ...categoryAxis.axisLabel, width: 132, overflow: 'truncate' },
      },
      series: [
        {
          type: 'bar',
          barMaxWidth: 16,
          data: top.map((row) => toNumber(row[1])).reverse(),
          itemStyle: { color: chartColors.series, borderRadius: [0, 2, 2, 0] },
        },
      ],
    });
  }

  return baseOption({
    tooltip,
    xAxis: {
      ...categoryAxis,
      data: names,
      axisLabel: {
        ...categoryAxis.axisLabel,
        interval: 0,
        rotate: names.length > 6 ? 30 : 0,
      },
    },
    yAxis: valueAxis,
    series: [
      {
        type: 'bar',
        barMaxWidth: 36,
        data: values,
        itemStyle: { color: chartColors.series, borderRadius: [2, 2, 0, 0] },
      },
    ],
  });
}

export function ChartView({ spec, result, height = 260 }: ChartViewProps) {
  const option = useMemo(
    () => (result ? buildOption(spec, result) : null),
    [spec, result],
  );

  if (!option || !result) {
    return (
      <div className="flex h-32 items-center justify-center text-[13px] text-ink-3">
        Nothing to plot for this result.
      </div>
    );
  }

  const description = `Chart of ${humanize(result.columns[1] ?? 'values')} by ${humanize(
    result.columns[0] ?? 'category',
  )}`;

  return <LazyChart option={option} height={height} description={description} />;
}
