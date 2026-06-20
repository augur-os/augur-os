/**
 * @jest-environment node
 */
import fs from "fs";
import os from "os";
import path from "path";

function writeSkill(root: string, skill: string): void {
  const skillDir = path.join(root, skill);
  fs.mkdirSync(skillDir, { recursive: true });
  fs.writeFileSync(
    path.join(skillDir, "SKILL.md"),
    [
      "---",
      `name: ${skill}`,
      "description: Test skill",
      "x-augur-hub: workspace",
      "---",
      "",
    ].join("\n"),
    "utf8",
  );
}

describe("skill-config runtime state", () => {
  const originalEnv = { ...process.env };
  let tempDir: string;
  let repoRoot: string;
  let runtimeDir: string;

  beforeEach(() => {
    jest.resetModules();
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "augur-skill-config-"));
    repoRoot = path.join(tempDir, "repo");
    runtimeDir = path.join(tempDir, "state");
    fs.mkdirSync(path.join(repoRoot, "config", "system"), { recursive: true });
    fs.mkdirSync(path.join(repoRoot, "project-brain", "capabilities", "skills"), { recursive: true });
    fs.mkdirSync(path.join(runtimeDir, "dashboard"), { recursive: true });
    process.env = {
      ...originalEnv,
      AUGUR_ROOT: repoRoot,
      AUGUR_STATE: runtimeDir,
    };
    delete process.env.AUGUR_MANAGED_SKILL_DIRS;
    delete process.env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS;
    delete process.env.AUGUR_INCLUDE_LOCAL_SKILLS;
  });

  afterEach(() => {
    process.env = { ...originalEnv };
    fs.rmSync(tempDir, { recursive: true, force: true });
    jest.resetModules();
  });

  it("does not apply runtime disabled state to repo-root skills after migration", async () => {
    const rootSkills = path.join(repoRoot, "skills");
    writeSkill(rootSkills, "root-only");
    fs.writeFileSync(
      path.join(runtimeDir, "dashboard", "skills-state.yaml"),
      ["version: 1", "disabled:", "  - root-only", ""].join("\n"),
      "utf8",
    );

    const { readConfigFile } = await import("@/lib/skill-config");

    expect(readConfigFile(path.join(rootSkills, "root-only")).enabled).toBe(true);
  });

  it("does not treat root skills as runtime-canonical after project-brain has team skills", async () => {
    const sharedSkills = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const rootSkills = path.join(repoRoot, "skills");
    writeSkill(sharedSkills, "shared-existing");
    writeSkill(rootSkills, "root-only");
    fs.writeFileSync(
      path.join(runtimeDir, "dashboard", "skills-state.yaml"),
      ["version: 1", "disabled:", "  - root-only", ""].join("\n"),
      "utf8",
    );

    const { readConfigFile } = await import("@/lib/skill-config");

    expect(readConfigFile(path.join(rootSkills, "root-only")).enabled).toBe(true);
  });
});
