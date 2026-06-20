/**
 * Command Runner Utilities
 *
 * Provides runCommand and runJsonCommand for running arbitrary CLI commands.
 * This module was recreated after the original was deprecated - these functions
 * are needed by several API routes that run non-Python commands.
 */

import { spawn, SpawnOptions } from "child_process";

export interface CommandOptions {
  cwd?: string;
  env?: NodeJS.ProcessEnv;
  timeout?: number;
}

export interface CommandResult {
  stdout: string;
  stderr: string;
  exitCode: number | null;
}

/**
 * Run a command and return its output.
 *
 * @param command - The command to run
 * @param args - Arguments to pass to the command
 * @param options - Optional configuration
 * @returns Promise with stdout, stderr, and exit code
 *
 * @example
 * ```typescript
 * const { stdout } = await runCommand('osascript', ['-e', 'POSIX path of (choose file)']);
 * ```
 */
export async function runCommand(
  command: string,
  args: string[],
  options: CommandOptions = {},
): Promise<CommandResult> {
  const { cwd, env, timeout = 30000 } = options;

  return new Promise((resolve, reject) => {
    const spawnOptions: SpawnOptions = {
      cwd,
      env: env || process.env,
      stdio: ["ignore", "pipe", "pipe"],
    };

    const proc = spawn(command, args, spawnOptions);

    const MAX_OUTPUT = 5 * 1024 * 1024; // 5MB
    let stdout = "";
    let stderr = "";

    proc.stdout?.setEncoding("utf8");
    proc.stderr?.setEncoding("utf8");
    proc.stdout?.on("data", (chunk) => {
      if (stdout.length < MAX_OUTPUT) stdout += chunk;
    });
    proc.stderr?.on("data", (chunk) => {
      if (stderr.length < MAX_OUTPUT) stderr += chunk;
    });

    const timer = setTimeout(() => {
      proc.kill();
      reject(new Error(`Command timed out after ${timeout}ms`));
    }, timeout);

    proc.on("close", (code) => {
      clearTimeout(timer);
      resolve({ stdout, stderr, exitCode: code });
    });

    proc.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
  });
}

/**
 * Run a command and parse the output as JSON.
 *
 * @param command - The command to run
 * @param args - Arguments to pass to the command
 * @param options - Optional configuration
 * @returns Parsed JSON output
 *
 * @example
 * ```typescript
 * const data = await runJsonCommand('python3', ['script.py', '--json']);
 * ```
 */
export async function runJsonCommand<T = unknown>(
  command: string,
  args: string[],
  options: CommandOptions = {},
): Promise<T> {
  const result = await runCommand(command, args, options);

  if (result.exitCode !== 0) {
    throw new Error(
      result.stderr || `Command failed with exit code ${result.exitCode}`,
    );
  }

  const output = result.stdout.trim();
  if (!output) {
    throw new Error("No output from command");
  }

  return JSON.parse(output) as T;
}
