'use client';

/**
 * ADR-274 D9: Production chart renderer using Recharts.
 *
 * Replaces the stub ChartRenderer. Supports bar, line, area, pie, donut.
 * Responsive container with tooltip and legend.
 *
 * Chart type selection guide:
 * - area:  Real-time / streaming data, or trend data with filled backdrop.
 *          Use bright pulse colors (cyan, emerald). fillOpacity 0.2 by default.
 * - line:  Time-series forecasts (solid actual, dashed forecast), or multi-series
 *          comparisons. Distinct colors per series, no dots by default.
 * - bar:   Categorical comparisons, rankings, discrete buckets.
 * - pie/donut: Part-of-whole breakdowns (budget splits, status distributions).
 */

import { dynamicRecharts } from '@/lib/charts/recharts';
import { BarChart3 } from 'lucide-react';

import type { ChartDefinition } from './types';

const Area = dynamicRecharts('Area');
const AreaChart = dynamicRecharts('AreaChart');
const Bar = dynamicRecharts('Bar');
const BarChart = dynamicRecharts('BarChart');
const CartesianGrid = dynamicRecharts('CartesianGrid');
const Cell = dynamicRecharts('Cell');
const Legend = dynamicRecharts('Legend');
const Line = dynamicRecharts('Line');
const LineChart = dynamicRecharts('LineChart');
const Pie = dynamicRecharts('Pie');
const PieChart = dynamicRecharts('PieChart');
const ResponsiveContainer = dynamicRecharts('ResponsiveContainer');
const Tooltip = dynamicRecharts('Tooltip');
const XAxis = dynamicRecharts('XAxis');
const YAxis = dynamicRecharts('YAxis');

/** Default animation duration (ms) for chart transitions */
const ANIMATION_DURATION = 300;

/**
 * Augur accent palette — ordered for visual distinction across series.
 * cyan first (primary accent), then emerald, amber, rose, violet, orange, blue, pink.
 */
const CHART_COLORS = [
  'hsl(var(--chart-1))',
  'hsl(var(--chart-2))',
  'hsl(var(--chart-3))',
  'hsl(var(--chart-4))',
  'hsl(var(--chart-5))',
];

const COLOR_MAP: Record<string, string> = {
  cyan: 'hsl(var(--chart-1))',
  emerald: 'hsl(var(--chart-2))',
  green: 'hsl(var(--chart-2))',
  amber: 'hsl(var(--chart-3))',
  yellow: 'hsl(var(--chart-3))',
  red: 'hsl(var(--chart-4))',
  rose: 'hsl(var(--chart-4))',
  purple: 'hsl(var(--chart-5))',
  violet: 'hsl(var(--chart-5))',
  indigo: 'hsl(var(--chart-5))',
  blue: 'hsl(var(--chart-1))',
  teal: 'hsl(var(--chart-2))',
  orange: 'hsl(var(--chart-3))',
  pink: 'hsl(var(--chart-4))',
};

const AXIS_TICK_PROPS = { fontSize: 12, fill: 'var(--text-muted, #9ca3af)' };

function getPieCellKey(
  entry: Record<string, unknown>,
  chart: ChartDefinition,
): string {
  return `${String(entry[chart.x_field] ?? 'segment')}:${String(
    entry[chart.y_field] ?? 'value',
  )}`;
}

interface RechartsRendererProps {
  data: Record<string, unknown>[];
  chart: ChartDefinition;
}

export function RechartsRenderer({ data, chart }: RechartsRendererProps) {
  const height = chart.height ?? 300;
  const mainColor = chart.color ? (COLOR_MAP[chart.color] ?? chart.color) : CHART_COLORS[0];

  if (data.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border,#e5e7eb)]"
        style={{ height }}
      >
        <BarChart3 className="size-8 text-[var(--text-muted,#9ca3af)]" />
        <p className="mt-2 text-sm text-[var(--text-muted,#9ca3af)]">No chart data</p>
      </div>
    );
  }

  // Pie / Donut
  if (chart.type === 'pie' || chart.type === 'donut') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={data}
            dataKey={chart.y_field}
            nameKey={chart.x_field}
            cx="50%"
            cy="50%"
            outerRadius={chart.type === 'donut' ? 100 : 120}
            innerRadius={chart.type === 'donut' ? 60 : 0}
            label={({ name, percent }: { name: string; percent: number }) =>
              `${name} ${(percent * 100).toFixed(0)}%`
            }
            animationDuration={ANIMATION_DURATION}
          >
            {data.map((entry, idx) => (
              <Cell
                key={getPieCellKey(entry, chart)}
                fill={CHART_COLORS[idx % CHART_COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  // Shared axis/grid props for dark-theme-aware rendering
  const gridStroke = 'var(--border, #e5e7eb)';
  const axisStroke = 'var(--text-muted, #9ca3af)';
  // Bar chart
  if (chart.type === 'bar') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis dataKey={chart.x_field} tick={AXIS_TICK_PROPS} stroke={axisStroke} />
          <YAxis tick={AXIS_TICK_PROPS} stroke={axisStroke} />
          <Tooltip />
          <Legend />
          <Bar
            dataKey={chart.y_field}
            fill={mainColor}
            radius={[4, 4, 0, 0]}
            animationDuration={ANIMATION_DURATION}
          />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  // Area chart — 20% opacity fill for clean trend backdrop
  if (chart.type === 'area') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis dataKey={chart.x_field} tick={AXIS_TICK_PROPS} stroke={axisStroke} />
          <YAxis tick={AXIS_TICK_PROPS} stroke={axisStroke} />
          <Tooltip />
          <Legend />
          <Area
            type="monotone"
            dataKey={chart.y_field}
            stroke={mainColor}
            strokeWidth={2}
            fill={mainColor}
            fillOpacity={0.2}
            dot={false}
            activeDot={{ r: 5, strokeWidth: 0 }}
            animationDuration={ANIMATION_DURATION}
          />
        </AreaChart>
      </ResponsiveContainer>
    );
  }

  // Line chart (default) — clean lines, dots only on hover
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
        <XAxis dataKey={chart.x_field} tick={AXIS_TICK_PROPS} stroke={axisStroke} />
        <YAxis tick={AXIS_TICK_PROPS} stroke={axisStroke} />
        <Tooltip />
        <Legend />
        <Line
          type="monotone"
          dataKey={chart.y_field}
          stroke={mainColor}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 5, strokeWidth: 0 }}
          animationDuration={ANIMATION_DURATION}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
