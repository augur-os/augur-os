/**
 * Tool Assembly — ADR-260 Phase 3 / ADR-802 Phase 2
 *
 * Generates assembled_tool_config.json by combining:
 * - Workspace-contributor skills (declare /workspace/* pages) for skill→tool mapping
 * - System-level tool config (core_tools, shared groups, operation_hidden)
 * - Display metadata (tool display names, categories, icons)
 *
 * Output: config/dashboard/generated/assembled_tool_config.json
 *
 * This replaces the centralized mcp_tool_groups.yaml and tool_display_names.yaml
 * with a single generated file assembled from plugin data + system constants.
 */

import fs from "fs/promises";
import path from "path";
import type { MountConfig } from "./types";
import { discoverPagesFromFilesystem, type DiscoveredPage } from "../../lib/plugin-discovery/page-discovery";
import { scanSkillConfigs } from "../../lib/plugin-discovery";
import { isWorkspaceContributor } from "../../lib/plugin-discovery/scanner";

// Workspace is the only dashboard surface (ADR-802). Tool grouping and page
// discovery are gated on this single hub.
const WORKSPACE_HUB = "workspace";

// ---------------------------------------------------------------------------
// System Constants — formerly centralized in mcp_tool_groups.yaml
// These are infrastructure/cross-cutting tools, not plugin-specific.
// ---------------------------------------------------------------------------

const CORE_TOOLS: string[] = [
  // Skill discovery
  "list-skills",
  "get-skill",
  "find-skill",
  "skill-action",
  // Workflow execution
  "execute-chain",
  "get-all-chains",
  // System status
  "health",
  "metrics",
  // Utility
  "system-open",
  "system-open-file",
  "send-ide-prompt",
  // Universal search
  "search-augur-data",
  "search-documents",
  "markdown-rag-search",
  "unified-search",
  "get-context",
  "load-reference",
  // AI Bridge & Orchestration
  "get-ai-bridge-status",
  "manage-tools-catalog",
  "manage-cli-agents",
  // Dev-only (hidden in operation mode)
  "load-module",
  "get-config",
  "file-read",
  "file-write",
  "file-list",
  "file-search",
  "file-read-multi",
  "file-info",
  "switch-mcp-context",
  "preload-mcp-context",
  "get-mcp-context-stats",
  "list-mcp-tools",
  "get-mcp-diagnostics",
  "get-api-route-stats",
  "test-mcp-connection",
  "list-services",
  "get-ide-status",
  "get-chat-session",
  "save-performance-metric",
  "get-performance-metrics",
  "get-path-config",
  "update-path-config",
  "cleanup-path",
];

const TOOL_GROUPS: Record<string, string[]> = {
  WORKFLOW: [
    "execute-chain",
    "list-chains",
    "list-jobs",
    "get-job-status",
    "cancel-job",
    "list-automations",
    "validate-agent-wizard",
    "send-ide-prompt",
    "cross-skill",
    "cache-control",
  ],
  SETTINGS: [
    "get-design-standards",
    "get-ide-history",
    "get-ide-status",
    "get-chat-session",
    "update-chat-session",
    "clear-system-cache",
    "get-path-config",
    "update-path-config",
  ],
  WIKI_MAINTENANCE: [
    "wiki-read",
    "wiki-write",
    "wiki-list",
    "wiki-tags",
    "wiki-log",
    "wiki-search",
    "wiki-rebuild",
    "wiki-update",
    "wiki-apply-concept-batch",
    "wiki-report-data",
    "wiki-rewrite-candidates",
  ],
};

const PRIORITY_ORDER: string[] = ["WORKFLOW", "SETTINGS", "WIKI_MAINTENANCE"];

const OPERATION_HIDDEN: string[] = [
  "sync-bugs",
  "check-expirations",
  "list-automations",
  "cross-skill",
];

// System pages not backed by a hub — manually maintained
const SYSTEM_PAGES: Record<
  string,
  { description: string; groups: string[]; max_tools: number; skill?: string }
> = {
  "/": {
    description: "Home page / default context",
    groups: [],
    max_tools: 15,
  },
  "/browse": {
    description: "Capability inventory and control plane",
    groups: [],
    max_tools: 15,
  },
  "/settings": {
    description: "System configuration and IDE integration",
    groups: ["SETTINGS"],
    max_tools: 30,
  },
};

// Hub pages that also need shared tool groups — formerly in mcp_tool_groups.yaml
const PAGE_GROUP_OVERRIDES: Record<string, string[]> = {
  "/brain": ["WIKI_MAINTENANCE"],
  "/workspace/memory": ["WIKI_MAINTENANCE"],
};

// ---------------------------------------------------------------------------
// Display Name Defaults — auto-generated or from legacy config
// ---------------------------------------------------------------------------

