import { ArrowRight, Link2 } from 'lucide-react';
import type { Relationship } from '../../types';
import { formatShare } from '../../lib/format';
import { Badge } from '../ui/Badge';

interface JoinGraphProps {
  relationships: Relationship[];
}

const typeLabel: Record<Relationship['type'], string> = {
  many_to_one: 'Many to one',
  one_to_one: 'One to one',
};

/** Relationships arrive as `table.column`. Table names are snake_case and never
 *  contain a dot, so the first dot is the boundary. */
function splitQualified(qualified: string): { table: string; column: string } {
  const dot = qualified.indexOf('.');
  if (dot === -1) return { table: qualified, column: '' };
  return { table: qualified.slice(0, dot), column: qualified.slice(dot + 1) };
}

function Endpoint({ qualified }: { qualified: string }) {
  const { table, column } = splitQualified(qualified);
  return (
    <span className="break-all">
      <span className="text-ink">{table}</span>
      {column ? <span className="text-ink-3">.{column}</span> : null}
    </span>
  );
}

function describe(relationship: Relationship): string {
  const from = splitQualified(relationship.from);
  const to = splitQualified(relationship.to);
  const link =
    relationship.type === 'one_to_one'
      ? `Each ${from.table} row matches one ${to.table} row.`
      : `Many ${from.table} rows point to one ${to.table} row.`;

  if (relationship.containment === undefined) return link;
  return `${link} ${formatShare(relationship.containment)} of ${from.column} values appear in ${to.table}.`;
}

/** The joins the engine will use to combine tables. They are inferred from the
 *  values themselves, so each carries how sure the detection was. */
export function JoinGraph({ relationships }: JoinGraphProps) {
  if (relationships.length === 0) {
    return (
      <div className="flex items-start gap-2.5 px-4 py-6 text-[13px] leading-5 text-ink-2">
        <Link2 className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden="true" />
        <p>
          No links between tables were found. Questions that combine tables need a shared key,
          such as an ID column that appears in both.
        </p>
      </div>
    );
  }

  const ordered = [...relationships].sort((a, b) => b.confidence - a.confidence);

  return (
    <ul className="divide-y divide-line">
      {ordered.map((relationship) => (
        <li key={`${relationship.from}>${relationship.to}`} className="px-4 py-3">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[13px]">
            <Endpoint qualified={relationship.from} />
            <ArrowRight className="size-3.5 shrink-0 text-ink-3" role="img" aria-label="joins to" />
            <Endpoint qualified={relationship.to} />
          </div>
          <p className="mt-1 text-[13px] leading-5 text-ink-2">{describe(relationship)}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Badge>{typeLabel[relationship.type] ?? relationship.type}</Badge>
            <Badge mono>{formatShare(relationship.confidence, 0)} sure</Badge>
            {relationship.confirmed ? <Badge tone="up">Confirmed</Badge> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}
