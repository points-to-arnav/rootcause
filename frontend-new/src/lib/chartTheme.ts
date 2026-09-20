import type { EChartsOption } from 'echarts';
import { formatCompact, formatNumber } from './format';

/* One palette, one grid, one tooltip — shared by every chart in the app so
   that two charts side by side read as the same system. Categorical colours
   are ordered by how distinguishable the first few are from each other. */
export const chartColors = {
  series: '#5b8def',
  up: '#3fb47f',
  down: '#e5606b',
  neutral: '#5a6069',
  axis: '#343a44',
  grid: '#222730',
  label: '#6b7480',
  labelStrong: '#9ba3ae',
} as const;

export const categorical = [
  '#5b8def',
  '#3fb47f',
  '#d8a13a',
  '#a78bfa',
  '#4bb3c4',
  '#e5606b',
  '#8b93a1',
] as const;

const fontFamily = "'IBM Plex Sans', system-ui, sans-serif";
const monoFamily = "'IBM Plex Mono', ui-monospace, monospace";

export const axisLabel = {
  color: chartColors.label,
  fontSize: 11,
  fontFamily: monoFamily,
} as const;

/** Everything a chart needs before it knows what it is plotting. */
export function baseOption(overrides: Partial<EChartsOption> = {}): EChartsOption {
  return {
    backgroundColor: 'transparent',
    animationDuration: 320,
    animationEasing: 'cubicOut',
    textStyle: { fontFamily },
    grid: { left: 8, right: 16, top: 16, bottom: 4, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a1e24',
      borderColor: '#343a44',
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: '#e6e8eb', fontSize: 12, fontFamily },
      axisPointer: {
        type: 'line',
        lineStyle: { color: '#343a44', width: 1 },
      },
    },
    ...overrides,
  };
}

export const valueAxis = {
  type: 'value' as const,
  axisLine: { show: false },
  axisTick: { show: false },
  splitLine: { lineStyle: { color: chartColors.grid, type: 'solid' as const } },
  axisLabel: { ...axisLabel, formatter: (value: number) => formatCompact(value) },
};

export const categoryAxis = {
  type: 'category' as const,
  axisLine: { lineStyle: { color: chartColors.axis } },
  axisTick: { show: false },
  splitLine: { show: false },
  axisLabel,
};

/** Tooltip body shared by the single-series charts. */
export function pointTooltip(name: string, value: number, unitLabel?: string): string {
  return [
    `<div style="color:#9ba3ae;font-size:11px;margin-bottom:2px">${escapeHtml(name)}</div>`,
    `<div style="font-family:${monoFamily};font-variant-numeric:tabular-nums">`,
    `<strong>${formatNumber(value)}</strong>`,
    unitLabel ? `<span style="color:#6b7480"> ${escapeHtml(unitLabel)}</span>` : '',
    '</div>',
  ].join('');
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
