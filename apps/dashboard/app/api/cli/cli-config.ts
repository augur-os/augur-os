/**
 * CLI Route — Configuration & Environment
 *
 * CLI agent registry, command resolution, environment variable
 * construction, and session file management.
 *
 * Extracted from route.ts to isolate config lookup and env setup
 * from PTY lifecycle and request handling.
 */

import path from "path";
import fs from "fs";
import yaml from "js-yaml";
import { AUGUR_STATE_DIR, AUGUR_VAULT_CONFIG_DIR, AUGUR_VAULT_DIR } from "@/lib/paths";

export type CliCategory = "remote" | "local" | "ide";

const USER_HOME = process.env.USERPROFILE || process.env.HOME || "";

export const AUGUR_ROOT =
  process.env.AUGUR_ROOT ||
  path.join(USER_HOME, "Projects", "Augur");

// Prefer the resolved vault config root (handles the _augur/ domains layout),
// with the legacy flat vault/ai path kept readable during migration.
// Deduped: AUGUR_VAULT_CONFIG_DIR commonly resolves to <vault>/_augur/config, so
// the first two candidates can be identical. Set-dedup keeps the error message and
// the per-call scan clean without changing lookup order.
const CLI_AGENTS_PATH_CANDIDATES = Array.from(
  new Set([
    path.join(AUGUR_VAULT_CONFIG_DIR, "ai", "cli_agents.yaml"),
    // Explicit _augur/config candidate. AUGUR_VAULT_CONFIG_DIR is resolved ONCE at
    // module load via existsSync, so if the server booted before the vault's
    // _augur/config existed (e.g. mid vault-sync during `aug dev build`), it cached
    // the legacy path and EVERY CLI chat failed with "Unknown CLI: <cli>" until the
    // next restart. resolveCliAgentsPath() re-checks each candidate at call time, so
    // this finds the real file regardless of that cached choice.
    path.join(AUGUR_VAULT_DIR, "_augur", "config", "ai", "cli_agents.yaml"),
    path.join(AUGUR_VAULT_DIR, "config", "ai", "cli_agents.yaml"),
    path.join(AUGUR_VAULT_DIR, "ai", "cli_agents.yaml"),
  ]),
);

const CHAT_SESSION_FILE = path.join(
  AUGUR_STATE_DIR,
  "temp",
  "chat_session.json",
);
const PREFERENCES_PATH = path.join(AUGUR_STATE_DIR, "preferences.yaml");
const DEFAULT_OLLAMA_MODEL = "qwen3.5:9b";

const CLIENT_TO_CLI_ID: Record<string, string> = {
  "claude-code": "claude",
  claude_code: "claude",
  "claude-desktop": "claude",
  claude_desktop: "claude",
  cursor: "cursor-cli",
  copilot: "copilot-cli",
};

/**
 * Build a PATH that includes common user binary directories.
 * The Next.js server process may inherit a stripped-down PATH that
 * doesn't include ~/.local/bin, /opt/homebrew/bin, etc.
 */
const EXTRA_PATH_DIRS = (() => {
  if (process.platform === "win32") {
    const appData = process.env.APPDATA || path.join(USER_HOME, "AppData", "Roaming");
    const localAppData = process.env.LOCALAPPDATA || path.join(USER_HOME, "AppData", "Local");
    return [
      path.join(appData, "npm"),
      path.join(localAppData, "Programs", "Python", "Python311", "Scripts"),
      path.join(localAppData, "Programs", "Python", "Python312", "Scripts"),
    ];
  }

  return [
    path.join(USER_HOME, ".local", "bin"),
    path.join(USER_HOME, ".npm-global", "bin"),
    "/usr/local/bin",
    "/opt/homebrew/bin",
    "/opt/homebrew/sbin",
  ];
})();

function getEnhancedPath(): string {
  const currentPath = process.env.PATH || "";
  // Prepend extra dirs so they're found first, dedup later via the OS
  return [...EXTRA_PATH_DIRS, currentPath].join(path.delimiter);
}

/**
 * Resolve a command name to an absolute path by searching the enhanced PATH.
 * node-pty's posix_spawnp searches the PARENT process PATH, not the child env,
 * so bare command names like "claude" fail when the Next.js server has a stripped PATH.
 */
export function resolveCommand(cmd: string): string {
  if (path.isAbsolute(cmd)) return cmd;

  const allDirs = [...EXTRA_PATH_DIRS, ...(process.env.PATH || "").split(path.delimiter)];
  for (const dir of allDirs) {
    for (const candidate of commandCandidates(dir, cmd)) {
      try {
        fs.accessSync(candidate, fs.constants.X_OK);
        return candidate;
      } catch {
        // not found in this dir, continue
      }
    }
  }
  // Fall back to bare name — let posix_spawnp try (will fail with clear error)
  return cmd;
}

