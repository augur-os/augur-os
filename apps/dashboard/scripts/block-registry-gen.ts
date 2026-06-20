/**
 * Generate custom block component registry from YAML page configs and SKILL.md.
 *
 * Extracted from generate-tab-registry.ts for module size.
 *
 * Scans YAML page configs for `type: custom` blocks and generates a registry
 * mapping component names to lazy-import factories.
 *
 * Output: lib/blocks/custom-block-registry.ts
 *
 * The registry uses `@/features/components/{component}` import paths which resolve
 * to `apps/dashboard/features/components/{component}` via tsconfig paths.
 */

import fs from "fs/promises";
import fsSync from "fs";
import path from "path";
import yaml from "yaml";
import type { DiscoveredPage } from "../lib/plugin-discovery";
import {
  discoverRepoRoot,
  getClientSkillDirs,
  getProjectBrainSkillsRoot,
} from "../lib/plugin-discovery";
import { getDashboardRoot, FEATURES_DIR } from "./lib/path-utils";

/**
 * Register a custom block component if it exists on disk.
 * Returns true if registered, false otherwise. Pushes warnings on failure.
 */
function registerComponent(
  componentName: string,
  sourceLabel: string,
  componentsDir: string,
  customComponents: Map<string, string>,
  warnings: string[],
): boolean {
  const filePath = path.resolve(componentsDir, `${componentName}.tsx`);
  if (fsSync.existsSync(filePath)) {
    customComponents.set(componentName, `@/${FEATURES_DIR}/components/${componentName}`);
    return true;
  }
  warnings.push(
    `   WARNING: custom_blocks component "${componentName}" from ${sourceLabel} not found at ${filePath}`,
  );
  return false;
}

function repoRelativeSourceLabel(sourcePath: string, repoRoot: string): string {
  const resolvedSource = path.resolve(sourcePath);
  const relative = path.relative(repoRoot, resolvedSource);
  if (relative && !relative.startsWith("..") && !path.isAbsolute(relative)) {
    return relative.split(path.sep).join(path.posix.sep);
  }
  return sourcePath;
}

function generatedSkillSourceLabel(page: DiscoveredPage, repoRoot: string): string {
  if (page.sourceConfigPath) {
    return repoRelativeSourceLabel(page.sourceConfigPath, repoRoot);
  }
  if (page.sourceSkillDir) {
    return repoRelativeSourceLabel(
      path.join(page.sourceSkillDir, "SKILL.md"),
      repoRoot,
    );
  }
  return repoRelativeSourceLabel(
    path.join(getProjectBrainSkillsRoot(repoRoot), page.skill, "SKILL.md"),
    repoRoot,
  );
}

/**
 * Scan YAML page configs for `type: custom` blocks and generate a registry
 * mapping component names to lazy-import factories.
 *
 * Output: lib/blocks/custom-block-registry.ts
 */
