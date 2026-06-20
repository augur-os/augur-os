/**
 * Python Script Runner Utility
 *
 * Standardized helper for running Python scripts from API routes.
 * Eliminates 20-30 lines of boilerplate per route.
 */

import { spawn } from "child_process";
import path from "path";
import { AUGUR_PYTHON, AUGUR_ROOT } from "../paths";

const MAX_OUTPUT = 5 * 1024 * 1024; // 5 MB cap for stdout/stderr accumulation

export type PythonRunnerOptions = {
  args?: string[];
  env?: Record<string, string>;
  cwd?: string;
  timeout?: number;
  parseJSON?: boolean;
};

export type PythonResult<T = any> = {
  success: boolean;
  data?: T;
  stdout?: string;
  error?: string;
};

/**
 * Run a Python script file and return results
 *
 * @example
 * const result = await runPythonScript('project-brain/capabilities/skills/career-ops/scripts/career_hardening.py');
 * if (result.success) {
 *   return NextResponse.json(result.data);
 * }
 */
export async function runPythonScript<T = any>(
  scriptPath: string,
  options: PythonRunnerOptions = {},
): Promise<PythonResult<T>> {
  const {
    args = [],
    env = {},
    cwd,
    timeout = 30000,
    parseJSON = true,
  } = options;

  return new Promise((resolve) => {
    const python = AUGUR_PYTHON;
    const proc = spawn(python, [scriptPath, ...args], {
      env: { ...process.env, ...env },
      cwd,
    });

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (data) => {
      if (stdout.length < MAX_OUTPUT) stdout += data.toString();
    });
    proc.stderr.on("data", (data) => {
      if (stderr.length < MAX_OUTPUT) stderr += data.toString();
    });

    const timer = setTimeout(() => {
      proc.kill();
      resolve({ success: false, error: "Script timed out" });
    }, timeout);

    proc.on("close", (code) => {
      clearTimeout(timer);

      if (code === 0) {
        if (parseJSON) {
          try {
            const data = JSON.parse(stdout.trim());
            resolve({ success: true, data });
          } catch (e) {
            const detail = e instanceof Error ? e.message : String(e);
            resolve({
              success: false,
              stdout,
              error: `Failed to parse JSON output: ${detail}`,
            });
          }
        } else {
          resolve({ success: true, stdout, data: stdout as T });
        }
      } else {
        resolve({
          success: false,
          error: stderr || `Process exited with code ${code}`,
        });
      }
    });

    proc.on("error", (err) => {
      clearTimeout(timer);
      resolve({ success: false, error: err.message });
    });
  });
}

/**
 * Run inline Python code and return results
 *
 * @example
 * const result = await runPythonCode(`
 *   import json
 *   print(json.dumps({"hello": "world"}))
 * `);
 */
async function runPythonCode<T = any>(
  code: string,
  options: Omit<PythonRunnerOptions, "args"> = {},
): Promise<PythonResult<T>> {
  const { env = {}, cwd, timeout = 30000, parseJSON = true } = options;

  return new Promise((resolve) => {
    const python = AUGUR_PYTHON;
    const proc = spawn(python, ["-c", code], {
      env: { ...process.env, ...env },
      cwd,
    });

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (data) => {
      if (stdout.length < MAX_OUTPUT) stdout += data.toString();
    });
    proc.stderr.on("data", (data) => {
      if (stderr.length < MAX_OUTPUT) stderr += data.toString();
    });

    const timer = setTimeout(() => {
      proc.kill();
      resolve({ success: false, error: "Script timed out" });
    }, timeout);

    proc.on("close", (code) => {
      clearTimeout(timer);

      if (code === 0) {
        if (parseJSON) {
          try {
            const data = JSON.parse(stdout.trim());
            resolve({ success: true, data });
          } catch (e) {
            const detail = e instanceof Error ? e.message : String(e);
            resolve({
              success: false,
              stdout,
              error: `Failed to parse JSON output: ${detail}`,
            });
          }
        } else {
          resolve({ success: true, stdout, data: stdout as T });
        }
      } else {
        resolve({
          success: false,
          error: stderr || `Process exited with code ${code}`,
        });
      }
    });

    proc.on("error", (err) => {
      clearTimeout(timer);
      resolve({ success: false, error: err.message });
    });
  });
}

/**
 * Resolve path to Python script within augur repo
 *
 * @example
 * const scriptPath = resolvePythonScriptPath('project-brain/capabilities/skills/career-ops/scripts/career_hardening.py');
 */
export function resolvePythonScriptPath(relativePath: string): string {
  return path.join(AUGUR_ROOT, relativePath);
}

/**
 * Get standard PYTHONPATH for augur scripts
 */
export function getAugurPythonPath(): string {
  return AUGUR_ROOT;
}
