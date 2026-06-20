/**
 * @jest-environment node
 *
 * Tests for Tab Registry output format validation (ADR-218).
 *
 * Validates that the generated registry file (lib/tabs/generated-registry.ts)
 * conforms to the expected format:
 * 1. All hubs sorted alphabetically
 * 2. Every hub has an overview tab
 * 3. Tab hrefs follow /{hub}/{skill}/{page} pattern
 * 4. No stale fields (group, groupLabel) from the old format
 * 5. Contributors array is present and sorted
 */

import { describe, it, expect } from '@jest/globals';
import fs from 'fs';
import path from 'path';

const REGISTRY_PATH = path.resolve(
  __dirname,
  '../../../apps/dashboard/lib/tabs/generated-registry.ts',
);

/**
 * Parse the generated registry file to extract the JSON data.
 * We read the raw TS file and extract the JSON literals.
 */
function readGeneratedRegistry(): string {
  return fs.readFileSync(REGISTRY_PATH, 'utf-8');
}

function extractJSON(content: string, varName: string): any {
  // Match: export const varName: Type = <JSON>;
  const pattern = new RegExp(
    `export const ${varName}[^=]*=\\s*([\\s\\S]*?);\\s*\\n(?:export|/\\*\\*|$)`,
  );
  const match = content.match(pattern);
  if (!match) throw new Error(`Could not find ${varName} in generated registry`);
  return JSON.parse(match[1].trim());
}

