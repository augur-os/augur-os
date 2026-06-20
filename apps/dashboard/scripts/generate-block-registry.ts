/**
 * Generate Block Registry from plugin skill metadata contributions.blocks[]
 *
 * Scans all plugins for block declarations and produces a TypeScript registry.
 * Mirrors the pattern from generate-tab-registry.ts (ADR-218).
 *
 * Determinism: blocks sorted alphabetically by ID, idempotent output.
 *
 * Output:
 *   lib/blocks/generated-block-registry.ts
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import yaml from "js-yaml";
import type {
  BlockManifest,
  BlockType,
  ConfigSchema,
  RowAction,
  EditableField,
  BlockSearch,
  BlockFilter,
  BlockQuickAdd,
  BlockGroupBy,
  BlockProgress,
  BlockChart,
  BlockKanban,
  BlockTab,
  StatCardAction,
} from "../lib/blocks/types";
import { getClientSkillDirs } from "../lib/plugin-discovery";
import { getDashboardRoot } from "./lib/path-utils";

const scriptFilename = fileURLToPath(import.meta.url);
const scriptDir = path.dirname(scriptFilename);
const DASHBOARD_ROOT = getDashboardRoot(scriptDir);
const DASHBOARD_APP_DIR = path.join(DASHBOARD_ROOT, "app");
const OUTPUT_PATH = path.join(
  DASHBOARD_ROOT,
  "lib",
  "blocks",
  "generated-block-registry.ts",
);

/**
 * Parse YAML frontmatter from markdown content (between --- markers).
 */
function parseFrontmatter(content: string): Record<string, unknown> {
  if (!content.startsWith("---")) return {};
  const endIdx = content.indexOf("---", 3);
  if (endIdx === -1) return {};
  try {
    return (yaml.load(content.slice(3, endIdx)) as Record<string, unknown>) ?? {};
  } catch {
    return {};
  }
}

/**
 * Marker in SKILL.md header that identifies adapted copies.
 * Adapted copies should not be re-discovered as independent skills.
 */
const ADAPTED_COPY_MARKER = "AUGUR-ADAPTED-COPY";

/**
 * Check if a route has a mounted page.tsx in the dashboard app directory.
 * Returns true if the page exists, false otherwise.
 */
