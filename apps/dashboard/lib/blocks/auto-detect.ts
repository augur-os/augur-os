export type FieldRole =
  | 'title' | 'subtitle' | 'badge' | 'icon' | 'meta'
  | 'timestamp' | 'duration' | 'size'
  | 'metric' | 'metric-pct' | 'currency' | 'progress'
  | 'boolean' | 'nested' | 'array' | 'longtext'
  | 'detail';

const TITLE_KEYS = new Set(['name', 'title', 'label', 'subject']);
const SUBTITLE_KEYS = new Set(['description', 'summary', 'detail', 'subtitle']);
const BADGE_KEYS = new Set(['status', 'state', 'phase', 'type', 'category']);
/** Fields that are MCP envelope metadata — should be hidden from display */
const META_KEYS = new Set(['skill', 'version', 'source', 'vault_status', 'success', 'id']);
const ICON_KEYS = new Set(['icon', 'emoji']);
const TIMESTAMP_KEYS = new Set(['created', 'updated', 'timestamp']);
const METRIC_KEYS = new Set(['count', 'total', 'errors', 'warnings']);

export function detectFieldRole(key: string, value: unknown): FieldRole {
  const k = key.toLowerCase();
  if (META_KEYS.has(k)) return 'meta';
  if (TITLE_KEYS.has(k)) return 'title';
  if (SUBTITLE_KEYS.has(k)) return 'subtitle';
  if (BADGE_KEYS.has(k)) return 'badge';
  if (ICON_KEYS.has(k)) return 'icon';
  if (TIMESTAMP_KEYS.has(k)) return 'timestamp';
  if (METRIC_KEYS.has(k)) return 'metric';
  if (k.endsWith('_at') || k.endsWith('_date')) return 'timestamp';
  if (k.endsWith('_percent') || k.endsWith('_rate') || k.endsWith('_pct') || k === 'ratio') return 'metric-pct';
  if (k.endsWith('_seconds') || k.endsWith('_ms') || k === 'uptime' || k === 'duration') return 'duration';
  if (k.endsWith('_bytes') || k.endsWith('_size') || k.endsWith('_mb')) return 'size';
  if (k.endsWith('_count')) return 'metric';
  if (k.startsWith('total_') && !k.endsWith('_value') && !k.endsWith('_cost') && !k.endsWith('_revenue') && !k.endsWith('_amount')) return 'metric';
  if (k === 'progress' || k === 'completion') return 'progress';
  if (k === 'value' || k === 'cost_basis' || k === 'price' || k === 'amount' || k === 'balance' || k === 'target' || k === 'current' || k === 'remaining' || k.endsWith('_value') || k === 'total_value' || k === 'total_cost' || k === 'total_revenue' || k === 'total_amount') return 'currency';
  if (typeof value === 'boolean') return 'boolean';
  if (Array.isArray(value)) return 'array';
  if (value !== null && typeof value === 'object') return 'nested';
  if (typeof value === 'string' && value.length > 100) return 'longtext';
  return 'detail';
}

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
  const pct = value <= 1 && value >= 0 ? value * 100 : value;
  return `${Number(pct.toFixed(1))}%`;
}

function formatNumber(value: number): string {
  return value.toLocaleString('en-US');
}

function formatCurrency(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function autoFormat(value: unknown, role: FieldRole): string {
  if (value == null) return '\u2014';
  switch (role) {
    case 'timestamp': return typeof value === 'string' ? relativeTime(value) : String(value);
    case 'duration': return typeof value === 'number' ? formatDuration(value) : String(value);
    case 'size': return typeof value === 'number' ? formatSize(value) : String(value);
    case 'metric-pct': return typeof value === 'number' ? formatPercent(value) : String(value);
    case 'metric': return typeof value === 'number' ? formatNumber(value) : String(value);
    case 'currency': return typeof value === 'number' ? formatCurrency(value) : String(value);
    case 'progress': return typeof value === 'number' ? `${Number(value.toFixed(1))}%` : String(value);
    case 'boolean': return value ? 'Yes' : 'No';
    case 'array': return Array.isArray(value) ? `${value.length} items` : String(value);
    case 'nested': return typeof value === 'object' ? `${Object.keys(value as object).length} fields` : String(value);
    default: return String(value);
  }
}

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

export function detectFields(obj: Record<string, unknown>): Map<string, FieldRole> {
  const map = new Map<string, FieldRole>();
  for (const [key, value] of Object.entries(obj)) {
    map.set(key, detectFieldRole(key, value));
  }
  return map;
}
