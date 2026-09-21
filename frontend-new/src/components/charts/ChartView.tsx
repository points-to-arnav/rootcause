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

const MAX_SERIES = 6;

/** Rows of (period, dimension, measure): one series per dimension value across
 *  the periods, as lines or as grouped bars.
 *
 *  More than six series cannot be read, so the smallest fold into "Other". That
 *  sum is only valid for an additive measure; the server answers a non-additive
 *  result with a `table` chart instead, so this is never asked to fold one. */
function buildSeriesOption(rows: Scalar[][], asBars: boolean): EChartsOption {
  // Decide once which column is the measure: the numeric one. A null in one row
  // must not make that row's dimension text look like the measure.
  const numericMiddle = rows.filter((row) => typeof row[1] === 'number').length;
  const numericLast = rows.filter((row) => typeof row[2] === 'number').length;
  const valueIndex = numericLast >= numericMiddle ? 2 : 1;
  const labelIndex = valueIndex === 2 ? 1 : 2;

  const periods: string[] = [];
  const seenPeriods = new Set<string>();
  const cells = new Map<string, Map<string, number | null>>();

  for (const row of rows) {
    const period = String(row[0] ?? '');
    const label = row[labelIndex];
    const group = label === null || label === undefined ? '(missing)' : String(label);
    if (!seenPeriods.has(period)) {
      seenPeriods.add(period);
      periods.push(period);
    }
    const byPeriod = cells.get(group) ?? new Map<string, number | null>();
    const raw = row[valueIndex];
    byPeriod.set(period, typeof raw === 'number' ? raw : null);
    cells.set(group, byPeriod);
  }

  interface Group {
    name: string;
    byPeriod: Map<string, number | null>;
    total: number;
    isOther: boolean;
  }

  let groups: Group[] = [...cells.entries()]
    .map(([name, byPeriod]) => ({
      name,
      byPeriod,
      total: [...byPeriod.values()].reduce<number>((sum, value) => sum + (value ?? 0), 0),
      isOther: false,
    }))
    .sort((a, b) => b.total - a.total);

  if (groups.length > MAX_SERIES) {
    const rest = groups.slice(MAX_SERIES - 1);
    const other = new Map<string, number | null>();
    for (const period of periods) {
      other.set(period, rest.reduce((sum, group) => sum + (group.byPeriod.get(period) ?? 0), 0));
    }
    groups = [
      ...groups.slice(0, MAX_SERIES - 1),
      { name: 'Other', byPeriod: other, total: 0, isOther: true },
    ];
  }

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
    tooltip: {
      ...baseOption().tooltip,
      axisPointer: asBars
        ? { type: 'shadow' }
        : { type: 'line', lineStyle: { color: '#343a44', width: 1 } },
      valueFormatter: (value: unknown) =>
        typeof value === 'number' ? formatNumber(value) : '—',
    },
    xAxis: {
      ...categoryAxis,
      data: periods,
      boundaryGap: asBars,
      axisLabel: {
        ...categoryAxis.axisLabel,
        interval: 0,
        rotate: periods.length > 6 ? 30 : 0,
      },
    },
    yAxis: valueAxis,
    series: groups.map((group, index) => {
      const colour = group.isOther ? chartColors.neutral : categorical[index % categorical.length];
      const data = periods.map((period) => group.byPeriod.get(period) ?? null);
      return asBars
        ? {
            name: group.name,
            type: 'bar' as const,
            barMaxWidth: 22,
            data,
            itemStyle: { color: colour, borderRadius: [2, 2, 0, 0] },
          }
        : {
            name: group.name,
            type: 'line' as const,
            data,
            smooth: false,
            symbol: 'circle',
            symbolSize: 5,
            showSymbol: periods.length <= 24,
            itemStyle: { color: colour },
            lineStyle: { width: 1.75, color: colour },
          };
    }),
  });
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

  const lowered = columns.map((column) => column.toLowerCase());
  const isComparison =
    spec?.type === 'grouped_bar' || (lowered.includes('current') && lowered.includes('previous'));

  /* Period, dimension, measure: a series per dimension value. Without this a
     three-column result was read as "current versus baseline" and the dimension's
     text was plotted as if it were a number. */
  if (columns.length === 3 && !isComparison && (spec?.type === 'line' || spec?.type === 'bar')) {
    return buildSeriesOption(rows, spec.type === 'bar');
  }

  /* Two measure columns against one category: current versus baseline. */
  const isGrouped = isComparison || columns.length >= 3;
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

  /* A time axis reads as a line; everything else reads as bars. That is only a
     guess from the column's name, so a chart type the server settled on wins:
     asked for bars over months, the user gets bars over months. */
  const firstColumn = columns[0]?.toLowerCase() ?? '';
  const temporalAxis = /month|date|day|week|quarter|year|period|time/.test(firstColumn);
  const serverWantsBars = spec?.type === 'bar' || spec?.type === 'bar_h';
  const looksTemporal = spec?.type === 'line' || (temporalAxis && !serverWantsBars);

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

  /* Rankings go horizontal once the labels stop fitting under a vertical axis.
     Periods stay vertical: a time series read top to bottom is not a time series. */
  const horizontal = spec?.type === 'bar_h' || (names.length > 7 && !temporalAxis);
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
