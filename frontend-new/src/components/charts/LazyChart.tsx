import { Suspense, lazy } from 'react';
import type { EChartsOption } from 'echarts';
import { Skeleton } from '../ui/Skeleton';

/* echarts is the largest dependency in the app. Loading it only when a chart
   is actually on screen keeps the Data page and an empty Ask page light. */
const EChart = lazy(() =>
  import('./EChart').then((module) => ({ default: module.EChart })),
);

interface LazyChartProps {
  option: EChartsOption;
  height: number;
  description: string;
}

export function LazyChart({ option, height, description }: LazyChartProps) {
  return (
    <Suspense fallback={<Skeleton className="w-full" style={{ height }} />}>
      <EChart option={option} height={height} description={description} />
    </Suspense>
  );
}