function commandCandidates(dir: string, cmd: string): string[] {
  const direct = path.join(dir, cmd);
  if (process.platform !== "win32" || path.extname(cmd)) {
    return [direct];
  }
  const extensions = (process.env.PATHEXT || ".COM;.EXE;.BAT;.CMD")
    .split(";")
    .map((ext) => ext.trim())
    .filter(Boolean);
  const candidates: string[] = [];
  for (const ext of extensions) {
    candidates.push(`${direct}${ext}`);
    const lower = ext.toLowerCase();
    if (lower !== ext) {
      candidates.push(`${direct}${lower}`);
    }
  }
  candidates.push(direct);
  return candidates;
}

export function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function resolveCliAgentsPath(): string | null {
  for (const candidate of CLI_AGENTS_PATH_CANDIDATES) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

export function getCliAgentsConfig(): Record<string, any> {
  const cliAgentsPath = resolveCliAgentsPath();
  // A vault that has not been onboarded yet (or is mid vault-sync) legitimately has
  // no cli_agents.yaml. Degrade to the built-in default agent instead of throwing —
  // throwing here 500s /api/cli/configs and /api/session/init, which logged a console
  // error on every page load and broke session init on a fresh brain. A genuinely
  // missing *requested* CLI is still surfaced by callers (SessionManager) as a
  // distinct "CLI '<id>' not found" error.
  if (!cliAgentsPath) {
    return withDirectOllamaAgent({});
  }
  // @fs-exempt: read-only load of local cli_agents.yaml config on session init.
  // An MCP file-read round-trip adds no safety for read-only local config. See ADR-817.
  const content = fs.readFileSync(cliAgentsPath, "utf-8");
  const data = yaml.load(content) as Record<string, any>;
  const agents =
    data?.agents && typeof data.agents === "object" ? { ...data.agents } : {};
  return withDirectOllamaAgent(agents);
}

function canonicalCliId(clientId: string): string {
  const normalized = clientId.trim().toLowerCase();
  return CLIENT_TO_CLI_ID[normalized] || normalized;
}

function readDefaultClientId(): string | null {
  const data = readPreferences();
  const defaultClient = data?.client_routing?.default_client;
  return isNonEmptyString(defaultClient) ? defaultClient.trim() : null;
}

function readPreferences(): Record<string, any> | null {
  try {
    if (!fs.existsSync(PREFERENCES_PATH)) return null;
    const content = fs.readFileSync(PREFERENCES_PATH, "utf-8");
    const data = yaml.load(content) as Record<string, any>;
    return data && typeof data === "object" ? data : null;
  } catch {
    return null;
  }
}

export function readConfiguredOllamaModel(): string {
  const model = readPreferences()?.local_backends?.ollama?.model;
  return isNonEmptyString(model) ? model.trim() : DEFAULT_OLLAMA_MODEL;
}

function withDirectOllamaAgent(agents: Record<string, any>): Record<string, any> {
  if (Object.prototype.hasOwnProperty.call(agents, "ollama")) {
    return agents;
  }

  return {
    ...agents,
    ollama: {
      label: "Ollama",
      cmd: ["ollama", "run", readConfiguredOllamaModel()],
      cwd: ".",
      category: "local",
      group: "ollama",
    },
  };
}

export function resolveDefaultCliId(
  agents: Record<string, any> = getCliAgentsConfig(),
): string {
  const defaultClient = readDefaultClientId();
  if (defaultClient) {
    const cliId = canonicalCliId(defaultClient);
    if (Object.prototype.hasOwnProperty.call(agents, cliId)) {
      return cliId;
    }
    if (Object.prototype.hasOwnProperty.call(agents, defaultClient)) {
      return defaultClient;
    }
  }

  return Object.keys(agents)[0] || "";
}

export function isValidCli(cliId: string): boolean {
  // ADR-160: Agent bubble IDs use the pattern "agent-bubble-{uuid}" and
  // resolve to the configured default CLI for config lookup.
  if (cliId.startsWith("agent-bubble-")) return true;
  try {
    const agents = getCliAgentsConfig();
    return Object.prototype.hasOwnProperty.call(agents, cliId);
  } catch {
    return false;
  }
}

/**
 * Resolve cliId to the config key used for cli_agents.yaml lookup.
 * Agent bubble IDs map to the configured default agent CLI.
 */
export function resolveConfigKey(cliId: string): string {
  if (cliId.startsWith("agent-bubble-")) return resolveDefaultCliId();
  return cliId;
}

export function isDirectOllamaCli(cliId: string): boolean {
  return resolveConfigKey(cliId) === "ollama";
}

export function extractOllamaRunModel(cmd: unknown): string | null {
  if (!Array.isArray(cmd) || cmd.length < 3) {
    return null;
  }

  const [binary, subcommand, model] = cmd;
  if (
    !isNonEmptyString(binary) ||
    !isNonEmptyString(subcommand) ||
    !isNonEmptyString(model)
  ) {
    return null;
  }

  const executable = path.basename(binary).replace(/\.(cmd|exe|bat|ps1)$/i, "");
  if (executable !== "ollama" || subcommand !== "run") {
    return null;
  }

  return model.trim();
}

export function getCliConfigOrThrow(cliId: string): Record<string, any> {
  const agents = getCliAgentsConfig();
  const config = agents[cliId];
  if (!config) {
    throw new Error(`CLI '${cliId}' not found in cli_agents.yaml`);
  }

  const cmd = config.cmd;
  if (!Array.isArray(cmd) || cmd.length === 0 || !isNonEmptyString(cmd[0])) {
    throw new Error(`CLI '${cliId}' has no cmd defined in cli_agents.yaml`);
  }

  return config;
}

export function buildCliSpawnEnv(
  config: Record<string, any>,
  currentPage?: string,
  themeMode?: "light" | "dark",
): Record<string, string> {
  // Clone process.env and remove all Claude/Codex session vars to prevent
  // "nested session" errors and env contamination from the parent process.
  // The dashboard may itself be running inside a Claude Code session whose
  // env vars (CLAUDECODE, CLAUDE_CODE_ENTRYPOINT, experimental flags, etc.)
  // would leak into the spawned CLI and cause API errors (500).
  const baseEnv = { ...process.env };
  for (const key of Object.keys(baseEnv)) {
    if (key === "CLAUDECODE" || key.startsWith("CLAUDE_CODE_")) {
      delete baseEnv[key];
    }
  }

  // COLORFGBG tells terminal-aware CLIs (claude, vim, etc.) about the background.
  // "15;0" = light fg on dark bg (dark mode), "0;15" = dark fg on light bg (light mode).
  const colorfgbg = themeMode === "light" ? "0;15" : "15;0";

  return {
    ...baseEnv,
    ...(config.env || {}),
    PATH: getEnhancedPath(),
    COLORFGBG: colorfgbg,
    ...(currentPage ? { AUGUR_CURRENT_PAGE: currentPage } : {}),
  } as Record<string, string>;
}

export function resolveSpawnCommand(rawCmd: string): string {
  const resolvedCmd = resolveCommand(rawCmd);
  if (!fs.existsSync(resolvedCmd)) {
    throw new Error(
      `CLI binary not found: '${rawCmd}' (resolved to '${resolvedCmd}'). ` +
        `Checked dirs: ${EXTRA_PATH_DIRS.join(", ")}`,
    );
  }
  return resolvedCmd;
}

/**
 * Write chat session state to disk so MCP tools (get-chat-session) can read it.
 * This MUST happen before the PTY spawns so Claude Code sees the page context
 * when it calls get-chat-session during its mandatory session protocol.
 */
// @fs-exempt: writes the interactive CLI/PTY session state file. Called on every
// CLI lifecycle transition from the exempt terminal module (api/cli/actions.ts) —
// a hot, PTY-coupled path. Routing each status flip through an MCP file-write would
// add latency to the interactive terminal and couple the exempt feature to MCP. See ADR-817.
export function writeChatSession(data: Record<string, unknown>): void {
  try {
    const dir = path.dirname(CHAT_SESSION_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // Merge with existing session data if present
    let current: Record<string, unknown> = {};
    if (fs.existsSync(CHAT_SESSION_FILE)) {
      try {
        current = JSON.parse(fs.readFileSync(CHAT_SESSION_FILE, "utf-8"));
      } catch {
        /* start fresh */
      }
    }

    const merged = { ...current, ...data };
    fs.writeFileSync(CHAT_SESSION_FILE, JSON.stringify(merged, null, 2));
  } catch (err) {
    console.error("Failed to write chat session:", err);
  }
}

export interface CliRequestBody {
  action?: string;
  cliId?: string;
  input?: string;
  data?: string;
  cols?: number;
  rows?: number;
  current_page?: string;
  airplaneMode?: boolean;
  themeMode?: "light" | "dark";
  autoContext?: boolean;
  verbosity?: import("@/lib/chat/quiet-filter").VerbosityLevel;
  takeOverSessionOwner?: boolean;
  /** ADR-160: Oneshot prompt to inject into agent bubble CLIs after startup */
  oneshotPrompt?: string;
  /** ADR-161: Pre-resolved context envelope for enriched session data */
  envelope?: {
    hub?: string;
    skill?: string | null;
    skillSummary?: string | null;
    skillTools?: string[];
    skillActions?: string[];
  };
}
