# Auto-Detect Blocks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `metrics-dashboard` block and enhance `card-grid` with convention-based auto-detection, enabling ~16 custom TSX pages to become YAML configs.

**Architecture:** Shared auto-detect engine (`auto-detect.ts`) provides pure functions for field role detection, value formatting, and badge coloring. `MetricsDashboardBlock` uses it to render multi-source metric cards. Existing `CardGridBlock` gains auto-detection for item lists. Both blocks read MCP data via `useBlockData`.

**Tech Stack:** React 19, TypeScript, Tanstack Query (via `useBlockData`), lucide-react icons, existing GlassCard/Badge components.

**Spec:** `docs/superpowers/specs/2026-03-29-auto-detect-blocks-design.md`

---

### Task 1: Auto-detect engine — field role detection

**Files:**
- Create: `apps/dashboard/lib/blocks/auto-detect.ts`
- Create: `apps/dashboard/lib/blocks/__tests__/auto-detect.test.ts`

- [ ] **Step 1: Write failing tests for `detectFieldRole`**

```typescript
// apps/dashboard/lib/blocks/__tests__/auto-detect.test.ts
import { detectFieldRole } from '../auto-detect';

describe('detectFieldRole', () => {
  // Title fields
  it('detects "name" as title', () => {
    expect(detectFieldRole('name', 'Daemon')).toBe('title');
  });
  it('detects "title" as title', () => {
    expect(detectFieldRole('title', 'My Page')).toBe('title');
  });
  it('detects "label" as title', () => {
    expect(detectFieldRole('label', 'X')).toBe('title');
  });

  // Badge fields
  it('detects "status" as badge', () => {
    expect(detectFieldRole('status', 'running')).toBe('badge');
  });
  it('detects "state" as badge', () => {
    expect(detectFieldRole('state', 'active')).toBe('badge');
  });
  it('detects "phase" as badge', () => {
    expect(detectFieldRole('phase', 'review')).toBe('badge');
  });

  // Timestamp fields
  it('detects "created_at" as timestamp', () => {
    expect(detectFieldRole('created_at', '2026-03-29')).toBe('timestamp');
  });
  it('detects "updated" as timestamp', () => {
    expect(detectFieldRole('updated', '2026-03-29')).toBe('timestamp');
  });
  it('detects "timestamp" as timestamp', () => {
    expect(detectFieldRole('timestamp', '2026-03-29')).toBe('timestamp');
  });

  // Duration fields
  it('detects "uptime_seconds" as duration', () => {
    expect(detectFieldRole('uptime_seconds', 3600)).toBe('duration');
  });
  it('detects "duration" as duration', () => {
    expect(detectFieldRole('duration', 120)).toBe('duration');
  });

  // Percentage fields
  it('detects "fix_rate" as metric-pct', () => {
    expect(detectFieldRole('fix_rate', 0.85)).toBe('metric-pct');
  });
  it('detects "success_percent" as metric-pct', () => {
    expect(detectFieldRole('success_percent', 95)).toBe('metric-pct');
  });

  // Size fields
  it('detects "file_bytes" as size', () => {
    expect(detectFieldRole('file_bytes', 1024)).toBe('size');
  });

  // Metric fields
  it('detects "error_count" as metric', () => {
    expect(detectFieldRole('error_count', 5)).toBe('metric');
  });
  it('detects "total" as metric', () => {
    expect(detectFieldRole('total', 42)).toBe('metric');
  });

  // Boolean
  it('detects boolean value as boolean', () => {
    expect(detectFieldRole('installed', true)).toBe('boolean');
  });

  // Nested object
  it('detects nested object as nested', () => {
    expect(detectFieldRole('config', { a: 1 })).toBe('nested');
  });

  // Array
  it('detects array as array', () => {
    expect(detectFieldRole('items', [1, 2])).toBe('array');
  });

  // Fallback
  it('falls back to detail for unknown fields', () => {
    expect(detectFieldRole('hostname', 'localhost')).toBe('detail');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/dashboard && npx jest lib/blocks/__tests__/auto-detect.test.ts --no-coverage`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `detectFieldRole`**

