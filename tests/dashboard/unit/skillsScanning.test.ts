/**
 * @jest-environment node
 */
import fs from "fs/promises";
import os from "os";
import path from "path";

import {
  buildSkillPathMap,
  scanSkillPackages,
} from "@/lib/server/skillsScanning";
import { getRepoRoot } from "@/lib/server/repo";

jest.mock("@/lib/server/repo", () => ({
  getRepoRoot: jest.fn(),
}));

const mockGetRepoRoot = getRepoRoot as jest.MockedFunction<typeof getRepoRoot>;

async function writeSkill(root: string, skill: string): Promise<void> {
  const skillDir = path.join(root, skill);
  await fs.mkdir(skillDir, { recursive: true });
  await fs.writeFile(
    path.join(skillDir, "SKILL.md"),
    [
      "---",
      `name: ${skill}`,
      `description: ${skill} description`,
      "x-augur-hub: workspace",
      "---",
      "",
    ].join("\n"),
    "utf8",
  );
}

describe("scanSkillPackages", () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "augur-skills-scan-"));
    mockGetRepoRoot.mockReturnValue(tempDir);
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
    jest.clearAllMocks();
  });

  it("scans project-brain/capabilities/skills and keeps its path over duplicate root skills", async () => {
    const sharedSkills = path.join(tempDir, "project-brain", "capabilities", "skills");
    const rootSkills = path.join(tempDir, "skills");
    await writeSkill(sharedSkills, "demo");
    await writeSkill(rootSkills, "demo");

    const result = await scanSkillPackages();

    expect(result.map((skill) => skill.slug)).toEqual(["demo"]);
    expect(result[0].path).toBe("demo");
    expect(result[0].absolutePath).toBe(path.join(sharedSkills, "demo"));
  });

  it("ignores repo-root skills when project-brain/capabilities/skills is empty", async () => {
    const rootSkills = path.join(tempDir, "skills");
    await fs.mkdir(path.join(tempDir, "project-brain", "capabilities", "skills"), {
      recursive: true,
    });
    await writeSkill(rootSkills, "root-only");

    const result = await scanSkillPackages();

    expect(result).toEqual([]);
  });

  it("does not scan root-only skills once project-brain has dashboard skills", async () => {
    const sharedSkills = path.join(tempDir, "project-brain", "capabilities", "skills");
    const rootSkills = path.join(tempDir, "skills");
    await writeSkill(sharedSkills, "shared-existing");
    await writeSkill(rootSkills, "root-only");

    const result = await scanSkillPackages();

    expect(result.map((skill) => skill.slug)).toEqual(["shared-existing"]);
    expect(result[0].absolutePath).toBe(path.join(sharedSkills, "shared-existing"));
  });

  it("returns an empty list when project-brain and repo-root skills are missing", async () => {
    const result = await scanSkillPackages();

    expect(result).toEqual([]);
  });

  it("does not include repo-root skills in capability path maps", async () => {
    const rootSkills = path.join(tempDir, "skills");
    await fs.mkdir(path.join(tempDir, "project-brain", "capabilities", "skills"), {
      recursive: true,
    });
    await writeSkill(rootSkills, "root-only");

    const result = await buildSkillPathMap();

    expect(result.get("root-only")).toBeUndefined();
  });
});
