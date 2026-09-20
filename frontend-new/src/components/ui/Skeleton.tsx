import clsx from 'clsx';
import type { CSSProperties } from 'react';

export function Skeleton({
  className,
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return <div className={clsx('shimmer rounded-sm', className)} style={style} aria-hidden="true" />;
}

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={clsx('space-y-2', className)} aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton key={index} className={clsx('h-3', index === lines - 1 ? 'w-2/5' : 'w-full')} />
      ))}
    </div>
  );
}