```typescript
// apps/dashboard/lib/blocks/auto-detect.ts

export type FieldRole =
  | 'title' | 'subtitle' | 'badge' | 'icon'
  | 'timestamp' | 'duration' | 'size'
  | 'metric' | 'metric-pct'
  | 'boolean' | 'nested' | 'array' | 'longtext'
  | 'detail';

const TITLE_KEYS = new Set(['name', 'title', 'label', 'subject', 'skill']);
const SUBTITLE_KEYS = new Set(['description', 'summary', 'detail', 'subtitle']);
const BADGE_KEYS = new Set(['status', 'state', 'phase', 'type', 'category']);
const ICON_KEYS = new Set(['icon', 'emoji']);
const TIMESTAMP_KEYS = new Set(['created', 'updated', 'timestamp']);
const METRIC_KEYS = new Set(['count', 'total', 'errors', 'warnings']);

export function detectFieldRole(key: string, value: unknown): FieldRole {
  const k = key.toLowerCase();

  // Exact key matches (highest priority)
  if (TITLE_KEYS.has(k)) return 'title';
  if (SUBTITLE_KEYS.has(k)) return 'subtitle';
  if (BADGE_KEYS.has(k)) return 'badge';
  if (ICON_KEYS.has(k)) return 'icon';
  if (TIMESTAMP_KEYS.has(k)) return 'timestamp';
  if (METRIC_KEYS.has(k)) return 'metric';

  // Suffix patterns
  if (k.endsWith('_at') || k.endsWith('_date')) return 'timestamp';
  if (k.endsWith('_percent') || k.endsWith('_rate') || k.endsWith('_pct') || k === 'ratio') return 'metric-pct';
  if (k.endsWith('_seconds') || k.endsWith('_ms') || k === 'uptime' || k === 'duration') return 'duration';
  if (k.endsWith('_bytes') || k.endsWith('_size') || k.endsWith('_mb')) return 'size';
  if (k.endsWith('_count')) return 'metric';

  // Value-based detection
  if (typeof value === 'boolean') return 'boolean';
  if (Array.isArray(value)) return 'array';
  if (value !== null && typeof value === 'object') return 'nested';
  if (typeof value === 'string' && value.length > 100) return 'longtext';

  return 'detail';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/dashboard && npx jest lib/blocks/__tests__/auto-detect.test.ts --no-coverage`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/blocks/auto-detect.ts apps/dashboard/lib/blocks/__tests__/auto-detect.test.ts
git commit -m "feat(blocks): add auto-detect engine — detectFieldRole with convention-based field detection"
```

---

### Task 2: Auto-detect engine — value formatting and badge colors

**Files:**
- Modify: `apps/dashboard/lib/blocks/auto-detect.ts`
- Modify: `apps/dashboard/lib/blocks/__tests__/auto-detect.test.ts`

- [ ] **Step 1: Write failing tests for `autoFormat` and `badgeColor`**

```typescript
// Append to apps/dashboard/lib/blocks/__tests__/auto-detect.test.ts
import { autoFormat, badgeColor, detectFields } from '../auto-detect';

describe('autoFormat', () => {
  it('formats timestamp as relative time', () => {
    const recent = new Date(Date.now() - 60_000).toISOString();
    expect(autoFormat(recent, 'timestamp')).toMatch(/1 min/);
  });
  it('formats duration seconds', () => {
    expect(autoFormat(3661, 'duration')).toBe('1h 1m');
  });
  it('formats large duration', () => {
    expect(autoFormat(172800, 'duration')).toBe('2d 0h');
  });
  it('formats small duration', () => {
    expect(autoFormat(45, 'duration')).toBe('45s');
  });
  it('formats percentage', () => {
    expect(autoFormat(0.857, 'metric-pct')).toBe('85.7%');
  });
  it('formats percentage already in percent form', () => {
    expect(autoFormat(85.7, 'metric-pct')).toBe('85.7%');
  });
  it('formats bytes', () => {
    expect(autoFormat(1536, 'size')).toBe('1.5 KB');
  });
  it('formats megabytes', () => {
    expect(autoFormat(2_500_000, 'size')).toBe('2.4 MB');
  });
  it('formats boolean true', () => {
    expect(autoFormat(true, 'boolean')).toBe('Yes');
  });
  it('formats boolean false', () => {
    expect(autoFormat(false, 'boolean')).toBe('No');
  });
  it('formats array as count', () => {
    expect(autoFormat([1, 2, 3], 'array')).toBe('3 items');
  });
  it('formats detail as string', () => {
    expect(autoFormat('hello', 'detail')).toBe('hello');
  });
  it('formats number metric', () => {
    expect(autoFormat(1234, 'metric')).toBe('1,234');
  });
  it('handles null', () => {
    expect(autoFormat(null, 'detail')).toBe('—');
  });
  it('handles undefined', () => {
    expect(autoFormat(undefined, 'detail')).toBe('—');
  });
});

