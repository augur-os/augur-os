import { spawn as nodeSpawn } from "child_process";
import fs from "fs";
import path from "path";

export interface NativeTerminalRequest {
  platform?: NodeJS.Platform;
  cwd: string;
  argv: string[];
  hasWindowsTerminal?: boolean;
}

export interface BuiltNativeTerminalCommand {
  command: string;
  args: string[];
  cwd: string;
}

interface LaunchDeps {
  spawn?: typeof nodeSpawn;
  commandExists?: (command: string) => Promise<boolean>;
}

function quotePosix(value: string): string {
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

function quotePowerShell(value: string): string {
  return `'${value.replace(/'/g, "''")}'`;
}

function appleScriptString(value: string): string {
  return JSON.stringify(value);
}

async function defaultCommandExists(command: string): Promise<boolean> {
  const pathEntries = (process.env.PATH || "").split(path.delimiter);
  const checks = await Promise.all(
    pathEntries.map(async (entry) => {
      const candidate = path.join(entry, command);
      try {
        await fs.promises.access(candidate, fs.constants.F_OK);
        return true;
      } catch {
        return false;
      }
    }),
  );
  return checks.some(Boolean);
}

export function buildNativeTerminalCommand(
  request: NativeTerminalRequest,
): BuiltNativeTerminalCommand {
  const platform = request.platform ?? process.platform;
  const isAbsoluteCwd =
    platform === "win32"
      ? path.win32.isAbsolute(request.cwd)
      : path.isAbsolute(request.cwd);
  if (!request.cwd || !isAbsoluteCwd) {
    throw new Error("Native terminal cwd must be absolute");
  }
  if (!Array.isArray(request.argv) || request.argv.length === 0) {
    throw new Error("Native terminal argv must be non-empty");
  }
  if (
    !request.argv.every(
      (entry): entry is string => typeof entry === "string" && entry.length > 0,
    )
  ) {
    throw new Error("Native terminal argv entries must be non-empty strings");
  }

  if (platform === "darwin") {
    const shellLine = `cd ${quotePosix(request.cwd)} && ${request.argv
      .map(quotePosix)
      .join(" ")}`;
    return {
      command: "osascript",
      args: [
        "-e",
        `tell application "Terminal" to do script ${appleScriptString(shellLine)}`,
        "-e",
        'tell application "Terminal" to activate',
      ],
      cwd: request.cwd,
    };
  }

  if (platform === "win32") {
    const powerShellLine = `Set-Location -LiteralPath ${quotePowerShell(
      request.cwd,
    )}; & ${request.argv.map(quotePowerShell).join(" ")}`;
    if (request.hasWindowsTerminal) {
      return {
        command: "wt.exe",
        args: [
          "-d",
          request.cwd,
          "powershell.exe",
          "-NoExit",
          "-Command",
          powerShellLine,
        ],
        cwd: request.cwd,
      };
    }
    return {
      command: "powershell.exe",
      args: ["-NoExit", "-Command", powerShellLine],
      cwd: request.cwd,
    };
  }

  throw new Error(`Native terminal handoff is not supported on ${platform}`);
}

export async function launchNativeTerminal(
  request: NativeTerminalRequest,
  deps: LaunchDeps = {},
): Promise<BuiltNativeTerminalCommand> {
  const platform = request.platform ?? process.platform;
  const commandExists = deps.commandExists ?? defaultCommandExists;
  const built = buildNativeTerminalCommand({
    ...request,
    platform,
    hasWindowsTerminal:
      platform === "win32"
        ? request.hasWindowsTerminal ?? (await commandExists("wt.exe"))
        : false,
  });
  const spawnImpl = deps.spawn ?? nodeSpawn;
  const child = spawnImpl(built.command, built.args, {
    cwd: built.cwd,
    detached: true,
    stdio: "ignore",
  });
  const launchTurn = new Promise<void>((resolve, reject) => {
    let settled = false;
    child.on("error", (error) => {
      if (!settled) {
        settled = true;
        reject(error);
      }
    });
    setImmediate(() => {
      if (!settled) {
        settled = true;
        resolve();
      }
    });
  });
  child.unref();
  await launchTurn;
  return built;
}