describe('generated-registry format (ADR-218)', () => {
  let content: string;
  let registry: Record<string, any>;
  let managedHubs: string[];
  let navItems: any[];

  beforeAll(() => {
    content = readGeneratedRegistry();
    registry = extractJSON(content, 'pluginTabRegistry');
    managedHubs = extractJSON(content, 'pluginManagedHubs');
    navItems = extractJSON(content, 'pluginNavItems');
  });

  it('registry file exists and is non-empty', () => {
    expect(content.length).toBeGreaterThan(0);
    expect(Object.keys(registry).length).toBeGreaterThan(0);
  });

  it('hub keys are sorted alphabetically', () => {
    const keys = Object.keys(registry);
    const sorted = [...keys].sort();
    expect(keys).toEqual(sorted);
  });

  it('pluginManagedHubs matches registry keys', () => {
    const registryKeys = Object.keys(registry).sort();
    expect(managedHubs).toEqual(registryKeys);
  });

  it('every hub has an overview tab as the first tab', () => {
    for (const [hubId, config] of Object.entries(registry)) {
      expect(config.tabs.length).toBeGreaterThan(0);
      expect(config.tabs[0]).toEqual({
        id: 'overview',
        label: 'Overview',
        icon: 'LayoutDashboard',
        href: `/${hubId}`,
      });
    }
  });

  it('no tabs have stale group/groupLabel fields', () => {
    for (const [hubId, config] of Object.entries(registry)) {
      const allTabs = [...config.tabs, ...(config.overflow || [])];
      for (const tab of allTabs) {
        expect(tab).not.toHaveProperty('group');
        expect(tab).not.toHaveProperty('groupLabel');
      }
    }
  });

  it('content tab hrefs follow /{hub}/... pattern', () => {
    for (const [hubId, config] of Object.entries(registry)) {
      const allTabs = [...config.tabs, ...(config.overflow || [])];
      for (const tab of allTabs) {
        if (tab.id === 'overview') continue;
        // href should start with /{hubId}/ and have at least one more segment
        expect(tab.href).toMatch(new RegExp(`^/${hubId}/[^/]+`));
      }
    }
  });

  it('every hub has required fields', () => {
    for (const [hubId, config] of Object.entries(registry)) {
      expect(config.title).toBeTruthy();
      expect(config.basePath).toBe(`/${hubId}`);
      expect(Array.isArray(config.tabs)).toBe(true);
      expect(config.source).toBe('plugin');
    }
  });

  it('contributors array is sorted when present', () => {
    for (const [, config] of Object.entries(registry)) {
      if (config.contributors) {
        const sorted = [...config.contributors].sort();
        expect(config.contributors).toEqual(sorted);
      }
    }
  });

  it('navItems cover all registry hubs', () => {
    const navHubIds = navItems.map((n: any) => n.hubId).sort();
    const registryKeys = Object.keys(registry).sort();
    expect(navHubIds).toEqual(registryKeys);
  });

  it('keeps only Workspace as a live dashboard hub in the generated registry', () => {
    expect(Object.keys(registry)).toEqual(['workspace']);
    expect(managedHubs).toEqual(['workspace']);
    expect(navItems.map((item: any) => item.hubId)).toEqual(['workspace']);
  });

  it('places the Workspace Inbox tab first after Overview', () => {
    // ADR-802 Phase 2: the tab id is "inbox" (the x-augur-dashboard-pages slug)
    const workspaceTabs = registry.workspace.tabs.map((tab: any) => tab.id);
    expect(workspaceTabs.slice(0, 2)).toEqual(['overview', 'inbox']);
  });

  // ADR-802 Phase 2: assembled-hubs.json is no longer written by the tab-registry
  // pipeline (the old multi-hub assembleHubs() pipeline was deleted). The file is
  // gitignored and contains a stale empty artifact. This test is removed.

  it('does not leak staged skills into live hub tabs', () => {
    const serialized = JSON.stringify(registry);
    for (const stagedSkill of [
      'apple',
      'career-ops',
      'content',
      'finance',
      'google-workspace',
      'health',
      'home-automation',
      'lifestyle',
      'venture',
      'websites',
    ]) {
      expect(serialized).not.toContain(`\"skillId\":\"${stagedSkill}\"`);
    }
  });

  it('exposes flattened Workspace memory pages and no nested memory routes', () => {
    const workspaceTabs = [...registry.workspace.tabs, ...(registry.workspace.overflow || [])];
    const workspaceConfigPages = registry.workspace.configPages || [];
    const workspaceAutoPages = registry.workspace.autoPages || [];
    const serialized = JSON.stringify([
      ...workspaceTabs,
      ...workspaceConfigPages,
      ...workspaceAutoPages,
    ]);

    for (const href of [
      '/workspace/memory',
      '/workspace/daily-logs',
      '/workspace/profile',
      '/workspace/inbox',
      '/workspace/insights',
      '/workspace/agents',
      '/workspace/harness',
    ]) {
      expect(serialized).toContain(`"href":"${href}"`);
    }

    for (const removedHref of ['/workspace/search', '/workspace/wiki']) {
      expect(serialized).not.toContain(`"href":"${removedHref}"`);
    }

    // Memory-family pages stay flat (no nested children).
    for (const tab of workspaceTabs) {
      if (['memory', 'daily-logs', 'profile', 'memory-review'].includes(tab.id)) {
        expect(tab.children).toBeUndefined();
      }
    }

    // Pre-migration nested brain routes must never reappear, and the
    // workspace hub must not regrow nested knowledge/ai-subpage routes.
    // (/workspace/ai and /workspace/rag are real config pages — not listed.)
    for (const staleHref of [
      '/brain/knowledge',
      '/brain/knowledge/memory',
      '/brain/knowledge/memory/daily-logs',
      '/brain/knowledge/memory/profile',
      '/brain/knowledge/memory/workspace',
      '/brain/ai',
      '/brain/ai/agents',
      '/brain/rag',
      '/workspace/knowledge',
      '/workspace/knowledge/memory',
      '/workspace/ai/agents',
    ]) {
      expect(serialized).not.toContain(`"href":"${staleHref}"`);
    }
  });

  // ADR-802 Phase 2: the blocks/configPages pipeline was part of assembleHubs()
  // which has been deleted. The new tab registry (generated from
  // x-augur-dashboard-pages) is a flat tab list with no embedded block configs.
  // The Documents overview card lives in BrainOverviewHome, not the tab registry.

  it('does not expose staged Dev and Life pages in generated page collections', () => {
    const serialized = JSON.stringify(registry);
    for (const stagedHref of [
      '/adaptive/loop-ops',
      '/command/daemon',
      '/command/document-extractor',
      '/command/plugin-pack',
      '/dev/auto-vault-hygiene',
      '/dev/auto-skill-quality',
      '/dev/platform-admin',
      '/dev/skill-scores',
      '/life/file-manager',
      '/life/file-manager/organize',
    ]) {
      expect(serialized).not.toContain(`"href":"${stagedHref}"`);
    }
  });

  it('header references ADR-802 (x-augur-dashboard-pages pipeline)', () => {
    // ADR-802 Phase 2: the registry is now generated from x-augur-dashboard-pages,
    // not the old assembleHubs() pipeline. The file header references ADR-802.
    expect(content).toContain('ADR-802');
  });

  describe('tab structure', () => {
    it('overview tab is always flat', () => {
      for (const hubId of Object.keys(registry)) {
        const overview = registry[hubId].tabs.find((t: any) => t.id === 'overview');
        expect(overview).toBeDefined();
        expect(overview.children).toBeUndefined();
      }
    });

    it('only emits one overview destination per hub', () => {
      for (const [hubId, config] of Object.entries(registry)) {
        const allTabs = [...config.tabs, ...(config.overflow || [])].flatMap((tab: any) =>
          Array.isArray(tab.children) ? tab.children : [tab],
        );
        const overviewTabs = allTabs.filter((tab: any) => tab.id === 'overview');
        expect(overviewTabs).toHaveLength(1);
        expect(overviewTabs[0].href).toBe(`/${hubId}`);
      }
    });

    it('grouped tabs have valid children with required fields', () => {
      for (const hubId of Object.keys(registry)) {
        const hub = registry[hubId];
        for (const tab of [...hub.tabs, ...(hub.overflow || [])]) {
          if (tab.children) {
            expect(Array.isArray(tab.children)).toBe(true);
            expect(tab.children.length).toBeGreaterThanOrEqual(2);
            for (const child of tab.children) {
              expect(child.id).toBeTruthy();
              expect(child.label).toBeTruthy();
              expect(child.href).toBeTruthy();
              expect(child.skillId).toBe(tab.skillId);
            }
          }
        }
      }
    });
  });
});
