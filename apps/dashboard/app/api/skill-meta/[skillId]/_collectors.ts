/**
 * Section collectors for the Skill Meta API route.
 *
 * Extracted from route.ts (WS5 decomposition). Each collector assembles one
 * section of the SkillMeta payload from MCP-backed sources, independently of
 * the others (the route catches each failure into `_errors`).
 */

import yaml from "js-yaml";
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";
import { mcpReadFile, mcpListDir } from "./_mcp";
import {
  normalizeUpstream,
  normalizeOwnership,
  parseMarkdownContent,
  fileExtension,
} from "./_normalize";
import type {
  SkillMeta,
  DataSource,
  AugurYaml,
  SkillMetaSkill,
  SkillStatusPayload,
} from "./_types";

const DATA_FILE_EXTENSIONS = new Set(["yaml", "yml", "json", "md"]);

/** 1. Skill info from augur.yaml */
export function collectSkillInfo(
  skillId: string,
  cfg: AugurYaml,
  bundle: string,
  status?: SkillStatusPayload | null,
) : SkillMetaSkill {
  const upstream = normalizeUpstream(cfg.upstream ?? cfg["x-augur-upstream"] ?? status?.upstream);
  const source = (typeof cfg["x-augur-source"] === "string" && cfg["x-augur-source"].trim())
    ? cfg["x-augur-source"].trim()
    : status?.source ?? upstream?.source;
  const ownership = normalizeOwnership(cfg.ownership ?? status?.ownership ?? (upstream ? "adopted" : undefined));
  return {
    id: skillId,
    title: cfg.title || cfg.name || skillId,
    icon: cfg.icon || "Box",
    hub: cfg.contributes_to || cfg["x-augur-hub"] || bundle,
    state: cfg.state || "dev",
    isNewToDashboard: status?.isNewToDashboard ?? false,
    ownership,
    source,
    upstream,
    updateAvailable: status?.updateAvailable ?? false,
  };
}

/** 2. Actions from contributions + assets/actions/*.md files */
export async function collectActions(
  cfg: AugurYaml,
  skillDir: string,
  skillRepo: "code" | "auto",
  structuredSkill: boolean,
): Promise<SkillMeta["actions"]> {
  const actions: SkillMeta["actions"] = [];
  const seen = new Set<string>();
  const contributions = cfg.contributions || {};

  // Actions from contributions.actions
  const rawActions = contributions.actions || [];
  for (const action of rawActions) {
    const id = action.id || action.name || "";
    if (id) seen.add(id);
    actions.push({
      id,
      title: action.title || action.label || action.id || "",
      description: action.description || "",
      icon: action.icon,
      dispatch: action.dispatch || "ide",
      primary: action.primary ?? false,
      chips: action.chips || action.keywords || [],
    });
  }

  // Commands from contributions.commands (visible non-auto commands as actions)
  const rawCommands = contributions.commands || [];
  for (const cmd of rawCommands) {
    if (cmd.visibility === "auto") continue;
    const id = cmd.id || "";
    if (id) seen.add(id);
    actions.push({
      id,
      title: cmd.title || cmd.id || "",
      description: cmd.description || "",
      icon: cmd.icon,
      dispatch: cmd.dispatch || "ide",
      primary: cmd.primary ?? false,
      chips: cmd.chips || cmd.keywords || [],
    });
  }

  if (!structuredSkill) return actions;

  // Scan assets/actions/*.md files for additional action definitions
  const actionEntries = await mcpListDir(`${skillDir}/assets/actions`, {
    repo: skillRepo,
    pattern: "*.md",
  });
  const actionContents = await Promise.all(
    actionEntries.map(async (entry) => {
      if (entry.type !== "file") return null;
      const name = entry.name as string;
      const content = await mcpReadFile(
        `${skillDir}/assets/actions/${name}`,
        skillRepo,
      );
      return { name, content };
    }),
  );
  for (const actionFile of actionContents) {
    if (!actionFile) continue;
    const { content } = actionFile;
    if (!content || !content.startsWith("---")) continue;
    const endIdx = content.indexOf("---", 3);
    if (endIdx <= 0) continue;
    try {
      const fm = yaml.load(content.slice(3, endIdx)) as Record<string, any>;
      if (!fm || !fm.id) continue;
      if (seen.has(fm.id)) continue; // Skip duplicates from contributions
      seen.add(fm.id);
      actions.push({
        id: fm.id,
        title: fm.label || fm.title || fm.id,
        description: fm.description || "",
        icon: fm.icon,
        dispatch: fm.dispatch || "ide",
        primary: fm.primary ?? false,
        chips: fm.chips || fm.keywords || [],
      });
    } catch {
      // Skip malformed action files
    }
  }

  return actions;
}

