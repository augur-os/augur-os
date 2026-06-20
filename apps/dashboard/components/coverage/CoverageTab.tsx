"use client";

import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import { dynamicRecharts } from "@/lib/charts/recharts";
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  TestTube2,
  FileCode,
} from "lucide-react";

const CartesianGrid = dynamicRecharts("CartesianGrid");
const Legend = dynamicRecharts("Legend");
const Line = dynamicRecharts("Line");
const LineChart = dynamicRecharts("LineChart");
const ResponsiveContainer = dynamicRecharts("ResponsiveContainer");
const Tooltip = dynamicRecharts("Tooltip");
const XAxis = dynamicRecharts("XAxis");
const YAxis = dynamicRecharts("YAxis");

interface CoverageEntry {
  timestamp: string;
  jest: {
    statements: number;
    branches: number;
    functions: number;
    lines: number;
  } | null;
  python: {
    statements: number;
    lines: number;
    missing: number;
    covered: number;
  } | null;
  test_counts: { python: number; typescript: number; total: number };
}

interface CoverageData {
  latest: CoverageEntry | null;
  history: CoverageEntry[];
  trends: { jest: string; python: string };
  totalEntries: number;
}

interface ChartRow {
  date: string;
  jest: number | null;
  python: number | null;
  tests: number | null;
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === "up")
    return <TrendingUp className="size-4 text-emerald-400" />;
  if (trend === "down")
    return <TrendingDown className="size-4 text-red-400" />;
  return <Minus className="size-4 text-zinc-400" />;
}

function StatCard({
  label,
  value,
  trend,
  icon: Icon,
}: {
  label: string;
  value: string;
  trend?: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="glass-panel p-4 rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-zinc-400">{label}</span>
        <Icon className="size-4 text-zinc-500" />
      </div>
      <div className="flex items-center gap-2">
        <span className="text-2xl font-bold text-zinc-100">{value}</span>
        {trend ? <TrendIcon trend={trend} /> : null}
      </div>
    </div>
  );
}

function CoverageLoading() {
  return (
    <div className="glass-panel p-6 animate-pulse">
      <div className="h-8 bg-zinc-800 rounded w-48 mb-4" />
      <div className="h-64 bg-zinc-800 rounded" />
    </div>
  );
}

function CoverageError({ error }: { error: string }) {
  return (
    <div className="glass-panel p-6">
      <p className="text-red-400">Failed to load coverage data: {error}</p>
    </div>
  );
}

function CoverageEmpty() {
  return (
    <div className="glass-panel p-6">
      <h2 className="text-lg font-semibold text-zinc-100 mb-2">
        Coverage Tracking
      </h2>
      <p className="text-zinc-400">
        No coverage data available yet. Coverage will be collected after the
        first nightly run.
      </p>
      <p className="text-zinc-500 text-sm mt-2">
        Run{" "}
        <code className="text-cyan-400">
          python .github/scripts/coverage_tracker.py --save
        </code>{" "}
        to collect initial data.
      </p>
    </div>
  );
}

function buildChartData(history: CoverageEntry[]): ChartRow[] {
  return history.map((entry) => ({
    date: new Date(entry.timestamp).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    }),
    jest: entry.jest?.lines ?? null,
    python: entry.python?.statements ?? null,
    tests: entry.test_counts?.total ?? null,
  }));
}

function CoverageSummary({
  latest,
  trends,
}: {
  latest: CoverageEntry;
  trends: CoverageData["trends"];
}) {
  const jestCov = latest.jest?.lines ?? 0;
  const pythonCov = latest.python?.statements ?? 0;
  const testCount = latest.test_counts?.total ?? 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <StatCard
        label="TypeScript Coverage"
        value={`${jestCov.toFixed(1)}%`}
        trend={trends.jest}
        icon={FileCode}
      />
      <StatCard
        label="Python Coverage"
        value={`${pythonCov.toFixed(1)}%`}
        trend={trends.python}
        icon={FileCode}
      />
      <StatCard
        label="Total Test Files"
        value={String(testCount)}
        icon={TestTube2}
      />
    </div>
  );
}

