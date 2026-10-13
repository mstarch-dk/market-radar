/** A tiny line of weekly closes (rebased to 100), coloured by its direction over the window. */
export function Sparkline({ values, width = 120, height = 32 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return null;
  const lo = Math.min(...values), hi = Math.max(...values);
  const span = hi - lo || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * width},${height - 2 - ((v - lo) / span) * (height - 4)}`).join(" ");
  const up = values[values.length - 1]! >= values[0]!;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="spark" aria-label="Last 6 months, weekly">
      <polyline points={pts} fill="none" stroke={up ? "var(--pos)" : "var(--neg)"} strokeWidth={1.5} strokeLinejoin="round" />
    </svg>
  );
}
