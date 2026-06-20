import { useState, type Dispatch, type SetStateAction } from "react";
import { toast } from "sonner";
import { useChatStore, type ChatState } from "@/lib/stores/chatStore";
import { trackAction } from "@/hooks/useUsageTracking";
import type { ActionDef, CompletionHint } from "@/lib/actions/types";
import {
  normalizeDispatchMode,
  resolveAutoDispatchMode,
} from "@/lib/actions/dispatch-mode";
import type {
  PreparedActionDispatch,
  PreparedActionDraft,
} from "@/lib/actions/preparedActionDraft";
import {
  resolveContext,
  buildPromptFromEnvelope,
  type ContextEnvelope,
} from "@/lib/chat/context-envelope";
import { mcpCall } from "@/lib/mcp/client";

export type { ActionDef };

interface ActionRunnerState {
  isExecuting: boolean;
  result: { type: "success" | "error"; message: string } | null;
  completionHint: CompletionHint | null;
  lastActionId: string | null;
}

/**
 * ADR-460: Resolve the agent tier for an action.
 * Explicit tier from action config takes priority, otherwise
 * keyword-based static routing determines the tier.
 */
function resolveTier(action: ActionDef): "fast" | "standard" | "deep" {
  if (action.tier) return action.tier;

  const signals = [action.id, action.label, action.description || ""]
    .join(" ")
    .toLowerCase();
  if (/quick.?check|lookup|search|status/.test(signals)) return "fast";
  if (/refactor|architect|debug.?complex|security|audit/.test(signals))
    return "deep";
  return "standard";
}

function shouldProceedWithConfirmation(action: ActionDef): boolean {
  if (!action.confirmation) return true;
  return window.confirm(action.confirmation);
}

function shouldProceedWithConcurrency(chatStore: ChatState): boolean {
  if (!(chatStore.isOpen && chatStore.isWaiting)) return true;
  return window.confirm(
    "An action is currently waiting for the IDE. Cancel it and start this new action?",
  );
}

function nowMs(): number {
  return Date.now();
}

/**
 * ADR-460: Best-effort write to the performance ledger after task completion.
 */
async function recordTaskCompletion(
  agent: string,
  tier: string,
  outcome: "success" | "failure" | "timeout",
  durationMs: number,
) {
  try {
    await mcpCall("set-config", {
      scope: "agent-telemetry-record",
      agent,
      tier,
      outcome,
      duration_seconds: durationMs / 1000,
    });
  } catch {
    /* best-effort -- don't block action on ledger write */
  }
}

async function runFire(
  action: ActionDef,
  setState: Dispatch<SetStateAction<ActionRunnerState>>,
): Promise<boolean> {
  const toastId = toast.loading(`Running ${action.label}...`);
  const pageContext =
    typeof window !== "undefined" ? window.location.pathname : action.page;

  // ADR-161: Resolve context with minimal budget for fire dispatch
  let hub: string | undefined;
  let skill: string | null | undefined;
  try {
    const envelope = await resolveContext(pageContext, "minimal");
    hub = envelope.hub;
    skill = envelope.skill;
  } catch {
    // Fallback: derive hub from page path
    hub = pageContext.split("/").filter(Boolean)[0];
  }

  // A fire action must declare an mcp_tool (ADR-807). There is no longer a
  // script-lookup fallback (execute-fast-action was retired).
  const mcpTool = action.mcp_tools?.[0];
  if (!mcpTool) {
    const msg = "fire action requires an mcp_tool";
    toast.error(`Action failed: ${msg}`, { id: toastId });
    setState((prev) => ({
      ...prev,
      isExecuting: false,
      result: { type: "error", message: msg },
    }));
    return false;
  }

  try {
    const data = await mcpCall<{ success?: boolean; error?: string; details?: string; message?: string }>(mcpTool, {
      ...(action.args as Record<string, unknown> | undefined),
      context: {
        page: pageContext,
        hub,
        skill,
        tier: resolveTier(action),
      },
    });

    if (!data.success) {
      throw new Error(data.error || data.details || "Action failed");
    }

    trackAction(action.id);
    toast.success(data.message || `${action.label} completed`, { id: toastId });
    setState((prev) => ({
      ...prev,
      isExecuting: false,
      result: { type: "success", message: data.message || action.label },
    }));
    return true;
  } catch (error) {
    const msg = error instanceof Error ? error.message : "Unknown error";
    toast.error(`Action failed: ${msg}`, { id: toastId });
    setState((prev) => ({
      ...prev,
      isExecuting: false,
      result: { type: "error", message: msg },
    }));
    return false;
  }
}

