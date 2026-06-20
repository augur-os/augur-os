/**
 * Unified CLI Runner for Augur
 *
 * Provides a single, consistent interface for running the Augur CLI command.
 * Extracted from duplicated code in mcp/capabilities, setup/skills/manager, and registry routes.
 */
import {
  runPythonScript,
  resolvePythonScriptPath,
  getAugurPythonPath,
} from "./pythonRunner";
import path from "path";

const CLI_SCRIPT = resolvePythonScriptPath("src/cli.py");
const AUGUR_ROOT = getAugurPythonPath();
// ADR-094: AUGUR_DATA_DIR eliminated — use AUGUR_ROOT directly

export interface CliRunnerOptions {
  /** Timeout in milliseconds (default: 30000) */
  timeout?: number;
  /** Whether to parse output as JSON (default: false for raw output) */
  parseJSON?: boolean;
  /** Additional environment variables */
  env?: Record<string, string>;
}

/**
 * Run the augur CLI with the given arguments.
 *
 * @param args - CLI arguments (e.g., ['list', '-j'] or ['-j', 'chains'])
 * @param options - Optional configuration
 * @returns Raw CLI output as string
 * @throws Error if CLI fails or produces no output
 *
 * @example
 * ```typescript
 * // Get skills list as JSON string
 * const output = await runAugurCli(['list', '-j']);
 * const data = JSON.parse(output);
 *
 * // Get chains with custom timeout
 * const chains = await runAugurCli(['-j', 'chains'], { timeout: 60000 });
 * ```
 */
async function runAugurCli(
  args: string[],
  options: CliRunnerOptions = {},
): Promise<string> {
  const { timeout = 30000, parseJSON = false, env = {} } = options;
  const pythonPath = [AUGUR_ROOT, `${AUGUR_ROOT}/src/mcp`, process.env.PYTHONPATH]
    .filter(Boolean)
    .join(path.delimiter);

  const result = await runPythonScript<any>(CLI_SCRIPT, {
    args,
    env: {
      PYTHONPATH: pythonPath,
      AUGUR_ROOT: AUGUR_ROOT,
      ...env,
    },
    cwd: AUGUR_ROOT,
    timeout,
    parseJSON,
  });

  if (!result.success) {
    throw new Error(result.error || `CLI failed for: ${args.join(" ")}`);
  }

  const output = (result.stdout || "").trim();
  if (!output) {
    throw new Error(`No output for: ${args.join(" ")}`);
  }

  return output;
}

/**
 * Run the augur CLI and parse output as JSON.
 *
 * @param args - CLI arguments
 * @param options - Optional configuration
 * @returns Parsed JSON response
 *
 * @example
 * ```typescript
 * interface SkillsResponse {
 *   skills: Array<{ name: string; description: string }>;
 * }
 *
 * const data = await runCliJSON<SkillsResponse>(['list', '-j']);
 * console.log(data.skills.length);
 * ```
 */
export async function runCliJSON<T>(
  args: string[],
  options: Omit<CliRunnerOptions, "parseJSON"> = {},
): Promise<T> {
  const output = await runAugurCli(args, options);
  return JSON.parse(output) as T;
}

/**
 * Run multiple CLI commands in parallel.
 *
 * @param commands - Array of CLI argument arrays
 * @returns Array of raw outputs in same order as commands
 *
 * @example
 * ```typescript
 * const [skillsRaw, chainsRaw, buttonsRaw] = await runCliParallel([
 *   ['-j', 'list'],
 *   ['-j', 'chains'],
 *   ['-j', 'buttons'],
 * ]);
 * ```
 */
async function runCliParallel(
  commands: string[][],
  options: CliRunnerOptions = {},
): Promise<string[]> {
  return Promise.all(commands.map((args) => runAugurCli(args, options)));
}

/**
 * Run multiple CLI commands in parallel and parse as JSON.
 *
 * @param commands - Array of CLI argument arrays
 * @returns Array of parsed JSON responses in same order as commands
 */
async function runCliJSONParallel<T extends any[]>(
  commands: string[][],
  options: Omit<CliRunnerOptions, "parseJSON"> = {},
): Promise<T> {
  const outputs = await runCliParallel(commands, options);
  return outputs.map((output) => JSON.parse(output)) as T;
}
