import fs from "fs/promises";
import os from "os";
import path from "path";

import {
  humanize,
  readSkillCommands,
  readSkillPrompts,
} from "@/lib/server/skillContent";

const testRoot = path.join(os.tmpdir(), "augur-skill-content-tests");

jest.mock("@/lib/paths", () => {
  const mockOs = require("os");
  const mockPath = require("path");
  return {
    AUGUR_ROOT: mockPath.join(mockOs.tmpdir(), "augur-skill-content-tests"),
  };
});

async function writeSkillFile(
  skillId: string,
  contentType: "prompts" | "commands",
  fileName: string,
  content: string,
  root: string = path.join(testRoot, "project-brain", "capabilities", "skills"),
) {
  const skillDir = path.join(root, skillId);
  const dir = path.join(skillDir, contentType);
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(
    path.join(skillDir, "SKILL.md"),
    `---\nname: ${skillId}\nx-augur-hub: workspace\n---\n`,
    "utf8",
  );
  await fs.writeFile(path.join(dir, fileName), content, "utf8");
}

describe("skillContent", () => {
  beforeEach(async () => {
    await fs.rm(testRoot, { recursive: true, force: true });
  });

  afterAll(async () => {
    await fs.rm(testRoot, { recursive: true, force: true });
  });

  it("returns an empty prompt list when the prompts directory is missing", async () => {
    await expect(readSkillPrompts("missing-prompts")).resolves.toEqual([]);
  });

  it("parses prompt files with frontmatter", async () => {
    await writeSkillFile(
      "writer",
      "prompts",
      "draft.md",
      `---
id: custom-draft
label: Draft Reply
description: Draft a concise reply
icon: Mail
---
Write a concise reply using the thread context.
`,
    );

    await expect(readSkillPrompts("writer")).resolves.toEqual([
      {
        id: "custom-draft",
        label: "Draft Reply",
        description: "Draft a concise reply",
        icon: "Mail",
        prompt: "Write a concise reply using the thread context.\n",
      },
    ]);
  });

  it("ignores prompts from repo-root skills while project-brain/capabilities/skills has no skill", async () => {
    await writeSkillFile(
      "writer",
      "prompts",
      "root-draft.md",
      `---
label: Root Draft
---
Draft from the root skill during transition.
`,
      path.join(testRoot, "skills"),
    );

    await expect(readSkillPrompts("writer")).resolves.toEqual([]);
  });

  it("keeps project-brain prompt content ahead of root skill content", async () => {
    await writeSkillFile(
      "writer",
      "prompts",
      "shared-draft.md",
      `---
label: Shared Draft
---
Draft from the shared skill.
`,
    );
    await writeSkillFile(
      "writer",
      "prompts",
      "root-draft.md",
      `---
label: Root Draft
---
Draft from the root skill.
`,
      path.join(testRoot, "skills"),
    );

    await expect(readSkillPrompts("writer")).resolves.toEqual([
      {
        id: "shared-draft",
        label: "Shared Draft",
        description: undefined,
        icon: undefined,
        prompt: "Draft from the shared skill.\n",
      },
    ]);
  });

  it("does not read root prompts once project-brain has dashboard skills", async () => {
    await writeSkillFile(
      "shared-existing",
      "prompts",
      "shared.md",
      `---
label: Shared
---
Shared prompt.
`,
    );
    await writeSkillFile(
      "writer",
      "prompts",
      "root-draft.md",
      `---
label: Root Draft
---
Draft from the root skill.
`,
      path.join(testRoot, "skills"),
    );

    await expect(readSkillPrompts("writer")).resolves.toEqual([]);
  });

  it("falls back to the filename stem when id is missing", async () => {
    await writeSkillFile(
      "writer",
      "prompts",
      "long-form.md",
      `---
label: Long Form
---
Expand the provided outline.
`,
    );

    const prompts = await readSkillPrompts("writer");

    expect(prompts[0]?.id).toBe("long-form");
  });

  it("humanizes ids when label is missing", () => {
    expect(humanize("weekly_memory_report")).toBe("Weekly Memory Report");
    expect(humanize("daily-brief")).toBe("Daily Brief");
  });

  it("builds command invocation from the command id", async () => {
    await writeSkillFile(
      "scheduler",
      "commands",
      "plan-day.md",
      `---
description: Plan the day
---
Use calendar and task context to plan the day.
`,
    );

    await expect(readSkillCommands("scheduler")).resolves.toEqual([
      {
        id: "plan-day",
        label: "Plan Day",
        description: "Plan the day",
        icon: undefined,
        command: "/plan-day",
      },
    ]);
  });

  it("ignores commands from repo-root skills while project-brain/capabilities/skills has no skill", async () => {
    await writeSkillFile(
      "scheduler",
      "commands",
      "root-plan.md",
      `---
description: Plan from root
---
Use root command content during transition.
`,
      path.join(testRoot, "skills"),
    );

    await expect(readSkillCommands("scheduler")).resolves.toEqual([]);
  });
});
