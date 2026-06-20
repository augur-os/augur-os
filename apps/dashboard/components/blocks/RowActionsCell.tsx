"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { MoreVertical, Circle } from "lucide-react";
import { resolveIcon as resolveIconFromMap } from "@/lib/icon-map";
import type { RowAction } from "@/lib/blocks/types";
import { useActionRunner } from "@/hooks/useActionRunner";
import ConfirmDialog from "./ConfirmDialog";
import ActionFormModal from "./ActionFormModal";

function buildPayload(
  row: Record<string, unknown>,
  fields?: string[],
): Record<string, unknown> {
  if (!fields) return { ...row };
  const payload: Record<string, unknown> = {};
  for (const field of fields) {
    if (field in row) payload[field] = row[field];
  }
  return payload;
}

interface RowActionsCellProps {
  actions: RowAction[];
  row: Record<string, unknown>;
  mcpTool?: string;
}

interface ConfirmState {
  action: RowAction;
  payload: Record<string, unknown>;
}

function ActionButton({
  action,
  onAction,
}: {
  action: RowAction;
  onAction: (action: RowAction) => void;
}) {
  return (
    <button type="button"
      title={action.label}
      aria-label={action.label}
      onClick={(e) => {
        e.stopPropagation();
        onAction(action);
      }}
      className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded border-0 bg-transparent p-2 text-[var(--text-secondary)]"
    >
      {React.createElement(resolveIconFromMap(action.icon, Circle), { size: 16 })}
    </button>
  );
}

export default function RowActionsCell({
  actions,
  row,
  mcpTool,
}: RowActionsCellProps) {
  const { runAction } = useActionRunner();
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);
  const [formAction, setFormAction] = useState<{ action: RowAction; payload: Record<string, unknown> } | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close kebab menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    function handleMouseDown(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, [menuOpen]);

  const executeAction = useCallback(
    (action: RowAction, payload: Record<string, unknown>) => {
      if (action.dispatch === "navigate") {
        let href = action.href_template ?? "";
        for (const [key, value] of Object.entries(payload)) {
          href = href.replace(`{${key}}`, String(value));
        }
        window.location.href = href;
        return;
      }

      runAction({
        id: action.id,
        label: action.label,
        description: `${action.label} via row action`,
        dispatch:
          action.dispatch === "fire"
            ? "fire"
            : action.dispatch === "modal"
              ? "modal"
              : "ide",
        page: window.location.pathname,
        args: { ...(action.static_args ?? {}), ...payload },
        mcp_tools: action.mcp_tool
          ? [action.mcp_tool]
          : mcpTool
            ? [mcpTool]
            : undefined,
      });
    },
    [runAction, mcpTool],
  );

  const dispatchAction = useCallback(
    (action: RowAction) => {
      const payload = buildPayload(row, action.payload_fields);

      if (action.fields && action.fields.length > 0) {
        setFormAction({ action, payload });
        return;
      }

      if (action.confirm) {
        setConfirmState({ action, payload });
        return;
      }

      executeAction(action, payload);
    },
    [row, executeAction],
  );

  const handleConfirm = useCallback(() => {
    if (!confirmState) return;
    executeAction(confirmState.action, confirmState.payload);
    setConfirmState(null);
  }, [confirmState, executeAction]);

  const handleCancel = useCallback(() => {
    setConfirmState(null);
  }, []);

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          position: "relative",
        }}
      >
        {actions.length <= 2 ? (
          actions.map((action) => (
            <ActionButton
              key={action.id}
              action={action}
              onAction={dispatchAction}
            />
          ))
        ) : (
          <div ref={menuRef} className="relative">
            <button type="button"
              title="Actions"
              aria-label="More actions"
              aria-haspopup="true"
              aria-expanded={menuOpen}
              onClick={(e) => {
                e.stopPropagation();
                setMenuOpen((prev) => !prev);
              }}
              className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded border-0 bg-transparent p-2 text-[var(--text-secondary)]"
            >
              <MoreVertical size={16} />
            </button>
            {menuOpen && (
              <div
                className="absolute right-0 top-full z-[100] mt-1 min-w-40 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-1 shadow-[0_4px_12px_rgba(0,0,0,0.15)]"
              >
                {actions.map((action) => {
                  return (
                    <button type="button"
                      key={action.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuOpen(false);
                        dispatchAction(action);
                      }}
                      className="flex w-full cursor-pointer items-center gap-2 rounded border-0 bg-transparent px-3 py-2 text-left text-[13px] text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                    >
                      {React.createElement(resolveIconFromMap(action.icon, Circle), { size: 14 })}
                      {action.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirmState !== null}
        message={
          confirmState?.action.confirm_message ??
          `Are you sure you want to ${confirmState?.action.label.toLowerCase()}?`
        }
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />

      {formAction?.action.fields && (
        <ActionFormModal
          open={formAction !== null}
          onClose={() => setFormAction(null)}
          actionId={formAction.action.id}
          actionLabel={formAction.action.label}
          dispatch={formAction.action.dispatch === "navigate" ? "fire" : formAction.action.dispatch}
          fields={formAction.action.fields}
          staticArgs={formAction.payload}
          mcpTool={formAction.action.mcp_tool ?? mcpTool}
          confirmText={formAction.action.confirmText}
          refetch={formAction.action.refetch}
        />
      )}
    </>
  );
}
