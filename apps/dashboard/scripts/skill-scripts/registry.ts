/**
 * Page Builder Block Registry (ADR-190)
 *
 * Discovers blocks from two sources:
 * 1. Hardcoded starter blocks (built-in)
 * 2. Plugin augur.yaml contributions.blocks[] entries
 */

import { discoverRepoRoot } from '@/lib/plugin-discovery';
import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import type { BlockManifest } from './types';

/**
 * Built-in starter blocks shipped with the page builder.
 */
const STARTER_BLOCKS: BlockManifest[] = [
  {
    id: 'quick-notes',
    name: 'Quick Notes',
    icon: 'StickyNote',
    category: 'content',
    render: 'markdown',
    source: 'plugin',
    component: 'QuickNotes',
    props: [
      { name: 'defaultContent', type: 'string', default: '', required: false },
    ],
  },
  {
    id: 'data-table',
    name: 'Data Table',
    icon: 'Table',
    category: 'data',
    render: 'table',
    source: 'plugin',
    component: 'DataTable',
    props: [
      { name: 'apiUrl', type: 'string', default: '', required: false },
    ],
  },
  {
    id: 'stat-cards',
    name: 'Stat Cards',
    icon: 'BarChart3',
    category: 'data',
    render: 'card',
    source: 'plugin',
    component: 'StatCards',
    props: [
      { name: 'apiUrl', type: 'string', default: '', required: false },
    ],
  },
  {
    id: 'chart',
    name: 'Chart',
    icon: 'LineChart',
    category: 'data',
    render: 'chart',
    source: 'plugin',
    component: 'ChartBlock',
    props: [
      { name: 'title', type: 'string', default: '', required: false },
      { name: 'chartType', type: 'select', default: 'bar', required: false, options: ['bar', 'line', 'pie'] },
    ],
  },
  {
    id: 'action-buttons',
    name: 'Action Buttons',
    icon: 'MousePointerClick',
    category: 'automation',
    render: 'card',
    source: 'plugin',
    component: 'ActionButtons',
    props: [
      { name: 'hub', type: 'string', default: '', required: false },
      { name: 'maxButtons', type: 'number', default: 8, required: false },
    ],
  },
  {
    id: 'mcp-tool-form',
    name: 'MCP Tool Form',
    icon: 'FormInput',
    category: 'automation',
    render: 'form',
    source: 'mcp',
    component: 'AutoForm',
    props: [
      { name: 'mcpTool', type: 'string', default: '', required: true },
      { name: 'mcpServer', type: 'string', default: '', required: false },
      { name: 'submitLabel', type: 'string', default: 'Submit', required: false },
    ],
  },
];

/**
 * Shape of a block entry inside augur.yaml contributions.blocks[].
 */
interface AugurYamlBlockEntry {
  id?: string;
  name?: string;
  icon?: string;
  category?: string;
  render?: string;
  source?: string;
  component?: string;
  mcpTool?: string;
  mcpServer?: string;
}

/**
 * Partial shape of augur.yaml we care about for block discovery.
 */
interface AugurYamlContributions {
  blocks?: AugurYamlBlockEntry[];
}

interface AugurYamlPartial {
  contributions?: AugurYamlContributions;
}

/**
 * Scan plugin augur.yaml files for contributions.blocks entries.
 * Skips files that are missing, unreadable, or have no blocks contributions.
 */
function scanPluginBlocks(): BlockManifest[] {
  const repoRoot = discoverRepoRoot();
  const pluginsDir = path.join(repoRoot, 'plugins');
  const discovered: BlockManifest[] = [];

  if (!fs.existsSync(pluginsDir)) {
    return discovered;
  }

  let bundles: string[];
  try {
    bundles = fs.readdirSync(pluginsDir);
  } catch {
    return discovered;
  }

  for (const bundle of bundles) {
    const skillsDir = path.join(pluginsDir, bundle, 'skills');
    if (!fs.existsSync(skillsDir)) {
      continue;
    }

    let skills: string[];
    try {
      skills = fs.readdirSync(skillsDir);
    } catch {
      continue;
    }

    for (const skill of skills) {
      const augurYamlPath = path.join(skillsDir, skill, 'augur.yaml');
      if (!fs.existsSync(augurYamlPath)) {
        continue;
      }

      let parsed: AugurYamlPartial;
      try {
        const raw = fs.readFileSync(augurYamlPath, 'utf-8');
        parsed = (yaml.load(raw) as AugurYamlPartial) ?? {};
      } catch {
        // Skip files that fail to parse
        continue;
      }

      const blocks = parsed?.contributions?.blocks;
      if (!Array.isArray(blocks) || blocks.length === 0) {
        continue;
      }

      for (const entry of blocks) {
        if (!entry?.id || !entry?.name) {
          // Minimum required fields — skip malformed entries
          continue;
        }

        const manifest: BlockManifest = {
          id: entry.id,
          name: entry.name,
          icon: entry.icon ?? 'Box',
          category: (entry.category as BlockManifest['category']) ?? 'custom',
          render: (entry.render as BlockManifest['render']) ?? 'card',
          source: (entry.source as BlockManifest['source']) ?? 'plugin',
          ...(entry.component !== undefined && { component: entry.component }),
          ...(entry.mcpTool !== undefined && { mcpTool: entry.mcpTool }),
          ...(entry.mcpServer !== undefined && { mcpServer: entry.mcpServer }),
        };

        discovered.push(manifest);
      }
    }
  }

  return discovered;
}

/**
 * Discover all available blocks from built-in starters and plugin augur.yaml files.
 *
 * Starter blocks win on id conflict with plugin-discovered blocks.
 * Returns both a flat list and a map grouped by category.
 */
export async function discoverBlocks(): Promise<{
  blocks: BlockManifest[];
  categories: Record<string, BlockManifest[]>;
}> {
  // Build a lookup from starter blocks so they win on conflict
  const starterById = new Map<string, BlockManifest>(
    STARTER_BLOCKS.map((b) => [b.id, b])
  );

  // Scan plugins for additional blocks
  const pluginBlocks = scanPluginBlocks();

  // Merge: starters first, then plugin blocks that don't conflict
  const merged: BlockManifest[] = [...STARTER_BLOCKS];
  for (const block of pluginBlocks) {
    if (!starterById.has(block.id)) {
      merged.push(block);
    }
  }

  // Group by category
  const categories: Record<string, BlockManifest[]> = {};
  for (const block of merged) {
    const cat = block.category;
    if (!categories[cat]) {
      categories[cat] = [];
    }
    categories[cat].push(block);
  }

  return { blocks: merged, categories };
}