function CoverageTrendChart({ chartData }: { chartData: ChartRow[] }) {
  return (
    <div className="glass-panel p-6 rounded-lg">
      <div className="flex items-center gap-2 mb-4">
        <BarChart3 className="size-5 text-cyan-400" />
        <h3 className="text-lg font-semibold text-zinc-100">
          Coverage Trend (Last 30 Days)
        </h3>
      </div>

      {chartData.length > 1 ? (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="date" stroke="hsl(var(--muted-foreground))" fontSize={12} />
            <YAxis
              domain={[0, 100]}
              stroke="hsl(var(--muted-foreground))"
              fontSize={12}
              tickFormatter={(v: number) => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                background: "hsl(var(--popover))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "8px",
              }}
              labelStyle={{ color: "hsl(var(--popover-foreground))" }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="jest"
              stroke="hsl(var(--chart-1))"
              strokeWidth={2}
              name="TypeScript"
              dot={false}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="python"
              stroke="hsl(var(--chart-2))"
              strokeWidth={2}
              name="Python"
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-zinc-500 text-center py-12">
          Need at least 2 data points to show trends. Check back after the next
          nightly run.
        </p>
      )}
    </div>
  );
}

function CoverageDetails({
  latest,
  totalEntries,
}: {
  latest: CoverageEntry;
  totalEntries: number;
}) {
  return (
    <div className="glass-panel p-6 rounded-lg">
      <h3 className="text-lg font-semibold text-zinc-100 mb-4">Details</h3>
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-zinc-400">Last Updated</span>
          <p className="text-zinc-200">
            {new Date(latest.timestamp).toLocaleString()}
          </p>
        </div>
        <div>
          <span className="text-zinc-400">Data Points</span>
          <p className="text-zinc-200">{totalEntries} entries</p>
        </div>

        {latest.jest ? (
          <>
            <div>
              <span className="text-zinc-400">TS Statements</span>
              <p className="text-zinc-200">
                {latest.jest.statements.toFixed(1)}%
              </p>
            </div>
            <div>
              <span className="text-zinc-400">TS Branches</span>
              <p className="text-zinc-200">
                {latest.jest.branches.toFixed(1)}%
              </p>
            </div>
            <div>
              <span className="text-zinc-400">TS Functions</span>
              <p className="text-zinc-200">
                {latest.jest.functions.toFixed(1)}%
              </p>
            </div>
          </>
        ) : null}

        {latest.python ? (
          <>
            <div>
              <span className="text-zinc-400">Python Covered Lines</span>
              <p className="text-zinc-200">{latest.python.covered}</p>
            </div>
            <div>
              <span className="text-zinc-400">Python Missing Lines</span>
              <p className="text-zinc-200">{latest.python.missing}</p>
            </div>
          </>
        ) : null}

        <div>
          <span className="text-zinc-400">Python Tests</span>
          <p className="text-zinc-200">
            {latest.test_counts?.python ?? 0} files
          </p>
        </div>
        <div>
          <span className="text-zinc-400">TypeScript Tests</span>
          <p className="text-zinc-200">
            {latest.test_counts?.typescript ?? 0} files
          </p>
        </div>
      </div>
    </div>
  );
}

function CoverageContent({ data }: { data: CoverageData }) {
  if (!data.latest) {
    return <CoverageEmpty />;
  }

  const chartData = buildChartData(data.history);

  return (
    <div className="space-y-6">
      <CoverageSummary latest={data.latest} trends={data.trends} />
      <CoverageTrendChart chartData={chartData} />
      <CoverageDetails latest={data.latest} totalEntries={data.totalEntries} />
    </div>
  );
}

export default function CoverageTab() {
  const { data, loading, error } = useMcpQuery<CoverageData>(
    "coverage-data",
    "file-read",
    "live",
    { args: { path: "metrics/coverage_history.json", repo: "runtime" } },
  );

  if (loading) {
    return <CoverageLoading />;
  }

  if (error) {
    return <CoverageError error={error} />;
  }

  if (!data) {
    return <CoverageEmpty />;
  }

  return <CoverageContent data={data} />;
}