function buildPrompt(action: ActionDef): string {
  if (action.prompt) return action.prompt;
  if (action.command) {
    return `Run the slash command: ${action.command}`;
  }
  return `**Action Request**: ${action.label}

## Context
- **Description**: ${action.description}
- **Page**: ${action.page}
- **Agents**: ${action.agents?.join(", ") || "Default"}

Please execute this request interactively.`;
}

function openPreparedActionDraft(
  action: ActionDef,
  dispatch: PreparedActionDispatch,
  prompt: string,
  tier: "fast" | "standard" | "deep",
  chatStore: ChatState,
  setState: Dispatch<SetStateAction<ActionRunnerState>>,
): boolean {
  const preparedDraft: PreparedActionDraft = {
    id: action.id,
    label: action.label,
    description: action.description,
    prompt,
    page: action.page,
    tier,
    dispatch,
    recommendedAgent: action.recommended_agent,
    createdAt: new Date().toISOString(),
  };

  trackAction(action.id);
  chatStore.openChatWithPreparedActionDraft(preparedDraft, {
    page: action.page,
    actionId: action.id,
    actionName: action.label,
    skill: action._plugin,
  });
  if (!chatStore.isEnlarged) {
    chatStore.toggleEnlarged();
  }
  setState((prev) => ({ ...prev, isExecuting: false, result: null }));
  return true;
}

async function runOneshot(
  action: ActionDef,
  chatStore: ChatState,
  setState: Dispatch<SetStateAction<ActionRunnerState>>,
): Promise<boolean> {
  const pageContext =
    typeof window !== "undefined" ? window.location.pathname : action.page;

  // ADR-161: Resolve context with minimal budget for oneshot
  const actionPrompt = buildPrompt(action);
  let envelope: ContextEnvelope | null = null;
  try {
    envelope = await resolveContext(pageContext, "minimal", {
      id: action.id,
      label: action.label,
      description: action.description || "",
      prompt: actionPrompt,
    });
  } catch {
    // Fallback: use legacy prompt if resolve-context fails
  }

  const prompt = envelope ? buildPromptFromEnvelope(envelope) : actionPrompt;
  return openPreparedActionDraft(
    action,
    "oneshot",
    prompt,
    resolveTier(action),
    chatStore,
    setState,
  );
}

async function runChat(
  action: ActionDef,
  chatStore: ChatState,
  setState: Dispatch<SetStateAction<ActionRunnerState>>,
): Promise<boolean> {
  const pageContext =
    typeof window !== "undefined" ? window.location.pathname : action.page;

  // ADR-161: Resolve context with standard budget for chat sessions
  const actionPrompt = buildPrompt(action);
  let envelope: ContextEnvelope | null = null;
  try {
    envelope = await resolveContext(pageContext, "standard", {
      id: action.id,
      label: action.label,
      description: action.description || "",
      prompt: actionPrompt,
    });
  } catch {
    // Fallback to legacy flow
  }

  const tier = resolveTier(action);
  const prompt = envelope ? buildPromptFromEnvelope(envelope) : actionPrompt;

  return openPreparedActionDraft(
    action,
    "chat",
    prompt,
    tier,
    chatStore,
    setState,
  );
}

