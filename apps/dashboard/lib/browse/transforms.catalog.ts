import type { BrowseItem, BrowseCardAction, CLIToolStatus } from "./types";
import type { BlockManifest } from "@/lib/blocks/types";
import {
  extractIndexedArtifacts,
  mergePagesSources,
  type IndexedPageEntry,
  type LiveTabEntry,
} from "./pages-merge";

// Blocks
export function transformBlocks(blocks: BlockManifest[]): BrowseItem[] {
  return blocks.map((b) => ({
    id: b.id,
    title: b.title,
    description: `${b.skill || b.hub} · ${b.type || "block"}`,
    icon: b.icon,
    typeBadge: b.type,
    primaryAction: {
      label: "Preview",
      type: "navigate",
      target: `/browse/blocks/${encodeURIComponent(b.id)}`,
    },
    metadata: { skill: b.skill, enabled: "true" },
  }));
}

// Pages
export function transformPages(
  pages: LiveTabEntry[],
  indexedPages?: IndexedPageEntry[],
): BrowseItem[] {
  return mergePagesSources(
    pages,
    extractIndexedArtifacts(indexedPages),
    indexedPages,
  );
}

// MCP Tools
export function transformMcpTools(
  tools: {
    id: string;
    title: string;
    hub: string;
    enabled: boolean;
    category: string;
  }[],
): BrowseItem[] {
  return tools.map((t) => ({
    id: t.id,
    title: t.title,
    description: `${t.category} tool${t.enabled ? "" : " (disabled)"}`,
    icon: "Wrench",
    typeBadge: t.category,
    primaryAction: {
      label: "Test Tool",
      type: "run-mcp",
      target: t.id,
    },
    metadata: { enabled: t.enabled ? "true" : "false" },
  }));
}

// Integrations
export function transformIntegrations(
  items: {
    id: string;
    title: string;
    description: string;
    hub: string;
    path: string;
    status: string;
    cli_tools?: CLIToolStatus[];
    mcp_tool_count?: number;
  }[],
): BrowseItem[] {
  return items.map((i) => {
    const cliTools: CLIToolStatus[] = (i.cli_tools || []).map((ct) => ({
      name: ct.name,
      installed: ct.installed,
      version: ct.version,
      configured: ct.configured,
      install_hint: ct.install_hint,
      homepage: ct.homepage,
    }));

    // Build CLI names string for the help action
    const installedCliNames = cliTools
      .flatMap((ct) => (ct.installed ? [ct.name] : []))
      .join(",");

    const actions: BrowseCardAction[] = [];
    if (installedCliNames) {
      actions.push({
        id: `cli-help-${i.id}`,
        label: "CLI --help",
        icon: "Terminal",
        type: "cli-help",
        target: installedCliNames,
      });
    }

    // Add "Reveal Config" action if path exists
    if (i.path) {
      actions.push({
        id: `reveal-${i.id}`,
        label: "Reveal Config",
        icon: "FolderOpen",
        type: "open-file",
        target: i.path,
      });
    }

    return {
      id: i.id,
      title: i.title,
      description: i.description,
      icon: "Plug",
      path: i.path,
      primaryAction: {
        label: "Help",
        type: "run-action",
        target: `${i.id} --help`,
      },
      actions,
      cliTools,
      metadata: {
        status: i.status,
        ...(i.mcp_tool_count ? { mcp_tool_count: String(i.mcp_tool_count) } : {}),
      },
    };
  });
}

// Prompts
export function transformPrompts(
  items: {
    id: string;
    title: string;
    description: string;
    hub: string;
    path: string;
  }[],
): BrowseItem[] {
  return items.map((p) => {
    // Parse owning skill name from path segments containing /skills/{skill}/...
    const pathParts = p.path.split("/");
    const skillsIdx = pathParts.indexOf("skills");
    const skill = skillsIdx >= 0 && skillsIdx + 1 < pathParts.length ? pathParts[skillsIdx + 1] : undefined;

    // Build a readable title from the ID (kebab-case → Title Case)
    const readableTitle = p.title
      .replace(/^ide-prompt-?/, "IDE Prompt: ")
      .replace(/-/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());

    // Build useful description — skip TODO placeholders and raw tags
    const rawDesc = p.description || "";
    const isPlaceholder = rawDesc.includes("TODO") || rawDesc.startsWith("<") || rawDesc.trim().length < 5;
    const description = isPlaceholder
      ? `Prompt template for ${skill || p.hub} skill`
      : rawDesc;

    // Detect dispatch type from the path or metadata
    const fileName = pathParts[pathParts.length - 1] || "";
    const dispatch = fileName.includes("ide-prompt") ? "ide" : undefined;

    return {
      id: p.id,
      title: readableTitle,
      description,
      icon: "MessageSquare",
      path: p.path,
      primaryAction: {
        label: "Open Template",
        type: "open-file" as const,
        target: p.path,
      },
      metadata: {
        ...(skill ? { skill } : {}),
        ...(dispatch ? { dispatch } : {}),
      },
    };
  });
}

// Commands
export function transformCommands(
  items: {
    id: string;
    title: string;
    description: string;
    hub: string;
    path: string;
    category: string;
  }[],
): BrowseItem[] {
  return items.map((c) => ({
    id: c.id,
    title: c.title,
    description: c.description,
    icon: "Terminal",
    typeBadge: c.category,
    path: c.path,
    primaryAction: {
      label: "Copy Command",
      type: "copy",
      target: c.id,
    },
    actions: [
      { id: `help-${c.id}`, label: "Show Help", icon: "Terminal", type: "run-action", target: `${c.id} --help` },
      { id: `open-${c.id}`, label: "Open File", icon: "FolderOpen", type: "open-file", target: c.path },
    ],
  }));
}

// Agents
export function transformAgents(
  items: {
    id: string;
    title: string;
    description: string;
    hub: string;
    path: string;
    tier: string;
    mode: string;
  }[],
): BrowseItem[] {
  return items.map((a) => ({
    id: a.id,
    title: a.title,
    description: a.description,
    icon: "Bot",
    typeBadge: a.tier,
    path: a.path,
    primaryAction: {
      label: "Open Config",
      type: "open-file",
      target: a.path,
    },
    metadata: { mode: a.mode, tier: a.tier },
  }));
}