/** 2b. Prompts and commands from Agent Skills standard directories */
export async function collectPromptsAndCommands(
  skillDir: string,
  skillRepo: "code" | "auto",
  structuredSkill: boolean,
): Promise<{
  prompts: SkillMeta["prompts"];
  commands: SkillMeta["commands"];
}> {
  if (!structuredSkill) {
    return { prompts: [], commands: [] };
  }

  const scanMarkdownDir = async (dirPath: string) => {
    const entries = await mcpListDir(dirPath, {
      repo: skillRepo,
      pattern: "*.md",
    });
    const files = entries.filter((entry) => {
      const name = typeof entry.name === "string" ? entry.name : "";
      return entry.type === "file" && name.toLowerCase().endsWith(".md");
    });

    const parsed = await Promise.all(files.map(async (entry) => {
      const name = entry.name as string;
      const content = await mcpReadFile(`${dirPath}/${name}`, skillRepo);
      return content ? parseMarkdownContent(name, content) : null;
    }));

    return parsed.filter((item): item is NonNullable<typeof item> => item !== null);
  };

  const [promptEntries, commandEntries] = await Promise.all([
    scanMarkdownDir(`${skillDir}/prompts`),
    scanMarkdownDir(`${skillDir}/commands`),
  ]);

  return {
    prompts: promptEntries.map((prompt) => ({
      id: prompt.id,
      label: prompt.label,
      description: prompt.description,
      icon: prompt.icon,
      prompt: prompt.body,
    })),
    commands: commandEntries.map((command) => ({
      id: command.id,
      label: command.label,
      description: command.description,
      icon: command.icon,
      command: `/${command.id}`,
    })),
  };
}

/** 3. MCP tools from mcp.tools[] or contributions.mcp_tools[] */
export function collectMcpTools(cfg: AugurYaml): SkillMeta["mcpTools"] {
  const tools: SkillMeta["mcpTools"] = [];

  // From top-level mcp.tools
  const mcpSection = cfg.mcp || {};
  const mcpTools = mcpSection.tools || [];
  for (const tool of mcpTools) {
    if (typeof tool === "string") {
      tools.push({ name: tool, description: "", schema: {} });
    } else if (tool && typeof tool === "object") {
      tools.push({
        name: tool.name || tool.id || "",
        description: tool.description || "",
        schema: tool.schema || tool.input_schema || {},
      });
    }
  }

  // From contributions.mcp_tools
  const contribTools = (cfg.contributions || {}).mcp_tools || [];
  for (const tool of contribTools) {
    if (typeof tool === "string") {
      tools.push({ name: tool, description: "", schema: {} });
    } else if (tool && typeof tool === "object") {
      tools.push({
        name: tool.name || tool.id || "",
        description: tool.description || "",
        schema: tool.schema || tool.input_schema || {},
      });
    }
  }

  return tools;
}

/** 4. Custom data sources from contributions.data_sources[] */
export function collectCustomSources(cfg: AugurYaml): DataSource[] {
  const sources: DataSource[] = [];
  const dataSources = (cfg.contributions || {}).data_sources || [];

  for (const ds of dataSources) {
    sources.push({
      id: ds.id || "",
      type: ds.type || "mcp_tool",
      source: ds.source || ds.mcp_tool || ds.api_route || "",
      display: ds.display || "table",
      title: ds.title || ds.id || "",
      config: ds.config,
      // ADR-274 capability fields (pass through from augur.yaml)
      search: ds.search,
      filters: ds.filters,
      quick_add: ds.quick_add,
      group_by: ds.group_by,
      stats: ds.stats,
      view_modes: ds.view_modes,
      default_view: ds.default_view,
      progress: ds.progress,
      gallery: ds.gallery,
      row_action: ds.row_action,
      chart: ds.chart,
      export: ds.export,
      kanban: ds.kanban,
      tabs: ds.tabs,
    });
  }

  return sources;
}

