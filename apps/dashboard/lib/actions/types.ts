/**
 * Action types — ADR-130 v2
 *
 * Canonical ActionDef interface used across:
 *   - API routes (actions, registry)
 *   - Client hooks (useActionRunner, useItemActions)
 *   - Shared lib (actions/discovery)
 */

export type DispatchMode = "fire" | "oneshot" | "chat" | "ide" | "modal" | "api" | "auto";

export interface CompletionHint {
  type: "poll";
  url: string;
  field: string;
  done_value: string;
  interval_ms?: number;
  timeout_ms?: number;
}

export interface ActionDef {
  id: string;
  label: string;
  description: string;
  dispatch: DispatchMode;
  page: string;
  agents?: string[];
  args?: Record<string, unknown>;
  confirmation?: string;
  recommended_agent?: string;
  prompt?: string;
  prompt_file?: string;
  command?: string;
  icon?: string;
  script?: string;
  script_path?: string;
  requires_service?: string | string[];
  unavailable_label?: string;
  schedulable?: boolean;
  mcp_tools?: string[];
  completion_hint?: CompletionHint;
  next_action?: string;
  tier?: "fast" | "standard" | "deep";
  _plugin?: string;
}
