import type { Scalar, ValueFormat } from '../types';

const compact = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

const currency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

const compactCurrency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  maximumFractionDigits: 1,
});

/** Full precision for a table cell, where the reader compares exact values. */
export function formatNumber(value: number, maxFractionDigits = 2): string {
  return value.toLocaleString('en-US', { maximumFractionDigits: maxFractionDigits });
}

/** Shortened for an axis or a headline figure, where space matters more. */
export function formatCompact(value: number): string {
  return Math.abs(value) >= 10_000 ? compact.format(value) : formatNumber(value, 1);
}

/** Renders a measure the way the server said it should be read. */
export function formatValue(value: number, format: ValueFormat = 'number'): string {
  switch (format) {
    case 'currency':
      return Math.abs(value) >= 1_000_000 ? compactCurrency.format(value) : currency.format(value);
    case 'percent':
      return `${formatNumber(value, 1)}%`;
    case 'count':
      return formatNumber(value, 0);
    default:
      return formatNumber(value);
  }
}

export function formatSigned(value: number, format: ValueFormat = 'number'): string {
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${formatValue(Math.abs(value), format)}`;
}

export function formatPercent(value: number, fractionDigits = 1): string {
  return `${value.toFixed(fractionDigits)}%`;
}

export function formatSignedPercent(value: number, fractionDigits = 1): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(fractionDigits)}%`;
}

/** Turns a fraction such as 0.6422 into `64.2%`. */
export function formatShare(fraction: number, fractionDigits = 1): string {
  return `${(fraction * 100).toFixed(fractionDigits)}%`;
}

export function formatSignedShare(fraction: number, fractionDigits = 1): string {
  const sign = fraction > 0 ? '+' : '';
  return `${sign}${(fraction * 100).toFixed(fractionDigits)}%`;
}

export function formatCell(value: Scalar): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return formatNumber(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return value;
}

/** Turns `total_revenue` into `Total revenue` for a column header. */
export function humanize(name: string): string {
  const spaced = name.replace(/[_-]+/g, ' ').trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** `customers.region` reads as `Region` once the table is already known. */
export function columnLabel(qualified: string): string {
  const parts = qualified.split('.');
  return humanize(parts[parts.length - 1] ?? qualified);
}

export function formatDate(iso: string | undefined | null): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

export function formatTime(date = new Date()): string {
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${formatNumber(count, 0)} ${count === 1 ? singular : plural}`;
}
