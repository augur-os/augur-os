#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const dashboardDir = path.resolve(scriptDir, "..");
const projectRoot = path.resolve(dashboardDir, "../..");
const timeoutMs = Number.parseInt(process.env.BUILD_LOCK_TIMEOUT_MS || "300000", 10);
const command = process.argv.slice(2);

if (command.length === 0) {
  console.error("Usage: build-lock.mjs <command> [args...]");
  process.exit(1);
}

const python = resolveProjectPython();
const runtimeDir = resolveRuntimeDir(python);
const instance = resolveDashboardInstance(python);
const lockDir = instance.build_lock_dir;
fs.mkdirSync(lockDir, { recursive: true });

const lockFile = path.join(lockDir, "dashboard_build.lock");
const metaFile = path.join(lockDir, "dashboard_build.lock.meta");

const lifecycleBeforeGate = readLifecycleState(python, instance);
runLifecycleGate(python, command, lifecycleActionFor(lifecycleBeforeGate), instance);
await acquireLock(lockFile, metaFile, timeoutMs, command);

let cleaned = false;
let buildSucceeded = false;
const cleanup = () => {
  if (cleaned) {
    return;
  }
  cleaned = true;
  restoreLifecycleState(python, lifecycleBeforeGate, instance, buildSucceeded);
  try {
    if (fs.existsSync(metaFile)) {
      const meta = JSON.parse(fs.readFileSync(metaFile, "utf8"));
      if (meta.pid === process.pid) {
        fs.rmSync(metaFile, { force: true });
        fs.rmSync(lockFile, { force: true });
      }
    }
  } catch {
    // Lock cleanup is best-effort; stale PID detection handles leftovers.
  }
};

process.on("exit", cleanup);
process.on("SIGINT", () => {
  cleanup();
  process.exit(130);
});
process.on("SIGTERM", () => {
  cleanup();
  process.exit(143);
});

const childEnv = {
  ...process.env,
  AUGUR_BUILD_LOCK_HELD: "1",
  AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS:
    process.env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS || "1",
};

const result = spawnSync(command[0], command.slice(1), {
  cwd: dashboardDir,
  env: childEnv,
  stdio: "inherit",
  shell: process.platform === "win32",
});
const exitCode = result.status ?? (result.signal ? 1 : 0);
buildSucceeded = exitCode === 0;
cleanup();
process.exit(exitCode);

async function acquireLock(lockPath, metaPath, timeout, cmd) {
  const deadline = Date.now() + timeout;
  while (true) {
    try {
      const fd = fs.openSync(lockPath, "wx");
      fs.closeSync(fd);
      fs.writeFileSync(
        metaPath,
        JSON.stringify(
          {
            pid: process.pid,
            host: os.hostname(),
            started: new Date().toISOString(),
            command: cmd.join(" "),
          },
          null,
          2,
        ),
      );
      console.log(`Build lock acquired (PID: ${process.pid})`);
      return;
    } catch (error) {
      if (error.code !== "EEXIST") {
        throw error;
      }
      if (clearStaleLock(lockPath, metaPath)) {
        continue;
      }
      if (Date.now() >= deadline) {
        console.error(`ERROR: Could not acquire build lock after ${timeout}ms.`);
        process.exit(1);
      }
      await sleep(500);
    }
  }
}

function clearStaleLock(lockPath, metaPath) {
  try {
    if (!fs.existsSync(metaPath)) {
      fs.rmSync(metaPath, { force: true });
      fs.rmSync(lockPath, { force: true });
      return true;
    }
    let meta;
    try {
      meta = JSON.parse(fs.readFileSync(metaPath, "utf8"));
    } catch {
      console.warn(`Removing stale build lock with unreadable metadata: ${metaPath}`);
      fs.rmSync(metaPath, { force: true });
      fs.rmSync(lockPath, { force: true });
      return true;
    }
    if (Number.isInteger(meta.pid) && isPidAlive(meta.pid)) {
      return false;
    }
    fs.rmSync(metaPath, { force: true });
    fs.rmSync(lockPath, { force: true });
    return true;
  } catch {
    return false;
  }
}

function isPidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function lifecycleActionFor(previousState) {
  return previousState?.state === "healthy" ? "rebuild" : "start";
}

function lifecycleScriptPath() {
  return path.join(projectRoot, "project-brain", "capabilities", "skills", "daemon", "scripts", "dashboard_lifecycle.py");
}

function runLifecycleGate(pythonConfig, cmd, action, instance) {
  const lifecycle = lifecycleScriptPath();
  if (!fs.existsSync(lifecycle)) {
    return;
  }
  const result = spawnSync(
    pythonConfig.command,
    [
      ...pythonConfig.args,
      lifecycle,
      "request-action",
      "--actor",
      "build_lock",
      "--action",
      action,
      "--reason",
      `build-lock.mjs: ${cmd.join(" ")}`,
      "--instance", instance.instance_id,
    ],
    {
      cwd: projectRoot,
      env: process.env,
      encoding: "utf8",
    },
  );
  if (result.status !== 0) {
    if (result.stdout) {
      process.stderr.write(result.stdout);
    }
    if (result.stderr) {
      process.stderr.write(result.stderr);
    }
    process.exit(result.status ?? 1);
  }
}

function readLifecycleState(pythonConfig, instance) {
  const lifecycle = lifecycleScriptPath();
  if (!fs.existsSync(lifecycle)) {
    return null;
  }
  const result = spawnSync(
    pythonConfig.command,
    [...pythonConfig.args, lifecycle, "state", "--instance", instance.instance_id],
    {
      cwd: projectRoot,
      env: process.env,
      encoding: "utf8",
    },
  );
  if (result.status !== 0 || !result.stdout) {
    return null;
  }
  const start = result.stdout.indexOf("{");
  const end = result.stdout.lastIndexOf("}");
  if (start === -1 || end <= start) {
    return null;
  }
  try {
    return JSON.parse(result.stdout.slice(start, end + 1));
  } catch {
    return null;
  }
}

function restoreLifecycleState(pythonConfig, previousState, instance, succeeded) {
  if (!previousState) {
    return;
  }
  const code = String.raw`
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
scripts = root / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts"
for item in (str(root), str(scripts)):
    if item not in sys.path:
        sys.path.insert(0, item)

import dashboard_lifecycle

previous = json.loads(sys.argv[2])
target_instance = sys.argv[3]
succeeded = sys.argv[4] == "1"
dashboard_lifecycle.release_build_lock_state(
    previous,
    succeeded=succeeded,
    instance_id=target_instance,
)
`;
  spawnSync(
    pythonConfig.command,
    [
      ...pythonConfig.args,
      "-c",
      code,
      projectRoot,
      JSON.stringify(previousState),
      instance.instance_id,
      succeeded ? "1" : "0",
    ],
    {
      cwd: projectRoot,
      env: process.env,
      encoding: "utf8",
    },
  );
}

function resolveDashboardInstance(pythonConfig) {
  const resolver = path.join(projectRoot, "scripts", "dashboard_instance.py");
  const fallback = {
    instance_id: "main",
    build_lock_dir: path.join(runtimeDir, "locks", "dashboard", "main"),
  };
  if (!fs.existsSync(resolver)) {
    return fallbackOrExit("scripts/dashboard_instance.py is missing");
  }
  const result = spawnSync(
    pythonConfig.command,
    [
      ...pythonConfig.args,
      resolver,
      "--root",
      projectRoot,
      "--runtime-dir",
      runtimeDir,
    ],
    {
      cwd: projectRoot,
      env: process.env,
      encoding: "utf8",
    },
  );
  if (result.status !== 0 || !result.stdout.trim()) {
    return fallbackOrExit("scripts/dashboard_instance.py failed or emitted no JSON", result);
  }
  try {
    const instance = JSON.parse(result.stdout);
    if (isValidDashboardInstance(instance)) {
      return instance;
    }
    return fallbackOrExit("scripts/dashboard_instance.py emitted invalid instance metadata", result);
  } catch {
    return fallbackOrExit("scripts/dashboard_instance.py emitted invalid JSON", result);
  }

  function fallbackOrExit(reason, failedResult = null) {
    if (isClearlyMainCheckout()) {
      console.warn(`WARNING: ${reason}; using conservative main dashboard build lock fallback.`);
      return fallback;
    }
    console.error(`ERROR: Unable to resolve dashboard instance: ${reason}.`);
    console.error("Refusing to use main dashboard build lock fallback outside the main checkout.");
    if (failedResult?.stdout?.trim()) {
      console.error(`resolver stdout: ${failedResult.stdout.trim()}`);
    }
    if (failedResult?.stderr?.trim()) {
      console.error(`resolver stderr: ${failedResult.stderr.trim()}`);
    }
    process.exit(failedResult?.status || 1);
  }
}

