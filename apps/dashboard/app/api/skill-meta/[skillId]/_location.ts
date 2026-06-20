/**
 * Skill location resolution, bundle derivation, and status fetch for the
 * Skill Meta API route.
 *
 * Extracted from route.ts (WS5 decomposition). Sub-modules import siblings
 * directly (never via a package index) to avoid import cycles.
 */

import path from "path";
import yaml from "js-yaml";
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";
import { mcpReadFile } from "./_mcp";
import { normalizeSkillStatus, frontmatterString } from "./_normalize";
import type {
  AugurYaml,
  SkillStatusPayload,
  SkillRuntimeLocation,
  SkillLocationRoots,
} from "./_types";

const RETIRED_REPO_ROOT_SKILL_SEGMENTS = ["skills"];

function resolveSkillLocation(location: string): {
  skillDir: string;
  skillFilePath: string;
  structuredSkill: boolean;
} {
  const normalized = location.trim();
  const lastSegment = normalized.split(/[\\/]/).pop() || "";
  const looksLikeFile = /\.[a-z0-9]+$/i.test(lastSegment);
  if (!looksLikeFile) {
    return {
      skillDir: normalized,
      skillFilePath: `${normalized}/SKILL.md`,
      structuredSkill: true,
    };
  }

  const separatorIndex = Math.max(normalized.lastIndexOf("/"), normalized.lastIndexOf("\\"));
  const skillDir = separatorIndex >= 0 ? normalized.slice(0, separatorIndex) : ".";
  return {
    skillDir,
    skillFilePath: normalized,
    structuredSkill: lastSegment === "SKILL.md",
  };
}

function normalizeSkillLocationPath(location: string): string {
  return location.trim().replace(/\\/g, "/").replace(/\/+$/, "");
}

function expandHomePath(location: string): string {
  if (location === "~") return process.env.HOME || process.env.USERPROFILE || location;
  if (location.startsWith("~/") || location.startsWith("~\\")) {
    const home = process.env.HOME || process.env.USERPROFILE;
    return home ? path.join(home, location.slice(2)) : location;
  }
  return location;
}

function uniqueNormalizedPaths(paths: Array<string | undefined | null>): string[] {
  const seen = new Set<string>();
  const normalizedPaths: string[] = [];
  for (const rawPath of paths) {
    if (!rawPath || !rawPath.trim()) continue;
    const normalized = normalizeSkillLocationPath(path.resolve(expandHomePath(rawPath.trim())));
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    normalizedPaths.push(normalized);
  }
  return normalizedPaths;
}

function inferredProjectRoots(): string[] {
  const cwd = path.resolve(process.cwd());
  const candidates = [
    process.env.AUGUR_ROOT,
    process.env.AUGUR_CORE,
    process.env.AUGUR_REPO,
    cwd,
  ];

  if (
    path.basename(cwd) === "dashboard" &&
    path.basename(path.dirname(cwd)) === "apps"
  ) {
    candidates.push(path.resolve(cwd, "../.."));
  }

  return uniqueNormalizedPaths(candidates);
}

function isSameOrDescendantPath(location: string, root: string): boolean {
  return location === root || location.startsWith(`${root}/`);
}

function isUnderAnyRoot(location: string, roots: string[]): boolean {
  return roots.some((root) => isSameOrDescendantPath(location, root));
}

function addVaultSkillRoot(roots: string[], vaultPath: unknown): void {
  if (typeof vaultPath !== "string" || !vaultPath.trim()) return;
  roots.push(path.join(vaultPath.trim(), "skills"));
}

function configuredVaultSkillRootsFromEnv(): string[] {
  const roots: string[] = [];
  addVaultSkillRoot(roots, process.env.AUGUR_VAULT);
  return roots;
}

async function configuredVaultSkillRootsFromConfig(): Promise<string[]> {
  const roots: string[] = [];

  const projectYaml = await mcpReadFile("project.yaml", "code");
  if (projectYaml) {
    try {
      const projectConfig = yaml.load(projectYaml) as Record<string, any> | null;
      addVaultSkillRoot(roots, projectConfig?.paths?.vault);
    } catch {
      // Ignore malformed config here; skill-status source still carries truth.
    }
  }

  const vaultYaml = await mcpReadFile("config/system/vault.yaml", "code");
  if (vaultYaml) {
    try {
      const vaultConfig = yaml.load(vaultYaml) as Record<string, any> | null;
      addVaultSkillRoot(roots, vaultConfig?.vault?.path);
    } catch {
      // Ignore malformed config here; the route can still use explicit sources.
    }
  }

  return roots;
}

async function getSkillLocationRoots(): Promise<SkillLocationRoots> {
  const projectRoots = inferredProjectRoots();
  return {
    sharedSkillRoots: uniqueNormalizedPaths(
      projectRoots.map((root) =>
        path.join(root, "project-brain", "capabilities", "skills"),
      ),
    ),
    privateSkillRoots: uniqueNormalizedPaths([
      ...configuredVaultSkillRootsFromEnv(),
      ...(await configuredVaultSkillRootsFromConfig()),
    ]),
    repoRootSkillRoots: uniqueNormalizedPaths(
      projectRoots.map((root) =>
        path.join(root, ...RETIRED_REPO_ROOT_SKILL_SEGMENTS),
      ),
    ),
  };
}

