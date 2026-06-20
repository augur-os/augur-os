"use server";

import fs from "fs/promises";
import { revalidatePath } from "next/cache";
import { spawn } from "child_process";
import os from "os";
import path from "path";
import yaml from "yaml";

import { auth } from "@/lib/auth/server-action";
import { AUGUR_ROOT, getSkillSubPath } from "@/lib/paths";
import { runCommand } from "@/lib/server/spawn";

function getClaudeDesktopConfigPath() {
  const home = os.homedir();

  if (process.platform === "win32") {
    const appData =
      process.env.APPDATA || path.join(home, "AppData", "Roaming");
    return path.join(appData, "Claude", "claude_desktop_config.json");
  }

  if (process.platform === "darwin") {
    return path.join(
      home,
      "Library",
      "Application Support",
      "Claude",
      "claude_desktop_config.json",
    );
  }

  const xdg = process.env.XDG_CONFIG_HOME;
  if (xdg) return path.join(xdg, "Claude", "claude_desktop_config.json");
  return path.join(home, ".config", "Claude", "claude_desktop_config.json");
}

type ActionResult = { success: true } | { success: false; error: string };
type PickFileResult =
  | { success: true; path: string }
  | { success: false; error: string };

// NOTE: CreateInterviewProjectInput and CreateInterviewProjectResult removed
// These types are now plugin-provided via vertical-work/careers/

type TokenizeState = {
  current: string;
  quote: '"' | "'" | null;
  escaping: boolean;
};

function consumeEscapedChar(state: TokenizeState, char: string): boolean {
  if (!state.escaping) return false;
  state.current += char;
  state.escaping = false;
  return true;
}

function beginEscape(state: TokenizeState, char: string): boolean {
  if (char !== "\\") return false;
  state.escaping = true;
  return true;
}

function consumeQuotedChar(state: TokenizeState, char: string): boolean {
  if (!state.quote) return false;
  if (char === state.quote) {
    state.quote = null;
  } else {
    state.current += char;
  }
  return true;
}

function beginQuote(state: TokenizeState, char: string): boolean {
  if (char !== '"' && char !== "'") return false;
  state.quote = char;
  return true;
}

function consumeWhitespace(
  state: TokenizeState,
  char: string,
  tokens: string[],
): boolean {
  if (!/\s/.test(char)) return false;
  if (state.current) {
    tokens.push(state.current);
    state.current = "";
  }
  return true;
}

function tokenizeCommand(input: string): string[] {
  const tokens: string[] = [];
  const state: TokenizeState = {
    current: "",
    quote: null,
    escaping: false,
  };

  for (let i = 0; i < input.length; i += 1) {
    const char = input[i];
    if (consumeEscapedChar(state, char)) continue;
    if (beginEscape(state, char)) continue;
    if (consumeQuotedChar(state, char)) continue;
    if (beginQuote(state, char)) continue;
    if (consumeWhitespace(state, char, tokens)) continue;
    state.current += char;
  }

  if (state.current) tokens.push(state.current);
  return tokens;
}

async function spawnCommand(command: string, args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: "ignore" });
    child.once("error", reject);
    child.once("exit", (code) => {
      if (code === 0 || code === null) {
        resolve();
        return;
      }
      reject(new Error(`Command failed: ${command} (${code ?? "unknown"})`));
    });
  });
}

function isWithinRoot(targetPath: string, rootPath: string) {
  const relative = path.relative(rootPath, targetPath);
  return (
    relative === "" ||
    (relative !== ".." &&
      !relative.startsWith(`..${path.sep}`) &&
      !path.isAbsolute(relative))
  );
}

function normalizeFsPath(targetPath: string) {
  const resolved = path.resolve(targetPath);
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}

function getRepoRootForOpen() {
  return AUGUR_ROOT;
}

function getDeleteAllowedRoots() {
  return [AUGUR_ROOT];
}

function getOpenAllowedRoots() {
  return [
    AUGUR_ROOT,
    getRepoRootForOpen(),
    path.dirname(getClaudeDesktopConfigPath()),
    path.join(os.homedir(), ".cursor"),
  ];
}

// NOTE: normalizeProjectId removed - was only used by createInterviewProject

async function assertPathAllowedForOpen(targetPath: string): Promise<void> {
  const resolved = normalizeFsPath(targetPath);
  const baseAllowed = getOpenAllowedRoots().map(normalizeFsPath);
  if (baseAllowed.some((root) => isWithinRoot(resolved, root))) return;

  throw new Error("Path is outside allowed roots");
}

