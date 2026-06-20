/**
 * Generate Page Manifest - ADR-105 Phase 2 + ADR-128 + ADR-802 Phase 2
 *
 * Scans plugin skill configs and generates a baseline manifest for regression
 * protection and feature detection.
 *
 * ADR-802: Workspace is the only dashboard surface. The manifest is no longer
 * a per-hub map — it has a single `workspace` page entry aggregating across the
 * workspace-contributor skills (those declaring at least one /workspace/* page
 * via x-augur-dashboard-pages).
 */

import path from "path";
import { fileURLToPath } from "url";
import {
  scanSkillConfigs,
} from "../lib/plugin-discovery";
import { isWorkspaceContributor } from "../lib/plugin-discovery/scanner";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const WORKSPACE_HUB = "workspace";

interface PageEntry {
  route: string;
  hub_id: string;
  hub_title: string;
  bundle: string;
  skill_count: number;
  has_api: boolean;
  tool_count: number;
  widget_count: number;
  tabs: string[];
}

async function main() {
  console.log("🔍 Scanning plugin skill metadata...\n");

  const allConfigs = scanSkillConfigs({ startDir: __dirname });
  const workspaceConfigs = allConfigs.filter((sc) =>
    isWorkspaceContributor(sc.config.dashboard_pages ?? []),
  );

  // Aggregate across workspace-contributor skills — workspace is the sole surface.
  const toolSet = new Set<string>();
  const slugSet = new Set<string>();
  let hasApi = false;
  for (const sc of workspaceConfigs) {
    if (sc.hasApi) hasApi = true;
    for (const tool of sc.config.mcp_tools ?? []) toolSet.add(tool);
    for (const page of sc.config.dashboard_pages ?? []) {
      if (page.slug) slugSet.add(page.slug);
    }
  }

  // widget_count has no non-hub source under the workspace-page model; pages
  // declare routes, not widget contributions. Reported as 0 (see ADR-802).
  const pages: PageEntry[] =
    workspaceConfigs.length > 0
      ? [
          {
            route: `/${WORKSPACE_HUB}`,
            hub_id: WORKSPACE_HUB,
            hub_title: "Workspace",
            bundle: WORKSPACE_HUB,
            skill_count: workspaceConfigs.length,
            has_api: hasApi,
            tool_count: toolSet.size,
            widget_count: 0,
            tabs: ["overview", ...[...slugSet].sort()],
          },
        ]
      : [];

  const totalTools = pages.reduce((sum, p) => sum + p.tool_count, 0);
  const totalWithApi = pages.filter((p) => p.has_api).length;

  console.log(
    `   ${pages.length} surface(s) from ${workspaceConfigs.length} workspace-contributor skill(s)`,
  );
  console.log(`   ${totalWithApi} surface(s) with API`);
  console.log(`   ${totalTools} total tools\n`);

  console.log("Surfaces:");
  for (const page of pages) {
    const apiIndicator = page.has_api ? " [API]" : "";
    const toolIndicator =
      page.tool_count > 0 ? ` (${page.tool_count} tools)` : "";
    console.log(
      `   ${page.route} — ${page.hub_title} (${page.skill_count} skills)${apiIndicator}${toolIndicator}`,
    );
  }
}

main().catch(console.error);