async function runIde(
  action: ActionDef,
  chatStore: ChatState,
  setState: Dispatch<SetStateAction<ActionRunnerState>>,
): Promise<boolean> {
  const pageContext =
    typeof window !== "undefined" ? window.location.pathname : action.page;

  // ADR-161: Resolve context with rich budget for IDE dispatch
  const actionPrompt = buildPrompt(action);
  let envelope: ContextEnvelope | null = null;
  try {
    envelope = await resolveContext(pageContext, "rich", {
      id: action.id,
      label: action.label,
      description: action.description || "",
      prompt: actionPrompt,
    });
  } catch {
    // Fallback to legacy prompt
  }

  const tier = resolveTier(action);
  const prompt = envelope
    ? `[Tier: ${tier}]\n${buildPromptFromEnvelope(envelope)}`
    : `[Tier: ${tier}]\n${actionPrompt}`;

  return openPreparedActionDraft(
    action,
    "ide",
    prompt,
    tier,
    chatStore,
    setState,
  );
}

/**
 * ADR-020 cleanup: resolve auto dispatch without the retired /api/llm path.
 * Prefers IDE when one is connected, otherwise falls back to oneshot CLI.
 */
async function resolveAutoMode(): Promise<"ide" | "oneshot"> {
  let hasIde = false;
  try {
    const ideData = await mcpCall("get-ide-status", {}) as {
      active_ide?: string;
      available_ides?: Array<{ name: string; status: string }>;
    };
    const ideCount = ideData.available_ides?.length ?? (ideData.active_ide ? 1 : 0);
    hasIde = ideCount > 0;
  } catch {
    // IDE detection unavailable
  }
  return resolveAutoDispatchMode({ hasIde });
}

export function useActionRunner() {
  const [state, setState] = useState<ActionRunnerState>({
    isExecuting: false,
    result: null,
    completionHint: null,
    lastActionId: null,
  });

  const chatStore = useChatStore();

  const runAction = async (action: ActionDef): Promise<boolean> => {
    if (!shouldProceedWithConfirmation(action)) return false;
    if (!shouldProceedWithConcurrency(chatStore)) return false;

    setState({
      isExecuting: true,
      result: null,
      completionHint: null,
      lastActionId: action.id,
    });

    // ADR-460: Track dispatch timing for performance ledger
    const tier = resolveTier(action);
    const agent = action.recommended_agent || action.agents?.[0] || "unknown";
    const startMs = nowMs();

    try {
      let ok = true;
      const dispatch = normalizeDispatchMode(action.dispatch);
      switch (dispatch) {
        case "fire":
          ok = await runFire(action, setState);
          recordTaskCompletion(agent, tier, ok ? "success" : "failure", nowMs() - startMs);
          return ok;
        case "oneshot":
          ok = await runOneshot(action, chatStore, setState);
          recordTaskCompletion(agent, tier, ok ? "success" : "failure", nowMs() - startMs);
          return ok;
        case "chat":
          ok = await runChat(action, chatStore, setState);
          recordTaskCompletion(agent, tier, ok ? "success" : "failure", nowMs() - startMs);
          return ok;
        case "ide":
          ok = await runIde(action, chatStore, setState);
          if (action.completion_hint) {
            setState((prev) => ({
              ...prev,
              completionHint: action.completion_hint ?? null,
            }));
          }
          recordTaskCompletion(agent, tier, ok ? "success" : "failure", nowMs() - startMs);
          return ok;
        case "modal":
          // modal dispatch is handled by component-level modal state
          setState((prev) => ({ ...prev, isExecuting: false, result: null }));
          return true;
        case "auto": {
          const resolved = await resolveAutoMode();
          return await runAction({ ...action, dispatch: resolved });
        }
      }
    } catch (err) {
      console.error("Action Runner Error:", err);
      recordTaskCompletion(agent, tier, "failure", nowMs() - startMs);
      setState((prev) => ({
        ...prev,
        isExecuting: false,
        result: { type: "error", message: "Internal error" },
      }));
      toast.error("Internal action runner error");
      return false;
    }
    return false;
  };

  return {
    runAction,
    isExecuting: state.isExecuting,
    result: state.result,
    completionHint: state.completionHint,
    lastActionId: state.lastActionId,
    clearResult: () =>
      setState((prev) => ({ ...prev, result: null, completionHint: null })),
  };
}