export async function generateCustomBlockRegistry(
  discoveredPages: DiscoveredPage[],
  dirname: string,
): Promise<number> {
  const repoRoot = discoverRepoRoot(dirname);
  const dashboardRoot = getDashboardRoot(dirname);
  const blocksDir = path.resolve(dashboardRoot, "lib", "blocks");
  const componentsDir = path.resolve(dashboardRoot, FEATURES_DIR, "components");

  const customComponents = new Map<string, string>();
  const warnings: string[] = [];

  // Source 1: YAML page configs with `type: custom` blocks
  const configPages = discoveredPages.filter((p) => p.yamlConfig || p.generatedConfig);
  for (const page of configPages) {
    let parsed: Record<string, unknown>;
    let sourceLabel: string;
    try {
      if (page.yamlConfig) {
        const raw = fsSync.readFileSync(page.yamlConfig, "utf8");
        parsed = yaml.parse(raw) as Record<string, unknown>;
        sourceLabel = repoRelativeSourceLabel(page.yamlConfig, repoRoot);
      } else if (page.generatedConfig) {
        parsed = page.generatedConfig as unknown as Record<string, unknown>;
        sourceLabel = generatedSkillSourceLabel(page, repoRoot);
      } else {
        continue;
      }
    } catch {
      continue; // Already warned by generateYamlPageWrappers
    }

    const blocks = parsed.blocks;
    if (!Array.isArray(blocks)) continue;

    for (const block of blocks) {
      const b = block as Record<string, unknown>;
      if (b.type !== "custom") continue;
      const component = b.component as string | undefined;
      if (!component) {
        warnings.push(
          `   WARNING: Custom block in ${sourceLabel} missing "component" field`,
        );
        continue;
      }

      registerComponent(component, sourceLabel, componentsDir, customComponents, warnings);
    }
  }

  // Source 2: SKILL.md x-augur-config.contributions.custom_blocks[]
  const managedSkillDirs = getClientSkillDirs(dirname);
  for (const skillsDir of Object.values(managedSkillDirs)) {
    let skillDirs: string[] = [];
    try {
      skillDirs = (await fs.readdir(skillsDir, { withFileTypes: true }))
        .filter((d) => d.isDirectory())
        .map((d) => d.name);
    } catch {
      // skills root not found
      continue;
    }

    for (const skillDir of skillDirs) {
      const skillMdPath = path.resolve(skillsDir, skillDir, "SKILL.md");
      if (!fsSync.existsSync(skillMdPath)) continue;

      let raw: string;
      try {
        raw = fsSync.readFileSync(skillMdPath, "utf8");
      } catch {
        continue;
      }

      const fmMatch = raw.match(/^---\n([\s\S]*?)\n---/);
      if (!fmMatch) continue;

      let fm: Record<string, unknown>;
      try {
        fm = yaml.parse(fmMatch[1]) as Record<string, unknown>;
      } catch {
        continue;
      }

      const augurConfig = fm["x-augur-config"] as Record<string, unknown> | undefined;
      if (!augurConfig) continue;
      const contributions = augurConfig.contributions as Record<string, unknown> | undefined;
      if (!contributions) continue;
      const customBlocks = contributions.custom_blocks as Array<Record<string, unknown>> | undefined;
      if (!Array.isArray(customBlocks)) continue;

      for (const cb of customBlocks) {
        const componentName = cb.component as string | undefined;
        if (!componentName) {
          warnings.push(
            `   WARNING: custom_blocks entry in ${repoRelativeSourceLabel(skillMdPath, repoRoot)} missing "component" field`,
          );
          continue;
        }

        registerComponent(
          componentName,
          repoRelativeSourceLabel(skillMdPath, repoRoot),
          componentsDir,
          customComponents,
          warnings,
        );
      }
    }
  }

  for (const w of warnings) {
    console.warn(w);
  }

  // Generate the registry file
  const entries = Array.from(customComponents.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, importPath]) => `  "${name}": () => import("${importPath}"),`)
    .join("\n");

  const output = `// AUTO-GENERATED — DO NOT EDIT
// Generated by: scripts/generate-tab-registry.ts
// Custom block components discovered from augur/pages/*.yaml

import type { ComponentType } from "react";

export const CUSTOM_BLOCK_COMPONENTS: Record<string, () => Promise<{ default: ComponentType<any> }>> = {
${entries}
};
`;

  const outputPath = path.resolve(blocksDir, "custom-block-registry.ts");
  await fs.mkdir(blocksDir, { recursive: true });

  // Idempotency: skip write if output is identical
  try {
    const existing = await fs.readFile(outputPath, "utf8");
    if (existing === output) {
      console.log(
        `   No changes: lib/blocks/custom-block-registry.ts is already up to date`,
      );
      return customComponents.size;
    }
  } catch {
    // File doesn't exist yet
  }

  // Atomic write
  const tmpPath = outputPath + ".tmp";
  await fs.writeFile(tmpPath, output, "utf8");
  await fs.rename(tmpPath, outputPath);
  console.log(
    `   Generated: lib/blocks/custom-block-registry.ts (${customComponents.size} custom component(s))`,
  );

  return customComponents.size;
}