/** 5. Vault notes — list .md files and read first 200 chars as preview */
export async function collectVaultNotes(
  bundle: string,
  skillId: string,
): Promise<SkillMeta["vaultNotes"]> {
  const vaultDir = `${bundle}/${skillId}`;
  const entries = await mcpListDir(vaultDir, {
    repo: "data",
    pattern: "*.md",
  });

  if (entries.length === 0) return [];

  const notes = (
    await Promise.all(entries.map(async (entry) => {
      if (entry.type !== "file") return null;

      const name = entry.name as string;
      const modified = entry.modified || entry.mtime || "";

      // Read first 200 chars as preview via file-read
      const filePath = `${bundle}/${skillId}/${name}`;
      const content = await mcpReadFile(filePath, "data");
      const preview = content ? content.slice(0, 200) : "";

      return { name, modified, preview };
    }))
  ).filter(
    (note): note is NonNullable<SkillMeta["vaultNotes"]>[number] =>
      Boolean(note),
  );

  notes.sort(
    (a, b) =>
      new Date(b.modified).getTime() - new Date(a.modified).getTime(),
  );
  return notes;
}

/** 6. Documents — list files, get name/size/modified */
export async function collectDocuments(
  bundle: string,
  skillId: string,
): Promise<SkillMeta["documents"]> {
  // Documents dir is resolved by get_documents_dir()/{bundle}/{skillId}
  // The file-list tool with repo "auto" should resolve this if we give an absolute-ish path.
  // Use the known documents path pattern.
  const docsPath = `~/Documents/Augur/${bundle}/${skillId}`;
  const entries = await mcpListDir(docsPath, { repo: "auto" });

  if (entries.length === 0) return [];

  const docs: SkillMeta["documents"] = [];

  for (const entry of entries) {
    if (entry.type !== "file") continue;
    const name = entry.name as string;
    if (name.startsWith(".")) continue;

    const ext = fileExtension(name);

    docs.push({
      name,
      type: ext,
      size: entry.size ?? 0,
      modified: entry.modified || entry.mtime || "",
    });
  }

  docs.sort(
    (a, b) =>
      new Date(b.modified).getTime() - new Date(a.modified).getTime(),
  );
  return docs;
}

/** 7. Assets — scan assets/ in skill root for template files */
export async function collectAssets(
  skillDir: string,
  skillRepo: "code" | "auto",
  structuredSkill: boolean,
): Promise<SkillMeta["assets"]> {
  if (!structuredSkill) return [];
  const assetsDir = `${skillDir}/assets`;
  const entries = await mcpListDir(assetsDir, {
    repo: skillRepo,
    recursive: true,
    limit: 500,
  });

  if (entries.length === 0) return [];

  const assets: SkillMeta["assets"] = [];

  for (const entry of entries) {
    if (entry.type !== "file") continue;
    const name = entry.name as string;
    if (name.startsWith(".")) continue;

    const ext = fileExtension(name);

    // For recursive listings, the name may include relative path
    const relativeName = entry.relative_path || name;

    assets.push({
      name: relativeName,
      type: ext,
      purpose: inferAssetPurpose(name, ext),
    });
  }

  return assets;
}

/** Infer purpose of an asset file from its name/extension */
function inferAssetPurpose(name: string, ext: string): string {
  const lower = name.toLowerCase();
  if (lower.includes("template")) return "template";
  if (lower.includes("seed")) return "seed-data";
  if (lower.includes("prompt")) return "prompt";
  if (lower.includes("schema")) return "schema";
  if (ext === "yaml" || ext === "yml") return "config";
  if (ext === "json") return "data";
  if (ext === "md") return "documentation";
  if (ext === "py") return "script";
  if (ext === "ts" || ext === "tsx") return "component";
  return "resource";
}

