/**
 * ADR-272 / ADR-453: Skill Meta API Route — MCP-first
 *
 * GET /api/skill-meta/[skillId]
 *
 * Assembles metadata from 11+ heterogeneous sources for a skill's auto-page.
 * Each section is fetched independently with try/catch — failures populate
 * the `_errors` record instead of returning 500.
 *
 * All file operations go through MCP tools (file-read, file-list, file-read-multi).
 * No direct fs imports.
 *
 * WS5 decomposition: the heterogeneous helpers were extracted into sibling
 * modules behind this stable route. The HTTP contract (GET + dynamic) and the
 * assembled response are unchanged.
 *   - ./_types       shared types
 *   - ./_mcp         MCP file-read / file-list helpers
 *   - ./_normalize   pure normalization / parsing helpers
 *   - ./_location    skill location resolution, bundle derivation, status fetch
 *   - ./_collectors  per-section collectors
 */

import { NextRequest, NextResponse } from "next/server";
import matter from "gray-matter";
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";
import type { AugurYaml, SkillMeta, SkillMetaSkill, DataSource } from "./_types";
import { mcpReadFile } from "./_mcp";
import {
  fetchSkillStatus,
  resolveAllowedSkillLocation,
  resolveRepoOwnedFallbackSkillLocation,
  resolveSkillRepo,
  deriveBundle,
} from "./_location";
import {
  collectSkillInfo,
  collectActions,
  collectPromptsAndCommands,
  collectMcpTools,
  collectCustomSources,
  collectVaultNotes,
  collectDocuments,
  collectAssets,
  collectDataFiles,
  collectBlocks,
  collectConfig,
  collectSkillDoc,
  collectLogs,
  collectHealth,
} from "./_collectors";

export const dynamic = "force-dynamic";

