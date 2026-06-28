#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { safeHeapMb } from "./lib/heap-clamp.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const dashboardDir = path.resolve(scriptDir, "..");
const projectRoot = path.resolve(dashboardDir, "../..");

// Production mode (ADR-787): build once and serve the production bundle via
// `next start` instead of the Turbopack dev server. The main checkout runs prod
// on :3000; worktrees keep running dev. Dev-only watchers are skipped in prod.
const IS_PROD = process.argv.includes("--prod");

if (isCliEntrypoint()) {
  if (process.platform !== "win32") {
    const shellScript = path.join(scriptDir, "start-dev.sh");
    const child = spawn(shellScript, process.argv.slice(2), {
      cwd: dashboardDir,
      env: process.env,
      stdio: "inherit",
    });
    child.on("error", (error) => {
      console.error(`[start-dev] failed to launch ${shellScript}: ${error.message}`);
      process.exit(1);
    });
    child.on("exit", (code, signal) => {
      process.exit(code ?? (signal ? 1 : 0));
    });
  } else {
    startWindows();
  }
}

function startWindows() {
  const python = resolvePython();
  const env = { ...process.env };
  const preflight = runPreflight(python, env);
  const projectPython = { command: preflight.python_path || python.command, args: [] };

  env.AUGUR_ROOT = preflight.project_root;
  env.AUGUR_STATE = preflight.runtime_dir;
  env.AUGUR_RUNTIME = preflight.runtime_dir;
  env.AUGUR_PYTHON = projectPython.command;
  env.MCP_PORT = String(preflight.mcp_port ?? "");
  env.AUGUR_MCP_CLIENT_ID = String(preflight.mcp_client_id ?? "");
  applyInstanceEnv(env, preflight);
  env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS =
    env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS || "1";
  setPathEnv(env, [path.dirname(projectPython.command), path.dirname(process.execPath)]);
  env.PYTHONPATH = prependPathList(env.PYTHONPATH, [
    path.join(env.AUGUR_ROOT, "src", "mcp"),
    env.AUGUR_ROOT,
  ]);
  env.PYTHONIOENCODING = env.PYTHONIOENCODING || "utf-8";
  env.PYTHONUTF8 = env.PYTHONUTF8 || "1";
  env.NODE_PATH = prependPathList(env.NODE_PATH, [
    path.join(projectRoot, "apps", "dashboard", "node_modules"),
  ]);

  // Warm the Python bytecode cache in the background. The MCP backend imports
  // ~856 .py files; compiling them on a cold cache (first run, post-pull, or
  // after /dev-clean) adds ~14s to the MCP cold start. compileall persists the
  // .pyc and is a near-instant no-op when the cache is already warm. Detached +
  // unref'd + best-effort: it never blocks or breaks dashboard startup.
  try {
    const warmBytecode = spawn(
      projectPython.command,
      [...projectPython.args, "-m", "compileall", "-q", "src"],
      { cwd: env.AUGUR_ROOT, env, stdio: "ignore", detached: true },
    );
    warmBytecode.unref();
    warmBytecode.on("error", () => {});
  } catch {
    // Bytecode warmup is an optimization only; ignore any failure.
  }

  const inferredHubs = preflight.dev_hubs || "";
  if (!env.AUGUR_DEV_HUBS && inferredHubs) {
    env.AUGUR_DEV_HUBS = inferredHubs;
    console.log(`Auto-focused worktree hubs: ${env.AUGUR_DEV_HUBS}`);
  }

  env.NEXT_DISABLE_MEM_OVERRIDE = "1";
  env.MIMALLOC_PURGE_DELAY = "0";
  env.MIMALLOC_ARENA_EAGER_COMMIT = "0";
  env.NODE_OPTIONS = appendNodeOptions(env.NODE_OPTIONS, [
    `--max-old-space-size=${safeHeapMb(4096)}`,
    "--max-semi-space-size=64",
  ]);

  // Tell mount-plugins' clearNextCache that this prebuild precedes a PROD serve,
  // so it preserves the freshly-built .next instead of wiping it (ADR-787).
  if (IS_PROD) {
    env.AUGUR_PROD_SERVE = "1";
  }

  ensureDashboardDependencies(env);
  runWindowsPrebuild(projectPython, env);

  const dashboardPort = resolveDashboardPort(preflight);
  if (preflight.instance_kind && preflight.instance_kind !== "main") {
    console.log(`${preflight.instance_kind} dashboard instance detected - using port ${dashboardPort}`);
  }
  stopExistingDashboardListener(dashboardPort);

  // Prod marker (ADR-787): tells the in-process dashboard_monitor that :3000 is
  // a user-managed production server it must NOT auto-recover (recovery wipes the
  // build and relaunches dev). Written before the supervisor is ensured so the
  // monitor sees it on its first check; removed when this serving process exits.
  const prodMarker = IS_PROD
    ? path.join(env.AUGUR_STATE || "", "dashboard.prod_managed")
    : null;
  if (prodMarker) {
    try {
      fs.mkdirSync(path.dirname(prodMarker), { recursive: true });
      fs.writeFileSync(prodMarker, `${process.pid}\n${new Date().toISOString()}\n`);
    } catch (e) {
      console.error(`[start-dev] could not write prod marker: ${e.message}`);
    }
  }

  const children = [];
  const cleanup = () => {
    if (prodMarker) {
      try {
        fs.rmSync(prodMarker, { force: true });
      } catch {
        /* best-effort */
      }
    }
    for (const child of children) {
      if (!child.killed) {
        child.kill();
      }
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

  // Dev-only watchers (live plugin re-mount + error-stream tail) make no sense
  // for a built production image — the bundle is fixed until the next build.
  if (!IS_PROD) {
    console.log("Starting plugin watcher...");
    children.push(
      spawnChecked(process.execPath, ["scripts/dist/mount-plugins.mjs", "--watch"], {
        cwd: dashboardDir,
        env,
        longRunning: true,
      }),
    );

    if (
      env.AUGUR_ACTIVE_ERROR_WATCH === "1" ||
      (!env.AUGUR_ACTIVE_ERROR_WATCH && process.stdout.isTTY)
    ) {
      console.log("Starting active error watcher...");
      children.push(
        spawnChecked(projectPython.command, [...projectPython.args, "scripts/watch_error_streams.py"], {
          cwd: dashboardDir,
          env,
          longRunning: true,
          stdio: ["ignore", "inherit", "inherit"],
        }),
      );
    }
  }

  // Ensure the consolidated daemon supervisor is up (ADR-787 Part B). It runs
  // the background daemons as in-process threads (replacing the ~18-process
  // fleet). Detached + self-guarded (refuses to double-start via its PID file),
  // so it persists across dashboard restarts and only one instance ever runs.
  console.log("Ensuring daemon supervisor...");
  const supervisor = spawn(
    projectPython.command,
    [
      ...projectPython.args,
      path.join(projectRoot, "project-brain", "capabilities", "skills", "daemon", "scripts", "daemon_supervisor.py"),
    ],
    { cwd: projectRoot, env, detached: true, stdio: "ignore" },
  );
  supervisor.on("error", (e) => console.error(`[start-dev] daemon supervisor failed to start: ${e.message}`));
  supervisor.unref();

  const nextCommand = resolveNextCommand();
  let next;
  if (IS_PROD) {
    // SERVE ONLY. The production build is produced by the `build:safe` step in
    // the `pnpm prod` script BEFORE this runs. build.mjs stops the whole
    // dashboard process tree at startup (it is designed to run standalone), so
    // it cannot run nested inside this serving process — doing so killed
    // start-dev before it could serve. build:safe also holds the build lock, so
    // the in-process dashboard_monitor skips recovery while :3000 is down
    // building (otherwise it would "recover" the absent server to dev,
    // defeating prod — ADR-787).
    env.NODE_ENV = "production";
    if (!fs.existsSync(path.join(dashboardDir, ".next", "BUILD_ID"))) {
      console.error(
        "[start-dev] No production build found (.next/BUILD_ID missing). " +
        "Run `pnpm run build:safe` first, or use `pnpm prod`.",
      );
      process.exit(1);
    }
    console.log(`Starting production server (next start) on port ${dashboardPort}...`);
    next = spawnChecked(
      nextCommand.command,
      [...nextCommand.args, "start", "--port", dashboardPort],
      {
        cwd: dashboardDir,
        env,
        longRunning: true,
        shell: nextCommand.shell,
      },
    );
    next.on("exit", (code, signal) => {
      cleanup();
      process.exit(code ?? (signal ? 1 : 0));
    });
    return;
  }

  console.log("Starting Next.js...");
  next = spawnChecked(
    nextCommand.command,
    [...nextCommand.args, "dev", "--turbopack", "--port", dashboardPort],
    {
      cwd: dashboardDir,
      env,
      longRunning: true,
      shell: nextCommand.shell,
    },
  );
  next.on("exit", (code, signal) => {
    cleanup();
    process.exit(code ?? (signal ? 1 : 0));
  });
}

function runPreflight(python, env) {
  const preflightArgs = [
    ...python.args,
    path.join(projectRoot, "scripts", "worktree_preflight.py"),
    "--root",
    projectRoot,
    "--profile",
    "dashboard",
    "--repair",
  ];
  if (env.AUGUR_INTERACTIVE === "1") {
    preflightArgs.push("--interactive");
  }
  const result = runCapture(
    python.command,
    preflightArgs,
    {
      cwd: projectRoot,
      env,
      label: "dashboard preflight",
    },
  );
  const start = result.stdout.indexOf("{");
  const end = result.stdout.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) {
    throw new Error(`dashboard preflight did not return JSON:\n${result.stdout}`);
  }
  return JSON.parse(result.stdout.slice(start, end + 1));
}

function isCliEntrypoint() {
  return Boolean(process.argv[1]) && import.meta.url === pathToFileURL(process.argv[1]).href;
}

export function resolveDashboardPort(preflight) {
  const instanceKind = preflight.instance_kind || (preflight.worktree ? "worktree" : "main");
  const port = normalizeDashboardPort(preflight.dashboard_port);

  if (instanceKind === "main") {
    return "3000";
  }

  if (instanceKind === "worktree" || instanceKind === "isolated") {
    if (port && port !== "3000") {
      return port;
    }
    throw new Error(
      `${instanceKind} dashboard instance requires an allocated dashboard_port other than 3000`,
    );
  }

  throw new Error(`Unknown dashboard instance_kind: ${instanceKind}`);
}

function normalizeDashboardPort(value) {
  if (value === undefined || value === null || value === "") {
    return "";
  }
  const port = Number(value);
  if (!Number.isInteger(port) || port <= 0) {
    return "";
  }
  return String(port);
}

export function applyInstanceEnv(env, preflight) {
  const instanceKind = preflight.instance_kind || (preflight.worktree ? "worktree" : "main");
  const instanceId = preflight.instance_id || instanceKind;
  const defaults = instanceDefaults(instanceKind);
  const browserMode = preflight.browser_mode || defaults.browserMode;
  const healPolicy = preflight.heal_policy || defaults.healPolicy;
  const visibilityPolicy = preflight.visibility_policy || defaults.visibilityPolicy;

  env.AUGUR_INSTANCE_ID = instanceId;
  env.AUGUR_INSTANCE_KIND = instanceKind;
  env.AUGUR_BROWSER_MODE = browserMode;
  env.AUGUR_HEAL_POLICY = healPolicy;
  env.AUGUR_VISIBILITY_POLICY = visibilityPolicy;
  env.NEXT_PUBLIC_AUGUR_INSTANCE_ID = instanceId;
  env.NEXT_PUBLIC_AUGUR_INSTANCE_KIND = instanceKind;
  env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY = visibilityPolicy;
}

function instanceDefaults(instanceKind) {
  if (instanceKind === "main") {
    return {
      browserMode: "visible_allowed",
      healPolicy: "enabled",
      visibilityPolicy: "visible_allowed",
    };
  }

  if (instanceKind === "worktree") {
    return {
      browserMode: "headless_only",
      healPolicy: "validation_only",
      visibilityPolicy: "no_visible_mutation",
    };
  }

  if (instanceKind === "isolated") {
    return {
      browserMode: "headless_only",
      healPolicy: "disabled",
      visibilityPolicy: "no_visible_mutation",
    };
  }

  throw new Error(`Unknown dashboard instance_kind: ${instanceKind}`);
}

function runWindowsPrebuild(python, env) {
  console.log("Running Windows dashboard prebuild...");
  runChecked(process.execPath, ["scripts/build-scripts.mjs"], {
    cwd: dashboardDir,
    env,
    label: "build dashboard scripts",
  });
  runChecked(process.execPath, ["scripts/dist/setup-mcp.mjs"], {
    cwd: dashboardDir,
    env,
    label: "setup dashboard MCP",
  });
  runChecked(python.command, [...python.args, "scripts/generate_registry.py"], {
    cwd: dashboardDir,
    env,
    label: "generate dashboard registry",
  });
  runChecked(process.execPath, ["scripts/dist/mount-plugins.mjs"], {
    cwd: dashboardDir,
    env,
    label: "mount dashboard plugins",
  });
  runChecked(process.execPath, ["scripts/dist/generate-block-registry.mjs"], {
    cwd: dashboardDir,
    env,
    label: "generate dashboard block registry",
  });
  runChecked(process.execPath, ["scripts/dist/generate-tab-registry.mjs"], {
    cwd: dashboardDir,
    env,
    label: "generate dashboard tabs",
  });
  runChecked(process.execPath, ["scripts/dist/generate-item-actions.mjs"], {
    cwd: dashboardDir,
    env,
    label: "generate dashboard item actions",
  });
}

function ensureDashboardDependencies(env) {
  const nextCmd = path.join(dashboardDir, "node_modules", ".bin", "next.cmd");
  const nextBin = path.join(dashboardDir, "node_modules", ".bin", "next");
  if (fs.existsSync(nextCmd) || fs.existsSync(nextBin)) {
    return;
  }

  console.log("Dashboard dependencies are missing; installing with pnpm...");
  const pnpm = resolvePnpm();
  runChecked(pnpm.command, [...pnpm.args, "install", "--frozen-lockfile"], {
    cwd: dashboardDir,
    env,
    label: "install dashboard dependencies",
    shell: pnpm.shell,
  });
}

function stopExistingDashboardListener(port) {
  const script = `
$owners = @(Get-NetTCPConnection -LocalPort ${Number(port)} -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
foreach ($ownerPid in $owners) {
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue
  if ($null -eq $proc) { continue }
  $command = [string]$proc.CommandLine
  if ($command -match "next dev|next-server|apps[\\\\/]dashboard|pnpm.*next") {
    Write-Host "Stopping stale dashboard listener on port ${port} (PID $ownerPid)..."
    Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
  }
}
for ($i = 0; $i -lt 40; $i++) {
  $remaining = @(Get-NetTCPConnection -LocalPort ${Number(port)} -State Listen -ErrorAction SilentlyContinue)
  if ($remaining.Count -eq 0) { exit 0 }
  Start-Sleep -Milliseconds 250
}
exit 1
`;
  const result = spawnSync(
    "powershell.exe",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
    { cwd: dashboardDir, encoding: "utf8" },
  );
  if (result.stdout) {
    process.stdout.write(result.stdout);
  }
  if (result.status !== 0) {
    console.warn(
      `[start-dev] port ${port} is still in use; Next.js will report the binding error if it cannot recover.`,
    );
  }
}

function resolvePython() {
  const candidates = [
    process.env.AUGUR_PYTHON,
    path.join(projectRoot, ".venv", "Scripts", "python.exe"),
    path.join(projectRoot, ".venv", "bin", "python3"),
    path.join(projectRoot, ".venv", "bin", "python"),
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return { command: candidate, args: [] };
    }
  }

  throw new Error(
    `No project Python found. Run uv sync from ${projectRoot} before starting the dashboard.`,
  );
}

