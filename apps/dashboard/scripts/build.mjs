#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const dashboardDir = path.resolve(scriptDir, "..");
const projectRoot = path.resolve(dashboardDir, "../..");

if (process.platform !== "win32") {
  const result = spawnSync(path.join(scriptDir, "build.sh"), process.argv.slice(2), {
    cwd: dashboardDir,
    env: process.env,
    stdio: "inherit",
  });
  process.exit(result.status ?? (result.signal ? 1 : 0));
}

const env = {
  ...process.env,
  AUGUR_ROOT: projectRoot,
  AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS:
    process.env.AUGUR_DASHBOARD_INCLUDE_LOCAL_SKILLS || "1",
  NODE_PATH: prependPathList(process.env.NODE_PATH, [
    path.join(projectRoot, "apps", "dashboard", "node_modules"),
  ]),
};
env.NODE_OPTIONS = appendNodeOptions(env.NODE_OPTIONS, ["--max-old-space-size=8192"]);

const pnpm = resolvePnpm();
stopExistingDashboardProcesses();
runChecked(pnpm, ["run", "ensure-generated"]);
removeBuildArtifacts();

let result = runBuild(pnpm, []);
if (
  result.status !== 0 &&
  (isTurbopackManifestRace(result.output) || isTurbopackPrerenderInvariant(result.output))
) {
  const retryMessage = isTurbopackManifestRace(result.output)
    ? "Detected Turbopack manifest race. Retrying production build with webpack..."
    : "Detected Turbopack prerender invariant. Retrying production build with webpack...";
  console.log(retryMessage);
  removeBuildArtifacts();
  result = runBuild(pnpm, ["--webpack"]);
}

process.exit(result.status ?? 1);

function runBuild(pnpmConfig, buildArgs) {
  const args = [...pnpmConfig.args, "exec", "next", "build", ...buildArgs];
  const child = spawnSync(pnpmConfig.command, args, {
    cwd: dashboardDir,
    env,
    encoding: "utf8",
    shell: pnpmConfig.shell,
  });
  const output = `${child.stdout || ""}${child.stderr || ""}`;
  if (child.stdout) {
    process.stdout.write(child.stdout);
  }
  if (child.stderr) {
    process.stderr.write(child.stderr);
  }
  return { status: child.status ?? (child.signal ? 1 : 0), output };
}

function runChecked(pnpmConfig, args) {
  const child = spawnSync(pnpmConfig.command, [...pnpmConfig.args, ...args], {
    cwd: dashboardDir,
    env,
    stdio: "inherit",
    shell: pnpmConfig.shell,
  });
  if (child.status !== 0) {
    process.exit(child.status ?? 1);
  }
}

function removeBuildArtifacts() {
  for (const target of [
    path.join(dashboardDir, ".next"),
    path.join(projectRoot, ".next"),
  ]) {
    fs.rmSync(target, { recursive: true, force: true, maxRetries: 20, retryDelay: 100 });
  }

  const tsbuildinfo = path.join(dashboardDir, "tsconfig.tsbuildinfo");
  try {
    const stat = fs.lstatSync(tsbuildinfo);
    if (stat.isSymbolicLink()) {
      fs.rmSync(tsbuildinfo, { force: true });
    }
  } catch {
    // Missing tsbuildinfo is expected on fresh checkouts.
  }
}

function stopExistingDashboardProcesses() {
  const script = `
$pids = New-Object System.Collections.Generic.HashSet[int]
$portOwners = @(Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
foreach ($ownerPid in $portOwners) {
  [void]$pids.Add([int]$ownerPid)
}
$dashboardProcesses = @(Get-CimInstance Win32_Process | Where-Object {
  $cmd = [string]$_.CommandLine
  $cmd -and $cmd -match "next dev|next-server|scripts[\\\\/]start-dev\\.mjs|mount-plugins\\.mjs --watch"
})
foreach ($proc in $dashboardProcesses) {
  [void]$pids.Add([int]$proc.ProcessId)
}
foreach ($targetPid in $pids) {
  if ($targetPid -eq $PID) { continue }
  Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
}
for ($i = 0; $i -lt 40; $i++) {
  $remaining = @(Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue)
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
  if (result.status !== 0) {
    console.warn("[build] dashboard port 3000 may still be occupied before build cleanup.");
  }
}

function resolvePnpm() {
  if (
    process.env.npm_execpath &&
    fs.existsSync(process.env.npm_execpath) &&
    path.basename(process.env.npm_execpath).toLowerCase().includes("pnpm")
  ) {
    return { command: process.execPath, args: [process.env.npm_execpath], shell: false };
  }

  return {
    command: process.platform === "win32" ? "corepack.cmd" : "corepack",
    args: ["pnpm"],
    shell: process.platform === "win32",
  };
}

function isTurbopackManifestRace(output) {
  return /ENOENT: no such file or directory, open\s+'.*[/\\]\.next[/\\](required-server-files\.json|server[/\\]pages-manifest\.json|static[/\\].*[/\\]_buildManifest\.js\.tmp|turbopack)/s.test(output);
}

function isTurbopackPrerenderInvariant(output) {
  return (
    output.includes("Expected workStore to be initialized") &&
    output.includes("Export encountered an error on /_global-error/page")
  );
}

function prependPathList(currentValue, entries) {
  return [...entries.filter(Boolean), currentValue].filter(Boolean).join(path.delimiter);
}

function appendNodeOptions(currentValue, options) {
  const current = currentValue || "";
  const additions = options.filter((option) => !current.includes(option.split("=")[0]));
  return [current, ...additions].filter(Boolean).join(" ");
}
