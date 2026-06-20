import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import { getSkillDataPath } from '@/lib/paths';

type Dict = Record<string, unknown>;

export interface UsageEvent {
  id: string;
  type: string;
  createdAt: string;
  payload: Dict;
}

function randomId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function getPageBuilderDataDir(): string {
  return getSkillDataPath('page-builder');
}

export function readPageBuilderDataFile<T>(fileName: string, fallback: T): T {
  try {
    const filePath = path.join(getPageBuilderDataDir(), fileName);
    if (!fs.existsSync(filePath)) return fallback;
    const raw = fs.readFileSync(filePath, 'utf-8');
    const parsed = yaml.load(raw) as T | null;
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

export function writePageBuilderDataFile(fileName: string, data: unknown): void {
  const filePath = path.join(getPageBuilderDataDir(), fileName);
  fs.writeFileSync(filePath, yaml.dump(data, { lineWidth: -1, noRefs: true }), 'utf-8');
}

export function appendUsageEvent(type: string, payload: Dict): UsageEvent {
  const usage = readPageBuilderDataFile<{ _meta?: Dict; events?: UsageEvent[] }>(
    'usage-history.yaml',
    { events: [] }
  );
  const events = Array.isArray(usage.events) ? usage.events : [];

  const event: UsageEvent = {
    id: randomId('usage'),
    type,
    createdAt: new Date().toISOString(),
    payload,
  };

  events.push(event);
  const trimmed = events.slice(-500);

  writePageBuilderDataFile('usage-history.yaml', {
    _meta: usage._meta ?? {
      description: 'Event log for Page Builder usage patterns',
      purpose: 'Track how users create pages to prioritize future hardening',
      updateInstructions: 'Append-only, managed by page-builder API routes',
    },
    events: trimmed,
  });

  return event;
}