function stripSkillMdSuffix(location: string): string {
  return location.endsWith("/SKILL.md")
    ? location.slice(0, -"/SKILL.md".length)
    : location;
}

function isKnownExternalClientSkillPath(location: string): boolean {
  return (
    location.startsWith("~/.claude/skills/") ||
    location.startsWith("~/.codex/skills/") ||
    location.startsWith("~/.gemini/skills/") ||
    location.startsWith("~/.opencode/skills/") ||
    location.startsWith("~/.agents/skills/") ||
    location.includes("/.claude/skills/") ||
    location.includes("/.codex/skills/") ||
    location.includes("/.gemini/skills/") ||
    location.includes("/.opencode/skills/") ||
    location.includes("/.agents/skills/") ||
    location.includes("/plugins/cache/") ||
    location.includes("/skills-latest/skills/") ||
    location.includes("/.config/opencode/skills/")
  );
}

function isRepoRootSkillLocation(
  location: string,
  skillId: string,
  status?: SkillStatusPayload | null,
  roots?: SkillLocationRoots,
): boolean {
  const normalized = normalizeSkillLocationPath(expandHomePath(location));
  const skillDir = stripSkillMdSuffix(normalized).replace(/^\.\//, "");
  const relativeRootSkillDir = `skills/${skillId}`;

  if (
    skillDir === relativeRootSkillDir ||
    skillDir.startsWith(`${relativeRootSkillDir}/`)
  ) {
    return true;
  }

  if (
    status?.source === "private-vault" ||
    skillDir.includes("/project-brain/capabilities/skills/") ||
    skillDir.startsWith("project-brain/capabilities/skills/") ||
    skillDir.includes("/private-vault/capabilities/skills/") ||
    skillDir.startsWith("private-vault/capabilities/skills/") ||
    status?.ownership === "external" ||
    isKnownExternalClientSkillPath(skillDir)
  ) {
    return false;
  }

  if (roots && isUnderAnyRoot(skillDir, roots.sharedSkillRoots)) return false;
  if (roots && isUnderAnyRoot(skillDir, roots.privateSkillRoots)) return false;
  if (roots && isUnderAnyRoot(skillDir, roots.repoRootSkillRoots)) return true;
  return false;
}

export async function resolveAllowedSkillLocation(
  skillId: string,
  location: string,
  status?: SkillStatusPayload | null,
): Promise<SkillRuntimeLocation | null> {
  const roots = await getSkillLocationRoots();
  if (isRepoRootSkillLocation(location, skillId, status, roots)) {
    return null;
  }

  const resolved = resolveSkillLocation(location);
  return {
    skillDir: resolved.skillDir,
    skillReadDir: resolved.skillDir,
    skillFilePath: resolved.skillFilePath,
    structuredSkill: resolved.structuredSkill,
  };
}

export function resolveSkillRepo(filePath: string): "code" | "auto" {
  const normalized = filePath.trim();
  if (
    normalized.startsWith("/") ||
    normalized.startsWith("~/") ||
    /^[A-Za-z]:[\\/]/.test(normalized)
  ) {
    return "auto";
  }
  return "code";
}

export async function resolveRepoOwnedFallbackSkillLocation(
  skillId: string,
): Promise<SkillRuntimeLocation | null> {
  const sharedSkillDir = `project-brain/capabilities/skills/${skillId}`;
  const sharedSkillFilePath = `${sharedSkillDir}/SKILL.md`;
  const sharedSkillContent = await mcpReadFile(sharedSkillFilePath, "code");
  if (sharedSkillContent && sharedSkillContent.trim()) {
    return {
      skillDir: sharedSkillDir,
      skillReadDir: sharedSkillDir,
      skillFilePath: sharedSkillFilePath,
      structuredSkill: true,
    };
  }

  return null;
}

export async function fetchSkillStatus(skillId: string): Promise<SkillStatusPayload | null> {
  try {
    const result = await callMCPTool("skill-status", { name: skillId });
    if (result.isError) return null;
    return normalizeSkillStatus(MCPBridge.parseJSON(result));
  } catch {
    return null;
  }
}

/** Extract the bundle name from an old plugins/<bundle>/skills/<skill> path. */
function extractBundle(skillDir: string): string {
  const sep = "/";
  const parts = skillDir.split(sep);
  // Also handle backslash paths from Windows
  const allParts = parts.flatMap((p) => p.split("\\"));
  const skillsIdx = allParts.lastIndexOf("skills");
  if (skillsIdx > 0) {
    return allParts[skillsIdx - 1];
  }
  return "";
}

export function deriveBundle(skillDir: string, cfg: AugurYaml): string {
  return (
    frontmatterString(cfg, "contributes_to") ||
    frontmatterString(cfg, "x-augur-hub") ||
    extractBundle(skillDir)
  );
}