async function assertPathAllowedForDelete(targetPath: string): Promise<void> {
  const resolved = normalizeFsPath(targetPath);
  const allowed = getDeleteAllowedRoots()
    .map(normalizeFsPath)
    .some((root) => isWithinRoot(resolved, root));
  if (!allowed) throw new Error("Path is outside allowed roots");
}

async function assertPathAllowedForWrite(targetPath: string): Promise<void> {
  // For now, writing is only allowed inside the user data root.
  return assertPathAllowedForDelete(targetPath);
}

async function assertPathAllowedForOpenDirectory(
  targetPath: string,
): Promise<void> {
  const resolved = normalizeFsPath(targetPath);
  const baseAllowed = getOpenAllowedRoots().map(normalizeFsPath);
  if (baseAllowed.some((root) => isWithinRoot(resolved, root))) return;

  throw new Error("Path is outside allowed roots");
}

function getPreferredEditorCommand() {
  const raw =
    process.env.AUGUR_EDITOR ?? process.env.VISUAL ?? process.env.EDITOR;
  if (!raw) return null;

  const parts = tokenizeCommand(raw).filter(Boolean);
  if (parts.length === 0) return null;

  return { command: parts[0], args: parts.slice(1), raw };
}

async function openWithSystemDefault(targetPath: string) {
  const platform = os.platform();
  if (platform === "darwin") {
    await spawnCommand("open", [targetPath]);
    return;
  }
  if (platform === "win32") {
    await spawnCommand("cmd", ["/c", "start", "", targetPath]);
    return;
  }
  await spawnCommand("xdg-open", [targetPath]);
}

async function tryPreferredEditorCommand(
  preferred: ReturnType<typeof getPreferredEditorCommand>,
  targetPath: string,
  platform: NodeJS.Platform,
): Promise<boolean> {
  if (!preferred) return false;

  try {
    await spawnCommand(preferred.command, [...preferred.args, targetPath]);
    return true;
  } catch (error) {
    if (platform === "darwin" && preferred.args.length === 0) {
      try {
        await spawnCommand("open", ["-a", preferred.raw, targetPath]);
        return true;
      } catch {
        return false;
      }
    }
    return false;
  }
}

function getCliCandidates(_platform: NodeJS.Platform): string[] {
  return [
    "cursor",
    "code",
    "zed",
    "subl",
    "idea",
    "webstorm",
    "pycharm",
    "goland",
    "rubymine",
    "clion",
    "fleet",
  ];
}

async function tryOpenWithCommands(
  commands: string[],
  targetPath: string,
): Promise<boolean> {
  return tryOpenCommandAt(commands, targetPath, 0);
}

async function tryOpenCommandAt(
  commands: string[],
  targetPath: string,
  index: number,
): Promise<boolean> {
  const command = commands[index];
  if (!command) {
    return false;
  }

  try {
    await spawnCommand(command, [targetPath]);
    return true;
  } catch {
    return tryOpenCommandAt(commands, targetPath, index + 1);
  }
}

async function tryOpenWithMacApps(targetPath: string): Promise<boolean> {
  const macAppCandidates = [
    "Visual Studio Code",
    "Cursor",
    "Zed",
    "Sublime Text",
  ];
  return tryOpenMacAppAt(macAppCandidates, targetPath, 0);
}

async function tryOpenMacAppAt(
  appNames: string[],
  targetPath: string,
  index: number,
): Promise<boolean> {
  const appName = appNames[index];
  if (!appName) {
    return false;
  }

  try {
    await spawnCommand("open", ["-a", appName, targetPath]);
    return true;
  } catch {
    return tryOpenMacAppAt(appNames, targetPath, index + 1);
  }
}

interface OpenCandidate {
  root: string;
  fullPath: string;
}

async function tryOpenCandidateAt(
  candidates: OpenCandidate[],
  index: number,
): Promise<boolean> {
  const candidate = candidates[index];
  if (!candidate) {
    return false;
  }

  if (!isWithinRoot(candidate.fullPath, candidate.root)) {
    return tryOpenCandidateAt(candidates, index + 1);
  }

  try {
    const stat = await fs["stat"](candidate.fullPath);
    if (!stat.isFile()) {
      return tryOpenCandidateAt(candidates, index + 1);
    }
    await openInPreferredEditor(candidate.fullPath);
    return true;
  } catch {
    return tryOpenCandidateAt(candidates, index + 1);
  }
}

