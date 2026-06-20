/**
 * @jest-environment node
 */
import fs from "fs/promises";
import os from "os";
import path from "path";

import { generateYamlPageWrappers } from "@/scripts/yaml-page-gen";
import type { DiscoveredPage } from "@/lib/plugin-discovery";

describe("generateYamlPageWrappers", () => {
  let tempDir: string;
  let scriptsDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "augur-yaml-pages-"));
    scriptsDir = path.join(tempDir, "apps", "dashboard", "scripts");
    await fs.mkdir(path.join(tempDir, "config", "system"), { recursive: true });
    await fs.mkdir(scriptsDir, { recursive: true });
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it("labels project-brain YAML sources with repo-relative project-brain paths", async () => {
    const yamlPath = path.join(
      tempDir,
      "project-brain",
      "capabilities",
      "skills",
      "demo",
      "augur",
      "pages",
      "overview.yaml",
    );
    await fs.mkdir(path.dirname(yamlPath), { recursive: true });
    await fs.writeFile(
      yamlPath,
      [
        "hub: workspace",
        "route: demo",
        "title: Demo",
        "blocks: []",
      ].join("\n"),
      "utf8",
    );

    await generateYamlPageWrappers(
      [
        {
          pageId: "demo",
          routePath: "/workspace/demo",
          skill: "demo",
          bundle: "workspace",
          hubId: "workspace",
          isOwner: false,
          overrides: {},
          yamlConfig: yamlPath,
        },
      ],
      scriptsDir,
    );

    const wrapper = await fs.readFile(
      path.join(tempDir, "apps", "dashboard", "lib", "configs", "workspace-demo.tsx"),
      "utf8",
    );
    expect(wrapper).toContain(
      "// AUTO-GENERATED from project-brain/capabilities/skills/demo/augur/pages/overview.yaml",
    );
  });

  it("labels generated skill configs with project-brain SKILL.md paths", async () => {
    const sourceConfigPath = path.join(
      tempDir,
      "project-brain",
      "capabilities",
      "skills",
      "demo",
      "SKILL.md",
    );
    await generateYamlPageWrappers(
      [
        {
          pageId: "demo",
          routePath: "/workspace/demo",
          skill: "demo",
          bundle: "workspace",
          hubId: "workspace",
          isOwner: false,
          overrides: {},
          sourceConfigPath,
          generatedConfig: {
            title: "Demo",
            icon: "Brain",
            hub: "workspace",
            route: "demo",
            blocks: [],
          },
        } as DiscoveredPage,
      ],
      scriptsDir,
    );

    const wrapper = await fs.readFile(
      path.join(tempDir, "apps", "dashboard", "lib", "configs", "workspace-demo.tsx"),
      "utf8",
    );
    expect(wrapper).toContain(
      "// AUTO-GENERATED from project-brain/capabilities/skills/demo/SKILL.md",
    );
  });

  it("labels generated repo-root configs with their actual SKILL.md paths", async () => {
    const sourceConfigPath = path.join(
      tempDir,
      "skills",
      "demo",
      "SKILL.md",
    );
    await generateYamlPageWrappers(
      [
        {
          pageId: "demo",
          routePath: "/workspace/demo",
          skill: "demo",
          bundle: "workspace",
          hubId: "workspace",
          isOwner: false,
          overrides: {},
          sourceConfigPath,
          generatedConfig: {
            title: "Demo",
            icon: "Brain",
            hub: "workspace",
            route: "demo",
            blocks: [],
          },
        } as DiscoveredPage,
      ],
      scriptsDir,
    );

    const wrapper = await fs.readFile(
      path.join(tempDir, "apps", "dashboard", "lib", "configs", "workspace-demo.tsx"),
      "utf8",
    );
    expect(wrapper).toContain(
      "// AUTO-GENERATED from skills/demo/SKILL.md",
    );
  });

  it("labels generated private-vault configs with their actual SKILL.md path", async () => {
    const privateRoot = `${tempDir}-private-vault`;
    const privateSkillMd = path.join(
      privateRoot,
      "skills",
      "apple",
      "SKILL.md",
    );

    try {
      await generateYamlPageWrappers(
        [
          {
            pageId: "apple",
            routePath: "/life/apple",
            skill: "apple",
            bundle: "life",
            hubId: "life",
            isOwner: false,
            overrides: {},
            sourceConfigPath: privateSkillMd,
            generatedConfig: {
              title: "Apple",
              icon: "Apple",
              hub: "life",
              route: "apple",
              blocks: [],
            },
          } as DiscoveredPage,
        ],
        scriptsDir,
      );

      const wrapper = await fs.readFile(
        path.join(tempDir, "apps", "dashboard", "lib", "configs", "life-apple.tsx"),
        "utf8",
      );
      expect(wrapper).toContain(`// AUTO-GENERATED from ${privateSkillMd}`);
    } finally {
      await fs.rm(privateRoot, { recursive: true, force: true });
    }
  });
});
