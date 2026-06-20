/**
 * Page Codegen Engine (ADR-190)
 *
 * Validates builder state, generates page.tsx + optional route.ts,
 * and updates the target skill's augur.yaml.
 *
 * Note: mount-plugins is NOT called here — the calling API route
 * handles that step directly (spawn requires a standalone route file).
 */

import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import { discoverRepoRoot } from '@/lib/plugin-discovery';
import type { PageBuilderState, SaveResponse } from './types';
import { generatePageTemplate } from './templates/page-template';
import { generateRouteTemplate, needsApiRoute } from './templates/route-template';
import { discoverBlocks } from './registry';

/**
 * Validate the page builder state before codegen.
 */
function validate(state: PageBuilderState): string | null {
  if (!state.name || !state.name.trim()) {
    return 'Page name is required';
  }
  if (!state.slug || !state.slug.trim()) {
    return 'Page slug is required';
  }
  if (!state.hub || !state.hub.trim()) {
    return 'Hub is required';
  }
  if (!state.targetSkill || !state.targetSkill.trim()) {
    return 'Target skill is required';
  }
  if (!state.blocks || state.blocks.length === 0) {
    return 'At least one block is required';
  }
  // Validate slug format
  if (!/^[a-z0-9-]+$/.test(state.slug)) {
    return 'Slug must contain only lowercase letters, numbers, and hyphens';
  }
  return null;
}

/**
 * Find the target skill's plugin directory.
 */
function findSkillDir(targetSkill: string): string | null {
  const repoRoot = discoverRepoRoot();
  const pluginsDir = path.join(repoRoot, 'plugins');

  if (!fs.existsSync(pluginsDir)) return null;

  for (const bundle of fs.readdirSync(pluginsDir)) {
    const skillsDir = path.join(pluginsDir, bundle, 'skills');
    if (!fs.existsSync(skillsDir)) continue;

    for (const skill of fs.readdirSync(skillsDir)) {
      if (skill === targetSkill) {
        return path.join(skillsDir, skill);
      }
    }
  }
  return null;
}

/**
 * Update a skill's augur.yaml to add a new page entry.
 */
function updateAugurYaml(skillDir: string, state: PageBuilderState): void {
  const yamlPath = path.join(skillDir, 'augur.yaml');
  if (!fs.existsSync(yamlPath)) {
    throw new Error(`augur.yaml not found at ${yamlPath}`);
  }

  const content = fs.readFileSync(yamlPath, 'utf-8');
  const config = yaml.load(content) as Record<string, unknown>;

  // Ensure contributions.pages exists
  if (!config.contributions) {
    config.contributions = {};
  }
  const contributions = config.contributions as Record<string, unknown>;
  if (!contributions.pages) {
    contributions.pages = [];
  }
  const pages = contributions.pages as Array<Record<string, unknown>>;

  // Check for duplicate
  if (pages.some((p) => p.id === state.slug)) {
    throw new Error(`Page "${state.slug}" already exists in ${yamlPath}`);
  }

  // Find next available order value
  const maxOrder = pages.reduce((max, p) => {
    const order = typeof p.order === 'number' ? p.order : 0;
    return Math.max(max, order);
  }, 0);

  pages.push({
    id: state.slug,
    title: state.name,
    icon: state.icon || 'FileText',
    order: maxOrder + 10,
    purpose: `Page built with Page Builder (${state.blocks.length} blocks)`,
    keywords: ['page-builder', 'generated'],
    state: 'dev',
  });

  fs.writeFileSync(yamlPath, yaml.dump(config, { lineWidth: -1, noRefs: true }), 'utf-8');
}

/**
 * Main codegen pipeline: validate, generate files, update YAML.
 *
 * Does NOT run mount-plugins — the caller (API route) handles that.
 */
export async function generatePage(state: PageBuilderState): Promise<SaveResponse> {
  // Step 1: Validate
  const validationError = validate(state);
  if (validationError) {
    return { success: false, error: validationError };
  }

  // Step 2: Find skill directory
  const skillDir = findSkillDir(state.targetSkill);
  if (!skillDir) {
    return { success: false, error: `Skill "${state.targetSkill}" not found` };
  }

  const filesCreated: string[] = [];

  try {
    // Discover blocks once, used for page template and API route generation
    const { blocks: allBlocks } = await discoverBlocks();
    const blockRegistry = new Map(allBlocks.map((b) => [b.id, b]));

    // Step 3: Generate page.tsx
    const pageDir = path.join(skillDir, 'augur', 'dashboard', state.slug);
    fs.mkdirSync(pageDir, { recursive: true });

    const mcpBlockTypes = state.blocks
      .filter((b) => blockRegistry.get(b.blockType)?.source === 'mcp')
      .map((b) => b.blockType);
    const uniqueMcpBlockTypes = Array.from(new Set(mcpBlockTypes));

    const pageContent = generatePageTemplate(state, uniqueMcpBlockTypes);
    const pagePath = path.join(pageDir, 'page.tsx');
    fs.writeFileSync(pagePath, pageContent, 'utf-8');
    filesCreated.push(pagePath);

    // Step 4: Generate API route if MCP blocks present
    if (needsApiRoute(state, blockRegistry)) {
      const apiDir = path.join(skillDir, 'augur', 'api', state.hub, state.slug);
      fs.mkdirSync(apiDir, { recursive: true });

      const routeContent = generateRouteTemplate(state, blockRegistry);
      const routePath = path.join(apiDir, 'route.ts');
      fs.writeFileSync(routePath, routeContent, 'utf-8');
      filesCreated.push(routePath);
    }

    // Step 5: Update augur.yaml
    updateAugurYaml(skillDir, state);

    const pageUrl = `/${state.hub}/${state.slug}`;
    return { success: true, pageUrl, filesCreated };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return { success: false, error: message, filesCreated };
  }
}
