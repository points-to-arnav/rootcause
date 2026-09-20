interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  tone?: 'up' | 'down' | 'flat';
}

const strokes = {
  up: '#3fb47f',
  down: '#e5606b',
  flat: '#6b7480',
} as const;

/** A plain SVG trend line. Inline enough not to pull echarts into a KPI tile. */
export function Sparkline({ values, width = 96, height = 26, tone = 'flat' }: SparklineProps) {
  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);

  const points = values.map((value, index) => {
    const x = index * step;
    const y = height - 2 - ((value - min) / span) * (height - 4);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      fill="none"
      aria-hidden="true"
      className="overflow-visible"
    >
      <polyline
        points={points.join(' ')}
        stroke={strokes[tone]}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
