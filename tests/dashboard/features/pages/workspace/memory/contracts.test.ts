import { getPrimarySourceFreshnessLabel } from '@/features/pages/workspace/memory/contracts';

describe('getPrimarySourceFreshnessLabel', () => {
  beforeEach(() => {
    jest.spyOn(Date, 'now').mockReturnValue(Date.UTC(2026, 3, 22, 12, 0, 0));
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('prefers the primary source modifiedAt over generatedAt and other sources', () => {
    expect(
      getPrimarySourceFreshnessLabel({
        memory: { exists: true, label: 'Memory', modifiedAt: '2026-04-22T10:00:00.000Z' },
        daily: { exists: true, label: 'Daily', modifiedAt: '2026-04-22T11:30:00.000Z' },
        profile: { exists: true, label: 'Profile', modifiedAt: '2026-04-22T11:45:00.000Z' },
        generatedAt: '2026-04-22T11:00:00.000Z',
      }),
    ).toBe('Updated 2h ago');
  });

  it('falls back to top-level generatedAt before other source modifiedAt values', () => {
    expect(
      getPrimarySourceFreshnessLabel({
        memory: { exists: true, label: 'Memory' },
        daily: { exists: true, label: 'Daily', modifiedAt: '2026-04-22T11:30:00.000Z' },
        profile: { exists: true, label: 'Profile', modifiedAt: '2026-04-22T11:45:00.000Z' },
        generatedAt: '2026-04-22T10:30:00.000Z',
      }),
    ).toBe('Updated 1h ago');
  });
});