describe('badgeColor', () => {
  it('returns green for running', () => {
    expect(badgeColor('running')).toBe('green');
  });
  it('returns green for active', () => {
    expect(badgeColor('active')).toBe('green');
  });
  it('returns red for error', () => {
    expect(badgeColor('error')).toBe('red');
  });
  it('returns red for failed', () => {
    expect(badgeColor('failed')).toBe('red');
  });
  it('returns amber for pending', () => {
    expect(badgeColor('pending')).toBe('amber');
  });
  it('returns amber for warning', () => {
    expect(badgeColor('warning')).toBe('amber');
  });
  it('returns gray for unknown', () => {
    expect(badgeColor('unknown')).toBe('gray');
  });
  it('returns blue for unrecognized', () => {
    expect(badgeColor('custom-value')).toBe('blue');
  });
  it('is case-insensitive', () => {
    expect(badgeColor('Running')).toBe('green');
  });
});

describe('detectFields', () => {
  it('detects roles for all fields in an object', () => {
    const obj = { name: 'Test', status: 'ok', created_at: '2026-01-01', count: 5 };
    const fields = detectFields(obj);
    expect(fields.get('name')).toBe('title');
    expect(fields.get('status')).toBe('badge');
    expect(fields.get('created_at')).toBe('timestamp');
    expect(fields.get('count')).toBe('metric');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/dashboard && npx jest lib/blocks/__tests__/auto-detect.test.ts --no-coverage`
Expected: FAIL — `autoFormat`, `badgeColor`, `detectFields` not exported

- [ ] **Step 3: Implement `autoFormat`, `badgeColor`, `detectFields`**

Append to `apps/dashboard/lib/blocks/auto-detect.ts`:

```typescript
// --- Value formatting ---

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  if (isNaN(then)) return dateStr;
  const diffMs = now - then;
  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${Math.round(seconds % 60)}s`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ${minutes % 60}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatPercent(value: number): string {
  // If value is 0-1, treat as ratio; if >1, treat as already a percentage
  const pct = value <= 1 && value >= 0 ? value * 100 : value;
  return `${Number(pct.toFixed(1))}%`;
}

function formatNumber(value: number): string {
  return value.toLocaleString('en-US');
}

export function autoFormat(value: unknown, role: FieldRole): string {
  if (value == null) return '—';

  switch (role) {
    case 'timestamp':
      return typeof value === 'string' ? relativeTime(value) : String(value);
    case 'duration':
      return typeof value === 'number' ? formatDuration(value) : String(value);
    case 'size':
      return typeof value === 'number' ? formatSize(value) : String(value);
    case 'metric-pct':
      return typeof value === 'number' ? formatPercent(value) : String(value);
    case 'metric':
      return typeof value === 'number' ? formatNumber(value) : String(value);
    case 'boolean':
      return value ? 'Yes' : 'No';
    case 'array':
      return Array.isArray(value) ? `${value.length} items` : String(value);
    case 'nested':
      return typeof value === 'object' ? `${Object.keys(value as object).length} fields` : String(value);
    default:
      return String(value);
  }
}

// --- Badge colors ---

const GREEN_VALUES = new Set(['running', 'active', 'success', 'healthy', 'ok', 'true', 'enabled', 'connected', 'available', 'pass', 'passed']);
const RED_VALUES = new Set(['error', 'failed', 'critical', 'down', 'false', 'offline', 'unavailable', 'blocked', 'fail']);
const AMBER_VALUES = new Set(['pending', 'warning', 'degraded', 'paused', 'review', 'waiting', 'stale', 'partial']);
const GRAY_VALUES = new Set(['idle', 'unknown', 'disabled', 'stopped', 'archived', 'draft', 'inactive']);

export type BadgeColor = 'green' | 'red' | 'amber' | 'gray' | 'blue';

export function badgeColor(value: string): BadgeColor {
  const v = value.toLowerCase();
  if (GREEN_VALUES.has(v)) return 'green';
  if (RED_VALUES.has(v)) return 'red';
  if (AMBER_VALUES.has(v)) return 'amber';
  if (GRAY_VALUES.has(v)) return 'gray';
  return 'blue';
}

// --- Batch detection ---

export function detectFields(obj: Record<string, unknown>): Map<string, FieldRole> {
  const map = new Map<string, FieldRole>();
  for (const [key, value] of Object.entries(obj)) {
    map.set(key, detectFieldRole(key, value));
  }
  return map;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/dashboard && npx jest lib/blocks/__tests__/auto-detect.test.ts --no-coverage`
Expected: PASS (all ~30 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/lib/blocks/auto-detect.ts apps/dashboard/lib/blocks/__tests__/auto-detect.test.ts
git commit -m "feat(blocks): add autoFormat, badgeColor, detectFields to auto-detect engine"
```

---

### Task 3: MetricsDashboardBlock component

**Files:**
- Create: `apps/dashboard/components/blocks/types/MetricsDashboardBlock.tsx`
- Modify: `apps/dashboard/lib/blocks/block-resolver.ts`
- Modify: `apps/dashboard/lib/blocks/types.ts`

- [ ] **Step 1: Register the new block type**

In `apps/dashboard/lib/blocks/types.ts`, add `"metrics-dashboard"` to the `BlockType` union:

```typescript
export type BlockType =
  | "stat-card"
  // ... existing types ...
  | "widget"
  | "metrics-dashboard";
```

In `apps/dashboard/lib/blocks/block-resolver.ts`, add the dynamic import:

```typescript
"metrics-dashboard": dynamic(() => import("@/components/blocks/types/MetricsDashboardBlock")),
```

- [ ] **Step 2: Create the MetricsDashboardBlock component**

```typescript
// apps/dashboard/components/blocks/types/MetricsDashboardBlock.tsx
'use client';

import { useMemo } from 'react';
import * as LucideIcons from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import type { GlassCardColor } from '@/components/ui/GlassCard';
import { Badge } from '@/components/ui/Badge';
import type { BlockProps } from '@/lib/blocks/types';
import { useBlockData } from '@/lib/blocks/useBlockData';
import { detectFields, autoFormat, badgeColor } from '@/lib/blocks/auto-detect';
import type { FieldRole, BadgeColor } from '@/lib/blocks/auto-detect';

const ICONS = LucideIcons as unknown as Record<string, LucideIcon>;
const VALID_COLORS: Set<string> = new Set(['cyan', 'purple', 'emerald', 'amber', 'blue', 'rose', 'violet', 'pink']);

interface MetricsSource {
  mcp_tool: string;
  title?: string;
  icon?: string;
  color?: string;
  skill_id?: string;
}

interface MetricsDashboardConfig {
  title?: string;
  sources?: MetricsSource[];
  [key: string]: unknown;
}

const BADGE_VARIANT: Record<BadgeColor, 'success' | 'destructive' | 'outline' | 'default'> = {
  green: 'success',
  red: 'destructive',
  amber: 'outline',
  gray: 'outline',
  blue: 'default',
};

function smartLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, c => c.toUpperCase());
}

function SourceCard({ source }: { source: MetricsSource }) {
  const dataSource = useMemo(() => ({ mcpTool: source.mcp_tool }), [source.mcp_tool]);
  const config = useMemo(
    () => (source.skill_id ? { skillId: source.skill_id } : {}),
    [source.skill_id],
  );
  const { data, loading, error } = useBlockData(dataSource, config, 'metrics-dashboard');

  const iconName = source.icon || 'Activity';
  const IconComponent = ICONS[iconName] || LucideIcons.Activity;
  const color = (source.color && VALID_COLORS.has(source.color) ? source.color : 'cyan') as GlassCardColor;
  const title = source.title || source.mcp_tool.replace(/^get-/, '').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  if (loading) {
    return (
      <GlassCard color={color} icon={IconComponent} title={title}>
        <div className="space-y-3 animate-pulse">
          <div className="h-4 w-32 rounded bg-[var(--bg-secondary)]" />
          <div className="grid grid-cols-3 gap-3">
            <div className="h-16 rounded-xl bg-[var(--bg-secondary)]" />
            <div className="h-16 rounded-xl bg-[var(--bg-secondary)]" />
            <div className="h-16 rounded-xl bg-[var(--bg-secondary)]" />
          </div>
        </div>
      </GlassCard>
    );
  }

  if (error) {
    return (
      <GlassCard color={color} icon={IconComponent} title={title}>
        <p className="text-sm text-[var(--text-muted)]">Failed to load: {error}</p>
      </GlassCard>
    );
  }

  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return (
      <GlassCard color={color} icon={IconComponent} title={title}>
        <p className="text-sm text-[var(--text-muted)]">No data</p>
      </GlassCard>
    );
  }

  const obj = data as Record<string, unknown>;
  const fields = detectFields(obj);

  // Split fields into stat tiles (metrics, badges, timestamps, durations, booleans)
  // and detail rows (everything else)
  const statRoles: Set<FieldRole> = new Set(['metric', 'metric-pct', 'duration', 'size', 'badge', 'boolean', 'timestamp']);
  const stats: Array<{ key: string; role: FieldRole; value: unknown }> = [];
  const details: Array<{ key: string; role: FieldRole; value: unknown }> = [];

  for (const [key, role] of fields) {
    const value = obj[key];
    if (value == null) continue;
    if (role === 'nested' || role === 'array') {
      details.push({ key, role, value });
    } else if (statRoles.has(role)) {
      stats.push({ key, role, value });
    } else if (role !== 'title' && role !== 'subtitle' && role !== 'icon') {
      details.push({ key, role, value });
    }
  }

  return (
    <GlassCard color={color} icon={IconComponent} title={title}>
      {stats.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-3">
          {stats.map(({ key, role, value }) => (
            <div
              key={key}
              className="rounded-xl border border-[var(--border-color)]/50 bg-[var(--bg-secondary)]/40 p-3"
            >
              <p className="text-xs text-[var(--text-muted)] mb-1">{smartLabel(key)}</p>
              {role === 'badge' ? (
                <Badge variant={BADGE_VARIANT[badgeColor(String(value))]}>
                  {String(value)}
                </Badge>
              ) : (
                <p className="text-lg font-semibold text-[var(--text-primary)]">
                  {autoFormat(value, role)}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
      {details.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {details.slice(0, 6).map(({ key, role, value }) => (
            <div key={key} className="flex items-center justify-between text-sm">
              <span className="text-[var(--text-muted)]">{smartLabel(key)}</span>
              <span className="text-[var(--text-secondary)]">{autoFormat(value, role)}</span>
            </div>
          ))}
        </div>
      )}
    </GlassCard>
  );
}

export default function MetricsDashboardBlock({ config }: BlockProps<MetricsDashboardConfig>) {
  const sources = config.sources || [];

  if (sources.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)]">
        <p className="text-sm text-[var(--text-muted)]">No sources configured</p>
      </div>
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      {sources.map((source, i) => (
        <SourceCard key={source.mcp_tool + i} source={source} />
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Verify build passes**

Run: `cd apps/dashboard && pnpm run build:scripts && npx next build 2>&1 | grep -E "Compiled|Type error|Failed"`
Expected: `Compiled successfully`

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/components/blocks/types/MetricsDashboardBlock.tsx apps/dashboard/lib/blocks/block-resolver.ts apps/dashboard/lib/blocks/types.ts
git commit -m "feat(blocks): add metrics-dashboard block — multi-source auto-formatted metric cards"
```

---

### Task 4: Enhance CardGridBlock with auto-detection

**Files:**
- Modify: `apps/dashboard/components/blocks/types/CardGridBlock.tsx`

- [ ] **Step 1: Add auto-detection to CardGridBlock**

At the top of `CardGridBlock.tsx`, add the import:

```typescript
import { detectFields, autoFormat, badgeColor } from '@/lib/blocks/auto-detect';
import type { FieldRole, BadgeColor } from '@/lib/blocks/auto-detect';
import { Badge } from '@/components/ui/Badge';
```

Add a field role cache hook inside the component (after data is resolved):

```typescript
// Auto-detect field roles from first item
const fieldRoles = useMemo(() => {
  if (!items || items.length === 0) return new Map<string, FieldRole>();
  const first = items[0] as Record<string, unknown>;
  return detectFields(first);
}, [items]);

// Determine card structure from roles
const titleField = useMemo(() => {
  for (const [key, role] of fieldRoles) if (role === 'title') return key;
  return null;
}, [fieldRoles]);

const subtitleField = useMemo(() => {
  for (const [key, role] of fieldRoles) if (role === 'subtitle') return key;
  return null;
}, [fieldRoles]);

const badgeField = useMemo(() => {
  for (const [key, role] of fieldRoles) if (role === 'badge') return key;
  return null;
}, [fieldRoles]);

const timestampField = useMemo(() => {
  for (const [key, role] of fieldRoles) if (role === 'timestamp') return key;
  return null;
}, [fieldRoles]);

const detailFields = useMemo(() => {
  const skip = new Set([titleField, subtitleField, badgeField, timestampField].filter(Boolean));
  const result: string[] = [];
  for (const [key, role] of fieldRoles) {
    if (skip.has(key)) continue;
    if (role === 'nested' || role === 'array' || role === 'icon') continue;
    result.push(key);
    if (result.length >= 4) break;
  }
  return result;
}, [fieldRoles, titleField, subtitleField, badgeField, timestampField]);
```

Update the card rendering section to use auto-detected fields. In the card render function, replace the generic field dump with role-aware rendering:

```typescript
// Inside the card rendering (grid/card/list view), replace the item display:
const item = items[i] as Record<string, unknown>;
const itemTitle = titleField ? String(item[titleField] ?? '') : `Item ${i + 1}`;
const itemSubtitle = subtitleField ? String(item[subtitleField] ?? '') : undefined;
const itemBadge = badgeField ? String(item[badgeField] ?? '') : undefined;
const itemTimestamp = timestampField ? autoFormat(item[timestampField], 'timestamp') : undefined;

// Render:
<div className="space-y-2">
  <div className="flex items-start justify-between gap-2">
    <div className="min-w-0">
      <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{itemTitle}</p>
      {itemSubtitle && (
        <p className="text-xs text-[var(--text-muted)] mt-0.5 line-clamp-2">{itemSubtitle}</p>
      )}
    </div>
    {itemBadge && (
      <Badge variant={BADGE_VARIANT[badgeColor(itemBadge)]}>{itemBadge}</Badge>
    )}
  </div>
  {detailFields.length > 0 && (
    <div className="space-y-1">
      {detailFields.map(field => {
        const role = fieldRoles.get(field) || 'detail';
        const val = item[field];
        if (val == null) return null;
        return (
          <div key={field} className="flex items-center justify-between text-xs">
            <span className="text-[var(--text-muted)]">{smartLabel(field)}</span>
            <span className="text-[var(--text-secondary)]">{autoFormat(val, role)}</span>
          </div>
        );
      })}
    </div>
  )}
  {itemTimestamp && (
    <p className="text-xs text-[var(--text-muted)]">{itemTimestamp}</p>
  )}
</div>
```

Also update search auto-detection: when `search.enabled` is true but `search.fields` is empty, auto-populate from all string-valued fields:

```typescript
// After items are resolved:
const effectiveSearchFields = useMemo(() => {
  if (search?.fields && search.fields.length > 0) return search.fields;
  if (!search?.enabled || !items || items.length === 0) return [];
  const first = items[0] as Record<string, unknown>;
  return Object.keys(first).filter(k => typeof first[k] === 'string');
}, [search, items]);
```

- [ ] **Step 2: Verify build passes**

Run: `cd apps/dashboard && npx next build 2>&1 | grep -E "Compiled|Type error|Failed"`
Expected: `Compiled successfully`

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/components/blocks/types/CardGridBlock.tsx
git commit -m "feat(blocks): add convention-based auto-detection to card-grid block"
```

---

### Task 5: Convert first batch of custom pages to YAML — metrics-dashboard

**Files:**
- Create: YAML configs in `skills/*/augur/pages/`
- Delete: TSX pages in `skills/dashboard/pages/`

Convert 3 pages as a pilot batch to verify the metrics-dashboard block works end-to-end.

- [ ] **Step 1: Convert command/observe**

Create `skills/observe/augur/pages/overview.yaml`:

```yaml
title: Observe
icon: Activity
hub: command
route: observe
order: 40
blocks:
  - type: metrics-dashboard
    size: full
    sources:
      - mcp_tool: get-daemon-status
        title: Daemon Status
        icon: Server
        color: emerald
      - mcp_tool: get-self-heal-stats
        title: Self-Heal
        icon: ShieldCheck
        color: purple
      - mcp_tool: get-system-health
        title: System Health
        icon: Database
        color: blue
```

Delete: `skills/dashboard/pages/command/observe/page.tsx`
Remove empty directory: `skills/dashboard/pages/command/observe/`

- [ ] **Step 2: Convert career/growth**

Create `skills/growth/augur/pages/overview.yaml`:

```yaml
title: Growth
icon: TrendingUp
hub: career
route: growth
order: 40
blocks:
  - type: metrics-dashboard
    size: full
    sources:
      - mcp_tool: get-skill-health
        title: Growth Snapshot
        icon: TrendingUp
        color: emerald
        skill_id: growth
      - mcp_tool: list-skill-actions
        title: Actions
        icon: Zap
        color: purple
        skill_id: growth
      - mcp_tool: get-skill-doc
        title: Overview
        icon: BookOpen
        color: blue
        skill_id: growth
```

Delete: `skills/dashboard/pages/career/growth/page.tsx`

- [ ] **Step 3: Convert life/health**

Create `skills/health/augur/pages/overview.yaml`:

```yaml
title: Health
icon: Heart
hub: life
route: health
order: 40
blocks:
  - type: metrics-dashboard
    size: full
    sources:
      - mcp_tool: get-skill-health
        title: Health Status
        icon: Heart
        color: emerald
        skill_id: health
      - mcp_tool: get-skill-doc
        title: Overview
        icon: BookOpen
        color: blue
        skill_id: health
```

Delete: `skills/dashboard/pages/life/health/page.tsx`

- [ ] **Step 4: Rebuild and verify**

Run:
```bash
cd apps/dashboard
pnpm run build:scripts
node scripts/dist/mount-plugins.mjs 2>&1 | grep -E "orphan|Tab registry|YAML"
npx next build 2>&1 | grep -E "Compiled|Type error|Failed"
```

Expected: 0 orphans, build passes.

- [ ] **Step 5: Commit**

```bash
git add skills/observe/augur/pages/ skills/growth/augur/pages/ skills/health/augur/pages/
git add -u skills/dashboard/pages/
git commit -m "feat(pages): convert observe, growth, health to metrics-dashboard YAML configs"
```

---

### Task 6: Convert remaining metrics-dashboard pages

**Files:**
- Create: 8 more YAML configs
- Delete: 8 TSX pages

Convert the remaining 8 pages identified in the spec. Follow the same pattern as Task 5 — for each page:
1. Read the TSX to identify which MCP tools it calls
2. Write a YAML config with `type: metrics-dashboard` and the matching `sources[]`
3. Delete the TSX page

Pages to convert:
- [ ] `command/daemon` → `skills/daemon/augur/pages/overview.yaml`
- [ ] `career/project-dev` → `skills/project-dev/augur/pages/overview.yaml`
- [ ] `brain/books` → `skills/books/augur/pages/overview.yaml`
- [ ] `brain/scraper` → `skills/scraper/augur/pages/overview.yaml`
- [ ] `life/wearables` → `skills/wearables/augur/pages/overview.yaml`
- [ ] `command/document-extractor` → `skills/document-extractor/augur/pages/overview.yaml`
- [ ] `studio/workbench/audit` → `skills/dashboard/augur/pages/workbench-audit.yaml` (owned by dashboard skill)
- [ ] `templates/consulting-template` → `skills/consulting-template/augur/pages/overview.yaml`

- [ ] **Rebuild and verify:** 0 orphans, build passes.

- [ ] **Commit:**
```bash
git add skills/*/augur/pages/ -u skills/dashboard/pages/
git commit -m "feat(pages): convert 8 more pages to metrics-dashboard YAML configs"
```

---

### Task 7: Convert card-grid pages

**Files:**
- Create: 5 YAML configs
- Delete: 5 TSX pages

Convert pages that render item lists to use the enhanced `card-grid` block.

- [ ] **Step 1: Convert command/updater/plugins**

Create `skills/updater/augur/pages/plugins.yaml`:

```yaml
title: Plugins
icon: Package
hub: command
route: updater/plugins
order: 50
blocks:
  - type: card-grid
    mcp_tool: admin-updater-plugins
    size: full
    search:
      enabled: true
```

Delete: `skills/dashboard/pages/command/updater/plugins/page.tsx`

- [ ] **Step 2: Convert studio/design**

Create `skills/dashboard/augur/pages/design.yaml` (owned by dashboard skill):

```yaml
title: Design System
icon: Palette
hub: studio
route: design
order: 40
blocks:
  - type: card-grid
    mcp_tool: get-design-standards
    size: full
    search:
      enabled: true
```

Delete: `skills/dashboard/pages/studio/design/page.tsx`

- [ ] **Step 3: Convert studio/workbench**

Create `skills/dashboard/augur/pages/workbench.yaml`:

```yaml
title: Workbench
icon: Wrench
hub: studio
route: workbench
order: 30
blocks:
  - type: card-grid
    mcp_tool: list-mcp-tools
    title: MCP Tools
    size: full
    search:
      enabled: true
```

Delete: `skills/dashboard/pages/studio/workbench/page.tsx`

- [ ] **Step 4: Convert command/system-cleanup and studio/page-builder**

`skills/system-cleanup/augur/pages/overview.yaml`:
```yaml
title: System Cleanup
icon: Trash2
hub: command
route: system-cleanup
order: 50
blocks:
  - type: card-grid
    mcp_tool: get-system-cleanup-scan
    size: full
    search:
      enabled: true
```

`skills/dashboard/augur/pages/page-builder.yaml`:
```yaml
title: Page Builder
icon: LayoutDashboard
hub: studio
route: page-builder
order: 50
blocks:
  - type: card-grid
    mcp_tool: list-views
    size: full
    search:
      enabled: true
```

Delete the corresponding TSX pages.

- [ ] **Step 5: Rebuild and verify**

Run:
```bash
cd apps/dashboard
pnpm run build:scripts
node scripts/dist/mount-plugins.mjs 2>&1 | grep -E "orphan|Tab registry"
npx next build 2>&1 | grep -E "Compiled|Type error|Failed"
```

Expected: 0 orphans, build passes.

- [ ] **Step 6: Commit**

```bash
git add skills/*/augur/pages/ skills/dashboard/augur/pages/ -u skills/dashboard/pages/
git commit -m "feat(pages): convert 5 pages to card-grid YAML configs with auto-detection"
```

---

### Task 8: Final verification and cleanup

**Files:**
- None created

- [ ] **Step 1: Count final page state**

```bash
echo "YAML: $(find skills/*/augur/pages -name '*.yaml' | wc -l)"
echo "TSX:  $(find skills/dashboard/pages -name 'page.tsx' | wc -l)"
echo "Violations: $(find skills/*/augur/dashboard -name 'page.tsx' | grep -v dashboard/ | wc -l)"
```

Expected: ~46 YAML, ~28 TSX, 0 violations.

- [ ] **Step 2: Full build verification**

```bash
cd apps/dashboard && pnpm run build
```

Expected: Build passes, 0 orphan tabs.

- [ ] **Step 3: Run auto-detect tests**

```bash
cd apps/dashboard && npx jest lib/blocks/__tests__/auto-detect.test.ts --no-coverage
```

Expected: All tests pass.

- [ ] **Step 4: Commit any remaining cleanup**

```bash
git add -A && git status
# Only commit if there are changes
git commit -m "cleanup: final page migration state — $(find skills/*/augur/pages -name '*.yaml' | wc -l) YAML, $(find skills/dashboard/pages -name 'page.tsx' | wc -l) TSX"
```
