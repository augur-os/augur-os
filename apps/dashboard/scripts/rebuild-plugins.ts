// Compiled to scripts/dist/rebuild-plugins.mjs by build-scripts.mjs
/**
 * Rebuild Plugins — Orchestrator (ADR-187 Phase 5)
 *
 * Enforces the correct build order for plugin lifecycle scripts:
 *   1. mount-plugins  — symlink/copy pages into src/app/, assemble hubs, regenerate tab registry
 *   2. generate-block-registry — refresh dashboard block manifests from live skills
 *   3. generate-registry (optional) — update IDE registry.yaml
 *
 * Tab registry generation is handled internally by mount-plugins (Phase 6),
 * so there is no separate generate-tabs step.
 *
 * Usage:
 *   npm run rebuild-plugins [-- --dry-run] [-- --skip-registry]
 *
 * Also callable from /api/admin/rebuild and worktree setup.
 */

import { execSync } from "child_process";
import { existsSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

import { getDashboardRoot } from "./lib/path-utils";
const dashboardRoot = getDashboardRoot(__dirname);
const repoRoot = path.resolve(dashboardRoot, "..", "..");

const isDryRun = process.argv.includes("--dry-run");
const skipRegistry = process.argv.includes("--skip-registry");

function shellQuote(value: string): string {
  if (process.platform === "win32") {
    return `"${value.replace(/"/g, '\\"')}"`;
  }
  return `'${value.replace(/'/g, "'\\''")}'`;
}

function resolvePythonCommand(): string {
  const explicit = process.env.AUGUR_PYTHON?.trim();
  if (explicit) {
    return explicit;
  }

  const candidates =
    process.platform === "win32"
      ? [
          path.join(repoRoot, ".venv", "Scripts", "python.exe"),
          path.join(repoRoot, ".venv", "Scripts", "python3.exe"),
          path.join(repoRoot, ".venv", "bin", "python3"),
          path.join(repoRoot, ".venv", "bin", "python"),
        ]
      : [
          path.join(repoRoot, ".venv", "bin", "python3"),
          path.join(repoRoot, ".venv", "bin", "python"),
          path.join(repoRoot, ".venv", "Scripts", "python.exe"),
        ];

  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }

  return process.platform === "win32" ? "python" : "python3";
}

function run(label: string, command: string): void {
  console.log(`\n${"=".repeat(50)}`);
  console.log(`Step: ${label}`);
  console.log(`${"=".repeat(50)}`);

  if (isDryRun) {
    console.log(`[DRY RUN] Would execute: ${command}`);
    return;
  }

  try {
    execSync(command, {
      cwd: dashboardRoot,
      stdio: "inherit",
      env: {
        ...process.env,
        // Keep all rebuild side effects scoped to the active checkout/worktree.
        AUGUR_ROOT: process.env.AUGUR_ROOT || repoRoot,
        AUGUR_CORE: process.env.AUGUR_CORE || repoRoot,
        AUGUR_PYTHON: process.env.AUGUR_PYTHON || resolvePythonCommand(),
        AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS:
          process.env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS || "1",
        PYTHONUTF8: process.env.PYTHONUTF8 || "1",
        PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
      },
    });
  } catch (err) {
    console.error(`\nFailed at step: ${label}`);
    console.error(`Command: ${command}`);
    process.exit(1);
  }
}

async function main(): Promise<void> {
  console.log("Augur Plugin Rebuild Orchestrator (ADR-187)");
  console.log(`Dashboard root: ${dashboardRoot}`);

  if (isDryRun) {
    console.log("Mode: DRY RUN");
  }

  // Step 1: Mount plugins (symlink pages into src/app/, assemble hubs, regenerate tab registry)
  run("1/3 Mount plugins", "node scripts/dist/mount-plugins.mjs");

  // Step 2: Regenerate live block manifests from managed skill roots.
  run("2/3 Generate block registry", "node scripts/dist/generate-block-registry.mjs");

  // Step 3: Generate local Markdown skill registry (optional, Python)
  if (!skipRegistry) {
    run(
      "3/3 Generate local skill registry",
      `${shellQuote(resolvePythonCommand())} scripts/generate_registry.py`,
    );
  } else {
    console.log(
      "\nSkipping step 3/3: Generate local skill registry (--skip-registry)",
    );
  }

  console.log(`\n${"=".repeat(50)}`);
  console.log("Plugin rebuild complete!");
  console.log(`${"=".repeat(50)}`);
}

main().catch((err) => {
  console.error("Fatal error in rebuild orchestrator:", err);
  process.exit(1);
});
