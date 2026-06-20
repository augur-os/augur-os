/**
 * @jest-environment node
 */

import fs from "fs/promises";
import os from "os";
import path from "path";

import { discoverPagesFromFilesystem } from "../../../apps/dashboard/lib/plugin-discovery/page-discovery";

describe("discoverPagesFromFilesystem", () => {
  it("filters declared flat feature pages by enabled skills", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-page-discovery-"));
    const skillRoot = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const featurePagesDir = path.join(
      repoRoot,
      "apps",
      "dashboard",
      "features",
      "pages",
      "workspace",
    );

    await fs.mkdir(path.join(repoRoot, "config", "system"), { recursive: true });
    await fs.mkdir(skillRoot, { recursive: true });
    await fs.mkdir(featurePagesDir, { recursive: true });

    const writeSkillMd = async (
      skill: string,
      dashboardPage: string,
      isOwner = true,
    ) => {
      const skillDir = path.join(skillRoot, skill);
      await fs.mkdir(skillDir, { recursive: true });
      await fs.writeFile(
        path.join(skillDir, "SKILL.md"),
        [
          "---",
          "name: " + skill,
          "description: test",
          `x-augur-hub: workspace`,
          "x-augur-group: brain",
          "x-augur-release: mvp",
          "x-augur-config:",
          `  hub:`,
          `    id: workspace`,
          `    owner: ${isOwner}`,
          `  contributions:`,
          "    pages:",
          `      ${dashboardPage}:`,
          `        title: ${dashboardPage}`,
          "        icon: Activity",
          "        order: 30",
          `x-augur-dashboard-pages: ["/workspace/${dashboardPage}"]`,
          "---",
          "",
        ].join("\n"),
        "utf8",
      );
    };

    await writeSkillMd("knowledge", "memory");
    await writeSkillMd("staged", "staged-flat", false);

    for (const pageId of ["memory", "staged-flat"]) {
      const pageDir = path.join(featurePagesDir, pageId);
      await fs.mkdir(pageDir, { recursive: true });
      await fs.writeFile(
        path.join(pageDir, "page.tsx"),
        "export default function Page() { return null; }",
        "utf8",
      );
    }

    const discovered = discoverPagesFromFilesystem({
      startDir: repoRoot,
      enabledSkills: new Set(["knowledge"]),
    });

    const discoveredRoutes = discovered.map((page) => page.routePath);
    expect(discoveredRoutes).toContain("/workspace/memory");
    expect(discoveredRoutes).not.toContain("/workspace/staged-flat");

    const memoryPage = discovered.find((page) => page.routePath === "/workspace/memory");
    expect(memoryPage?.skill).toBe("knowledge");
    expect(memoryPage?.sourceSkillDir).toBe(path.join(skillRoot, "knowledge"));
    expect(memoryPage?.sourceConfigPath).toBe(
      path.join(skillRoot, "knowledge", "SKILL.md"),
    );

    await fs.rm(repoRoot, { recursive: true, force: true });
  });

  it("records private-vault source paths for discovered skill dashboard pages", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-page-discovery-"));
    const privateSkillRoot = path.join(repoRoot, "private-vault", "skills");
    const skillDir = path.join(privateSkillRoot, "apple");
    const dashboardDir = path.join(skillDir, "augur", "dashboard");

    await fs.mkdir(path.join(repoRoot, "config", "system"), { recursive: true });
    await fs.mkdir(dashboardDir, { recursive: true });
    await fs.writeFile(
      path.join(skillDir, "SKILL.md"),
      [
        "---",
        "name: apple",
        "description: Apple",
        "x-augur-dashboard-pages:",
        "  - route: /workspace/apple",
        "    title: Apple",
        "x-augur-config:",
        "  hub:",
        "    id: workspace",
        "    owner: false",
        "---",
        "",
      ].join("\n"),
      "utf8",
    );
    await fs.writeFile(
      path.join(dashboardDir, "page.tsx"),
      "export default function Page() { return null; }",
      "utf8",
    );

    const previous = process.env.AUGUR_MANAGED_SKILL_DIRS;
    process.env.AUGUR_MANAGED_SKILL_DIRS = privateSkillRoot;
    try {
      const discovered = discoverPagesFromFilesystem({
        startDir: repoRoot,
        enabledSkills: new Set(["apple"]),
      });

      const applePage = discovered.find((page) => page.routePath === "/workspace/apple");
      expect(applePage?.sourceSkillDir).toBe(skillDir);
      expect(applePage?.sourceConfigPath).toBe(path.join(skillDir, "SKILL.md"));
    } finally {
      if (previous === undefined) {
        delete process.env.AUGUR_MANAGED_SKILL_DIRS;
      } else {
        process.env.AUGUR_MANAGED_SKILL_DIRS = previous;
      }
      await fs.rm(repoRoot, { recursive: true, force: true });
    }
  });

  it("uses project-brain page metadata over a private-vault duplicate even when hub metadata changes", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-page-discovery-"));
    const sharedSkillRoot = path.join(repoRoot, "project-brain", "capabilities", "skills");
    const privateSkillRoot = path.join(repoRoot, "private-vault", "skills");

    // ADR-802 Phase 2: discovery reads x-augur-dashboard-pages for the surface
    // id (first route segment). Hub metadata (x-augur-config.hub.id) is still
    // used by resolveHubRole but not for the route. When both vaults declare
    // the same skill, the shared (project-brain) entry wins because
    // AUGUR_MANAGED_SKILL_DIRS lists it first.
    const writeSkill = async (root: string, route: string) => {
      const skillDir = path.join(root, "apple");
      const dashboardDir = path.join(skillDir, "augur", "dashboard");
      await fs.mkdir(dashboardDir, { recursive: true });
      await fs.writeFile(
        path.join(skillDir, "SKILL.md"),
        [
          "---",
          "name: apple",
          "description: Apple",
          "x-augur-dashboard-pages:",
          `  - route: ${route}`,
          "    title: Apple",
          "x-augur-config:",
          "  hub:",
          `    id: workspace`,
          "    owner: false",
          "---",
          "",
        ].join("\n"),
        "utf8",
      );
      await fs.writeFile(
        path.join(dashboardDir, "page.tsx"),
        "export default function Page() { return null; }",
        "utf8",
      );
    };

    await fs.mkdir(path.join(repoRoot, "config", "system"), { recursive: true });
    // private-vault declares /workspace/apple-private; shared declares /workspace/apple
    await writeSkill(privateSkillRoot, "/workspace/apple-private");
    await writeSkill(sharedSkillRoot, "/workspace/apple");

    const previous = process.env.AUGUR_MANAGED_SKILL_DIRS;
    process.env.AUGUR_MANAGED_SKILL_DIRS = [
      sharedSkillRoot,
      privateSkillRoot,
    ].join(path.delimiter);
    try {
      const discovered = discoverPagesFromFilesystem({
        startDir: repoRoot,
        enabledSkills: new Set(["apple"]),
      });

      // Both are discovered (different routes), but the shared skill's entry
      // comes from project-brain, so its sourceSkillDir resolves to sharedSkillRoot.
      const sharedPage = discovered.find((page) => page.routePath === "/workspace/apple");
      expect(sharedPage).toBeDefined();
      expect(sharedPage?.sourceSkillDir).toBe(
        path.join(sharedSkillRoot, "apple"),
      );
      expect(sharedPage?.sourceConfigPath).toBe(
        path.join(sharedSkillRoot, "apple", "SKILL.md"),
      );
    } finally {
      if (previous === undefined) {
        delete process.env.AUGUR_MANAGED_SKILL_DIRS;
      } else {
        process.env.AUGUR_MANAGED_SKILL_DIRS = previous;
      }
      await fs.rm(repoRoot, { recursive: true, force: true });
    }
  });
});