function resolvePnpm() {
  if (process.env.npm_execpath && fs.existsSync(process.env.npm_execpath)) {
    return { command: process.execPath, args: [process.env.npm_execpath], shell: false };
  }
  return { command: "pnpm", args: [], shell: true };
}

function resolveNextCommand() {
  const packageBin = path.join(dashboardDir, "node_modules", "next", "dist", "bin", "next");
  if (fs.existsSync(packageBin)) {
    return { command: process.execPath, args: [packageBin], shell: false };
  }

  const localBin = path.join(dashboardDir, "node_modules", ".bin", "next");
  if (fs.existsSync(localBin)) {
    return { command: localBin, args: [], shell: false };
  }

  const localCmd = path.join(dashboardDir, "node_modules", ".bin", "next.cmd");
  if (process.platform === "win32" && fs.existsSync(localCmd)) {
    return { command: "cmd.exe", args: ["/d", "/s", "/c", localCmd], shell: false };
  }

  return { command: "next", args: [], shell: process.platform === "win32" };
}

function runChecked(command, args, options) {
  const result = spawnSync(command, args, {
    cwd: options.cwd,
    env: options.env,
    stdio: "inherit",
    shell: options.shell ?? false,
  });
  if (result.status !== 0) {
    throw new Error(`${options.label || command} failed with exit code ${result.status}`);
  }
}

