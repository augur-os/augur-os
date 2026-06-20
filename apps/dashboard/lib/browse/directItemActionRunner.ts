import {
  resolveDirectItemActionArgs,
  type AiItemActionItem,
  type DirectItemAction,
} from "./itemActions";

export type DirectItemActionStatus = "success" | "cancelled" | "error";

export interface DirectItemActionResult {
  status: DirectItemActionStatus;
  result?: unknown;
  error?: Error;
}

export interface DirectItemActionRunner {
  callTool: (tool: string, args: Record<string, string>) => Promise<unknown>;
  confirm?: (message: string) => boolean;
  invalidate?: (queryKey: string) => void | Promise<void>;
  onLoading?: (message: string) => string | number;
  onSuccess?: (message: string, loadingId?: string | number) => void;
  onError?: (message: string, loadingId?: string | number) => void;
}

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "Direct item action failed");
}

function responseError(response: unknown): Error | null {
  if (!response || typeof response !== "object") return null;
  const record = response as {
    success?: unknown;
    error?: unknown;
    message?: unknown;
    needs_llm?: unknown;
    task?: unknown;
    submit_tool?: unknown;
  };
  if (record.needs_llm === true) {
    const task = typeof record.task === "string" && record.task.trim() ? record.task : "This action";
    const submitTool =
      typeof record.submit_tool === "string" && record.submit_tool.trim()
        ? ` via ${record.submit_tool}`
        : "";
    return new Error(`${task} requires AI handoff${submitTool}; it was not completed as a direct action.`);
  }
  if (record.success !== false) return null;
  if (typeof record.error === "string" && record.error.trim()) return new Error(record.error);
  if (typeof record.message === "string" && record.message.trim()) return new Error(record.message);
  return new Error("Direct item action failed");
}

export async function runDirectItemAction(
  action: DirectItemAction,
  item: AiItemActionItem,
  runner: DirectItemActionRunner,
): Promise<DirectItemActionResult> {
  if (!action.tool) {
    const error = new Error(`Direct item action ${action.id} does not declare an MCP tool.`);
    runner.onError?.(error.message);
    return { status: "error", error };
  }

  if (action.confirm) {
    const confirmed = runner.confirm?.(`Run ${action.label} for ${item.title}?`) ?? true;
    if (!confirmed) return { status: "cancelled" };
  }

  const loadingId = runner.onLoading?.(`Running ${action.label}...`);

  try {
    const result = await runner.callTool(action.tool, resolveDirectItemActionArgs(action, item));
    const error = responseError(result);
    if (error) throw error;

    await Promise.all(
      (action.invalidates ?? []).map((key) => runner.invalidate?.(key)),
    );

    runner.onSuccess?.(`${action.label} completed`, loadingId);
    return { status: "success", result };
  } catch (error) {
    const normalized = toError(error);
    runner.onError?.(`${action.label} failed: ${normalized.message}`, loadingId);
    return { status: "error", error: normalized };
  }
}
