"use client";

import { useState, useCallback } from "react";
import { Loader2, Zap } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { resolveIcon as resolveIconFromMap } from "@/lib/icon-map";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { useActionRunner } from "@/hooks/useActionRunner";
import { BlockShell } from "../BlockShell";
import ActionFormModal from "../ActionFormModal";
import type { DispatchMode } from "@/lib/actions/types";
import type { FormField } from "@/lib/plugin-schema/types";

function resolveIcon(name?: string): React.ElementType {
  return resolveIconFromMap(name, Zap);
}

interface ConfigAction {
  id: string;
  label: string;
  icon?: string;
  dispatch?: DispatchMode;
  mcp_tool?: string;
  fields?: FormField[];
  confirmText?: string;
  refetch?: string[];
}

interface ActionBarConfig {
  title?: string;
  /** Config-declared actions (from YAML) — takes precedence over MCP data */
  actions?: ConfigAction[];
}

interface ActionItem {
  id?: string;
  label: string;
  action?: string;
}

export default function ActionBarBlock(props: BlockProps<ActionBarConfig>) {
  const { config, dataSource, mode, onExpand } = props;
  const { title = "Actions" } = config;
  const { runAction, isExecuting, lastActionId, result } = useActionRunner();
  const queryClient = useQueryClient();

  // MCP-fetched actions (secondary source)
  const selfFetched = useBlockData<ActionItem[]>(dataSource, config, "action-bar");
  const fetchedData = (props.data as ActionItem[] | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  // Config-declared actions take precedence
  const configActions = config.actions ?? [];
  const mcpActions: ConfigAction[] = Array.isArray(fetchedData)
    ? fetchedData.map((a) => ({
        id: a.id ?? a.action ?? a.label,
        label: a.label,
        dispatch: "ide",
      }))
    : [];
  const actions = configActions.length > 0 ? configActions : mcpActions;

  // Form modal state
  const [formAction, setFormAction] = useState<ConfigAction | null>(null);

  const handleClick = useCallback(
    async (action: ConfigAction) => {
      if (action.fields && action.fields.length > 0) {
        setFormAction(action);
        return;
      }
      const ok = await runAction({
        id: action.id,
        label: action.label,
        description: action.label,
        dispatch: action.dispatch ?? "ide",
        page: typeof window !== "undefined" ? window.location.pathname : "",
        mcp_tools: action.mcp_tool ? [action.mcp_tool] : undefined,
      });
      if (ok) {
        queryClient.invalidateQueries({ queryKey: ["block-data"] });
      }
    },
    [queryClient, runAction],
  );

  return (
    <BlockShell title={title} icon={Zap} color="amber" onExpand={onExpand} staleError={error}>
      <div className="p-4 flex flex-wrap gap-2">
        {loading &&
          Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="h-8 w-20 rounded-lg bg-[var(--bg-hover)] animate-pulse" />
          ))}

        {!loading && actions.length === 0 && !error && (
          <p className="text-xs text-[var(--text-muted)] italic">No actions available</p>
        )}
        {!loading && actions.length === 0 && error && (
          <div className="text-center py-6">
            <p className="text-xs text-red-400/80">Failed to load data</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        )}
        {!loading &&
          actions.map((action, i) => {
            const Icon = resolveIcon(action.icon);
            return (
              <button type="button"
                key={action.id || i}
                className="flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border-color)]/30 bg-[var(--bg-hover)] px-3 py-2 text-xs font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)]/80 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={isExecuting}
                onClick={() => handleClick(action)}
              >
                {isExecuting && lastActionId === action.id ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <Icon className="size-3.5" aria-hidden="true" />
                )}
                {isExecuting && lastActionId === action.id ? "Running..." : action.label}
              </button>
            );
          })}
        {result && (
          <div
            role={result.type === "error" ? "alert" : "status"}
            className={`min-h-[44px] rounded-lg border px-3 py-2 text-xs ${
              result.type === "error"
                ? "border-[var(--accent-danger)]/30 text-[var(--accent-danger)]"
                : "border-[var(--accent-success)]/30 text-[var(--accent-success)]"
            }`}
          >
            {result.message}
          </div>
        )}
      </div>

      {formAction?.fields && (
        <ActionFormModal
          open={formAction !== null}
          onClose={() => setFormAction(null)}
          actionId={formAction.id}
          actionLabel={formAction.label}
          dispatch={(formAction.dispatch ?? "fire")}
          fields={formAction.fields}
          mcpTool={formAction.mcp_tool}
          confirmText={formAction.confirmText}
          refetch={formAction.refetch}
        />
      )}
    </BlockShell>
  );
}
