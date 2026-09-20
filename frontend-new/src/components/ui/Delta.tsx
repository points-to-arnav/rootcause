import clsx from 'clsx';
import { ArrowDown, ArrowUp, Minus } from 'lucide-react';
import { formatSignedPercent } from '../../lib/format';

interface DeltaProps {
  /** Percentage change. Direction comes from the sign unless it is overridden. */
  percent?: number;
  direction?: 'up' | 'down' | 'flat';
  label?: string;
  className?: string;
  /** When true, an upward move is bad (red) and a downward move is good (green), e.g. return rate. */
  inverted?: boolean;
}

/** A change, carried by an arrow as well as a colour so it stays readable in
 *  greyscale and for colour-blind vision. */
export function Delta({ percent, direction, label, className, inverted }: DeltaProps) {
  const resolved =
    direction ?? (percent === undefined || percent === 0 ? 'flat' : percent > 0 ? 'up' : 'down');

  const Icon = resolved === 'up' ? ArrowUp : resolved === 'down' ? ArrowDown : Minus;
  const tone =
    resolved === 'flat'
      ? 'text-ink-3'
      : (inverted ? resolved === 'down' : resolved === 'up')
        ? 'text-up'
        : 'text-down';

  return (
    <span className={clsx('inline-flex items-baseline gap-1 text-[13px]', className)}>
      <Icon className={clsx('size-3 self-center', tone)} aria-hidden="true" />
      <span className={clsx('tnum font-mono font-medium', tone)}>
        {percent === undefined ? '—' : formatSignedPercent(percent)}
      </span>
      {label ? <span className="text-ink-3">{label}</span> : null}
    </span>
  );
}
