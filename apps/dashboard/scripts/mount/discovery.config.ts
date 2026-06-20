/**
 * Mount Plugins — Discovery skill path & config parsing
 *
 * Resolves a skill's config file and web directories and parses SKILL.md
 * frontmatter into a DashboardYaml-compatible config object.
 *
 * Split out of discovery.ts (WS5 decomposition) — moved verbatim.
 */

import fsSync from "fs";
import path from "path";
import yaml from "yaml";
import type { DashboardYaml } from "../../lib/plugin-discovery";
import { parseFrontmatter } from "./discovery.shared";

// ============================================================================
// Skill Path Resolution
// ============================================================================

/**
 * Resolve the config file and web directories for a skill.
 *
 * ADR-432: Config now lives in SKILL.md frontmatter (x-augur-config).
 * Dashboard/API/lib directories remain under augur/.
 */
export async function resolveSkillPaths(skillDir: string): Promise<{
  configPath: string;
  dashboardDir: string;
  apiDir: string;
  libDir: string;
} | null> {
  const skillMd = path.join(skillDir, "SKILL.md");
  if (!fsSync.existsSync(skillMd)) {
    return null;
  }

  // Verify SKILL.md has a dashboard contribution signal in frontmatter
  // (ADR-802 Phase 2: x-augur-hub gate removed; admit on x-augur-dashboard-pages,
  // x-augur-mcp-tools, or non-empty x-augur-config/x-augur-config-file)
  try {
    const content = fsSync.readFileSync(skillMd, "utf8");
    const data = parseFrontmatter(content);
    const pages = data["x-augur-dashboard-pages"];
    const mcpTools = data["x-augur-mcp-tools"];
    const hasPages = Array.isArray(pages) && pages.length > 0;
    const hasMcpTools = Array.isArray(mcpTools) && mcpTools.length > 0;
    const hasConfig = !!data["x-augur-config"] || !!data["x-augur-config-file"];
    if (!hasPages && !hasMcpTools && !hasConfig) {
      return null;
    }
  } catch {
    return null;
  }

  const augurSubdir = path.join(skillDir, "augur");
  return {
    configPath: skillMd,
    dashboardDir: path.join(augurSubdir, "dashboard"),
    apiDir: path.join(augurSubdir, "api"),
    libDir: path.join(augurSubdir, "lib"),
  };
}

// ============================================================================
// Plugin Directory Scanning
// ============================================================================

/**
 * Parse SKILL.md frontmatter into a DashboardYaml-compatible config object.
 *
 * ADR-802 Phase 2: x-augur-hub is removed from frontmatter. Admit a skill
 * when it declares any dashboard contribution signal:
 *   - x-augur-dashboard-pages (a /workspace/* route)
 *   - x-augur-mcp-tools (non-empty)
 *   - x-augur-config / x-augur-config-file (non-empty)
 *
 * contributes_to is derived from the first declared workspace page route
 * (e.g. "/workspace/memory" → "workspace"), or defaults to "workspace".
 */
export function parseSkillMdConfig(filePath: string, content: string): DashboardYaml | null {
  const data = parseFrontmatter(content);

  // Support x-augur-config-file sidecar: load config from external YAML
  // when frontmatter has a pointer but no inline x-augur-config.
  let augurConfig = (data["x-augur-config"] ?? {}) as Record<string, unknown>;
  const configFile = data["x-augur-config-file"];
  if (configFile && typeof configFile === "string" && !data["x-augur-config"]) {
    const sidecarPath = path.join(path.dirname(filePath), configFile);
    try {
      const sidecarContent = fsSync.readFileSync(sidecarPath, "utf8");
      const parsed = yaml.parse(sidecarContent) as Record<string, unknown> | null;
      if (parsed && typeof parsed === "object") {
        augurConfig = parsed;
      }
    } catch {
      // Sidecar missing or invalid — proceed without config
    }
  }

  const rawPages = data["x-augur-dashboard-pages"];
  const mcpTools = Array.isArray(data["x-augur-mcp-tools"])
    ? (data["x-augur-mcp-tools"] as string[])
    : undefined;

  // Admit condition: any contribution signal must be present
  const hasPages = Array.isArray(rawPages) && rawPages.length > 0;
  const hasMcpTools = !!(mcpTools && mcpTools.length);
  const hasConfig = !!(augurConfig && Object.keys(augurConfig).length);
  if (!hasPages && !hasMcpTools && !hasConfig) return null;

  // Derive contributes_to (ADR-802 Phase 2: x-augur-hub removed from frontmatter):
  // 1. Prefer first declared dashboard page route segment (e.g. /workspace/foo → workspace)
  //    — this is the authoritative surface signal, matching scanner.ts behaviour
  // 2. Fall back to x-augur-config.hub.id (legacy surface for skills with no pages)
  // 3. Default to "workspace"
  let contributes_to = "workspace";
  let derivedFromPages = false;
  if (hasPages && Array.isArray(rawPages)) {
    for (const entry of rawPages) {
      const route =
        typeof entry === "string" ? entry : (entry as Record<string, unknown>)?.["route"];
      if (typeof route === "string" && route.startsWith("/")) {
        const segment = route.replace(/^\//, "").split("/")[0];
        if (segment) {
          contributes_to = segment;
          derivedFromPages = true;
          break;
        }
      }
    }
  }
  if (!derivedFromPages) {
    const hubBlock = augurConfig.hub as Record<string, unknown> | undefined;
    if (hubBlock && typeof hubBlock.id === "string" && hubBlock.id) {
      contributes_to = hubBlock.id;
    }
  }

  const dependencies = data["x-augur-dependencies"] ?? augurConfig.dependencies;

  return {
    contributes_to,
    ...augurConfig,
    dependencies,
  } as DashboardYaml;
}
