/**
 * Generate wrapper TSX files for YAML config-driven pages.
 *
 * Extracted from generate-tab-registry.ts for module size.
 *
 * For each discovered page with a yamlConfig path, generates:
 *   lib/configs/{hub}-{route}.tsx — wrapper that renders ConfigPage with inline config
 *
 * The generated wrappers are importable by the catch-all registry just like
 * normal page.tsx files.
 */

import fs from "fs/promises";
import fsSync from "fs";
import path from "path";
import yaml from "yaml";
import type { DiscoveredPage } from "../lib/plugin-discovery";
import {
  discoverRepoRoot,
  getProjectBrainSkillsRoot,
} from "../lib/plugin-discovery";

import { getDashboardRoot } from "./lib/path-utils";

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
 * Generate wrapper TSX files for YAML config-driven pages.
 *
 * For each discovered page with a yamlConfig path, generates:
 *   lib/configs/{hub}-{route}.tsx — wrapper that renders ConfigPage with inline config
 *
 * The generated wrappers are importable by the catch-all registry just like
 * normal page.tsx files.
 */
export async function generateYamlPageWrappers(
  discoveredPages: DiscoveredPage[],
  dirname: string,
): Promise<number> {
  const repoRoot = discoverRepoRoot(dirname);
  const dashboardRoot = getDashboardRoot(dirname);
  const configsDir = path.resolve(dashboardRoot, "lib", "configs");

  // Clean stale generated files
  try {
    const existing = await fs.readdir(configsDir);
    for (const f of existing) {
      if (f.endsWith(".tsx") || f.endsWith(".json")) {
        await fs.unlink(path.join(configsDir, f));
      }
    }
  } catch {
    // Directory doesn't exist yet — will be created below
  }

  const configPages = discoveredPages.filter((p) => p.yamlConfig || p.generatedConfig);
  if (configPages.length === 0) return 0;

  await fs.mkdir(configsDir, { recursive: true });

  let count = 0;
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
      const failureSource = page.yamlConfig || `generated config for ${page.skill}`;
      console.warn(`   WARNING: Failed to parse config: ${failureSource}`);
      continue;
    }

    const routeSlug = (parsed.route as string).replace(/\//g, "-");
    const wrapperName = `${parsed.hub}-${routeSlug}`;

    // Write config as JSON (for potential runtime use)
    const jsonPath = path.join(configsDir, `${wrapperName}.json`);
    await fs.writeFile(jsonPath, JSON.stringify(parsed, null, 2), "utf8");

    // Generate wrapper TSX that renders ConfigPage with inline config
    const configJson = JSON.stringify(parsed, null, 2)
      .split("\n")
      .map((line, i) => (i === 0 ? line : `  ${line}`))
      .join("\n");

    const tsxContent = `// AUTO-GENERATED from ${sourceLabel}
// Do not edit — changes will be overwritten by generate-tab-registry.ts
import { ConfigPage } from '@/components/plugin/ConfigPage';
import type { PageConfig } from '@/lib/blocks/flow-types';

const config: PageConfig = ${configJson};

export default function Page() {
  return <ConfigPage config={config} skillId="${page.skill}" />;
}
`;

    const tsxPath = path.join(configsDir, `${wrapperName}.tsx`);
    await fs.writeFile(tsxPath, tsxContent, "utf8");
    count++;
  }

  if (count > 0) {
    console.log(`   Generated ${count} YAML page wrapper(s) in lib/configs/`);
  }

  return count;
}
