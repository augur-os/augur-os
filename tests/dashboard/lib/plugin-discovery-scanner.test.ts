/**
 * @jest-environment node
 */
import fs from "fs";
import os from "os";
import path from "path";

import {
  scanSkillConfigs,
  parseDashboardPages,
  isWorkspaceContributor,
} from "../../../apps/dashboard/lib/plugin-discovery/scanner";

function writeSkill(root: string, skill: string, hub: string): void {
  const skillDir = path.join(root, skill);
  fs.mkdirSync(skillDir, { recursive: true });
  fs.writeFileSync(
    path.join(skillDir, "SKILL.md"),
    [
      "---",
      `name: ${skill}`,
      `description: ${skill}`,
      `x-augur-hub: ${hub}`,
      "x-augur-config:",
      "  hub:",
      `    id: ${hub}`,
      "    owner: false",
      "---",
      "",
    ].join("\n"),
    "utf8",
  );
}

test("parseDashboardPages reads enriched object entries", () => {
  const pages = parseDashboardPages([
    { route: "/workspace/memory", title: "Memory", icon: "Brain", order: 10, keywords: ["memory"] },
  ]);
  expect(pages).toEqual([
    { route: "/workspace/memory", slug: "memory", title: "Memory", icon: "Brain", order: 10, keywords: ["memory"] },
  ]);
});

test("parseDashboardPages tolerates legacy string entries", () => {
  const pages = parseDashboardPages(["/workspace/inbox"]);
  expect(pages[0]).toMatchObject({ route: "/workspace/inbox", slug: "inbox" });
});

test("isWorkspaceContributor true only when a /workspace page is declared", () => {
  expect(isWorkspaceContributor(parseDashboardPages(["/workspace/memory"]))).toBe(true);
  expect(isWorkspaceContributor(parseDashboardPages(["/command/foo"]))).toBe(false);
  expect(isWorkspaceContributor(parseDashboardPages([]))).toBe(false);
});

describe("scanSkillConfigs", () => {
  const originalManagedSkillDirs = process.env.AUGUR_MANAGED_SKILL_DIRS;

  afterEach(() => {
    if (originalManagedSkillDirs === undefined) {
      delete process.env.AUGUR_MANAGED_SKILL_DIRS;
    } else {
      process.env.AUGUR_MANAGED_SKILL_DIRS = originalManagedSkillDirs;
    }
  });

  it("deduplicates managed roots by skill name so project-brain wins when hub metadata changes", () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "augur-skill-configs-"));
    const repoRoot = path.join(tempDir, "repo");
    const sharedSkills = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const privateSkills = path.join(tempDir, "private-vault", "skills");
    fs.mkdirSync(path.join(repoRoot, "config", "system"), { recursive: true });
    writeSkill(privateSkills, "apple", "life");
    writeSkill(sharedSkills, "apple", "command");
    process.env.AUGUR_MANAGED_SKILL_DIRS = [
      sharedSkills,
      privateSkills,
    ].join(path.delimiter);

    const configs = scanSkillConfigs({ startDir: repoRoot });

    expect(configs.map((config) => config.skill)).toEqual(["apple"]);
    // ADR-802 Phase 2: discovery no longer derives contributes_to from
    // x-augur-hub. The shared-root copy still wins the dedupe by skill name.
    expect(configs[0].config.contributes_to).toBeUndefined();
    expect(configs[0].path).toBe(path.join(sharedSkills, "apple", "SKILL.md"));

    fs.rmSync(tempDir, { recursive: true, force: true });
  });
});