function runCapture(command, args, options) {
  const result = spawnSync(command, args, {
    cwd: options.cwd,
    env: options.env,
    encoding: "utf8",
    shell: options.shell ?? false,
  });
  if (result.status !== 0) {
    if (result.stdout) {
      process.stdout.write(result.stdout);
    }
    if (result.stderr) {
      process.stderr.write(result.stderr);
    }
    throw new Error(`${options.label || command} failed with exit code ${result.status}`);
  }
  return result;
}

function spawnChecked(command, args, options) {
  const child = spawn(command, args, {
    cwd: options.cwd,
    env: options.env,
    stdio: options.stdio ?? "inherit",
    shell: options.shell ?? false,
  });
  child.on("error", (error) => {
    console.error(`[start-dev] ${command} failed to start: ${error.message}`);
    if (!options.longRunning) {
      process.exit(1);
    }
  });
  return child;
}

function prependPathList(currentValue, entries) {
  return [...entries.filter(Boolean), currentValue].filter(Boolean).join(path.delimiter);
}

function setPathEnv(env, entries) {
  const key = Object.keys(env).find((name) => name.toLowerCase() === "path") || "PATH";
  const value = prependPathList(env[key], entries);
  env[key] = value;
  env.PATH = value;
}

function appendNodeOptions(currentValue, options) {
  const current = currentValue || "";
  const additions = options.filter((option) => !current.includes(option.split("=")[0]));
  return [current, ...additions].filter(Boolean).join(" ");
}