/** 8. Data files — scan the skill vault data directory for YAML/JSON/MD files */
export async function collectDataFiles(
  skillId: string,
): Promise<SkillMeta["dataFiles"]> {
  // Use get-skill to find vault data path, or construct from convention
  // Vault data lives at get_vault_dir()/{bundle}/{skillId}/ which is the "data" repo
  // We list recursively with specific patterns
  const entries = await mcpListDir(skillId, {
    repo: "data",
    pattern: "*.{yaml,yml,json,md}",
    recursive: true,
    limit: 500,
  });

  if (entries.length === 0) return [];

  const dataFiles = (
    await Promise.all(entries.map(async (entry) => {
      if (entry.type !== "file") return null;
      const name = entry.name as string;
      if (name.startsWith(".")) return null;

      const ext = fileExtension(name, "").toLowerCase();
      if (!DATA_FILE_EXTENSIONS.has(ext)) return null;

      const relName = entry.relative_path || name;
      const fileType =
        ext === "yml" ? "yaml" : (ext as "yaml" | "json" | "md");

      // Read file content for preview
      const filePath = `${skillId}/${relName}`;
      const content = await mcpReadFile(filePath, "data");

      if (!content) {
        return { name: relName, type: fileType, count: 0, preview: [] };
      }

      if (fileType === "yaml") {
        try {
          const parsed = yaml.load(content);
          const items = Array.isArray(parsed) ? parsed : parsed ? [parsed] : [];
          return {
            name: relName,
            type: "yaml",
            count: items.length,
            preview: items.slice(0, 3) as Array<Record<string, unknown>>,
          };
        } catch {
          return { name: relName, type: "yaml", count: 0, preview: [] };
        }
      }
      if (fileType === "json") {
        try {
          const parsed = JSON.parse(content);
          const items = Array.isArray(parsed) ? parsed : parsed ? [parsed] : [];
          return {
            name: relName,
            type: "json",
            count: items.length,
            preview: items.slice(0, 3) as Array<Record<string, unknown>>,
          };
        } catch {
          return { name: relName, type: "json", count: 0, preview: [] };
        }
      }
      if (fileType === "md") {
        return {
          name: relName,
          type: "md",
          count: 1,
          preview: [{ content: content.slice(0, 200) }],
        };
      }
      return null;
    }))
  ).filter(
    (file): file is NonNullable<SkillMeta["dataFiles"]>[number] =>
      Boolean(file),
  );

  return dataFiles;
}

/** 9. Blocks from contributions.blocks[] */
export function collectBlocks(cfg: AugurYaml): SkillMeta["blocks"] {
  const blocks: SkillMeta["blocks"] = [];
  const rawBlocks = (cfg.contributions || {}).blocks || [];

  for (const block of rawBlocks) {
    blocks.push({
      id: block.id || "",
      title: block.name || block.id || "",
      icon: block.icon || "Box",
      type: block.render || "custom",
      expandTo: block.expandTo || block.expand_to,
    });
  }

  return blocks;
}

/** 10. Config from augur.yaml config: section */
export function collectConfig(cfg: AugurYaml): SkillMeta["config"] {
  const configSection = cfg.config || {};
  const entries: SkillMeta["config"] = [];

  for (const [key, value] of Object.entries(configSection)) {
    entries.push({
      key,
      value: value as unknown,
      editable: typeof value !== "object",
    });
  }

  return entries;
}

/** 10b. Check for SKILL.md and return full content for detail panel */
export async function collectSkillDoc(
  skillFilePath: string,
  skillRepo: "code" | "auto",
  fallbackContent?: string | null,
): Promise<{ hasSkillMd: boolean; skillMdPreview?: string; skillDoc?: string }> {
  const directContent = await mcpReadFile(skillFilePath, skillRepo);
  const content = directContent && directContent.trim()
    ? directContent
    : (fallbackContent ?? null);
  if (!content) {
    return { hasSkillMd: false };
  }

  return {
    hasSkillMd: true,
    skillMdPreview: content.slice(0, 300),
    skillDoc: content,
  };
}

