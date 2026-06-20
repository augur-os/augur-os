import type { PageConfig, BlockConfig } from "./flow-types";

/**
 * Canonical auto-page renderer for skills without custom pages (ADR-491).
 *
 * When mcpTools are provided, generates smart blocks:
 * - `get-*` tools → metrics-dashboard sources (paired into half-width blocks)
 * - `list-*` tools → data-table blocks
 * - `run-*`/`refresh-*` tools → action-bar buttons
 *
 * Falls back to the generic layout (health + actions + vault-notes + docs)
 * when no MCP tools are provided.
 */

interface AutoPageOpts {
  title?: string;
  icon?: string;
  hub?: string;
  mcpTools?: string[];
}

const ICON_MAP: Record<string, string> = {
  status: "Activity",
  health: "Heart",
  metrics: "TrendingUp",
  stats: "BarChart3",
  config: "Settings",
  portfolio: "Briefcase",
  goals: "Target",
  crypto: "Bitcoin",
  competition: "Swords",
  analytics: "PieChart",
  position: "Compass",
  gtm: "Megaphone",
  pipeline: "Workflow",
  codebase: "FileCode",
  commit: "GitCommit",
  sessions: "Clock",
  logs: "ScrollText",
  inventory: "Package",
};

const COLOR_CYCLE = ["emerald", "blue", "violet", "amber", "rose", "cyan", "purple", "pink"] as const;
const ICON_PATTERNS = Object.entries(ICON_MAP).map(([keyword, icon]) => ({
  icon,
  pattern: new RegExp(keyword),
}));

function guessIcon(tool: string): string {
  for (const { icon, pattern } of ICON_PATTERNS) {
    if (pattern.test(tool)) return icon;
  }
  return "LayoutDashboard";
}

function toolToTitle(tool: string): string {
  return tool
    .replace(/^(get|list|run|refresh|update|search)-/, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function buildDefaultPageConfig(
  skillId: string,
  opts?: AutoPageOpts,
): PageConfig {
  const tools = opts?.mcpTools ?? [];
  const title =
    opts?.title ??
    skillId
      .replace(/-/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());

  // No MCP tools → fallback to generic layout
  if (tools.length === 0) {
    return {
      title,
      icon: opts?.icon ?? "FileText",
      hub: opts?.hub ?? "",
      route: skillId,
      blocks: [
        { type: "health", mcp_tool: "get-skill-health", skill_id: skillId },
        {
          type: "action-bar",
          mcp_tool: "list-skill-actions",
          skill_id: skillId,
        },
        {
          type: "vault-notes",
          mcp_tool: "list-skill-vault-notes",
          scope: "skill" as const,
          skill_id: skillId,
        },
        { type: "markdown", mcp_tool: "get-skill-doc", skill_id: skillId },
      ],
    };
  }

  // Smart layout from MCP tools
  const blocks: BlockConfig[] = [];

  // 1. Collect action tools → action-bar
  const actionTools = tools.filter(
    (t) => t.startsWith("run-") || t.startsWith("refresh-"),
  );
  if (actionTools.length > 0) {
    blocks.push({
      type: "action-bar",
      size: "full",
      actions: actionTools.slice(0, 6).map((t) => ({
        id: t,
        label: toolToTitle(t),
        icon: guessIcon(t),
        dispatch: t.startsWith("run-") || t.startsWith("refresh-")
          ? "fire"
          : "ide",
        mcp_tool: t,
        description: toolToTitle(t),
      })),
    });
  }

  // 2. Collect get-* tools → metrics-dashboard sources (skip generic skill tools)
  const SKIP_TOOLS = new Set([
    "get-skill-health",
    "get-skill-doc",
    "list-skill-actions",
    "list-skill-vault-notes",
  ]);
  const getTools = tools.filter(
    (t) => t.startsWith("get-") && !SKIP_TOOLS.has(t),
  );

  // Pair get-tools into half-width metrics-dashboard blocks
  let colorIdx = 0;
  for (let i = 0; i < getTools.length; i += 1) {
    const tool = getTools[i];
    const hasPartner = i + 1 < getTools.length;
    blocks.push({
      type: "metrics-dashboard",
      title: toolToTitle(tool),
      size: hasPartner ? "half" : getTools.length === 1 ? "full" : "half",
      sources: [
        {
          mcp_tool: tool,
          title: toolToTitle(tool),
          icon: guessIcon(tool),
          color: COLOR_CYCLE[colorIdx % COLOR_CYCLE.length],
        },
      ],
    });
    colorIdx++;
  }

  // 3. Collect list-* tools → data-table blocks (skip generic)
  const listTools = tools.filter(
    (t) => t.startsWith("list-") && !SKIP_TOOLS.has(t),
  );
  for (const tool of listTools.slice(0, 3)) {
    blocks.push({
      type: "data-table",
      title: toolToTitle(tool),
      size: "full",
      mcp_tool: tool,
      search: { enabled: true },
    });
  }

  // If no blocks were generated, fallback
  if (blocks.length === 0) {
    blocks.push(
      { type: "health", mcp_tool: "get-skill-health", skill_id: skillId },
      {
        type: "action-bar",
        mcp_tool: "list-skill-actions",
        skill_id: skillId,
      },
    );
  }

  return {
    title,
    icon: opts?.icon ?? "FileText",
    hub: opts?.hub ?? "",
    route: skillId,
    blocks,
  };
}
