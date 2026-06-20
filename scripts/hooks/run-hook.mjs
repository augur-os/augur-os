#!/usr/bin/env node
/**
 * Cross-platform hook runner for lightweight Augur agent hooks.
 *
 * Client hook configs run command strings under different shells on Windows,
 * macOS, and Linux. Keeping the hook entry point in Node avoids direct `.sh`
 * execution on Windows while preserving the existing fast hook behavior.
 */

import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const hookName = process.argv[2] || "";
const hookArgs = process.argv.slice(3);
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, "..", "..");

const DASHBOARD_SHORTCUT_REASON =
  "Blocked by rule 29: use /dev-build (rebuild) or /dev-debug (diagnose). Manual dev-server gymnastics bypass /dev-build safety (port-owner detection, codex thread state, vault sync, post-build verify).";

async function readStdin() {
  if (process.stdin.isTTY) {
    return "";
  }

  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf8");
}

function parseJson(value, fallback = {}) {
  if (!value || typeof value !== "string") {
    return fallback;
  }
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function toolInput(data) {
  const input = data?.tool_input ?? data?.toolInput ?? {};
  if (typeof input === "string") {
    return parseJson(input, {});
  }
  return input && typeof input === "object" ? input : {};
}

function printJson(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function platformStateDir() {
  if (process.env.AUGUR_RUNTIME_DIR) {
    return process.env.AUGUR_RUNTIME_DIR;
  }
  if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Application Support", "Augur", "state");
  }
  if (process.platform === "win32") {
    return path.join(
      process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"),
      "Augur",
      "state",
    );
  }
  return path.join(process.env.XDG_STATE_HOME || path.join(os.homedir(), ".local", "state"), "augur");
}

function platformLogsDir() {
  if (process.env.AUGUR_LOGS_DIR) {
    return process.env.AUGUR_LOGS_DIR;
  }
  if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Logs", "Augur");
  }
  if (process.platform === "win32") {
    return path.join(
      process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"),
      "Augur",
      "logs",
    );
  }
  return path.join(process.env.XDG_STATE_HOME || path.join(os.homedir(), ".local", "state"), "augur", "logs");
}

function normalizeSlashes(value) {
  return String(value || "").replaceAll("\\", "/");
}

function isoStampForFile() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z").replaceAll(":", "-");
}

function probeMcpPort() {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: "127.0.0.1", port: 8080 });
    const finish = () => {
      socket.destroy();
      resolve();
    };
    socket.setTimeout(2000);
    socket.on("connect", finish);
    socket.on("timeout", finish);
    socket.on("error", finish);
  });
}

function maybeCleanupStaleRemoteControl() {
  const stateFile = path.join(platformStateDir(), "remote-control.json");
  if (!fs.existsSync(stateFile)) {
    return;
  }

  const state = parseJson(fs.readFileSync(stateFile, "utf8"), null);
  const createdAt = state?.created_at ? Date.parse(state.created_at) : Number.NaN;
  if (!Number.isFinite(createdAt)) {
    return;
  }

  const ageMs = Date.now() - createdAt;
  if (ageMs > 24 * 60 * 60 * 1000) {
    fs.rmSync(stateFile, { force: true });
  }
}