function hasPageForRoute(expandTo: string): boolean {
  const pathname = expandTo.split(/[?#]/, 1)[0] || "/";
  const segments = pathname.split("/").filter(Boolean);
  const pagePath = path.join(DASHBOARD_APP_DIR, ...segments, "page.tsx");
  if (fs.existsSync(pagePath)) {
    return true;
  }

  try {
    const routeGroupPageExists = fs
      .readdirSync(DASHBOARD_APP_DIR, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && /^\(.+\)$/.test(entry.name))
      .some((entry) =>
        fs.existsSync(path.join(DASHBOARD_APP_DIR, entry.name, ...segments, "page.tsx")),
      );
    if (routeGroupPageExists) {
      return true;
    }
  } catch {
    // Fall through to catch-all route detection.
  }

  if (segments.length >= 2) {
    const catchAllPagePath = path.join(
      DASHBOARD_APP_DIR,
      segments[0],
      "[[...slug]]",
      "page.tsx",
    );
    if (fs.existsSync(catchAllPagePath)) {
      return true;
    }
  }

  return false;
}

/**
 * Ensure expandTo uses the full /{hub}/{skill}/{page} route structure.
 * Some blocks declare short paths like /lifestyle/recipes — normalize
 * to the actual mounted route /lifestyle/lifestyle/recipes.
 */
function normalizeExpandTo(
  expandTo: string,
  hub: string,
  skill: string,
): string {
  if (hasPageForRoute(expandTo)) {
    return expandTo;
  }

  const segments = expandTo.split("/").filter(Boolean);
  // Already has hub/skill prefix (3+ segments with correct hub)
  if (segments.length >= 2 && segments[0] === hub && segments[1] === skill) {
    return expandTo;
  }
  // Flattened sibling hub routes such as /brain/memory are intentional.
  if (segments.length === 2 && segments[0] === hub && skill !== hub) {
    return expandTo;
  }
  // Short path like /lifestyle/recipes — needs skill segment
  if (segments.length >= 1 && segments[0] === hub) {
    const pageParts = segments.slice(1);
    return `/${hub}/${skill}${pageParts.length ? "/" + pageParts.join("/") : ""}`;
  }
  // Fully custom path — leave as-is
  return expandTo;
}

export function parseBlocksFromYaml(
  config: Record<string, unknown>,
  hub: string,
  skill: string,
): BlockManifest[] {
  const contributions = config.contributions as
    | Record<string, unknown>
    | undefined;
  if (!contributions?.blocks) return [];

  const blocks = contributions.blocks as Array<Record<string, unknown>>;
  return blocks.map((block) => {
    const rowActionsRaw = block.row_actions as
      | Array<Record<string, unknown>>
      | undefined;
    const rowActions: RowAction[] | undefined = rowActionsRaw?.map((ra) => ({
      id: ra.id as string,
      icon: ra.icon as string,
      label: ra.label as string,
      dispatch: ra.dispatch as RowAction["dispatch"],
      ...(ra.mcp_tool !== undefined && { mcp_tool: ra.mcp_tool as string }),
      ...(ra.payload_fields !== undefined && {
        payload_fields: ra.payload_fields as string[],
      }),
      ...(ra.confirm !== undefined && { confirm: ra.confirm as boolean }),
      ...(ra.confirm_message !== undefined && {
        confirm_message: ra.confirm_message as string,
      }),
      ...(ra.href_template !== undefined && {
        href_template: ra.href_template as string,
      }),
    }));

    const editableFieldsRaw = block.editable_fields as
      | Array<Record<string, unknown>>
      | undefined;
    const editableFields: EditableField[] | undefined = editableFieldsRaw?.map(
      (ef) => ({
        field: ef.field as string,
        type: ef.type as EditableField["type"],
        save_action: ef.save_action as string,
        ...(ef.options !== undefined && { options: ef.options as string[] }),
        ...(ef.min !== undefined && { min: ef.min as number }),
        ...(ef.max !== undefined && { max: ef.max as number }),
        ...(ef.placeholder !== undefined && {
          placeholder: ef.placeholder as string,
        }),
      }),
    );

    // ADR-274 Tier 1: search
    const searchRaw = block.search as Record<string, unknown> | undefined;
    const search: BlockSearch | undefined = searchRaw
      ? {
          enabled: (searchRaw.enabled as boolean) ?? false,
          ...(searchRaw.fields !== undefined && {
            fields: searchRaw.fields as string[],
          }),
          ...(searchRaw.placeholder !== undefined && {
            placeholder: searchRaw.placeholder as string,
          }),
        }
      : undefined;

    // ADR-274 Tier 1: filters (snake_case values/colors stay as-is)
    const filtersRaw = block.filters as
      | Array<Record<string, unknown>>
      | undefined;
    const filters: BlockFilter[] | undefined = filtersRaw?.map((f) => ({
      field: f.field as string,
      type: f.type as BlockFilter["type"],
      ...(f.label !== undefined && { label: f.label as string }),
      ...(f.values !== undefined && { values: f.values as string[] }),
      ...(f.colors !== undefined && {
        colors: f.colors as Record<string, string>,
      }),
    }));

    // ADR-274 Tier 1: quick_add → quickAdd
    const quickAddRaw = block.quick_add as Record<string, unknown> | undefined;
    const quickAdd: BlockQuickAdd | undefined = quickAddRaw
      ? {
          enabled: (quickAddRaw.enabled as boolean) ?? false,
          fields: (
            (quickAddRaw.fields as Array<Record<string, unknown>>) ?? []
          ).map((f) => ({
            name: f.name as string,
            type: f.type as string,
            ...(f.required !== undefined && {
              required: f.required as boolean,
            }),
            ...(f.placeholder !== undefined && {
              placeholder: f.placeholder as string,
            }),
            ...(f.options !== undefined && {
              options: f.options as string[],
            }),
          })),
          action: quickAddRaw.action as string,
        }
      : undefined;

    // ADR-274 Tier 1: group_by → groupBy
    const groupByRaw = block.group_by as Record<string, unknown> | undefined;
    const groupBy: BlockGroupBy | undefined = groupByRaw
      ? {
          field: groupByRaw.field as string,
          ...(groupByRaw.collapsed_default !== undefined && {
            collapsedDefault: groupByRaw.collapsed_default as boolean,
          }),
          ...(groupByRaw.show_count !== undefined && {
            showCount: groupByRaw.show_count as boolean,
          }),
          ...(groupByRaw.sort !== undefined && {
            sort: groupByRaw.sort as string,
          }),
        }
      : undefined;

    // ADR-274 Tier 2: view_modes → viewModes
    const viewModes = block.view_modes as string[] | undefined;
    const defaultView = (block.default_view as string) || undefined;

    // ADR-274 Tier 2: progress (snake_case → camelCase)
    const progressRaw = block.progress as
      | Record<string, unknown>
      | undefined;
    const progressDef: BlockProgress | undefined = progressRaw
      ? {
          valueField: progressRaw.value_field as string,
          maxField: progressRaw.max_field as string,
          labelField: progressRaw.label_field as string,
          ...(progressRaw.format !== undefined && {
            format: progressRaw.format as string,
          }),
          ...(progressRaw.color_rule !== undefined && {
            colorRule: progressRaw.color_rule as string,
          }),
        }
      : undefined;

    // ADR-274 Tier 2: chart (snake_case → camelCase)
    const chartRaw = block.chart as Record<string, unknown> | undefined;
    const chartDef: BlockChart | undefined = chartRaw
      ? {
          type: chartRaw.type as string,
          xField: chartRaw.x_field as string,
          yField: chartRaw.y_field as string,
          ...(chartRaw.color !== undefined && {
            color: chartRaw.color as string,
          }),
          ...(chartRaw.height !== undefined && {
            height: chartRaw.height as number,
          }),
        }
      : undefined;

    // ADR-274 Tier 3: export_enabled → exportEnabled
    const exportEnabled =
      block.export_enabled !== undefined
        ? (block.export_enabled as boolean)
        : undefined;

    // ADR-274 Tier 3: kanban (snake_case → camelCase)
    const kanbanRaw = block.kanban as Record<string, unknown> | undefined;
    const kanbanDef: BlockKanban | undefined = kanbanRaw
      ? {
          columnField: kanbanRaw.column_field as string,
          columns: kanbanRaw.columns as string[],
          cardTitleField: kanbanRaw.card_title_field as string,
          ...(kanbanRaw.card_subtitle_field !== undefined && {
            cardSubtitleField: kanbanRaw.card_subtitle_field as string,
          }),
          ...(() => {
            const onMoveRaw = kanbanRaw.on_move as
              | Record<string, unknown>
              | undefined;
            if (!onMoveRaw) return {};
            return {
              onMove: {
                action: onMoveRaw.action as string,
                idField: onMoveRaw.id_field as string,
                statusField: onMoveRaw.status_field as string,
              },
            };
          })(),
        }
      : undefined;

    // Inline stat-card action (e.g. "Sync now" → rag-sync)
    const actionRaw = block.action as Record<string, unknown> | undefined;
    const actionDef: StatCardAction | undefined = actionRaw
      ? {
          label: actionRaw.label as string,
          mcp_tool: actionRaw.mcp_tool as string,
        }
      : undefined;

    // ADR-274 Tier 3: tabs
    const tabsRaw = block.tabs as Array<Record<string, unknown>> | undefined;
    const tabsDef: BlockTab[] | undefined = tabsRaw?.map((t) => ({
      id: t.id as string,
      label: t.label as string,
      source: t.source as string,
    }));

    return {
      id: `${skill}:${block.id}`,
      type: block.type as BlockType,
      title: block.title as string,
      icon: (block.icon as string) || "Box",
      expandTo: block.expandTo
        ? (() => {
            const rawExpandTo = block.expandTo as string;
            const normalized = normalizeExpandTo(
              rawExpandTo,
              hub,
              skill,
            );
            if (normalized !== rawExpandTo && !hasPageForRoute(normalized)) {
              console.warn(
                `  [WARN] Stripping expandTo "${normalized}" from block ${skill}:${block.id} — no page.tsx found`,
              );
              return undefined;
            }
            return normalized;
          })()
        : undefined,
      configSchema: ((block.config_schema as Record<string, unknown>) ||
        {}) as ConfigSchema,
      dataSource: block.data_source
        ? (() => {
            const ds = block.data_source as Record<string, unknown>;
            if (ds.api_route) {
              console.error(
                `  [ERROR] Block ${skill}:${block.id} uses api_route — all blocks must use mcp_tool. Fix in SKILL.md x-augur-config.`,
              );
              process.exitCode = 1;
            }
            return { mcpTool: ds.mcp_tool as string | undefined };
          })()
        : undefined,
      hub,
      skill,
      category: (block.category as string) || hub,
      ...(rowActions && { rowActions }),
      ...(editableFields && { editableFields }),
      ...(actionDef && { action: actionDef }),
      // ADR-274 Tier 1
      ...(search && { search }),
      ...(filters && filters.length > 0 && { filters }),
      ...(quickAdd && { quickAdd }),
      ...(groupBy && { groupBy }),
      // ADR-274 Tier 2
      ...(viewModes && viewModes.length > 0 && { viewModes }),
      ...(defaultView && { defaultView }),
      ...(progressDef && { progress: progressDef }),
      ...(chartDef && { chart: chartDef }),
      // ADR-274 Tier 3
      ...(exportEnabled !== undefined && { exportEnabled }),
      ...(kanbanDef && { kanban: kanbanDef }),
      ...(tabsDef && tabsDef.length > 0 && { tabs: tabsDef }),
    };
  });
}

export function formatRegistryOutput(blocks: BlockManifest[]): string {
  const lines = [
    "// AUTO-GENERATED — do not edit. Run: npx tsx scripts/generate-block-registry.ts",
    "import type { BlockManifest } from './types';",
    "",
    "export const BLOCK_REGISTRY: Record<string, BlockManifest> = {",
  ];

  for (const block of blocks) {
    lines.push(
      `  '${block.id}': ${JSON.stringify(block, null, 4).replace(/\n/g, "\n  ")},`,
    );
  }

  lines.push("};");
  lines.push("");
  lines.push(
    "export const BLOCK_LIST: BlockManifest[] = Object.values(BLOCK_REGISTRY);",
  );
  lines.push("");
  lines.push("export function getBlocksByHub(hub: string): BlockManifest[] {");
  lines.push("  return BLOCK_LIST.filter((b) => b.hub === hub);");
  lines.push("}");
  lines.push("");

  return lines.join("\n");
}

/**
 * Resolve config from a SKILL.md file.
 *
 * ADR-432: Config now lives in SKILL.md frontmatter (x-augur-config).
 * Supports x-augur-config-file sidecar: loads config from an external YAML
 * file when the frontmatter has a pointer but no inline x-augur-config.
 */
function resolveSkillConfig(
  skillMdPath: string,
): { hub: string; skill: string; config: Record<string, unknown> } | null {
  if (!fs.existsSync(skillMdPath)) return null;

  const content = fs.readFileSync(skillMdPath, "utf-8");

  // Skip adapted copies
  if (content.includes(ADAPTED_COPY_MARKER)) return null;

  const data = parseFrontmatter(content);

  // ADR-802: the `x-augur-hub` field was deleted (no hub taxonomy) and the
  // dashboard collapsed to a single live surface keyed "workspace" (this mirrors
  // generate-tab-registry.ts, which keys its one hub "workspace"). Discovery
  // must NOT gate on the removed field — every real SKILL.md now lacks it, which
  // previously made this generator emit an empty registry. A skill contributes
  // blocks via `x-augur-config.contributions.blocks`. Note: `x-augur-group` is a
  // capability grouping, NOT the dashboard surface, so it must not drive `hub`.
  const hub = "workspace";

  const skillName = (data.name as string) || path.basename(path.dirname(skillMdPath));

  // Support x-augur-config-file sidecar
  let augurConfig = (data["x-augur-config"] ?? {}) as Record<string, unknown>;
  const configFile = data["x-augur-config-file"];
  if (configFile && typeof configFile === "string" && !data["x-augur-config"]) {
    const sidecarPath = path.join(path.dirname(skillMdPath), configFile as string);
    if (fs.existsSync(sidecarPath)) {
      try {
        const sidecarContent = fs.readFileSync(sidecarPath, "utf-8");
        const parsed = yaml.load(sidecarContent) as Record<string, unknown> | null;
        if (parsed && typeof parsed === "object") {
          augurConfig = parsed;
        }
      } catch {
        // Sidecar missing or invalid — proceed without config
      }
    }
  }

  // ADR-802: admit only skills that declare a contribution surface (blocks live
  // under contributions). This replaces the old "must declare x-augur-hub" gate;
  // skills with no contributions simply register no blocks.
  const contributions = (augurConfig as Record<string, unknown>).contributions;
  if (!contributions || typeof contributions !== "object") return null;

  return { hub, skill: skillName, config: augurConfig };
}

interface DiscoveredSkill {
  hub: string;
  skill: string;
  config: Record<string, unknown>;
}

/**
 * Discover all skills with block contributions from SKILL.md frontmatter.
 *
 * Scans managed skill roots in dashboard scan order.
 */
export function discoverPluginsFromSkillDirs(
  clientSkillDirs: Record<string, string>,
): DiscoveredSkill[] {
  const bySkillName = new Map<string, DiscoveredSkill>();

  for (const skillsDir of Object.values(clientSkillDirs)) {
    if (!fs.existsSync(skillsDir)) continue;
    const skills = fs
      .readdirSync(skillsDir)
      .filter((f) => {
        try {
          return fs.statSync(path.join(skillsDir, f)).isDirectory();
        } catch {
          return false;
        }
      });

    for (const skill of skills) {
      const skillMd = path.join(skillsDir, skill, "SKILL.md");
      const resolved = resolveSkillConfig(skillMd);
      if (resolved) {
        bySkillName.set(resolved.skill, resolved);
      }
    }
  }

  return Array.from(bySkillName.values());
}

function discoverPlugins(): DiscoveredSkill[] {
  return discoverPluginsFromSkillDirs(getClientSkillDirs(scriptDir));
}

export function generateBlockRegistry(): void {
  const plugins = discoverPlugins();
  const allBlocks: BlockManifest[] = [];

  for (const plugin of plugins) {
    const blocks = parseBlocksFromYaml(plugin.config, plugin.hub, plugin.skill);
    allBlocks.push(...blocks);
  }

  allBlocks.sort((a, b) => a.id.localeCompare(b.id));

  const output = formatRegistryOutput(allBlocks);
  fs.mkdirSync(path.dirname(OUTPUT_PATH), { recursive: true });
  fs.writeFileSync(OUTPUT_PATH, output, "utf-8");

  console.log(
    `Generated block registry: ${allBlocks.length} blocks from ${plugins.length} plugins`,
  );
}

// CLI entry point
const isDirectRun =
  typeof process.argv[1] === "string" &&
  path.resolve(process.argv[1]) === scriptFilename;

if (isDirectRun) {
  generateBlockRegistry();
}
