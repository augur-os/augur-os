/**
 * @jest-environment node
 */

import { readFileSync } from "fs";
import path from "path";

import {
  runCli,
  validateNoLegacyPages,
} from "@/scripts/validate-no-legacy-pages";

describe("validateNoLegacyPages", () => {
  it("rejects skill-owned legacy dashboard page sources", () => {
    const result = validateNoLegacyPages([
      "skills/demo/augur/dashboard/page.tsx",
      "skills/demo/augur/dashboard/tabs/OverviewTab.tsx",
    ]);

    expect(result.ok).toBe(false);
    expect(result.violations).toEqual([
      {
        kind: "legacy-dashboard-source",
        path: "skills/demo/augur/dashboard/page.tsx",
        message:
          "Skill-owned augur/dashboard page sources are legacy. Move dashboard pages to apps/dashboard/features/pages/ or capability metadata.",
      },
      {
        kind: "legacy-dashboard-source",
        path: "skills/demo/augur/dashboard/tabs/OverviewTab.tsx",
        message:
          "Skill-owned augur/dashboard page sources are legacy. Move dashboard pages to apps/dashboard/features/pages/ or capability metadata.",
      },
    ]);
  });

  it("rejects standalone YAML page routes under skill augur/pages", () => {
    const result = validateNoLegacyPages([
      "skills/demo/augur/pages/inbox.yaml",
      "skills/demo/augur/pages/tasks.yml",
    ]);

    expect(result.ok).toBe(false);
    expect(result.violations.map((violation) => violation.kind)).toEqual([
      "standalone-yaml-route",
      "standalone-yaml-route",
    ]);
    expect(result.violations.map((violation) => violation.path)).toEqual([
      "skills/demo/augur/pages/inbox.yaml",
      "skills/demo/augur/pages/tasks.yml",
    ]);
  });

  it("allows app surfaces and capability metadata", () => {
    const result = validateNoLegacyPages([
      "apps/dashboard/features/pages/workspace/inbox/page.tsx",
      "skills/demo/SKILL.md",
      "skills/demo/augur/profile.yaml",
      "skills/demo/augur/capabilities/actions.yaml",
      "docs/agent-topics/DASHBOARD.md",
    ]);

    expect(result).toEqual({
      ok: true,
      violations: [],
    });
  });

  it("normalizes absolute and platform-separated paths", () => {
    const result = validateNoLegacyPages([
      "/repo/skills/demo/augur/pages/inbox.yaml",
      "skills\\demo\\augur\\dashboard\\page.tsx",
    ]);

    expect(result.ok).toBe(false);
    expect(result.violations.map((violation) => violation.path)).toEqual([
      "/repo/skills/demo/augur/pages/inbox.yaml",
      "skills\\demo\\augur\\dashboard\\page.tsx",
    ]);
  });
});

describe("validate-no-legacy-pages CLI", () => {
  it("checks changed files by default package wiring instead of the full legacy tree", () => {
    const packageJsonPath = path.resolve(
      __dirname,
      "../../..",
      "apps/dashboard/package.json",
    );
    const packageJson = JSON.parse(readFileSync(packageJsonPath, "utf8")) as {
      scripts: Record<string, string>;
    };

    expect(packageJson.scripts["validate:no-legacy-pages"]).toBe(
      "node scripts/dist/validate-no-legacy-pages.mjs --base origin/main --changed",
    );
  });

  it("keeps --changed safe while --all catches existing legacy files", () => {
    const stdout: string[] = [];
    const stderr: string[] = [];
    const runGitCommand = jest.fn((args: string[]) => {
      const command = args.join(" ");
      const outputs: Record<string, string> = {
        "rev-parse --show-toplevel": "/repo\n",
        "diff --name-only --diff-filter=ACMR": "",
        "diff --cached --name-only --diff-filter=ACMR": "",
        "ls-files --others --exclude-standard": "",
        "ls-files --cached --others --exclude-standard":
          "skills/demo/augur/pages/legacy.yaml\n",
      };

      return {
        ok: command in outputs,
        stdout: outputs[command] ?? "",
        stderr: command in outputs ? "" : `Unexpected git command: ${command}`,
      };
    });

    expect(
      runCli(["--changed"], {
        cwd: "/repo/subdir",
        stdout: (message) => stdout.push(message),
        stderr: (message) => stderr.push(message),
        runGitCommand,
      }),
    ).toBe(0);
    expect(stdout.join("\n")).toContain("No paths to validate.");
    expect(stderr).toEqual([]);

    expect(
      runCli(["--all"], {
        cwd: "/repo/subdir",
        stdout: (message) => stdout.push(message),
        stderr: (message) => stderr.push(message),
        fileExists: () => true,
        runGitCommand,
      }),
    ).toBe(1);
    expect(stderr.join("\n")).toContain("skills/demo/augur/pages/legacy.yaml");
  });

  it("ignores deleted cached paths during full scans", () => {
    const stdout: string[] = [];
    const stderr: string[] = [];
    const runGitCommand = jest.fn((args: string[]) => {
      const command = args.join(" ");
      const outputs: Record<string, string> = {
        "rev-parse --show-toplevel": "/repo\n",
        "ls-files --cached --others --exclude-standard":
          "skills/demo/augur/pages/deleted.yaml\n",
      };

      return {
        ok: command in outputs,
        stdout: outputs[command] ?? "",
        stderr: command in outputs ? "" : `Unexpected git command: ${command}`,
      };
    });

    expect(
      runCli(["--all"], {
        cwd: "/repo/subdir",
        stdout: (message) => stdout.push(message),
        stderr: (message) => stderr.push(message),
        fileExists: () => false,
        runGitCommand,
      }),
    ).toBe(0);
    expect(stdout.join("\n")).toContain("No paths to validate.");
    expect(stderr).toEqual([]);
  });

  it("checks committed branch changes against a base ref", () => {
    const stdout: string[] = [];
    const stderr: string[] = [];
    const runGitCommand = jest.fn((args: string[]) => {
      const command = args.join(" ");
      const outputs: Record<string, string> = {
        "rev-parse --show-toplevel": "/repo\n",
        "merge-base origin/main HEAD": "abc123\n",
        "diff --name-only --diff-filter=ACMR abc123 HEAD":
          "skills/demo/augur/dashboard/page.tsx\n",
        "diff --name-only --diff-filter=ACMR": "",
        "diff --cached --name-only --diff-filter=ACMR": "",
        "ls-files --others --exclude-standard": "",
      };

      return {
        ok: command in outputs,
        stdout: outputs[command] ?? "",
        stderr: command in outputs ? "" : `Unexpected git command: ${command}`,
      };
    });

    expect(
      runCli(["--base", "origin/main", "--changed"], {
        cwd: "/repo/subdir",
        stdout: (message) => stdout.push(message),
        stderr: (message) => stderr.push(message),
        runGitCommand,
      }),
    ).toBe(1);
    expect(stderr.join("\n")).toContain("skills/demo/augur/dashboard/page.tsx");
    expect(stdout).toEqual([]);
  });
});