function isValidDashboardInstance(instance) {
  return (
    instance &&
    typeof instance === "object" &&
    typeof instance.instance_id === "string" &&
    instance.instance_id.trim().length > 0 &&
    typeof instance.build_lock_dir === "string" &&
    instance.build_lock_dir.trim().length > 0
  );
}

function isClearlyMainCheckout() {
  if (worktreeMarkerSaysWorktree(projectRoot)) {
    return false;
  }

  const dotGit = path.join(projectRoot, ".git");
  try {
    if (fs.statSync(dotGit).isDirectory()) {
      return true;
    }
  } catch {
    // Fall through to git's common-dir check.
  }

  const result = spawnSync("git", ["-C", projectRoot, "rev-parse", "--git-common-dir"], {
    cwd: projectRoot,
    env: process.env,
    encoding: "utf8",
  });
  if (result.status !== 0 || !result.stdout.trim()) {
    return false;
  }

  let commonDir = result.stdout.trim();
  if (!path.isAbsolute(commonDir)) {
    commonDir = path.resolve(projectRoot, commonDir);
  }
  return samePath(commonDir, path.join(projectRoot, ".git"));
}

function worktreeMarkerSaysWorktree(root) {
  const marker = path.join(root, ".augur-worktree.yaml");
  if (!fs.existsSync(marker)) {
    return false;
  }
  try {
    return /^\s*worktree\s*:\s*true\s*$/im.test(fs.readFileSync(marker, "utf8"));
  } catch {
    return false;
  }
}

function samePath(left, right) {
  const resolvedLeft = path.resolve(left);
  const resolvedRight = path.resolve(right);
  if (process.platform === "win32") {
    return resolvedLeft.toLowerCase() === resolvedRight.toLowerCase();
  }
  return resolvedLeft === resolvedRight;
}

function resolveRuntimeDir(pythonConfig) {
  const code = [
    "from src.config.paths import get_runtime_dir",
    "print(get_runtime_dir())",
  ].join("; ");
  const result = spawnSync(pythonConfig.command, [...pythonConfig.args, "-c", code], {
    cwd: projectRoot,
    env: process.env,
    encoding: "utf8",
  });
  if (result.status === 0 && result.stdout.trim()) {
    return result.stdout.trim();
  }
  if (process.env.AUGUR_RUNTIME) {
    return process.env.AUGUR_RUNTIME;
  }
  if (process.env.LOCALAPPDATA) {
    return path.join(process.env.LOCALAPPDATA, "Augur", "state");
  }
  return path.join(os.homedir(), ".local", "state", "augur");
}

function resolveProjectPython() {
  const candidates = [
    path.join(projectRoot, ".venv", "Scripts", "python.exe"),
    path.join(projectRoot, ".venv", "bin", "python3"),
    path.join(projectRoot, ".venv", "bin", "python"),
    process.env.AUGUR_PYTHON,
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return { command: candidate, args: [] };
    }
  }

  return { command: process.platform === "win32" ? "python" : "python3", args: [] };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
