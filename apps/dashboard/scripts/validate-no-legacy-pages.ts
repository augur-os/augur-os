// Compiled to scripts/dist/validate-no-legacy-pages.mjs by build-scripts.mjs
/**
 * Legacy dashboard page format guardrail.
 *
 * Checks path lists for retired skill-owned dashboard page sources and
 * standalone YAML route pages. The validator is path-list based on purpose so
 * callers can run it on explicit files, changed files, or full repo scans.
 */

import { spawnSync } from "child_process";
import { existsSync } from "fs";
import { join } from "path";

export type LegacyPageViolationKind =
  | "legacy-dashboard-source"
  | "standalone-yaml-route";

export interface LegacyPageViolation {
  kind: LegacyPageViolationKind;
  path: string;
  message: string;
}

export interface NoLegacyPagesValidationResult {
  ok: boolean;
  violations: LegacyPageViolation[];
}

const VIOLATION_MESSAGES: Record<LegacyPageViolationKind, string> = {
  "legacy-dashboard-source":
    "Skill-owned augur/dashboard page sources are legacy. Move dashboard pages to apps/dashboard/features/pages/ or capability metadata.",
  "standalone-yaml-route":
    "Standalone YAML page routes under augur/pages are legacy. Move routes to apps/dashboard/features/pages/ or skill capability metadata.",
};

const LEGACY_DASHBOARD_SOURCE_PATTERN =
  /(?:^|\/)skills\/[^/]+\/augur\/dashboard(?:\/|$)/;
const STANDALONE_YAML_ROUTE_PATTERN =
  /(?:^|\/)skills\/[^/]+\/augur\/pages\/[^/]+\.ya?ml$/i;

function normalizeForMatching(filePath: string): string {
  return filePath.trim().replace(/\\/g, "/").replace(/\/+/g, "/");
}

function classifyLegacyPagePath(
  filePath: string,
): LegacyPageViolationKind | null {
  const normalized = normalizeForMatching(filePath);

  if (LEGACY_DASHBOARD_SOURCE_PATTERN.test(normalized)) {
    return "legacy-dashboard-source";
  }

  if (STANDALONE_YAML_ROUTE_PATTERN.test(normalized)) {
    return "standalone-yaml-route";
  }

  return null;
}

export function validateNoLegacyPages(
  paths: Iterable<string>,
): NoLegacyPagesValidationResult {
  const violations: LegacyPageViolation[] = [];
  const seenViolations = new Set<string>();

  for (const inputPath of paths) {
    const pathText = String(inputPath);
    if (!pathText.trim()) continue;

    const kind = classifyLegacyPagePath(pathText);
    if (!kind) continue;

    const dedupeKey = `${kind}\0${pathText}`;
    if (seenViolations.has(dedupeKey)) continue;
    seenViolations.add(dedupeKey);

    violations.push({
      kind,
      path: pathText,
      message: VIOLATION_MESSAGES[kind],
    });
  }

  return {
    ok: violations.length === 0,
    violations,
  };
}

interface GitCommandResult {
  ok: boolean;
  stdout: string;
  stderr: string;
}

interface CliOptions {
  all: boolean;
  base: string | null;
  changed: boolean;
  help: boolean;
  paths: string[];
}

interface CliIo {
  cwd?: string;
  fileExists?: (path: string) => boolean;
  stdout?: (message: string) => void;
  stderr?: (message: string) => void;
  runGitCommand?: (args: string[], cwd: string) => GitCommandResult;
}

const USAGE = [
  "Usage:",
  "  node scripts/dist/validate-no-legacy-pages.mjs --changed",
  "  node scripts/dist/validate-no-legacy-pages.mjs --base origin/main --changed",
  "  node scripts/dist/validate-no-legacy-pages.mjs --all",
  "  node scripts/dist/validate-no-legacy-pages.mjs <path> [path...]",
  "",
  "Options:",
  "  --base REF  Validate files changed on this branch since REF.",
  "  --changed   Validate staged, unstaged, and untracked repo paths.",
  "  --all       Validate tracked and untracked repo paths.",
  "  --help      Show this help text.",
].join("\n");

function splitLines(output: string): string[] {
  return output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function uniquePaths(paths: Iterable<string>): string[] {
  return [...new Set(paths)];
}

function parseCliOptions(argv: string[]): CliOptions | string {
  const options: CliOptions = {
    all: false,
    base: null,
    changed: false,
    help: false,
    paths: [],
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") {
      options.help = true;
    } else if (arg === "--changed") {
      options.changed = true;
    } else if (arg === "--base") {
      const base = argv[index + 1];
      if (!base || base.startsWith("-")) {
        return "--base requires a ref argument.";
      }
      options.base = base;
      index += 1;
    } else if (arg === "--all") {
      options.all = true;
    } else if (arg.startsWith("-")) {
      return `Unknown option: ${arg}`;
    } else {
      options.paths.push(arg);
    }
  }

  if (options.all && (options.changed || options.base)) {
    return "Choose --all, or branch/change scoped validation, not both.";
  }

  return options;
}

function runGit(args: string[], cwd: string): GitCommandResult {
  const result = spawnSync("git", args, {
    cwd,
    encoding: "utf8",
  });

  return {
    ok: result.status === 0,
    stdout: result.stdout || "",
    stderr: result.stderr || result.error?.message || "",
  };
}

function discoverGitRoot(
  cwd: string,
  runGitCommand: (args: string[], cwd: string) => GitCommandResult = runGit,
): GitCommandResult {
  return runGitCommand(["rev-parse", "--show-toplevel"], cwd);
}