async function openInPreferredEditor(targetPath: string) {
  const preferred = getPreferredEditorCommand();
  const platform = os.platform();

  if (await tryPreferredEditorCommand(preferred, targetPath, platform)) return;
  if (await tryOpenWithCommands(getCliCandidates(platform), targetPath)) return;
  if (platform === "darwin" && (await tryOpenWithMacApps(targetPath))) return;

  await openWithSystemDefault(targetPath);
}

function isIndexedAudioPath(
  indexedPath: string | undefined,
  resolvedPath: string,
): boolean {
  if (!indexedPath) return false;
  return path.resolve(indexedPath) === resolvedPath;
}

function hasIndexedAudioPath(
  items: Array<{ audio_path?: string }>,
  resolvedPath: string,
): boolean {
  return items.some((item) =>
    isIndexedAudioPath(item?.audio_path, resolvedPath),
  );
}

export async function openScreenRecordingSettings(): Promise<ActionResult> {
  if (process.platform !== "darwin") {
    return {
      success: false,
      error: "Screen Recording settings are only supported on macOS",
    };
  }

  await auth();

  try {
    await spawnCommand("open", [
      "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
    ]);
    return { success: true };
  } catch (error) {
    console.error("Failed to open Screen Recording settings:", error);
    return {
      success: false,
      error: "Failed to open Screen Recording settings",
    };
  }
}

export async function openMicrophoneSettings(): Promise<ActionResult> {
  if (process.platform !== "darwin") {
    return {
      success: false,
      error: "Microphone settings are only supported on macOS",
    };
  }

  await auth();

  try {
    await spawnCommand("open", [
      "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
    ]);
    return { success: true };
  } catch (error) {
    console.error("Failed to open Microphone settings:", error);
    return { success: false, error: "Failed to open Microphone settings" };
  }
}

export async function openFile(filePath: string): Promise<ActionResult> {
  await auth();

  try {
    await assertPathAllowedForOpen(filePath);
    const resolved = path.resolve(filePath);
    const stats = await fs.stat(resolved);
    if (!stats.isFile()) {
      return { success: false, error: "Path is not a file" };
    }

    await openInPreferredEditor(resolved);
    return { success: true };
  } catch (error) {
    console.error(`Failed to open file ${filePath}:`, error);
    return { success: false, error: "Failed to open file in editor" };
  }
}

export async function openFileInSystem(
  filePath: string,
): Promise<ActionResult> {
  await auth();

  try {
    await assertPathAllowedForOpen(filePath);
    const resolved = path.resolve(filePath);
    const stats = await fs.stat(resolved);
    if (!stats.isFile()) {
      return { success: false, error: "Path is not a file" };
    }

    await openWithSystemDefault(resolved);
    return { success: true };
  } catch (error) {
    console.error(`Failed to open file ${filePath}:`, error);
    return { success: false, error: "Failed to open file" };
  }
}

export async function openDirectoryInSystem(
  dirPath: string,
): Promise<ActionResult> {
  await auth();

  try {
    await assertPathAllowedForOpenDirectory(dirPath);
    const resolved = path.resolve(dirPath);
    const stats = await fs.stat(resolved);
    if (!stats.isDirectory()) {
      return { success: false, error: "Path is not a directory" };
    }

    await openWithSystemDefault(resolved);
    return { success: true };
  } catch (error) {
    console.error(`Failed to open directory ${dirPath}:`, error);
    return { success: false, error: "Failed to open directory" };
  }
}

export async function openVoiceMemoAudio(
  audioPath: string,
): Promise<ActionResult> {
  await auth();

  try {
    const resolved = path.resolve(audioPath);
    const indexPath = path.join(
      getSkillSubPath("apple", "voice-memos"),
      "index.yaml",
    );
    const raw = await fs.readFile(indexPath, "utf8");
    const data = yaml.parse(raw) as { items?: Array<{ audio_path?: string }> };
    const items = Array.isArray(data?.items) ? data.items : [];
    const matchesIndex = hasIndexedAudioPath(items, resolved);

    if (!matchesIndex) {
      return { success: false, error: "Audio file is not indexed" };
    }

    const stats = await fs.stat(resolved);
    if (!stats.isFile()) {
      return { success: false, error: "Audio file not found" };
    }

    await openWithSystemDefault(resolved);
    return { success: true };
  } catch (error) {
    console.error(`Failed to open audio file ${audioPath}:`, error);
    return { success: false, error: "Failed to open audio file" };
  }
}

