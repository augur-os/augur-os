import fs from 'fs';
import os from 'os';
import path from 'path';

import {
  discoverPluginsFromSkillDirs,
  parseBlocksFromYaml,
  formatRegistryOutput,
} from '@/scripts/generate-block-registry';

const GENERATED_BLOCK_REGISTRY_PATH = path.resolve(
  __dirname,
  '../../../apps/dashboard/lib/blocks/generated-block-registry.ts',
);

describe('generate-block-registry', () => {
  it('parses blocks from skill config content', () => {
    const yaml = {
      name: 'lifestyle',
      contributes_to: 'lifestyle',
      contributions: {
        blocks: [
          {
            id: 'recipes',
            type: 'data-list',
            title: 'Recipes',
            icon: 'ChefHat',
            expandTo: '/lifestyle/recipes',
            config_schema: {
              filter: { type: 'enum', options: ['all', 'recent'], default: 'recent' },
            },
          },
        ],
      },
    };

    const blocks = parseBlocksFromYaml(yaml, 'lifestyle', 'lifestyle');
    expect(blocks).toHaveLength(1);
    expect(blocks[0].id).toBe('lifestyle:recipes');
    expect(blocks[0].type).toBe('data-list');
    expect(blocks[0].hub).toBe('lifestyle');
  });

  it('preserves explicit flattened Brain routes when normalizing block expand targets', () => {
    const yaml = {
      name: 'knowledge',
      contributions: {
        blocks: [
          {
            id: 'memory',
            type: 'data-list',
            title: 'Memory',
            icon: 'Brain',
            expandTo: '/workspace/memory',
          },
        ],
      },
    };

    const blocks = parseBlocksFromYaml(yaml, 'brain', 'knowledge');
    expect(blocks[0].expandTo).toBe('/workspace/memory');
  });

  it('preserves query routes to route-group pages such as Browse', () => {
    const yaml = {
      name: 'knowledge',
      contributions: {
        blocks: [
          {
            id: 'documents',
            type: 'data-table',
            title: 'Documents',
            icon: 'FileText',
            expandTo: '/browse?category=documents',
          },
        ],
      },
    };

    const blocks = parseBlocksFromYaml(yaml, 'brain', 'knowledge');
    expect(blocks[0].expandTo).toBe('/browse?category=documents');
  });

  it('returns empty array when no blocks declared', () => {
    const yaml = { name: 'test', contributions: { pages: [] } };
    const blocks = parseBlocksFromYaml(yaml, 'test', 'test');
    expect(blocks).toHaveLength(0);
  });

  it('formats registry as valid TypeScript', () => {
    const blocks = [
      {
        id: 'lifestyle:recipes',
        type: 'data-list' as const,
        title: 'Recipes',
        icon: 'ChefHat',
        expandTo: '/lifestyle/recipes',
        configSchema: {},
        hub: 'lifestyle',
        skill: 'lifestyle',
      },
    ];

    const output = formatRegistryOutput(blocks);
    expect(output).toContain('export const BLOCK_REGISTRY');
    expect(output).toContain("'lifestyle:recipes'");
    expect(output).toContain('export function getBlocksByHub');
  });

  it('keeps the generated block registry free of staged skill blocks', () => {
    const content = fs.readFileSync(GENERATED_BLOCK_REGISTRY_PATH, 'utf-8');
    for (const stagedSkill of [
      'career-ops',
      'content',
      'finance',
      'google-workspace',
      'health',
      'home-automation',
      'ingest',
      'vault',
      'venture',
      'websites',
    ]) {
      expect(content).not.toContain(`'${stagedSkill}:`);
    }
  });

  it('discovers block declarations from vault-local managed skill roots', () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'augur-block-registry-'));
    const vaultSkills = path.join(tempDir, 'vault', 'skills');
    const appleDir = path.join(vaultSkills, 'apple');
    fs.mkdirSync(appleDir, { recursive: true });
    fs.writeFileSync(
      path.join(appleDir, 'SKILL.md'),
      [
        '---',
        'name: apple',
        'description: vault Apple',
        'x-augur-group: life',
        'x-augur-config:',
        '  contributions:',
        '    blocks:',
        '      - id: reminders',
        '        type: data-list',
        '        title: Reminders',
        '---',
        '',
      ].join('\n'),
      'utf-8',
    );

    const plugins = discoverPluginsFromSkillDirs({ 'augur-vault': vaultSkills });

    expect(plugins.map((plugin) => plugin.skill)).toEqual(['apple']);
    // ADR-802: hub is the single live surface "workspace", independent of the
    // x-augur-group capability grouping (here "life").
    expect(plugins[0].hub).toBe('workspace');
    expect(plugins[0].config.contributions).toEqual({
      blocks: [{ id: 'reminders', type: 'data-list', title: 'Reminders' }],
    });

    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('prefers project-brain block declarations over vault duplicates', () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'augur-block-registry-'));
    const vaultSkills = path.join(tempDir, 'vault', 'skills');
    const repoSkills = path.join(tempDir, 'repo', 'project-brain', 'capabilities', 'skills');
    for (const [root, title] of [
      [vaultSkills, 'Vault Mail'],
      [repoSkills, 'Repo Mail'],
    ]) {
      const skillDir = path.join(root, 'apple');
      fs.mkdirSync(skillDir, { recursive: true });
      fs.writeFileSync(
        path.join(skillDir, 'SKILL.md'),
        [
          '---',
          'name: apple',
          'description: Apple',
          'x-augur-group: life',
          'x-augur-config:',
          '  contributions:',
          '    blocks:',
          '      - id: mail',
          '        type: data-list',
          `        title: ${title}`,
          '---',
          '',
        ].join('\n'),
        'utf-8',
      );
    }

    const plugins = discoverPluginsFromSkillDirs({
      'augur-vault': vaultSkills,
      augur: repoSkills,
    });

    expect(plugins.map((plugin) => plugin.skill)).toEqual(['apple']);
    expect(plugins[0].config.contributions).toEqual({
      blocks: [{ id: 'mail', type: 'data-list', title: 'Repo Mail' }],
    });

    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('discovers a hub-less skill (ADR-802) and defaults its hub to workspace', () => {
    // Real post-ADR-802 SKILL.md files carry NO x-augur-hub. Discovery must
    // admit them via x-augur-config.contributions and default the grouping
    // value to the single live surface ("workspace").
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'augur-block-registry-'));
    const repoSkills = path.join(tempDir, 'project-brain', 'capabilities', 'skills');
    const skillDir = path.join(repoSkills, 'knowledge');
    fs.mkdirSync(skillDir, { recursive: true });
    fs.writeFileSync(
      path.join(skillDir, 'SKILL.md'),
      [
        '---',
        'name: knowledge',
        'description: hub-less skill',
        'x-augur-config:',
        '  contributions:',
        '    blocks:',
        '      - id: memory',
        '        type: data-list',
        '        title: Memory',
        '---',
        '',
      ].join('\n'),
      'utf-8',
    );

    const plugins = discoverPluginsFromSkillDirs({ augur: repoSkills });

    expect(plugins.map((plugin) => plugin.skill)).toEqual(['knowledge']);
    expect(plugins[0].hub).toBe('workspace');

    fs.rmSync(tempDir, { recursive: true, force: true });
  });
});