const DISPLAY_NAMES: Record<
  string,
  { displayName: string; category: string; description?: string; icon?: string }
> = {
  "get-context": {
    displayName: "Get Context",
    category: "assistant",
    description: "Load relevant context for the current page",
    icon: "Brain",
  },
  "send-ide-prompt": {
    displayName: "Ask Assistant",
    category: "assistant",
    description: "Send a prompt to the AI assistant",
    icon: "MessageSquare",
  },
  "get-skill": {
    displayName: "Get Skill Info",
    category: "assistant",
    description: "Look up information about a skill",
    icon: "Info",
  },
  "list-skills": {
    displayName: "Browse Skills",
    category: "assistant",
    description: "See all available skills",
    icon: "List",
  },
  "find-skill": {
    displayName: "Find Skill",
    category: "assistant",
    description: "Search for a specific skill",
    icon: "Search",
  },
  "skill-action": {
    displayName: "Run Skill Action",
    category: "assistant",
    description: "Execute a skill's action",
    icon: "Play",
  },
  "load-reference": {
    displayName: "Load Reference",
    category: "assistant",
    description: "Load reference documentation",
    icon: "BookOpen",
  },
  "search-documents": {
    displayName: "Search Documents",
    category: "knowledge",
    description: "Search through your knowledge base",
    icon: "Search",
  },
  "index-documents": {
    displayName: "Index Documents",
    category: "knowledge",
    description: "Add documents to the knowledge base",
    icon: "Database",
  },
  "get-recent-ingestions": {
    displayName: "Recent Additions",
    category: "knowledge",
    description: "See recently added documents",
    icon: "Clock",
  },
  "markdown-rag-search": {
    displayName: "Search Notes",
    category: "knowledge",
    description: "Search through your markdown notes",
    icon: "FileText",
  },
  "markdown-rag-index": {
    displayName: "Index Notes",
    category: "knowledge",
    description: "Index new markdown notes",
    icon: "FilePlus",
  },
  "markdown-rag-stats": {
    displayName: "Knowledge Stats",
    category: "knowledge",
    description: "View knowledge base statistics",
    icon: "BarChart",
  },
  "search-augur-data": {
    displayName: "Search Data",
    category: "knowledge",
    description: "Search through your personal data",
    icon: "Search",
  },
  "analyze-import": {
    displayName: "Analyze Import",
    category: "knowledge",
    description: "Analyze data for import",
    icon: "FileSearch",
  },
  "apply-import": {
    displayName: "Apply Import",
    category: "knowledge",
    description: "Import analyzed data",
    icon: "Download",
  },
  "install-skill": {
    displayName: "Install Skill",
    category: "install",
    description: "Install an external skill from a URL or local path",
    icon: "Download",
  },
  "list-installed": {
    displayName: "List Installed",
    category: "install",
    description: "List all installed external skills with status",
    icon: "Package",
  },
  "uninstall-skill": {
    displayName: "Uninstall Skill",
    category: "install",
    description: "Remove an installed skill and clean up generated files",
    icon: "Trash2",
  },
  "execute-chain": {
    displayName: "Run Workflow",
    category: "workflow",
    description: "Execute an automated workflow",
    icon: "GitBranch",
  },
  "list-chains": {
    displayName: "Browse Workflows",
    category: "workflow",
    description: "See all available workflows",
    icon: "List",
  },
  "get-all-chains": {
    displayName: "All Workflows",
    category: "workflow",
    description: "List all workflow definitions",
    icon: "GitBranch",
  },
  "list-jobs": {
    displayName: "Running Tasks",
    category: "workflow",
    description: "See currently running tasks",
    icon: "Activity",
  },
  "get-job-status": {
    displayName: "Task Status",
    category: "workflow",
    description: "Check status of a running task",
    icon: "Clock",
  },
  "cancel-job": {
    displayName: "Cancel Task",
    category: "workflow",
    description: "Stop a running task",
    icon: "XCircle",
  },
  "refresh-inbox": {
    displayName: "Check Inbox",
    category: "inbox",
    description: "Refresh your inbox for new items",
    icon: "Inbox",
  },
  "get-reviews-summary": {
    displayName: "Review Summary",
    category: "inbox",
    description: "See pending reviews and notifications",
    icon: "Bell",
  },
  "manage-reviews": {
    displayName: "Manage Reviews",
    category: "inbox",
    description: "Review and act on notifications",
    icon: "CheckSquare",
  },
  "get-daily-summary": {
    displayName: "Daily Summary",
    category: "inbox",
    description: "Get your daily metrics and updates",
    icon: "Calendar",
  },
  health: {
    displayName: "System Health",
    category: "system",
    description: "Check system health status",
    icon: "Activity",
  },
  metrics: {
    displayName: "Metrics",
    category: "system",
    description: "View system metrics",
    icon: "BarChart",
  },
  "system-open": {
    displayName: "Open in System",
    category: "system",
    description: "Open a URL or application",
    icon: "ExternalLink",
  },
  "system-open-file": {
    displayName: "Open File",
    category: "system",
    description: "Open a file in the default application",
    icon: "FileText",
  },
  "get-system-health": {
    displayName: "Health Check",
    category: "system",
    description: "Full system health check",
    icon: "Activity",
  },
  "get-design-standards": {
    displayName: "Design Standards",
    category: "system",
    description: "Load design standards reference",
    icon: "Palette",
  },
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AssembledToolConfig {
  generated_at: string;
  core_tools: string[];
  tool_groups: Record<string, string[]>;
  priority_order: string[];
  operation_hidden: string[];
  pages: Record<
    string,
    {
      description: string;
      groups: string[];
      max_tools: number;
      skill?: string;
    }
  >;
  skill_tool_groups: Record<string, { tools: string[] }>;
  tools: Record<
    string,
    {
      displayName: string;
      category: string;
      description?: string;
      icon?: string;
    }
  >;
}

// ---------------------------------------------------------------------------
// Assembly Logic
// ---------------------------------------------------------------------------

function buildSkillToolGroups(
  repoRoot: string,
): Record<string, { tools: string[] }> {
  const groups: Record<string, { tools: string[] }> = {};
  // Workspace-contributor skills: those declaring at least one /workspace/* page.
  const skillConfigs = scanSkillConfigs({ startDir: repoRoot }).filter((sc) =>
    isWorkspaceContributor(sc.config.dashboard_pages ?? []),
  );
  const workspaceTools = new Set<string>();

  for (const skillConfig of skillConfigs) {
    const tools = Array.isArray(skillConfig.config.mcp_tools)
      ? skillConfig.config.mcp_tools
      : [];
    if (tools.length > 0) {
      groups[skillConfig.skill] = { tools: [...tools] };
    }
    for (const tool of tools) {
      workspaceTools.add(tool);
    }
  }

  // Workspace is the single dashboard surface: its tool group is the union of
  // all workspace-contributor skills' tools.
  groups[WORKSPACE_HUB] = { tools: Array.from(workspaceTools) };

  return groups;
}

function buildPages(
  discoveredPages: DiscoveredPage[],
): Record<
  string,
  { description: string; groups: string[]; max_tools: number; skill?: string }
> {
  const pages: typeof SYSTEM_PAGES = { ...SYSTEM_PAGES };

  for (const page of discoveredPages) {
    if (pages[page.routePath]) continue;
    pages[page.routePath] = {
      description: `Page ${page.routePath}`,
      groups: PAGE_GROUP_OVERRIDES[page.routePath] ?? [],
      max_tools: 20,
      skill: page.skill,
    };
  }

  // Add override-only pages (sub-routes not discovered from the filesystem)
  for (const [route, groups] of Object.entries(PAGE_GROUP_OVERRIDES)) {
    if (pages[route]) continue;
    pages[route] = {
      description: `Override page for ${route}`,
      groups,
      max_tools: 20,
    };
  }

  return pages;
}

export async function assembleToolConfig(
  repoRoot: string,
): Promise<AssembledToolConfig> {
  const discoveredPages = discoverPagesFromFilesystem({ startDir: repoRoot }).filter(
    (page) => page.hubId === WORKSPACE_HUB,
  );

  return {
    generated_at: new Date().toISOString(),
    core_tools: CORE_TOOLS,
    tool_groups: TOOL_GROUPS,
    priority_order: PRIORITY_ORDER,
    operation_hidden: OPERATION_HIDDEN,
    pages: buildPages(discoveredPages),
    skill_tool_groups: buildSkillToolGroups(repoRoot),
    tools: DISPLAY_NAMES,
  };
}

export async function assembleAndWriteToolConfig(
  config: MountConfig,
): Promise<AssembledToolConfig> {
  const outputPath = path.join(
    config.repoRoot,
    "config",
    "dashboard",
    "generated",
    "assembled_tool_config.json",
  );

  const assembled = await assembleToolConfig(config.repoRoot);

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, JSON.stringify(assembled, null, 2) + "\n");

  const toolCount = Object.keys(assembled.tools).length;
  const skillCount = Object.keys(assembled.skill_tool_groups).length;
  const pageCount = Object.keys(assembled.pages).length;
  console.log(
    `   Generated assembled_tool_config.json (${toolCount} display names, ${skillCount} skill groups, ${pageCount} pages)`,
  );

  return assembled;
}
