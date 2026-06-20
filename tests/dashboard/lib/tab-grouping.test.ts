import { describe, it, expect } from '@jest/globals';

describe('isGroupedTab', () => {
  it('returns true for tab with non-empty children array', () => {
    const { isGroupedTab } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    const grouped = {
      id: 'daemon', label: 'Daemon', icon: 'Server', href: '/command/daemon',
      children: [
        { id: 'health', label: 'Health', href: '/command/daemon/health' },
        { id: 'jobs', label: 'Jobs', href: '/command/daemon/jobs' },
      ],
    };
    expect(isGroupedTab(grouped)).toBe(true);
  });

  it('returns false for flat tab without children', () => {
    const { isGroupedTab } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    expect(isGroupedTab({ id: 'logs', label: 'Logs', href: '/command/logs' })).toBe(false);
  });

  it('returns false for tab with empty children', () => {
    const { isGroupedTab } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    expect(isGroupedTab({ id: 'x', label: 'X', href: '/x', children: [] })).toBe(false);
  });
});

describe('groupBySkillId', () => {
  it('leaves tabs without skillId as flat', () => {
    const { groupBySkillId } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    const tabs = [
      { id: 'overview', label: 'Overview', href: '/command' },
      { id: 'logs', label: 'Logs', href: '/command/logs', skillId: 'platform-admin' },
    ];
    const result = groupBySkillId(tabs);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual(tabs[0]);
    expect(result[1]).toEqual(tabs[1]);
  });

  it('groups tabs sharing a skillId into a GroupedTab', () => {
    const { groupBySkillId, isGroupedTab } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    const tabs = [
      { id: 'overview', label: 'Overview', href: '/command' },
      { id: 'daemon', label: 'Daemon', href: '/command/daemon', skillId: 'daemon' },
      { id: 'health', label: 'Health', href: '/command/daemon/health', skillId: 'daemon' },
      { id: 'jobs', label: 'Jobs', href: '/command/daemon/jobs', skillId: 'daemon' },
      { id: 'logs', label: 'Logs', href: '/command/logs', skillId: 'platform-admin' },
    ];
    const result = groupBySkillId(tabs);
    expect(result).toHaveLength(3);
    expect(result[0].id).toBe('overview');
    expect(isGroupedTab(result[1])).toBe(true);
    const group = result[1] as any;
    expect(group.id).toBe('daemon');
    expect(group.label).toBe('Daemon');
    expect(group.href).toBe('/command/daemon');
    expect(group.children).toHaveLength(3);
    expect(group.children[0].label).toBe('Daemon');
    expect(group.children[1].label).toBe('Health');
    expect(group.children[2].label).toBe('Jobs');
    expect(result[2].id).toBe('logs');
  });

  it('preserves order of first occurrence of each skillId', () => {
    const { groupBySkillId } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    const tabs = [
      { id: 'overview', label: 'Overview', href: '/life' },
      { id: 'voice', label: 'Voice Memos', href: '/life/apple/voice', skillId: 'apple' },
      { id: 'scenes', label: 'Scenes', href: '/life/home-automation/scenes', skillId: 'home-automation' },
      { id: 'lighting', label: 'Lighting', href: '/life/home-automation/lighting', skillId: 'home-automation' },
      { id: 'attention', label: 'Attention', href: '/life/attention', skillId: 'attention' },
    ];
    const result = groupBySkillId(tabs);
    expect(result).toHaveLength(4);
    expect(result[0].id).toBe('overview');
    expect(result[1].id).toBe('voice');
    expect(result[2].id).toBe('home-automation');
    expect(result[3].id).toBe('attention');
  });

  it('uses skillId as group label with smart formatting', () => {
    const { groupBySkillId, isGroupedTab } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    const tabs = [
      { id: 'a', label: 'A', href: '/x/home-automation/a', skillId: 'home-automation' },
      { id: 'b', label: 'B', href: '/x/home-automation/b', skillId: 'home-automation' },
    ];
    const result = groupBySkillId(tabs);
    expect(result).toHaveLength(1);
    expect(isGroupedTab(result[0])).toBe(true);
    expect(result[0].label).toBe('Home Automation');
  });

  it('groups tabs with same skillId even if they are parent/child routes', () => {
    const { groupBySkillId, isGroupedTab } = require('../../../apps/dashboard/lib/tabs/tab-grouping');
    const tabs = [
      { id: 'plugins', label: 'Custom Plugins', href: '/command/updater/plugins', skillId: 'updater', order: 60 },
      { id: 'updater', label: 'Updater', href: '/command/updater', skillId: 'updater' },
    ];
    const result = groupBySkillId(tabs);
    expect(isGroupedTab(result[0])).toBe(true);
    expect((result[0] as any).children).toHaveLength(2);
  });
});
