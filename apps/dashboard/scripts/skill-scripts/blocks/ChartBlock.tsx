'use client';

import { GlassCard } from '@/components/ui/GlassCard';
import { keyedRenderItems } from '@/lib/stable-render-key';

interface DataPoint {
  label: string;
  value: number;
}

interface ChartBlockProps {
  chartType?: 'line' | 'bar' | 'pie';
  data?: DataPoint[];
  title?: string;
}

const DEFAULT_DATA: DataPoint[] = [
  { label: 'Mon', value: 40 },
  { label: 'Tue', value: 65 },
  { label: 'Wed', value: 55 },
  { label: 'Thu', value: 80 },
  { label: 'Fri', value: 70 },
];

const CHART_COLORS = [
  'hsl(var(--chart-1))',
  'hsl(var(--chart-2))',
  'hsl(var(--chart-3))',
  'hsl(var(--chart-4))',
  'hsl(var(--chart-5))',
  'hsl(var(--chart-1))',
  'hsl(var(--chart-2))',
];

// ---------------------------------------------------------------------------
// Bar chart (horizontal bars)
// ---------------------------------------------------------------------------
function BarChart({ data }: { data: DataPoint[] }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="flex flex-col gap-2 w-full">
      {keyedRenderItems(data, (d) => d.label).map(({ item: d, key }, i) => (
        <div key={key} className="flex items-center gap-2">
          <span
            className="text-xs w-14 shrink-0 text-right truncate"
            style={{ color: 'var(--text-muted)' }}
          >
            {d.label}
          </span>
          <div
            className="flex-1 rounded-full overflow-hidden"
            style={{ background: 'var(--border-color)', height: '10px' }}
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${(d.value / max) * 100}%`,
                background: CHART_COLORS[i % CHART_COLORS.length],
              }}
            />
          </div>
          <span
            className="text-xs w-8 shrink-0 tabular-nums"
            style={{ color: 'var(--text-secondary)' }}
          >
            {d.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Line chart (SVG polyline)
// ---------------------------------------------------------------------------
function LineChart({ data }: { data: DataPoint[] }) {
  const W = 300;
  const H = 120;
  const PAD = 16;
  const max = Math.max(...data.map((d) => d.value), 1);
  const min = Math.min(...data.map((d) => d.value), 0);
  const range = max - min || 1;

  const points = data.map((d, i) => {
    const x = PAD + (i / Math.max(data.length - 1, 1)) * (W - PAD * 2);
    const y = H - PAD - ((d.value - min) / range) * (H - PAD * 2);
    return { x, y, ...d };
  });

  const polyline = points.map((p) => `${p.x},${p.y}`).join(' ');
  const area = [
    `M${points[0].x},${H - PAD}`,
    ...points.map((p) => `L${p.x},${p.y}`),
    `L${points[points.length - 1].x},${H - PAD}`,
    'Z',
  ].join(' ');

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: '120px' }}>
      <defs>
        <linearGradient id="line-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="hsl(var(--chart-1))" stopOpacity="0.25" />
          <stop offset="100%" stopColor="hsl(var(--chart-1))" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#line-fill)" />
      <polyline
        points={polyline}
        fill="none"
        stroke="hsl(var(--chart-1))"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {keyedRenderItems(points, (p) => `${p.label}:${p.x}:${p.y}:dot`).map(({ item: p, key }) => (
        <circle key={key} cx={p.x} cy={p.y} r="3" fill="hsl(var(--chart-1))" />
      ))}
      {keyedRenderItems(points, (p) => `${p.label}:${p.x}:${p.y}:label`).map(({ item: p, key }) => (
        <text
          key={key}
          x={p.x}
          y={H - 2}
          textAnchor="middle"
          fontSize="9"
          fill="var(--text-muted)"
        >
          {p.label}
        </text>
      ))}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Pie chart (SVG segments)
// ---------------------------------------------------------------------------
function PieChart({ data }: { data: DataPoint[] }) {
  const SIZE = 120;
  const R = 48;
  const CX = SIZE / 2;
  const CY = SIZE / 2;
  const total = data.reduce((s, d) => s + d.value, 0) || 1;

  const segments = data.map((d, i) => {
    const startAngle =
      -Math.PI / 2 +
      data.slice(0, i).reduce((s, prev) => s + (prev.value / total) * 2 * Math.PI, 0);
    const sweep = (d.value / total) * 2 * Math.PI;
    const x1 = CX + R * Math.cos(startAngle);
    const y1 = CY + R * Math.sin(startAngle);
    const x2 = CX + R * Math.cos(startAngle + sweep);
    const y2 = CY + R * Math.sin(startAngle + sweep);
    const largeArc = sweep > Math.PI ? 1 : 0;
    return {
      d: `M${CX},${CY} L${x1},${y1} A${R},${R} 0 ${largeArc} 1 ${x2},${y2} Z`,
      color: CHART_COLORS[i % CHART_COLORS.length],
      label: d.label,
      value: d.value,
    };
  });

  return (
    <div className="flex items-center gap-4">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        style={{ width: '120px', height: '120px', flexShrink: 0 }}
      >
        {segments.map((seg) => (
          <path key={seg.d} d={seg.d} fill={seg.color} stroke="var(--bg-card)" strokeWidth="1" />
        ))}
      </svg>
      <div className="flex flex-col gap-1.5 text-xs min-w-0">
        {segments.map((seg) => (
          <div key={`${seg.label}:${seg.value}:${seg.d}`} className="flex items-center gap-1.5 truncate">
            <span
              className="w-2.5 h-2.5 rounded-sm shrink-0"
              style={{ background: seg.color }}
            />
            <span style={{ color: 'var(--text-secondary)' }} className="truncate">
              {seg.label}
            </span>
            <span
              className="ml-auto pl-2 tabular-nums shrink-0"
              style={{ color: 'var(--text-muted)' }}
            >
              {seg.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function ChartBlock({
  chartType = 'bar',
  data = DEFAULT_DATA,
  title,
}: ChartBlockProps) {
  return (
    <GlassCard className="p-4">
      {title && (
        <div className="mb-3 text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
          {title}
        </div>
      )}
      {chartType === 'bar' && <BarChart data={data} />}
      {chartType === 'line' && <LineChart data={data} />}
      {chartType === 'pie' && <PieChart data={data} />}
    </GlassCard>
  );
}