// ─── Main handler ────────────────────────────────────────────────────

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ skillId: string }> },
) {
  const { skillId } = await params;

  if (!skillId) {
    return NextResponse.json(
      { error: "Missing skillId parameter" },
      { status: 400 },
    );
  }

  const skillStatus = await fetchSkillStatus(skillId);

  // Use get-skill MCP tool to resolve skill directory and metadata
  let skillDir: string | null = null;
  let skillReadDir: string | null = null;
  let skillFilePath: string | null = null;
  let structuredSkill = true;
  let getSkillContent: string | null = null;
  try {
    const result = await callMCPTool("get-skill", { skill_name: skillId });
    if (!result.isError) {
      const rawText = MCPBridge.extractText(result).trim();
      if (rawText) {
        getSkillContent = rawText;
      }
      if (rawText.startsWith("{")) {
        const data = MCPBridge.parseJSON(result) as Record<string, any>;
        // Legacy callers may still return path metadata here.
        const resolvedPath = typeof data.skill_dir === "string"
          ? data.skill_dir
          : (typeof data.path === "string" ? data.path : null);
        if (resolvedPath) {
          const resolved = await resolveAllowedSkillLocation(
            skillId,
            resolvedPath,
            skillStatus,
          );
          if (resolved) {
            skillDir = resolved.skillDir;
            skillReadDir = resolved.skillReadDir;
            skillFilePath = resolved.skillFilePath;
            structuredSkill = resolved.structuredSkill;
          }
        }
      }
    }
  } catch {
    // Fall through — we'll try to find it ourselves
  }

  if (!skillDir && skillStatus?.location) {
    const resolved = await resolveAllowedSkillLocation(
      skillId,
      skillStatus.location,
      skillStatus,
    );
    if (resolved) {
      skillDir = resolved.skillDir;
      skillReadDir = resolved.skillReadDir;
      skillFilePath = resolved.skillFilePath;
      structuredSkill = resolved.structuredSkill;
    }
  }

  // If get-skill didn't give us a path, try the canonical project-brain skill.
  if (!skillDir) {
    const resolved = await resolveRepoOwnedFallbackSkillLocation(skillId);
    if (resolved) {
      skillDir = resolved.skillDir;
      skillReadDir = resolved.skillReadDir;
      skillFilePath = resolved.skillFilePath;
      structuredSkill = resolved.structuredSkill;
    }
  }

  if (!skillDir || !skillReadDir || !skillFilePath) {
    return NextResponse.json(
      { error: `Skill '${skillId}' not found in any plugin bundle` },
      { status: 404 },
    );
  }

  const skillRepo = resolveSkillRepo(skillFilePath);

  // Parse skill config from SKILL.md frontmatter
  let cfg: AugurYaml;
  const directSkillMdContent = await mcpReadFile(skillFilePath, skillRepo);
  const skillMdContent = directSkillMdContent && directSkillMdContent.trim()
    ? directSkillMdContent
    : getSkillContent;
  if (skillMdContent && skillMdContent.startsWith("---")) {
    try {
      cfg = (matter(skillMdContent).data as AugurYaml) || {};
    } catch {
      return NextResponse.json(
        { error: `Failed to parse metadata for skill '${skillId}'` },
        { status: 500 },
      );
    }
  } else {
    return NextResponse.json(
      {
        error: `Failed to read SKILL.md for skill '${skillId}'`,
      },
      { status: 500 },
    );
  }

  const bundle = deriveBundle(skillDir, cfg);
  const errors: Record<string, { message: string; retryable: boolean }> = {};

  // 1. Skill info (synchronous, from yaml)
  let skill: SkillMetaSkill;
  try {
    skill = collectSkillInfo(skillId, cfg, bundle, skillStatus);
  } catch (err) {
    skill = {
      id: skillId,
      title: skillId,
      icon: "Box",
      hub: bundle,
      state: "dev",
      ownership: "augur",
    };
    errors.skill = {
      message: err instanceof Error ? err.message : String(err),
      retryable: false,
    };
  }

  // 2. Health — collected in parallel below (see Promise.allSettled)

  // 3. Actions (async — scans assets/actions/*.md files)
  let actions: SkillMeta["actions"] = [];
  try {
    actions = await collectActions(cfg, skillReadDir, skillRepo, structuredSkill);
  } catch (err) {
    errors.actions = {
      message: err instanceof Error ? err.message : String(err),
      retryable: true,
    };
  }

  let prompts: SkillMeta["prompts"] = [];
  let commands: SkillMeta["commands"] = [];
  try {
    const content = await collectPromptsAndCommands(
      skillReadDir,
      skillRepo,
      structuredSkill,
    );
    prompts = content.prompts;
    commands = content.commands;
  } catch (err) {
    errors.skillContent = {
      message: err instanceof Error ? err.message : String(err),
      retryable: true,
    };
  }

  // 4. MCP tools
  let mcpTools: SkillMeta["mcpTools"] = [];
  try {
    mcpTools = collectMcpTools(cfg);
  } catch (err) {
    errors.mcpTools = {
      message: err instanceof Error ? err.message : String(err),
      retryable: false,
    };
  }

  // 5. Custom data sources
  let customSources: DataSource[] = [];
  try {
    customSources = collectCustomSources(cfg);
  } catch (err) {
    errors.customSources = {
      message: err instanceof Error ? err.message : String(err),
      retryable: false,
    };
  }

  // 6. Blocks
  let blocks: SkillMeta["blocks"] = [];
  try {
    blocks = collectBlocks(cfg);
  } catch (err) {
    errors.blocks = {
      message: err instanceof Error ? err.message : String(err),
      retryable: false,
    };
  }

  // 7. Config (synchronous from yaml)
  let config: SkillMeta["config"] = [];
  try {
    config = collectConfig(cfg);
  } catch (err) {
    errors.config = {
      message: err instanceof Error ? err.message : String(err),
      retryable: false,
    };
  }

  // 2 + 7-12. Parallel async collectors (health included)
  const [
    healthResult,
    vaultNotesResult,
    documentsResult,
    assetsResult,
    dataFilesResult,
    logsResult,
    skillDocResult,
  ] = await Promise.allSettled([
    collectHealth(skillId, bundle),
    collectVaultNotes(bundle, skillId),
    collectDocuments(bundle, skillId),
    collectAssets(skillReadDir, skillRepo, structuredSkill),
    collectDataFiles(skillId),
    collectLogs(skillId),
    collectSkillDoc(skillFilePath, skillRepo, skillMdContent),
  ]);

  const health: SkillMeta["health"] =
    healthResult.status === "fulfilled"
      ? healthResult.value
      : { status: "unknown", lastCheck: new Date().toISOString(), errors24h: 0 };
  if (healthResult.status === "rejected") {
    errors.health = { message: String(healthResult.reason), retryable: true };
  }

  const vaultNotes =
    vaultNotesResult.status === "fulfilled" ? vaultNotesResult.value : [];
  if (vaultNotesResult.status === "rejected") {
    errors.vaultNotes = {
      message: String(vaultNotesResult.reason),
      retryable: true,
    };
  }

  const documents =
    documentsResult.status === "fulfilled" ? documentsResult.value : [];
  if (documentsResult.status === "rejected") {
    errors.documents = {
      message: String(documentsResult.reason),
      retryable: true,
    };
  }

  const assets =
    assetsResult.status === "fulfilled" ? assetsResult.value : [];
  if (assetsResult.status === "rejected") {
    errors.assets = { message: String(assetsResult.reason), retryable: true };
  }

  const dataFiles =
    dataFilesResult.status === "fulfilled" ? dataFilesResult.value : [];
  if (dataFilesResult.status === "rejected") {
    errors.dataFiles = {
      message: String(dataFilesResult.reason),
      retryable: true,
    };
  }

  const routeLogs =
    logsResult.status === "fulfilled" ? logsResult.value : [];
  if (logsResult.status === "rejected") {
    errors.logs = { message: String(logsResult.reason), retryable: true };
  }

  const skillDoc =
    skillDocResult.status === "fulfilled"
      ? skillDocResult.value
      : { hasSkillMd: false };
  if (skillDocResult.status === "rejected") {
    errors.skillDoc = {
      message: String(skillDocResult.reason),
      retryable: true,
    };
  }

  // Stats derived from collected data
  const stats: SkillMeta["stats"] = [
    { key: "Actions", value: actions.length, icon: "Zap" },
    { key: "MCP Tools", value: mcpTools.length, icon: "Wrench" },
    { key: "Vault Notes", value: vaultNotes.length, icon: "FileText" },
    { key: "Documents", value: documents.length, icon: "File" },
    { key: "Data Files", value: dataFiles.length, icon: "Database" },
    { key: "Assets", value: assets.length, icon: "Package" },
  ];

  const skillMeta: SkillMeta & {
    skill: SkillMetaSkill;
    logs: typeof routeLogs;
    skillDoc: typeof skillDoc;
  } = {
    skill,
    health,
    stats,
    blocks,
    actions,
    prompts,
    commands,
    vaultNotes,
    documents,
    assets,
    dataFiles,
    config,
    mcpTools,
    customSources,
    logs: routeLogs,
    skillDoc,
    _errors: errors,
  };

  return NextResponse.json(skillMeta);
}