function collectChangedPaths(
  cwd: string,
  runGitCommand: (args: string[], cwd: string) => GitCommandResult = runGit,
): string[] | string {
  const rootResult = discoverGitRoot(cwd, runGitCommand);
  if (!rootResult.ok) {
    return rootResult.stderr || "Unable to discover git repository root.";
  }
  const repoRoot = splitLines(rootResult.stdout)[0];
  if (!repoRoot) return "Unable to discover git repository root.";

  const commands = [
    ["diff", "--name-only", "--diff-filter=ACMR"],
    ["diff", "--cached", "--name-only", "--diff-filter=ACMR"],
    ["ls-files", "--others", "--exclude-standard"],
  ];

  const paths: string[] = [];
  for (const args of commands) {
    const result = runGitCommand(args, repoRoot);
    if (!result.ok) {
      return result.stderr || `git ${args.join(" ")} failed.`;
    }
    paths.push(...splitLines(result.stdout));
  }

  return uniquePaths(paths);
}

function collectBasePaths(
  cwd: string,
  baseRef: string,
  runGitCommand: (args: string[], cwd: string) => GitCommandResult = runGit,
): string[] | string {
  const rootResult = discoverGitRoot(cwd, runGitCommand);
  if (!rootResult.ok) {
    return rootResult.stderr || "Unable to discover git repository root.";
  }
  const repoRoot = splitLines(rootResult.stdout)[0];
  if (!repoRoot) return "Unable to discover git repository root.";

  const mergeBase = runGitCommand(["merge-base", baseRef, "HEAD"], repoRoot);
  if (!mergeBase.ok) {
    return mergeBase.stderr || `git merge-base ${baseRef} HEAD failed.`;
  }
  const mergeBaseSha = splitLines(mergeBase.stdout)[0];
  if (!mergeBaseSha) return `Unable to resolve merge base for ${baseRef}.`;

  const result = runGitCommand(
    ["diff", "--name-only", "--diff-filter=ACMR", mergeBaseSha, "HEAD"],
    repoRoot,
  );
  if (!result.ok) {
    return result.stderr || `git diff ${mergeBaseSha} HEAD failed.`;
  }

  return uniquePaths(splitLines(result.stdout));
}

function collectAllPaths(
  cwd: string,
  runGitCommand: (args: string[], cwd: string) => GitCommandResult = runGit,
  fileExists: (path: string) => boolean = existsSync,
): string[] | string {
  const rootResult = discoverGitRoot(cwd, runGitCommand);
  if (!rootResult.ok) {
    return rootResult.stderr || "Unable to discover git repository root.";
  }
  const repoRoot = splitLines(rootResult.stdout)[0];
  if (!repoRoot) return "Unable to discover git repository root.";

  const result = runGitCommand(
    ["ls-files", "--cached", "--others", "--exclude-standard"],
    repoRoot,
  );
  if (!result.ok) {
    return result.stderr || "git ls-files failed.";
  }

  return uniquePaths(
    splitLines(result.stdout).filter((relativePath) =>
      fileExists(join(repoRoot, relativePath)),
    ),
  );
}

export function runCli(argv: string[], io: CliIo = {}): number {
  const stdout = io.stdout ?? console.log;
  const stderr = io.stderr ?? console.error;
  const cwd = io.cwd ?? process.cwd();
  const fileExists = io.fileExists ?? existsSync;
  const runGitCommand = io.runGitCommand ?? runGit;
  const parsed = parseCliOptions(argv);

  if (typeof parsed === "string") {
    stderr(`${parsed}\n\n${USAGE}`);
    return 2;
  }

  if (parsed.help) {
    stdout(USAGE);
    return 0;
  }

  if (!parsed.all && !parsed.base && !parsed.changed && parsed.paths.length === 0) {
    stderr(`No paths provided.\n\n${USAGE}`);
    return 2;
  }

  let paths = parsed.paths;
  if (parsed.base) {
    const basePaths = collectBasePaths(cwd, parsed.base, runGitCommand);
    if (typeof basePaths === "string") {
      stderr(basePaths);
      return 2;
    }
    paths = uniquePaths([...paths, ...basePaths]);
  }
  if (parsed.changed) {
    const changedPaths = collectChangedPaths(cwd, runGitCommand);
    if (typeof changedPaths === "string") {
      stderr(changedPaths);
      return 2;
    }
    paths = uniquePaths([...paths, ...changedPaths]);
  } else if (parsed.all) {
    const allPaths = collectAllPaths(cwd, runGitCommand, fileExists);
    if (typeof allPaths === "string") {
      stderr(allPaths);
      return 2;
    }
    paths = uniquePaths([...paths, ...allPaths]);
  }

  const result = validateNoLegacyPages(paths);
  if (!result.ok) {
    stderr("Legacy dashboard page formats found:");
    for (const violation of result.violations) {
      stderr(`- ${violation.path}: ${violation.message}`);
    }
    return 1;
  }

  stdout(
    paths.length === 0
      ? "No paths to validate."
      : `Checked ${paths.length} path(s); no legacy page formats found.`,
  );
  return 0;
}

const invokedScript = (process.argv[1] ?? "").replace(/\\/g, "/");
if (/validate-no-legacy-pages\.(?:ts|mjs|js)$/.test(invokedScript)) {
  process.exitCode = runCli(process.argv.slice(2));
}
