import fs from "fs/promises";
import os from "os";
import path from "path";

import { discoverPlugins } from "../../../apps/dashboard/scripts/mount/discovery";
import { getClientSkillDirs } from "../../../apps/dashboard/lib/plugin-discovery/paths";

describe("discoverPlugins", () => {
  async function writeSkill(
    root: string,
    skill: string,
    description: string,
    hub: string = "life",
  ): Promise<void> {
    const skillDir = path.join(root, skill);
    await fs.mkdir(skillDir, { recursive: true });
    await fs.writeFile(
      path.join(skillDir, "SKILL.md"),
      [
        "---",
        `name: ${skill}`,
        `description: ${description}`,
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

  it("reads only enabled skills from a regenerated manifest", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-release-"));
    await fs.mkdir(path.join(repoRoot, "docs", "generated"), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, "docs", "generated", "skill-manifest.json"),
      JSON.stringify({
        generated_at: new Date().toISOString(),
        skills: [
          { name: "knowledge", path: "project-brain/capabilities/skills/knowledge" },
        ],
      }),
      "utf8",
    );

    for (const skill of ["knowledge", "content"]) {
      const skillDir = path.join(repoRoot, "project-brain", "capabilities", "skills", skill);
      await fs.mkdir(skillDir, { recursive: true });
      await fs.writeFile(
        path.join(skillDir, "SKILL.md"),
        [
          "---",
          `name: ${skill}`,
          "description: test",
          "x-augur-hub: workspace",
          "x-augur-group: brain",
          "x-augur-release: mvp",
          "x-augur-config:",
          "  hub:",
          "    id: brain",
          "    owner: false",
          "---",
          "",
        ].join("\n"),
        "utf8",
      );
    }

    const plugins = await discoverPlugins({
      repoRoot,
      dashboardRoot: repoRoot,
      appDir: path.join(repoRoot, "app"),
      corePluginsDir: path.join(repoRoot, "plugins"),
      userPluginsDir: null,
      clientSkillDirs: { augur: path.join(repoRoot, "project-brain", "capabilities", "skills") },
      pluginCacheDir: null,
      isDryRun: true,
      isClean: false,
      isVerbose: false,
      devHubFilter: null,
    });

    expect(plugins.map((plugin) => plugin.skill)).toEqual(["knowledge"]);
  });

  it("discovers vault-local skills from managed client roots when no fresh manifest exists", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-release-"));
    const vaultSkills = path.join(repoRoot, "vault", "skills");
    await writeSkill(vaultSkills, "apple", "vault Apple");

    const plugins = await discoverPlugins({
      repoRoot,
      dashboardRoot: repoRoot,
      appDir: path.join(repoRoot, "app"),
      corePluginsDir: path.join(repoRoot, "plugins"),
      userPluginsDir: null,
      clientSkillDirs: { "augur-vault": vaultSkills },
      pluginCacheDir: null,
      isDryRun: true,
      isClean: false,
      isVerbose: false,
      devHubFilter: null,
    });

    expect(plugins.map((plugin) => plugin.skill)).toEqual(["apple"]);
    expect(plugins[0].configPath).toBe(path.join(vaultSkills, "apple", "SKILL.md"));
  });

  it("keeps project-brain skills ahead of vault skills when managed roots contain duplicate names", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-release-"));
    const repoSkills = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const vaultSkills = path.join(repoRoot, "vault", "skills");
    await writeSkill(vaultSkills, "apple", "vault Apple");
    await writeSkill(repoSkills, "apple", "repo Apple");

    const plugins = await discoverPlugins({
      repoRoot,
      dashboardRoot: repoRoot,
      appDir: path.join(repoRoot, "app"),
      corePluginsDir: path.join(repoRoot, "plugins"),
      userPluginsDir: null,
      clientSkillDirs: { "augur-vault": vaultSkills, augur: repoSkills },
      pluginCacheDir: null,
      isDryRun: true,
      isClean: false,
      isVerbose: false,
      devHubFilter: null,
    });

    expect(plugins.map((plugin) => plugin.skill)).toEqual(["apple"]);
    expect(plugins[0].configPath).toBe(path.join(repoSkills, "apple", "SKILL.md"));
  });

  it("filters manifest entries outside allowed dashboard skill roots", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-release-"));
    const repoSkills = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const vaultSkills = path.join(repoRoot, "vault", "skills");
    await writeSkill(repoSkills, "knowledge", "repo Knowledge", "brain");
    await writeSkill(vaultSkills, "apple", "vault Apple", "life");
    await fs.mkdir(path.join(repoRoot, "docs", "generated"), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, "docs", "generated", "skill-manifest.json"),
      JSON.stringify({
        generated_at: new Date().toISOString(),
        skills: [
          { name: "knowledge", path: "project-brain/capabilities/skills/knowledge" },
          { name: "apple", path: path.join(vaultSkills, "apple") },
        ],
      }),
      "utf8",
    );

    const plugins = await discoverPlugins({
      repoRoot,
      dashboardRoot: repoRoot,
      appDir: path.join(repoRoot, "app"),
      corePluginsDir: path.join(repoRoot, "plugins"),
      userPluginsDir: null,
      clientSkillDirs: { augur: repoSkills },
      pluginCacheDir: null,
      isDryRun: true,
      isClean: false,
      isVerbose: false,
      devHubFilter: null,
    });

    expect(plugins.map((plugin) => plugin.skill)).toEqual(["knowledge"]);
  });

  it("bypasses manifest discovery when local skill roots are enabled", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-release-"));
    const repoSkills = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const vaultSkills = path.join(repoRoot, "vault", "skills");
    await writeSkill(repoSkills, "knowledge", "repo Knowledge", "brain");
    await writeSkill(vaultSkills, "apple", "vault Apple", "life");
    await fs.mkdir(path.join(repoRoot, "docs", "generated"), { recursive: true });
    await fs.writeFile(
      path.join(repoRoot, "docs", "generated", "skill-manifest.json"),
      JSON.stringify({
        generated_at: new Date().toISOString(),
        skills: [
          { name: "knowledge", path: "project-brain/capabilities/skills/knowledge" },
        ],
      }),
      "utf8",
    );

    const plugins = await discoverPlugins({
      repoRoot,
      dashboardRoot: repoRoot,
      appDir: path.join(repoRoot, "app"),
      corePluginsDir: path.join(repoRoot, "plugins"),
      userPluginsDir: null,
      clientSkillDirs: { "augur-vault": vaultSkills, augur: repoSkills },
      pluginCacheDir: null,
      isDryRun: true,
      isClean: false,
      isVerbose: false,
      devHubFilter: null,
    });

    expect(plugins.map((plugin) => plugin.skill).sort()).toEqual([
      "apple",
      "knowledge",
    ]);
  });

  it("deduplicates managed client skills by skill name even when metadata changes", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-release-"));
    const repoSkills = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const vaultSkills = path.join(repoRoot, "vault", "skills");
    await writeSkill(vaultSkills, "apple", "vault Apple", "life");
    await writeSkill(repoSkills, "apple", "promoted Apple", "command");

    const plugins = await discoverPlugins({
      repoRoot,
      dashboardRoot: repoRoot,
      appDir: path.join(repoRoot, "app"),
      corePluginsDir: path.join(repoRoot, "plugins"),
      userPluginsDir: null,
      clientSkillDirs: { "augur-vault": vaultSkills, augur: repoSkills },
      pluginCacheDir: null,
      isDryRun: true,
      isClean: false,
      isVerbose: false,
      devHubFilter: null,
    });

    expect(plugins.map((plugin) => plugin.skill)).toEqual(["apple"]);
    expect(plugins[0].hubId).toBe("command");
    expect(plugins[0].configPath).toBe(path.join(repoSkills, "apple", "SKILL.md"));
  });

  it("ignores repo-root skills during default dashboard discovery", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-release-"));
    const sharedSkills = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const rootSkills = path.join(repoRoot, "skills");
    await fs.mkdir(path.join(repoRoot, "config", "system"), { recursive: true });
    await fs.mkdir(sharedSkills, { recursive: true });
    await writeSkill(rootSkills, "knowledge", "root Knowledge", "brain");

    const plugins = await discoverPlugins({
      repoRoot,
      dashboardRoot: repoRoot,
      appDir: path.join(repoRoot, "app"),
      corePluginsDir: path.join(repoRoot, "plugins"),
      userPluginsDir: null,
      clientSkillDirs: getClientSkillDirs(repoRoot),
      pluginCacheDir: null,
      isDryRun: true,
      isClean: false,
      isVerbose: false,
      devHubFilter: null,
    });

    expect(plugins.map((plugin) => plugin.skill)).toEqual([]);
  });
});
