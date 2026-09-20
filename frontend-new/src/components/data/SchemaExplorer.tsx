import clsx from 'clsx';
import type { ColumnMeta, ColumnRole, SemanticResponse, TableSummary } from '../../types';
import { formatCell, formatNumber, pluralize } from '../../lib/format';
import { Badge } from '../ui/Badge';
import { Panel, PanelHeader } from '../ui/Panel';

interface SchemaExplorerProps {
  semantic: SemanticResponse;
  /** Name of the table whose columns are shown. An unknown name falls back to
   *  the first table rather than rendering nothing. */
  selectedTable: string;
  onSelectTable: (name: string) => void;
}

const tableRoleLabel: Record<TableSummary['role'], string> = {
  fact: 'Main',
  dimension: 'Lookup',
  mapping: 'Link',
};

const columnRoleLabel: Record<ColumnRole, string> = {
  id: 'ID',
  time: 'Date',
  measure: 'Measure',
  dimension: 'Category',
  text: 'Text',
};

/** What the column holds, in the form that helps most: a span for dates and
 *  numbers, a few examples for everything else. */
function describeContents(column: ColumnMeta): string {
  const { min, max } = column;

  if (min != null && max != null) {
    if (column.role === 'time') {
      // Dates are cut to the day as text; parsing them would shift the day for
      // anyone west of UTC.
      return `${min.slice(0, 10)} to ${max.slice(0, 10)}`;
    }
    if (column.role === 'measure') return `${formatBound(min)} to ${formatBound(max)}`;
  }
  if (column.samples && column.samples.length > 0) {
    return column.samples
      .slice(0, 3)
      .map((sample) => formatCell(sample))
      .join(', ');
  }
  return '—';
}

function formatBound(raw: string): string {
  const value = Number(raw);
  return raw.trim() !== '' && Number.isFinite(value) ? formatNumber(value) : raw;
}

export function SchemaExplorer({ semantic, selectedTable, onSelectTable }: SchemaExplorerProps) {
  const { tables } = semantic;
  const table = tables.find((candidate) => candidate.name === selectedTable) ?? tables[0];

  if (!table) {
    return (
      <Panel>
        <p className="text-[13px] text-ink-2">No tables were found in this dataset.</p>
      </Panel>
    );
  }

  const primaryDate = semantic.time.primary_column ?? null;

  return (
    <Panel flush>
      <PanelHeader
        title="Tables and columns"
        description={`${pluralize(tables.length, 'table')}. Pick one to see how each column was read.`}
      />

      <div className="grid md:grid-cols-[15rem_minmax(0,1fr)]">
        <nav
          aria-label="Tables"
          className={clsx(
            'flex gap-1 overflow-x-auto border-b border-line p-2',
            'md:block md:max-h-112 md:space-y-0.5 md:overflow-y-auto md:border-b-0 md:border-r',
          )}
        >
          {tables.map((candidate) => {
            const active = candidate.name === table.name;
            return (
              <button
                key={candidate.name}
                onClick={() => onSelectTable(candidate.name)}
                aria-current={active ? 'true' : undefined}
                className={clsx(
                  'flex w-44 shrink-0 flex-col rounded-md px-2.5 py-2 text-left transition-colors md:w-full',
                  active ? 'bg-raised text-ink' : 'text-ink-2 hover:bg-raised/60 hover:text-ink',
                )}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate text-[13px] font-medium">{candidate.display_name}</span>
                  <Badge>{tableRoleLabel[candidate.role] ?? candidate.role}</Badge>
                </span>
                <span className="tnum mt-0.5 font-mono text-[12px] text-ink-3">
                  {pluralize(candidate.row_count, 'row')}
                </span>
              </button>
            );
          })}
        </nav>

        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2 border-b border-line px-4 py-2.5">
            <h3 className="text-[13px] font-medium text-ink">{table.display_name}</h3>
            <span className="font-mono text-[12px] text-ink-3">{table.name}</span>
            <span className="tnum ml-auto font-mono text-[12px] text-ink-3">
              {pluralize(table.columns.length, 'column')}
            </span>
          </div>

          <div className="max-h-112 overflow-auto">
            <table className="w-full min-w-[34rem] text-[13px]">
              <thead className="sticky top-0 z-10 bg-surface">
                <tr>
                  <Th>Column</Th>
                  <Th>Kind</Th>
                  <Th>Type</Th>
                  <Th align="right">Missing</Th>
                  <Th align="right">Distinct</Th>
                  <Th>Contents</Th>
                </tr>
              </thead>
              <tbody>
                {table.columns.map((column) => (
                  <tr key={column.name} className="transition-colors hover:bg-raised/60">
                    <td className="border-b border-line/60 px-3 py-1.5">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                        <span className="text-ink">{column.display_name}</span>
                        {primaryDate === `${table.name}.${column.name}` ? (
                          <Badge tone="accent">Primary date</Badge>
                        ) : null}
                      </div>
                      {column.description ? (
                        <p className="mt-0.5 max-w-xs text-[12px] leading-4 text-ink-3">
                          {column.description}
                        </p>
                      ) : null}
                    </td>
                    <td className="border-b border-line/60 px-3 py-1.5">
                      <Badge>{columnRoleLabel[column.role] ?? column.role}</Badge>
                    </td>
                    <td className="border-b border-line/60 px-3 py-1.5 font-mono text-[12px] text-ink-2">
                      {column.dtype.toLowerCase()}
                    </td>
                    <td className="tnum border-b border-line/60 px-3 py-1.5 text-right font-mono text-ink">
                      {formatNumber(column.null_pct, 1)}%
                    </td>
                    <td className="tnum border-b border-line/60 px-3 py-1.5 text-right font-mono text-ink">
                      {column.distinct !== undefined ? formatNumber(column.distinct, 0) : '—'}
                    </td>
                    <td className="max-w-56 truncate border-b border-line/60 px-3 py-1.5 text-ink-2">
                      {describeContents(column)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Panel>
  );
}

function Th({ children, align = 'left' }: { children: string; align?: 'left' | 'right' }) {
  return (
    <th
      scope="col"
      className={clsx(
        'border-b border-line bg-surface px-3 py-2 font-medium text-ink-2',
        align === 'right' ? 'text-right' : 'text-left',
      )}
    >
      {children}
    </th>
  );
}
