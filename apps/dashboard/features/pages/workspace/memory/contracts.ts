export interface BrainDataSource {
  exists: boolean;
  label?: string | null;
  source?: string | null;
  path?: string | null;
  kind?: string | null;
  freshness?: string | null;
  modifiedAt?: string | null;
  generatedAt?: string | null;
  updatedAt?: string | null;
}

export interface BrainDataSources {
  memory?: BrainDataSource | null;
  daily?: BrainDataSource | null;
  profile?: BrainDataSource | null;
  index?: BrainDataSource | null;
  generatedAt?: string | null;
}

type BrainSourceKey = 'memory' | 'daily' | 'profile' | 'index';

export interface BrainOperationNotice {
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  timestamp: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function describeErrorPayload(error: unknown, details: unknown, actionLabel: string) {
  if (typeof error === 'string' && error.trim()) {
    return error.trim();
  }

  if (typeof details === 'string' && details.trim()) {
    return details.trim();
  }

  if (details instanceof Error && details.message.trim()) {
    return details.message.trim();
  }

  if (isRecord(details)) {
    const candidate = details.message ?? details.error ?? details.detail ?? details.reason;
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim();
    }
    try {
      const serialized = JSON.stringify(details);
      if (serialized && serialized !== '{}') {
        return serialized;
      }
    } catch {
      // Ignore serialization failures and fall through to the default label.
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }

  if (typeof error === 'string' && error.trim()) {
    return error.trim();
  }

  return `${actionLabel} failed`;
}

function hasFailureFlag(payload: unknown): payload is { success: false; error?: unknown; details?: unknown } {
  return isRecord(payload) && payload.success === false;
}

export function assertMcpSuccess<T>(payload: T, actionLabel: string): T {
  if (hasFailureFlag(payload)) {
    throw new Error(describeErrorPayload(payload.error, payload.details, actionLabel));
  }

  return payload;
}

export function formatOperationError(actionLabel: string, error: unknown): string {
  const message =
    error instanceof Error ? error.message : typeof error === 'string' ? error : String(error);
  const trimmed = message.trim();
  if (!trimmed) {
    return `${actionLabel} failed`;
  }

  const prefix = `${actionLabel} failed`;
  const normalized = trimmed.toLowerCase();
  if (
    normalized === prefix.toLowerCase() ||
    normalized.startsWith(`${prefix.toLowerCase()}:`) ||
    normalized.startsWith(`${prefix.toLowerCase()} -`)
  ) {
    return trimmed;
  }

  return `${prefix}: ${trimmed}`;
}

export function makeNotice(type: BrainOperationNotice['type'], message: string): BrainOperationNotice {
  return {
    type,
    message,
    timestamp: new Date().toISOString(),
  };
}

export function asBrainDataSource(value: unknown): BrainDataSource | null {
  if (!isRecord(value) || typeof value.exists !== 'boolean') {
    return null;
  }

  if (typeof value.label !== 'string' || !value.label.trim()) {
    return null;
  }

  return {
    exists: value.exists,
    label: value.label.trim(),
    source: typeof value.source === 'string' && value.source.trim() ? value.source.trim() : null,
    path: typeof value.path === 'string' && value.path.trim() ? value.path.trim() : null,
    kind: typeof value.kind === 'string' && value.kind.trim() ? value.kind.trim() : null,
    freshness: typeof value.freshness === 'string' && value.freshness.trim() ? value.freshness.trim() : null,
    modifiedAt: typeof value.modifiedAt === 'string' && value.modifiedAt.trim() ? value.modifiedAt.trim() : null,
    generatedAt: typeof value.generatedAt === 'string' && value.generatedAt.trim() ? value.generatedAt.trim() : null,
    updatedAt: typeof value.updatedAt === 'string' && value.updatedAt.trim() ? value.updatedAt.trim() : null,
  };
}

function formatRelativeAge(timestamp: number, now: number) {
  const deltaMs = Math.max(0, now - timestamp);
  const minutes = Math.floor(deltaMs / 60_000);
  if (minutes < 1) {
    return 'just now';
  }
  if (minutes < 60) {
    return `${minutes}m ago`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }

  const days = Math.floor(hours / 24);
  if (days < 7) {
    return `${days}d ago`;
  }

  return new Date(timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function formatFreshness(value: string | number | Date | null | undefined): string {
  if (value === null || value === undefined || value === '') {
    return 'Freshness unavailable';
  }

  const date = value instanceof Date ? value : new Date(value);
  const timestamp = date.getTime();
  if (!Number.isFinite(timestamp)) {
    return 'Freshness unavailable';
  }

  return `Updated ${formatRelativeAge(timestamp, Date.now())}`;
}

function resolveSourceLabel(source: BrainDataSource | null | undefined, fallback: string): string | null {
  if (!source || !source.exists) {
    return null;
  }

  const label = typeof source.label === 'string' ? source.label.trim() : '';
  if (label) {
    return label;
  }

  const sourceName = typeof source.source === 'string' ? source.source.trim() : '';
  if (sourceName) {
    return sourceName;
  }

  return fallback;
}

function resolveSourceModifiedAt(source: BrainDataSource | null | undefined): string | null {
  if (!source || !source.exists) {
    return null;
  }

  const modifiedAt = typeof source.modifiedAt === 'string' ? source.modifiedAt.trim() : '';
  if (modifiedAt) {
    return modifiedAt;
  }

  return null;
}

function resolvePrimarySource(sources: BrainDataSources | null | undefined): BrainDataSource | null {
  const orderedKeys: BrainSourceKey[] = ['memory', 'daily', 'profile', 'index'];

  for (const key of orderedKeys) {
    const source = sources?.[key];
    if (source?.exists) {
      return source;
    }
  }

  return null;
}

export function getPrimarySourceLabel(sources: BrainDataSources | null | undefined): string {
  const orderedSources: Array<[BrainSourceKey, string]> = [
    ['memory', 'Memory source'],
    ['daily', 'Daily source'],
    ['profile', 'Profile source'],
    ['index', 'Index source'],
  ];

  for (const [key, fallback] of orderedSources) {
    const label = resolveSourceLabel(sources?.[key], fallback);
    if (label) {
      return label;
    }
  }

  return 'No brain source available';
}

export function getPrimarySourceFreshnessLabel(sources: BrainDataSources | null | undefined): string {
  const primarySource = resolvePrimarySource(sources);
  const primaryModifiedAt = resolveSourceModifiedAt(primarySource);
  if (primaryModifiedAt) {
    return formatFreshness(primaryModifiedAt);
  }

  const generatedAt = typeof sources?.generatedAt === 'string' ? sources.generatedAt.trim() : '';
  if (generatedAt) {
    return formatFreshness(generatedAt);
  }

  const orderedKeys: BrainSourceKey[] = ['memory', 'daily', 'profile', 'index'];
  for (const key of orderedKeys) {
    if (sources?.[key] === primarySource) {
      continue;
    }
    const modifiedAt = resolveSourceModifiedAt(sources?.[key]);
    if (modifiedAt) {
      return formatFreshness(modifiedAt);
    }
  }

  return 'Freshness unavailable';
}