/** 11. Scan logs for skill-related entries */
export async function collectLogs(
  skillId: string,
): Promise<Array<{ timestamp: string; level: string; message: string }>> {
  const logs: Array<{ timestamp: string; level: string; message: string }> =
    [];

  // Check skill-specific log directory via file-list
  const logEntries = await mcpListDir(`~/Library/Logs/Augur/${skillId}`, {
    repo: "auto",
    pattern: "*.log",
  });

  // Sort by name descending (log files are typically named by date), take 3
  const sortedLogs = logEntries
    .filter((e) => e.type === "file")
    .sort((a, b) =>
      (b.name as string).localeCompare(a.name as string),
    )
    .slice(0, 3);

  const skillLogEntries = await Promise.all(
    sortedLogs.map(async (logFile) => {
      const content = await mcpReadFile(
        `~/Library/Logs/Augur/${skillId}/${logFile.name}`,
        "auto",
      );
      if (!content) return [];

      return content.trim().split("\n").slice(-10).map((line) => ({
        timestamp: extractTimestamp(line),
        level: inferLogLevel(line),
        message: line.slice(0, 200),
      }));
    }),
  );
  logs.push(...skillLogEntries.flat());

  // Also check general daemon log for skill mentions (read only tail)
  const daemonContent = await mcpReadFile(
    "~/Library/Logs/Augur/daemon.log",
    "auto",
  );
  if (daemonContent) {
    // Read only the last portion for skill mentions
    const tailContent =
      daemonContent.length > 512 * 1024
        ? daemonContent.slice(-512 * 1024)
        : daemonContent;
    const lines = tailContent.trim().split("\n");
    const relevant = lines
      .filter((l) => l.toLowerCase().includes(skillId.toLowerCase()))
      .slice(-5);
    for (const line of relevant) {
      logs.push({
        timestamp: extractTimestamp(line),
        level: inferLogLevel(line),
        message: line.slice(0, 200),
      });
    }
  }

  return logs.slice(-20);
}

/** Infer log level from a log line */
function inferLogLevel(line: string): string {
  const lower = line.toLowerCase();
  if (lower.includes("error") || lower.includes("fail")) return "error";
  if (lower.includes("warn")) return "warn";
  if (lower.includes("debug")) return "debug";
  return "info";
}

/** Extract ISO timestamp from beginning of a log line, or return empty string */
function extractTimestamp(line: string): string {
  // Match ISO-8601 or common log timestamp patterns at line start
  const match = line.match(
    /^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\s]*)/,
  );
  return match ? match[1] : "";
}

/** Health from MCP get-skill-health tool, with fallback to unknown baseline */
export async function collectHealth(
  skillId: string,
  bundle: string,
): Promise<SkillMeta["health"]> {
  const fallback: SkillMeta["health"] = {
    status: "unknown",
    lastCheck: new Date().toISOString(),
    errors24h: 0,
  };

  // 1. Try MCP tool get-skill-health directly
  try {
    const result = await callMCPTool("get-skill-health", {
      skill_id: skillId,
    });

    if (!result.isError) {
      const data = MCPBridge.parseJSON(result) as Record<string, any>;
      if (data && typeof data.status === "string") {
        return {
          status: data.status as SkillMeta["health"]["status"],
          lastCheck: data.lastCheck || new Date().toISOString(),
          errors24h:
            typeof data.errors24h === "number" ? data.errors24h : 0,
        };
      }
    }
  } catch {
    // MCP call failed — try hub health route
  }

  // 2. Try hub-level health route /api/{hub}/{skill}/health
  if (bundle) {
    const port = process.env.PORT || 3000;
    const baseUrl = `http://localhost:${port}`;
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);
      const res = await fetch(
        `${baseUrl}/api/${bundle}/${skillId}/health`,
        { cache: "no-store", signal: controller.signal },
      );
      clearTimeout(timeout);

      if (res.ok) {
        const result = await res.json();
        if (result && typeof result.status === "string") {
          return {
            status: result.status,
            lastCheck: result.lastCheck || new Date().toISOString(),
            errors24h:
              typeof result.errors24h === "number" ? result.errors24h : 0,
          };
        }
      }
    } catch {
      // Hub health route unavailable
    }
  }

  // 3. Fallback
  return fallback;
}
