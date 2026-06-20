import { describe, it, expect } from '@jest/globals';

describe('stale hidden hub cleanup', () => {
  it('hidden hub is excluded in production mode', () => {
    const { getEnabledSections } = require('../../../apps/dashboard/lib/navigation');
    const sections = getEnabledSections(false);
    const allItems = sections.flatMap((s: any) => s.items);
    const hidden = allItems.find((item: any) => item.href === '/hidden');
    expect(hidden).toBeUndefined();
  });

  it('hidden hub is excluded in development mode after route cleanup', () => {
    const { getEnabledSections } = require('../../../apps/dashboard/lib/navigation');
    const sections = getEnabledSections(true);
    const allItems = sections.flatMap((s: any) => s.items);
    const hidden = allItems.find((item: any) => item.href === '/hidden');
    expect(hidden).toBeUndefined();
  });

  it('Dev and Life hubs are excluded from primary navigation in development mode', () => {
    const { getEnabledSections } = require('../../../apps/dashboard/lib/navigation');
    const sections = getEnabledSections(true);
    const allItems = sections.flatMap((s: any) => s.items);

    expect(allItems.find((item: any) => item.href === '/dev')).toBeUndefined();
    expect(allItems.find((item: any) => item.href === '/life')).toBeUndefined();
  });
});