function printPendingAttentionActions() {
  const attentionDir =
    process.env.AUGUR_ATTENTION_SESSION_DIR ||
    path.join(os.homedir(), "Vault", "Augur", "admin", "attention", "actions", "session");
  if (!fs.existsSync(attentionDir)) {
    return;
  }

  const files = fs
    .readdirSync(attentionDir)
    .filter((name) => name.endsWith(".yaml") || name.endsWith(".yml"))
    .map((name) => path.join(attentionDir, name));

  if (files.length === 0) {
    return;
  }

  process.stdout.write(`\nYou have ${files.length} approved action(s) from Reminders:\n\n`);
  files.forEach((file, index) => {
    const text = fs.readFileSync(file, "utf8");
    const titleLine = text.split(/\r?\n/).find((line) => line.startsWith("reminder_title:")) || "";
    const title = titleLine.replace(/^reminder_title:\s*/, "").replace(/^['"]|['"]$/g, "") || path.basename(file);
    process.stdout.write(`  ${index + 1}. ${title}\n`);
  });
  process.stdout.write("\nExecute them now? (y/n/pick)\n");
}

async function sessionStart() {
  await probeMcpPort();
  maybeCleanupStaleRemoteControl();
  printPendingAttentionActions();
  worktreePurgeSweep();
}

function skillUsage(data) {
  const input = toolInput(data);
  const skillName = input.skill || input.name || "unknown";
  const logDir = platformLogsDir();
  ensureDir(logDir);
  fs.appendFileSync(
    path.join(logDir, "skill-usage.jsonl"),
    `${JSON.stringify({ ts: new Date().toISOString(), skill: skillName })}\n`,
  );
}

function postSkill(data) {
  const input = parseJson(process.env.CLAUDE_TOOL_INPUT || "", toolInput(data));
  const command = input.skill || input.name || "";
  if (!command || command === "auto-command-evolution") {
    return;
  }

  const timestamp = isoStampForFile();
  const logDir = path.join(platformStateDir(), "command-evolution", command, "executions");
  ensureDir(logDir);
  const log = {
    command,
    outcome: "executed",
    started_at: timestamp,
    completed_at: timestamp,
    duration_ms: 0,
    phases: [],
    learnings: [],
    metrics: {},
  };
  fs.writeFileSync(path.join(logDir, `${timestamp}.json`), `${JSON.stringify(log, null, 2)}\n`);
}

function checkSkillStructure(data) {
  const input = toolInput(data);
  const filePath = normalizeSlashes(input.file_path || input.path || data?.file_path || process.env.HOOK_FILE_PATH || "");
  const warnings = [
    [/\/\.config$/, "Writing to deprecated .config file. Use plugin enable/disable instead."],
    [/\/augur\/augur\.ya?ml$/, "Legacy skill manifest is retired. Use SKILL.md x-augur-* frontmatter."],
    [/\/augur\/version\.yaml$/, "version.yaml replaced by plugin.json version."],
    [/\/augur\/README\.md$/, "augur/README.md is auto-generated. Don't edit directly."],
    [/\/augur\/data\//, "augur/data/ is deprecated. Use assets/seeds/ instead."],
    [/\/assets\/prompts\//, "assets/prompts/ consolidated into assets/seeds/prompts/."],
    [/\/assets\/seed-data\//, "assets/seed-data/ renamed to assets/seeds/."],
  ];

  for (const [pattern, message] of warnings) {
    if (pattern.test(`/${filePath}`)) {
      printJson({ continue: true, systemMessage: `WARNING (ADR-430): ${message}` });
      return;
    }
  }
}

function dashboardShortcutBlocker(data) {
  const input = toolInput(data);
  const command = input.command || "";
  if (!command) {
    printJson({ continue: true });
    return;
  }

  // Keep in sync with scripts/hooks/dashboard-shortcut-patterns.sh (sourced by .githooks/).
  const patterns = [
    /rm\s+-[a-z]*r[a-z]*f?\s+.*\.next(\/|$|\s)/i,
    /(^|\s|&&\s*|;\s*|\|\|\s*|\|\s*)(pnpm|npm|yarn|bun|bunx|npx)(\s+--filter\s+\S+)?\s+(run\s+)?(dev|next\s+dev)(\s|$)/i,
    /(^|\s|&&\s*|;\s*|\|\|\s*)(npx\s+|bunx\s+)?(next\s+(dev|start)|next-server)(\s|$)/i,
    /(p?kill).*(next\.?dev|next-server|node.*3000)/i,
  ];

  if (patterns.some((pattern) => pattern.test(command))) {
    printJson({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: DASHBOARD_SHORTCUT_REASON,
      },
    });
    return;
  }

  printJson({ continue: true });
}

function sessionWikiFlag() {
  const flagDir = path.join(platformStateDir(), "wiki");
  ensureDir(flagDir);
  fs.writeFileSync(path.join(flagDir, "needs-update.flag"), `${new Date().toISOString()}\n`);
}

function locatePython() {
  const candidates = [];
  if (process.platform === "win32") {
    candidates.push(path.join(projectRoot, ".venv", "Scripts", "python.exe"));
  }
  candidates.push(path.join(projectRoot, ".venv", "bin", "python"));
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  for (const fallback of ["python3", "python"]) {
    // Hard timeout: a `--version` probe must never hang for more than a few
    // seconds. Without this, a wedged interpreter would block the hook (and
    // therefore the whole Claude Code response) indefinitely.
    const probe = spawnSync(fallback, ["--version"], {
      stdio: "ignore",
      timeout: 5_000,
      killSignal: "SIGTERM",
    });
    if (probe.status === 0) return fallback;
  }
  return null;
}

function gitCapture(cwd, args) {
  // Hard timeout: every git read used by the hook (rev-parse, status,
  // symbolic-ref, …) must complete in seconds. A blocked git op (lock
  // contention, frozen credential helper) would otherwise hang the hook —
  // the harness keeps spinning and the user sees "stuck for hours."
  const result = spawnSync("git", args, {
    cwd,
    encoding: "utf8",
    timeout: 30_000,
    killSignal: "SIGTERM",
  });
  return result.status === 0 ? result.stdout.trim() : "";
}

function pythonEnv() {
  const pythonPath = [projectRoot, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  return { ...process.env, PYTHONPATH: pythonPath };
}

function resolveVaultDir() {
  const py = locatePython();
  if (!py) return "";

  const result = spawnSync(
    py,
    ["-c", "from src.config.paths import get_vault_dir; print(get_vault_dir())"],
    {
      cwd: projectRoot,
      encoding: "utf8",
      env: pythonEnv(),
      stdio: ["ignore", "pipe", "pipe"],
      // Hard timeout: Python startup + a single import resolve must finish
      // in seconds. Without a timeout, a stalled interpreter would hang the
      // hook indefinitely.
      timeout: 30_000,
      killSignal: "SIGTERM",
    },
  );
  return result.status === 0 ? result.stdout.trim() : "";
}

function runSilent(command, args, cwd) {
  // Hard timeout: this helper backs the vault auto-commit chain (`git add`,
  // `git commit`, `git push`). `git push` over the network is the realistic
  // worst case — a 60s ceiling tolerates slow networks and large pushes
  // while making it impossible for the hook to spin for hours when the
  // remote is unreachable, frozen, or waiting on a credential prompt that
  // will never come.
  return spawnSync(command, args, {
    cwd,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    timeout: 60_000,
    killSignal: "SIGTERM",
  });
}

function vaultAutocommit() {
  const vaultDir = resolveVaultDir();
  if (!vaultDir || !fs.existsSync(vaultDir)) {
    return;
  }

  if (runSilent("git", ["rev-parse", "--git-dir"], vaultDir).status !== 0) {
    return;
  }

  if (runSilent("git", ["add", "-u"], vaultDir).status !== 0) {
    return;
  }

  const diff = runSilent("git", ["diff", "--cached", "--quiet"], vaultDir);
  if (diff.status === 0) {
    return;
  }
  if (diff.status !== 1) {
    return;
  }

  const stamp = new Date().toISOString().slice(0, 16).replace("T", "-").replace(":", "");
  runSilent("git", ["commit", "-m", `vault: auto-commit ${stamp}`], vaultDir);
}

function preCompact() {
  const checkpointDir = path.join(platformStateDir(), "checkpoints");
  ensureDir(checkpointDir);

  const nowIso = new Date().toISOString();
  const stamp = nowIso.replace(/[:]/g, "").replace(/\.\d{3}Z$/, "").replace("T", "-").slice(0, 15);
  const checkpoint = {
    timestamp: nowIso,
    branch: gitCapture(projectRoot, ["branch", "--show-current"]) || "unknown",
    head: gitCapture(projectRoot, ["rev-parse", "HEAD"]) || "unknown",
    dirty_files: (gitCapture(projectRoot, ["status", "--porcelain"]).match(/^/gm) || []).length,
    event: "pre_compact",
  };
  fs.writeFileSync(
    path.join(checkpointDir, `pre-compact-${stamp}.json`),
    `${JSON.stringify(checkpoint, null, 2)}\n`,
  );

  // Keep last 20 checkpoints.
  const entries = fs
    .readdirSync(checkpointDir)
    .filter((name) => name.startsWith("pre-compact-") && name.endsWith(".json"))
    .map((name) => ({ name, mtime: fs.statSync(path.join(checkpointDir, name)).mtimeMs }))
    .sort((a, b) => b.mtime - a.mtime);
  for (const stale of entries.slice(20)) {
    fs.rmSync(path.join(checkpointDir, stale.name), { force: true });
  }
}

function subagentStop(data) {
  const stateDir = platformStateDir();
  ensureDir(stateDir);
  const event = {
    timestamp: new Date().toISOString(),
    event: "subagent_stop",
    agent:
      process.env.agentName ||
      data?.agent_name ||
      data?.agentName ||
      data?.agent ||
      "unknown",
    exit_code: Number(process.env.exitCode ?? data?.exit_code ?? data?.exitCode ?? 0),
  };
  fs.appendFileSync(path.join(stateDir, "agent-log.jsonl"), `${JSON.stringify(event)}\n`);
}

// File-mutating tools whose targets count as "feature work" when they land on
// a skill's scripts/ or src/mcp/. Bash edits (sed/heredoc) are intentionally
// excluded — they are rare for feature code and matching them is fragile.
const EDIT_TOOL_NAMES = new Set(["Edit", "Write", "MultiEdit", "NotebookEdit"]);

// Recursively collect every {type:"tool_use"} block in a parsed transcript
// line. Claude Code nests tool_use blocks inside message.content arrays whose
// exact shape varies by client version, so we walk the whole object defensively
// rather than hard-coding a path.
function collectToolUses(node, out) {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node)) {
    for (const item of node) collectToolUses(item, out);
    return;
  }
  if (node.type === "tool_use" && typeof node.name === "string") {
    out.push(node);
  }
  for (const key of Object.keys(node)) {
    collectToolUses(node[key], out);
  }
}

// Files THIS session edited, derived from the session transcript that the Stop
// hook receives via `transcript_path`. This is the accurate signal for "what
// did this session change" — far better than git working-tree state, which is
// polluted by edits from prior sessions and unrelated dirty files on the branch.
function sessionEditedFiles(data) {
  const transcriptPath = data?.transcript_path || data?.transcriptPath || "";
  if (!transcriptPath || !fs.existsSync(transcriptPath)) return [];
  let text;
  try {
    text = fs.readFileSync(transcriptPath, "utf8");
  } catch {
    return [];
  }
  const files = new Set();
  for (const line of text.split("\n")) {
    if (!line.trim()) continue;
    const entry = parseJson(line, null);
    if (!entry) continue;
    const toolUses = [];
    collectToolUses(entry, toolUses);
    for (const tu of toolUses) {
      if (!EDIT_TOOL_NAMES.has(tu.name)) continue;
      const input = tu.input && typeof tu.input === "object" ? tu.input : {};
      const candidates = [input.file_path, input.path, input.notebook_path];
      if (Array.isArray(input.edits)) {
        for (const edit of input.edits) candidates.push(edit?.file_path);
      }
      for (const candidate of candidates) {
        if (typeof candidate === "string" && candidate.trim()) {
          files.add(candidate.trim());
        }
      }
    }
  }
  return [...files];
}

// Stop hook: once per session, if THIS session did feature work, force a
// conscious value-validation check before the session ends. "Feature work" =
// edits this session made under a skill's scripts/ or src/mcp/. This is a
// mechanical nudge for the recurring failure where work is verified
// mechanically (tests pass, build green, scan counts) but never run against
// real data to prove user value (agent-rules rule 34). It blocks exactly once,
// then a session flag lets the next Stop through — it is a reminder, not a loop.
//
// Scoping is transcript-derived, NOT git-derived: a session that only saved a
// note or read files must not trip the nudge just because the branch already
// had unrelated dirty feature files from earlier work.
function stopValueValidation(data) {
  try {
    const sessionId = String(data?.session_id || data?.sessionId || "nosession").replace(
      /[^A-Za-z0-9_-]/g,
      "",
    );
    const stateDir = platformStateDir();
    ensureDir(stateDir);
    const flag = path.join(stateDir, `value-validation-prompt-${sessionId}.flag`);
    if (fs.existsSync(flag)) {
      return; // already nudged this session — allow stop
    }

    const edited = sessionEditedFiles(data);
    // Anchored on `/` or string start so it matches both absolute transcript
    // paths (/Users/.../Augur/src/mcp/...) and repo-relative paths.
    const FEATURE_RE = /(project-brain\/capabilities\/skills\/[^/]+\/scripts\/|(^|\/)src\/mcp\/)/;
    const featureWork = edited.some((p) => FEATURE_RE.test(normalizeSlashes(p)));
    if (!featureWork) {
      return; // this session changed no feature logic — nothing to nudge
    }

    fs.writeFileSync(flag, new Date().toISOString());
    printJson({
      decision: "block",
      reason:
        "Value-validation check (agent-rules rule 34): this session edited " +
        "feature logic (a skill's scripts/ or src/mcp/). Before ending: did you " +
        "run the capability against REAL data (real vault/documents/index, not " +
        "only tmp-path fixtures) and show concrete user-facing output that " +
        "proves the value it promised? Tests passing, a green build, a dry-run " +
        "count, or a stats command returning zeros is NOT value validation. If " +
        "you already did this, state the real input used and value delivered, " +
        "then stop again. If you did not, do it now or report honestly what is " +
        "unvalidated. This nudge fires once per session.",
    });
  } catch {
    // Never let the Stop hook crash the session — fail open (allow stop).
  }
}

function remoteControlCleanup() {
  // The original macOS Reminders.app completion path used a Python module
  // (plugins/productivity/skills/apple/scripts/remote_control.py) that no
  // longer exists in the tree. Until that returns, the safe fallback is to
  // delete the stale state file so the next session starts clean.
  const stateFile = path.join(platformStateDir(), "remote-control.json");
  if (fs.existsSync(stateFile)) {
    fs.rmSync(stateFile, { force: true });
  }
}

function runPythonScript(relativeScript, extraArgs = []) {
  const py = locatePython();
  if (!py) return;
  const scriptPath = path.join(projectRoot, relativeScript);
  if (!fs.existsSync(scriptPath)) return;
  // Hard timeout: hook-driven Python scripts (worktree register/unregister,
  // configure-mcp, post-skill, …) must never block the harness. 60s tolerates
  // a slow `uv` import or filesystem walk; anything longer is a hang.
  spawnSync(py, [scriptPath, ...extraArgs], {
    cwd: projectRoot,
    env: { ...process.env, PYTHONPATH: projectRoot },
    // Drop the child's stdout: the hook's stdout is a reserved protocol channel
    // (e.g. WorktreeCreate's stdout is read by the harness to resolve the new
    // worktree cwd). Leaking worktree_registry.py's pretty-printed JSON here made
    // EnterWorktree chdir into the trailing '}'. Keep stderr for error visibility.
    stdio: ["ignore", "ignore", "inherit"],
    timeout: 60_000,
    killSignal: "SIGTERM",
  });
}

function worktreePurgeSweep() {
  // Reap any worktree queued for deferred purge that is now free (every live
  // AI/client owner has released the path). Spawned detached + unref'd so the
  // bounded session hook (10s) never blocks on git/worktree work; the sweep
  // self-times out and logs to the platform log dir.
  const py = locatePython();
  if (!py) return;
  const scriptPath = path.join(
    projectRoot,
    "project-brain/capabilities/skills/platform-admin/scripts/worktree_purge_queue.py",
  );
  if (!fs.existsSync(scriptPath)) return;
  try {
    const child = spawn(py, [scriptPath, "sweep", "--from-hook"], {
      cwd: projectRoot,
      env: { ...process.env, PYTHONPATH: projectRoot },
      detached: true,
      stdio: "ignore",
    });
    child.unref();
  } catch {
    // Queue maintenance must never break session start/end.
  }
}

function worktreeCreate(data) {
  // Harness WorktreeCreate contract: create the worktree and echo its path to
  // stdout. We provision a full Augur worktree (sibling augur-<name> + allocated
  // ports + .augur-worktree.yaml) so `aug dev build` resolves its own port.
  const py = locatePython();
  if (!py) {
    process.stderr.write("worktree-create: python not found\n");
    return;
  }
  const name =
    data && typeof data.name === "string" && data.name.trim()
      ? data.name.trim()
      : `wt-${Date.now()}`;
  const res = spawnSync(
    py,
    [path.join(projectRoot, "scripts/worktree_create.py"), "--name", name, "--repo", projectRoot],
    {
      cwd: projectRoot,
      env: { ...process.env, PYTHONPATH: projectRoot },
      encoding: "utf-8",
      timeout: 55_000,
      killSignal: "SIGTERM",
    },
  );
  if (res.stderr) process.stderr.write(res.stderr);
  // Echo ONLY the worktree path (last non-empty stdout line) — the harness reads
  // this hook's stdout as the new worktree's cwd; any extra output corrupts it.
  const lines = String(res.stdout || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const worktreePath = lines.length ? lines[lines.length - 1] : "";
  if (worktreePath) process.stdout.write(`${worktreePath}\n`);
}

function worktreeRemove(data) {
  // The harness WorktreeRemove event passes the worktree path via stdin
  // (`worktree_path`), NOT an env var. Resolve from stdin first; never act on the
  // main checkout.
  const worktreePath =
    (data && typeof data.worktree_path === "string" && data.worktree_path.trim()) ||
    process.env.CLAUDE_WORKTREE_PATH ||
    "";
  if (!worktreePath || path.resolve(worktreePath) === path.resolve(projectRoot)) {
    return;
  }
  // Cross-client, no-loss cleanup. The purge queue + `worktree-launch.sh cleanup`
  // (unregister + git worktree remove + codex thread repair + branch -D) is
  // CLIENT-NEUTRAL and owner-aware: it never deletes a path a live client (Claude,
  // Codex, Gemini, Copilot, Cowork, …) still owns, and refuses unmerged branches.
  // Enqueue, then sweep (reaps now if merged + clean + unowned; otherwise the
  // session-start/end sweeps reap it later — never losing commits). Augur is
  // cross-client: this hook is one client's entry into a shared cleanup, not the
  // only path. See ADR-810 + rule 26.
  const queue =
    "project-brain/capabilities/skills/platform-admin/scripts/worktree_purge_queue.py";
  runPythonScript(queue, ["enqueue", "--path", worktreePath]);
  runPythonScript(queue, ["sweep", "--from-hook"]);
}

function configureMcp() {
  runPythonScript("scripts/configure_mcp.py", ["--auto"]);
}

async function main() {
  const stdin = await readStdin();
  const data = parseJson(stdin, {});

  switch (hookName) {
    case "session-start":
      await sessionStart();
      break;
    case "skill-usage":
      skillUsage(data);
      break;
    case "post-skill":
      postSkill(data);
      break;
    case "check-skill-structure":
      checkSkillStructure(data);
      break;
    case "dashboard-shortcut-blocker":
      dashboardShortcutBlocker(data);
      break;
    case "session-wiki-flag":
      sessionWikiFlag();
      break;
    case "vault-autocommit":
      vaultAutocommit();
      break;
    case "pre-compact":
      preCompact();
      break;
    case "subagent-stop":
      subagentStop(data);
      break;
    case "stop":
      stopValueValidation(data);
      break;
    case "remote-control-cleanup":
      remoteControlCleanup();
      break;
    // `worktree-register` is the legacy name (older cached settings may still call
    // it); both route to the create+echo-path handler.
    case "worktree-register":
    case "worktree-create":
      worktreeCreate(data);
      break;
    case "worktree-purge-sweep":
      worktreePurgeSweep();
      break;
    case "worktree-remove":
    case "worktree-unregister":
      worktreeRemove(data);
      break;
    case "configure-mcp":
      configureMcp();
      break;
    default:
      break;
  }
}

main().catch((error) => {
  process.stderr.write(`Augur hook failed: ${error?.message || error}\n`);
  process.exitCode = 0;
});
