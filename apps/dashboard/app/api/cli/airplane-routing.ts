import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";

import { isNonEmptyString, resolveConfigKey } from "./cli-config";

/**
 * Auto-approve flags stripped from the original agent argv when airplane mode
 * routes the CLI through `ollama launch`.
 */
const AUTO_APPROVE_FLAGS = new Set([
  "--dangerously-skip-permissions",
  "--dangerously-bypass-approvals-and-sandbox",
  "--full-auto",
  "--yolo",
  "--force",
  "--approve-mcps",
]);

type AirplaneModeStatus = {
  airplane_mode?: {
    enabled?: boolean;
  };
};

export type AirplaneLaunchOverrides = {
  ready?: boolean;
  error?: string;
  setup_hint?: string;
  reason?: string;
  launch_argv?: unknown;
  model?: string;
};

export type AirplaneUnavailablePayload = {
  error: string;
  setup_hint: string;
  reason: string;
};

function resolveAirplaneIntegrationId(cliId: string): string {
  const configKey = resolveConfigKey(cliId);
  return configKey === "copilot-cli" ? "copilot" : configKey;
}

async function callMcpJson<T>(
  tool: string,
  args: Record<string, unknown>,
): Promise<T> {
  const result = await callMCPTool(tool, args, {});
  if (result.isError) {
    throw new Error(
      MCPBridge.extractText(result) || `MCP tool failed: ${tool}`,
    );
  }
  const raw = MCPBridge.extractText(result).trim();
  return raw ? (JSON.parse(raw) as T) : ({} as T);
}

export async function readCanonicalAirplaneMode(): Promise<boolean> {
  const status = await callMcpJson<AirplaneModeStatus>(
    "toggle-airplane-mode",
    { action: "status" },
  );
  return status.airplane_mode?.enabled === true;
}

export async function readAirplaneLaunchOverrides(
  cliId: string,
): Promise<AirplaneLaunchOverrides> {
  return callMcpJson<AirplaneLaunchOverrides>(
    "get-airplane-launch-overrides",
    { agent_id: resolveAirplaneIntegrationId(cliId) },
  );
}

export function airplaneUnavailablePayload(
  overrides: AirplaneLaunchOverrides | undefined,
): AirplaneUnavailablePayload {
  return {
    error: overrides?.error || "Airplane launch override is not ready",
    setup_hint:
      overrides?.setup_hint || "Check local backend setup and try again.",
    reason: overrides?.reason || "not_ready",
  };
}

function stripAutoApproveFlags(args: string[]): string[] {
  return args.filter((arg) => !AUTO_APPROVE_FLAGS.has(arg));
}

function requireLaunchArgv(value: unknown): string[] {
  if (
    !Array.isArray(value) ||
    value.length === 0 ||
    value.some((arg) => !isNonEmptyString(arg))
  ) {
    throw new Error("Airplane launch override did not provide launch_argv");
  }
  return value as string[];
}

export function applyAirplaneLaunchOverride(
  command: string,
  args: string[],
  overrides?: AirplaneLaunchOverrides,
): { command: string; args: string[] } {
  if (!overrides) {
    return { command, args };
  }

  const launchArgv = requireLaunchArgv(overrides.launch_argv);
  const ollamaBin = launchArgv[0];

  // Direct-ollama bypass: `ollama launch <cli>` wraps the agent CLI
  // (claude/codex), whose heavy request (large system prompt + 100+ tool
  // definitions) crashes the ollama model runner on constrained local hardware
  // (e.g. a 2GB iGPU) — the runner returns 500 and the CLI retries 11x, so
  // offline chat appears to hang. When the override names a local model, run it
  // directly with `ollama run <model>` — a lightweight chat the model can
  // actually serve — and reuse the existing PTY chat surface. Agent argv is
  // intentionally dropped; `ollama run` reads prompts from stdin.
  const directModel = overrides.model?.trim();
  if (directModel) {
    return { command: ollamaBin, args: ["run", directModel] };
  }

  return {
    command: ollamaBin,
    args: [...launchArgv.slice(1), ...stripAutoApproveFlags(args)],
  };
}
