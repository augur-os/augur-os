import { detectFieldRole } from '@/lib/blocks/auto-detect';

describe('detectFieldRole', () => {
  it('detects "name" as title', () => { expect(detectFieldRole('name', 'Daemon')).toBe('title'); });
  it('detects "title" as title', () => { expect(detectFieldRole('title', 'My Page')).toBe('title'); });
  it('detects "label" as title', () => { expect(detectFieldRole('label', 'X')).toBe('title'); });
  it('detects "status" as badge', () => { expect(detectFieldRole('status', 'running')).toBe('badge'); });
  it('detects "state" as badge', () => { expect(detectFieldRole('state', 'active')).toBe('badge'); });
  it('detects "phase" as badge', () => { expect(detectFieldRole('phase', 'review')).toBe('badge'); });
  it('detects "created_at" as timestamp', () => { expect(detectFieldRole('created_at', '2026-03-29')).toBe('timestamp'); });
  it('detects "updated" as timestamp', () => { expect(detectFieldRole('updated', '2026-03-29')).toBe('timestamp'); });
  it('detects "timestamp" as timestamp', () => { expect(detectFieldRole('timestamp', '2026-03-29')).toBe('timestamp'); });
  it('detects "uptime_seconds" as duration', () => { expect(detectFieldRole('uptime_seconds', 3600)).toBe('duration'); });
  it('detects "duration" as duration', () => { expect(detectFieldRole('duration', 120)).toBe('duration'); });
  it('detects "fix_rate" as metric-pct', () => { expect(detectFieldRole('fix_rate', 0.85)).toBe('metric-pct'); });
  it('detects "success_percent" as metric-pct', () => { expect(detectFieldRole('success_percent', 95)).toBe('metric-pct'); });
  it('detects "file_bytes" as size', () => { expect(detectFieldRole('file_bytes', 1024)).toBe('size'); });
  it('detects "error_count" as metric', () => { expect(detectFieldRole('error_count', 5)).toBe('metric'); });
  it('detects "total" as metric', () => { expect(detectFieldRole('total', 42)).toBe('metric'); });
  it('detects boolean value as boolean', () => { expect(detectFieldRole('installed', true)).toBe('boolean'); });
  it('detects nested object as nested', () => { expect(detectFieldRole('config', { a: 1 })).toBe('nested'); });
  it('detects array as array', () => { expect(detectFieldRole('items', [1, 2])).toBe('array'); });
  it('falls back to detail for unknown fields', () => { expect(detectFieldRole('hostname', 'localhost')).toBe('detail'); });
});

import { autoFormat, badgeColor, detectFields } from '@/lib/blocks/auto-detect';

describe('autoFormat', () => {
  it('formats timestamp as relative time', () => {
    const recent = new Date(Date.now() - 60_000).toISOString();
    expect(autoFormat(recent, 'timestamp')).toMatch(/1 min/);
  });
  it('formats duration seconds', () => { expect(autoFormat(3661, 'duration')).toBe('1h 1m'); });
  it('formats large duration', () => { expect(autoFormat(172800, 'duration')).toBe('2d 0h'); });
  it('formats small duration', () => { expect(autoFormat(45, 'duration')).toBe('45s'); });
  it('formats percentage', () => { expect(autoFormat(0.857, 'metric-pct')).toBe('85.7%'); });
  it('formats percentage already in percent form', () => { expect(autoFormat(85.7, 'metric-pct')).toBe('85.7%'); });
  it('formats bytes', () => { expect(autoFormat(1536, 'size')).toBe('1.5 KB'); });
  it('formats megabytes', () => { expect(autoFormat(2_500_000, 'size')).toBe('2.4 MB'); });
  it('formats boolean true', () => { expect(autoFormat(true, 'boolean')).toBe('Yes'); });
  it('formats boolean false', () => { expect(autoFormat(false, 'boolean')).toBe('No'); });
  it('formats array as count', () => { expect(autoFormat([1, 2, 3], 'array')).toBe('3 items'); });
  it('formats detail as string', () => { expect(autoFormat('hello', 'detail')).toBe('hello'); });
  it('formats number metric', () => { expect(autoFormat(1234, 'metric')).toBe('1,234'); });
  it('handles null', () => { expect(autoFormat(null, 'detail')).toBe('—'); });
  it('handles undefined', () => { expect(autoFormat(undefined, 'detail')).toBe('—'); });
});

describe('badgeColor', () => {
  it('returns green for running', () => { expect(badgeColor('running')).toBe('green'); });
  it('returns green for active', () => { expect(badgeColor('active')).toBe('green'); });
  it('returns red for error', () => { expect(badgeColor('error')).toBe('red'); });
  it('returns red for failed', () => { expect(badgeColor('failed')).toBe('red'); });
  it('returns amber for pending', () => { expect(badgeColor('pending')).toBe('amber'); });
  it('returns amber for warning', () => { expect(badgeColor('warning')).toBe('amber'); });
  it('returns gray for unknown', () => { expect(badgeColor('unknown')).toBe('gray'); });
  it('returns blue for unrecognized', () => { expect(badgeColor('custom-value')).toBe('blue'); });
  it('is case-insensitive', () => { expect(badgeColor('Running')).toBe('green'); });
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
