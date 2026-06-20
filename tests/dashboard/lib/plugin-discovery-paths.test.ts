/**
 * @jest-environment node
 */
import fs from "fs";
import os from "os";
import path from "path";

import {
  getClientSkillDirs,
  getCorePluginsDir,
  getProjectBrainSkillsRoot,
} from "@/lib/plugin-discovery/paths";

describe("plugin discovery path resolution", () => {
  const originalAugurCore = process.env.AUGUR_CORE;
  const originalManagedSkillDirs = process.env.AUGUR_MANAGED_SKILL_DIRS;
  const originalIncludeLocalSkills =
    process.env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS;

  afterEach(() => {
    if (originalAugurCore === undefined) {
      delete process.env.AUGUR_CORE;
    } else {
      process.env.AUGUR_CORE = originalAugurCore;
    }
    if (originalManagedSkillDirs === undefined) {
      delete process.env.AUGUR_MANAGED_SKILL_DIRS;
    } else {
      process.env.AUGUR_MANAGED_SKILL_DIRS = originalManagedSkillDirs;
    }
    if (originalIncludeLocalSkills === undefined) {
      delete process.env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS;
    } else {
      process.env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS =
        originalIncludeLocalSkills;
    }
  });

  it("prefers the active worktree plugins directory over inherited AUGUR_CORE drift", () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "augur-plugin-paths-"));
    const currentRoot = path.join(tempDir, "current-worktree");
    const staleRoot = path.join(tempDir, "stale-worktree");
    const currentPlugins = path.join(currentRoot, "plugins");
    const stalePlugins = path.join(staleRoot, "plugins");

    fs.mkdirSync(path.join(currentRoot, "config", "system"), { recursive: true });
    fs.mkdirSync(currentPlugins, { recursive: true });
    fs.mkdirSync(path.join(staleRoot, "config", "system"), { recursive: true });
    fs.mkdirSync(stalePlugins, { recursive: true });

    process.env.AUGUR_CORE = staleRoot;

    expect(getCorePluginsDir(path.join(currentRoot, "apps", "dashboard"))).toBe(
      currentPlugins,
    );

    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it("resolves the project-brain team skill root", () => {
    const repoRoot = path.join(os.tmpdir(), "augur-worktree");

    expect(getProjectBrainSkillsRoot(repoRoot)).toBe(
      path.join(repoRoot, "project-brain", "capabilities", "skills"),
    );
  });

  it("defaults dashboard discovery to project-brain skills for release generation", () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "augur-skill-paths-"));
    const repoRoot = path.join(tempDir, "current-worktree");
    const projectSkills = path.join(repoRoot, "project-brain", "capabilities", "skills");
    fs.mkdirSync(path.join(repoRoot, "config", "system"), { recursive: true });
    fs.mkdirSync(projectSkills, { recursive: true });
    delete process.env.AUGUR_MANAGED_SKILL_DIRS;
    delete process.env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS;

    const dirs = getClientSkillDirs(path.join(repoRoot, "apps", "dashboard"));

    expect(Object.values(dirs)).toEqual([projectSkills]);
    expect(dirs["augur"]).toBe(projectSkills);

    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it("honors explicit managed project and vault skill roots in scan order with project priority last", () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "augur-skill-paths-"));
    const repoRoot = path.join(tempDir, "current-worktree");
    const projectSkills = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const vaultSkills = path.join(tempDir, "vault", "skills");
    fs.mkdirSync(path.join(repoRoot, "config", "system"), { recursive: true });
    fs.mkdirSync(projectSkills, { recursive: true });
    fs.mkdirSync(vaultSkills, { recursive: true });

    process.env.AUGUR_MANAGED_SKILL_DIRS = [
      projectSkills,
      vaultSkills,
    ].join(path.delimiter);

    const dirs = getClientSkillDirs(path.join(repoRoot, "apps", "dashboard"));

    expect(Object.values(dirs)).toEqual([vaultSkills, projectSkills]);
    expect(dirs["augur-vault"]).toBe(vaultSkills);
    expect(dirs["augur"]).toBe(projectSkills);

    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it("drops stale project-brain skill roots from other Augur checkouts", () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "augur-skill-paths-"));
    const repoRoot = path.join(tempDir, "current-worktree");
    const staleRoot = path.join(tempDir, "main-checkout");
    const projectSkills = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const staleProjectSkills = path.join(staleRoot, "project-brain", "capabilities", "skills");
    const vaultSkills = path.join(tempDir, "vault", "capabilities", "skills");
    fs.mkdirSync(path.join(repoRoot, "config", "system"), { recursive: true });
    fs.mkdirSync(projectSkills, { recursive: true });
    fs.mkdirSync(staleProjectSkills, { recursive: true });
    fs.mkdirSync(vaultSkills, { recursive: true });

    process.env.AUGUR_MANAGED_SKILL_DIRS = [
      projectSkills,
      vaultSkills,
      staleProjectSkills,
    ].join(path.delimiter);

    const dirs = getClientSkillDirs(path.join(repoRoot, "apps", "dashboard"));

    expect(Object.values(dirs)).toEqual([vaultSkills, projectSkills]);
    expect(Object.values(dirs)).not.toContain(staleProjectSkills);
    expect(dirs["augur-vault"]).toBe(vaultSkills);
    expect(dirs["augur"]).toBe(projectSkills);

    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it("ignores repo-root skills during default release discovery", () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "augur-skill-paths-"));
    const repoRoot = path.join(tempDir, "current-worktree");
    const projectSkills = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const rootSkills = path.join(repoRoot, "skills");
    fs.mkdirSync(path.join(repoRoot, "config", "system"), { recursive: true });
    fs.mkdirSync(projectSkills, { recursive: true });
    fs.mkdirSync(path.join(rootSkills, "knowledge"), { recursive: true });
    fs.writeFileSync(
      path.join(rootSkills, "knowledge", "SKILL.md"),
      [
        "---",
        "name: knowledge",
        "description: Knowledge",
        "x-augur-hub: workspace",
        "---",
        "",
      ].join("\n"),
      "utf8",
    );
    delete process.env.AUGUR_MANAGED_SKILL_DIRS;
    delete process.env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS;

    const dirs = getClientSkillDirs(path.join(repoRoot, "apps", "dashboard"));

    expect(Object.values(dirs)).toEqual([projectSkills]);
    expect(dirs["augur"]).toBe(projectSkills);
    expect(dirs["augur-root-transitional"]).toBeUndefined();

    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it("stops using the repo-root fallback once project-brain has team skills", () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "augur-skill-paths-"));
    const repoRoot = path.join(tempDir, "current-worktree");
    const projectSkills = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const rootSkills = path.join(repoRoot, "skills");
    fs.mkdirSync(path.join(repoRoot, "config", "system"), { recursive: true });
    for (const root of [projectSkills, rootSkills]) {
      fs.mkdirSync(path.join(root, "knowledge"), { recursive: true });
      fs.writeFileSync(
        path.join(root, "knowledge", "SKILL.md"),
        [
          "---",
          "name: knowledge",
          "description: Knowledge",
          "x-augur-hub: workspace",
          "---",
          "",
        ].join("\n"),
        "utf8",
      );
    }
    delete process.env.AUGUR_MANAGED_SKILL_DIRS;
    delete process.env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS;

    const dirs = getClientSkillDirs(path.join(repoRoot, "apps", "dashboard"));

    expect(Object.values(dirs)).toEqual([projectSkills]);
    expect(dirs["augur"]).toBe(projectSkills);
    expect(dirs["augur-root-transitional"]).toBeUndefined();

    fs.rmSync(tempDir, { recursive: true, force: true });
  });
});
