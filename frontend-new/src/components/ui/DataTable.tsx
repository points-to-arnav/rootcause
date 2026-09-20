import { useMemo, useState } from 'react';
import clsx from 'clsx';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { Scalar } from '../../types';
import { formatCell, humanize } from '../../lib/format';

interface DataTableProps {
  columns: string[];
  rows: Scalar[][];
  maxHeight?: number;
  /** Off for short result sets where sorting would be noise. */
  sortable?: boolean;
}

type SortState = { index: number; direction: 'asc' | 'desc' } | null;

function isNumericColumn(rows: Scalar[][], index: number): boolean {
  const sample = rows.slice(0, 20).map((row) => row[index]);
  const numbers = sample.filter((value) => typeof value === 'number');
  return numbers.length > sample.length / 2;
}

function compare(a: Scalar, b: Scalar): number {
  if (a === null || a === undefined) return 1;
  if (b === null || b === undefined) return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return String(a).localeCompare(String(b), 'en', { numeric: true });
}

export function DataTable({ columns, rows, maxHeight = 340, sortable = true }: DataTableProps) {
  const [sort, setSort] = useState<SortState>(null);

  const numericColumns = useMemo(
    () => columns.map((_, index) => isNumericColumn(rows, index)),
    [columns, rows],
  );

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const result = compare(a[sort.index], b[sort.index]);
      return sort.direction === 'asc' ? result : -result;
    });
    return copy;
  }, [rows, sort]);

  function toggleSort(index: number) {
    setSort((current) => {
      if (current?.index !== index) return { index, direction: 'desc' };
      if (current.direction === 'desc') return { index, direction: 'asc' };
      return null;
    });
  }

  if (rows.length === 0) {
    return <p className="px-4 py-6 text-[13px] text-ink-3">This query returned no rows.</p>;
  }

  return (
    <div className="overflow-auto" style={{ maxHeight }}>
      <table className="w-full text-[13px]">
        <thead className="sticky top-0 z-10 bg-surface">
          <tr>
            {columns.map((column, index) => {
              const active = sort?.index === index;
              const alignRight = numericColumns[index];
              return (
                <th
                  key={column}
                  scope="col"
                  aria-sort={
                    active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'
                  }
                  className={clsx(
                    'border-b border-line bg-surface px-3 py-2 font-medium text-ink-2',
                    alignRight ? 'text-right' : 'text-left',
                  )}
                >
                  {sortable ? (
                    <button
                      onClick={() => toggleSort(index)}
                      className={clsx(
                        'inline-flex items-center gap-1 rounded-sm transition-colors hover:text-ink',
                        alignRight && 'flex-row-reverse',
                        active && 'text-ink',
                      )}
                    >
                      {humanize(column)}
                      {active ? (
                        sort.direction === 'asc' ? (
                          <ChevronUp className="size-3" aria-hidden="true" />
                        ) : (
                          <ChevronDown className="size-3" aria-hidden="true" />
                        )
                      ) : null}
                    </button>
                  ) : (
                    humanize(column)
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, rowIndex) => (
            <tr key={rowIndex} className="transition-colors hover:bg-raised/60">
              {row.map((value, cellIndex) => (
                <td
                  key={cellIndex}
                  className={clsx(
                    'border-b border-line/60 px-3 py-1.5',
                    numericColumns[cellIndex]
                      ? 'tnum text-right font-mono text-ink'
                      : 'text-left text-ink-2',
                  )}
                >
                  {formatCell(value)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