export async function openVoiceMemosAudioFolder(): Promise<ActionResult> {
  await auth();

  const dirPath = path.join(getSkillSubPath("apple", "voice-memos"), "audio");
  try {
    await fs.mkdir(dirPath, { recursive: true });
  } catch {
    // Ignore mkdir errors and let open handle missing path.
  }
  return openDirectoryInSystem(dirPath);
}

export async function openVoiceMemosTranscriptsFolder(): Promise<ActionResult> {
  await auth();

  const dirPath = path.join(
    getSkillSubPath("apple", "voice-memos"),
    "transcripts",
  );
  try {
    await fs.mkdir(dirPath, { recursive: true });
  } catch {
    // Ignore mkdir errors and let open handle missing path.
  }
  return openDirectoryInSystem(dirPath);
}

export async function pickAudioFile(): Promise<PickFileResult> {
  if (process.platform !== "darwin") {
    return { success: false, error: "File picker is only available on macOS" };
  }

  await auth();

  try {
    const { stdout } = await runCommand("osascript", [
      "-e",
      'POSIX path of (choose file with prompt "Select audio file")',
    ]);
    const selected = stdout.trim();
    if (!selected) return { success: false, error: "No file selected" };
    return { success: true, path: selected };
  } catch (error) {
    const message = (error as Error).message || "Failed to open file picker";
    return { success: false, error: message };
  }
}

export async function deleteFile(filePath: string): Promise<ActionResult> {
  await auth();

  try {
    await assertPathAllowedForDelete(filePath);
    const resolved = path.resolve(filePath);
    const stats = await fs.stat(resolved);
    if (!stats.isFile()) {
      return { success: false, error: "Path is not a file" };
    }

    await fs.unlink(resolved);
    revalidatePath("/"); // Revalidate everything to be safe
    return { success: true };
  } catch (error) {
    console.error(`Failed to delete file ${filePath}:`, error);
    return { success: false, error: "Failed to delete file" };
  }
}

// NOTE: createInterviewProject and archiveBacklogJob were removed
// These functions are now plugin-provided via vertical-work/careers/api/

export async function openDirectory(dirPath: string): Promise<ActionResult> {
  await auth();

  try {
    await assertPathAllowedForOpenDirectory(dirPath);
    const resolved = path.resolve(dirPath);
    const stats = await fs.stat(resolved);
    if (!stats.isDirectory()) {
      return { success: false, error: "Path is not a directory" };
    }

    // Force system default for directories (Finder/Explorer) instead of Editor
    await openDirectoryInSystem(resolved);
    return { success: true };
  } catch (error) {
    console.error(`Failed to open directory ${dirPath}:`, error);
    return { success: false, error: "Failed to open directory" };
  }
}

export async function openRepoInEditor(): Promise<ActionResult> {
  await auth();

  try {
    // When running from apps/dashboard, repo root is two levels up.
    const repoRoot = AUGUR_ROOT;
    await openInPreferredEditor(repoRoot);
    return { success: true };
  } catch (error) {
    console.error("Failed to open repo in editor:", error);
    return { success: false, error: "Failed to open repo in editor" };
  }
}

export async function openWorkspaceFile(
  relativePath: string,
): Promise<ActionResult> {
  await auth();

  try {
    const raw = typeof relativePath === "string" ? relativePath.trim() : "";
    if (!raw) return { success: false, error: "Missing file path" };

    const cleaned = raw.replace(/^[.][\\/]/, "");
    if (!cleaned) return { success: false, error: "Invalid file path" };

    const repoRoot = getRepoRootForOpen();
    const candidates = [
      { root: repoRoot, fullPath: [repoRoot, cleaned].join(path.sep) },
      { root: AUGUR_ROOT, fullPath: [AUGUR_ROOT, cleaned].join(path.sep) },
    ];

    if (await tryOpenCandidateAt(candidates, 0)) {
      return { success: true };
    }

    return {
      success: false,
      error: "File not found in repo or data directory",
    };
  } catch (error) {
    console.error("Failed to open workspace file:", error);
    return { success: false, error: "Failed to open file in editor" };
  }
}

export async function openCollateral(subPath?: string): Promise<ActionResult> {
  await auth();

  // Historical name: keep action stable, but point it at the user data repo.
  const target = subPath ? path.join(AUGUR_ROOT, subPath) : AUGUR_ROOT;
  return openDirectory(target);
}

// NOTE: analyzeJob was removed - now plugin-provided via vertical-work/careers/api/
