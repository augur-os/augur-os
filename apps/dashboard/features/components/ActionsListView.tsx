"use client";

import { usePathname, useSearchParams } from "next/navigation";
import React, { Suspense } from "react";
import { Sparkles, Zap, ArrowLeft } from "lucide-react";
import { usePageActionsData } from "@/features/hooks/usePageActionsData";
import { useActionRunner, type ActionDef } from "@/hooks/useActionRunner";

interface ActionsListViewProps {
  /** Called when user wants to go back to terminal view */
  onBack: () => void;
}

type ActionDispatch = "ai" | "fire";

function resolveActionDispatch(button: ActionDef): ActionDispatch {
  return button.dispatch === "fire" ? "fire" : "ai";
}

function filterButtonsByDispatch(
  buttons: ActionDef[],
  dispatch: ActionDispatch,
): ActionDef[] {
  return buttons.filter((button) => resolveActionDispatch(button) === dispatch);
}

type SearchParamsReader = Pick<URLSearchParams, "get">;

function readSearchParam(searchParams: SearchParamsReader, name: string): string | null {
  return searchParams.get(name);
}

function ActionSection({
  title,
  titleClass,
  Icon,
  buttons,
  runAction,
}: {
  title: string;
  titleClass: string;
  Icon: typeof Sparkles;
  buttons: ActionDef[];
  runAction: (action: ActionDef) => void;
}): React.JSX.Element {
  return (
    <div>
      <div
        className={`px-2 py-1.5 text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 ${titleClass}`}
      >
        <Icon className="size-3" />
        {title}
        <span className="ml-auto text-[var(--text-muted)]">
          {buttons.length}
        </span>
      </div>
      {buttons.map((action) => (
        <button type="button"
          key={action.id}
          onClick={() => runAction(action)}
          className="w-full text-left px-3 py-2.5 rounded-lg hover:bg-[var(--bg-secondary)] transition-colors group flex items-start gap-3"
        >
          <Icon
            className={`size-4 mt-0.5 shrink-0 transition-colors ${title === "AI Actions" ? "text-purple-400/70 group-hover:text-purple-400" : "text-emerald-400/70 group-hover:text-emerald-400"}`}
          />
          <div className="min-w-0">
            <div
              className={`text-sm font-medium text-[var(--text-primary)] transition-colors ${title === "AI Actions" ? "group-hover:text-purple-300" : "group-hover:text-emerald-300"}`}
            >
              {action.label}
            </div>
            {action.description && (
              <div className="text-xs text-[var(--text-muted)] mt-0.5 line-clamp-2 leading-relaxed">
                {action.description}
              </div>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}

function ActionsBody({
  loading,
  llmButtons,
  fastButtons,
  runAction,
}: {
  loading: boolean;
  llmButtons: ActionDef[];
  fastButtons: ActionDef[];
  runAction: (action: ActionDef) => void;
}): React.JSX.Element {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-[var(--text-muted)]">
        Loading actions…
      </div>
    );
  }

  if (llmButtons.length === 0 && fastButtons.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <Sparkles className="size-8 text-[var(--text-muted)] mb-2 opacity-50" />
        <p className="text-sm text-[var(--text-muted)]">
          No actions available for this page
        </p>
      </div>
    );
  }

  return (
    <>
      {llmButtons.length > 0 && (
        <ActionSection
          title="AI Actions"
          titleClass="text-purple-400"
          Icon={Sparkles}
          buttons={llmButtons}
          runAction={runAction}
        />
      )}
      {fastButtons.length > 0 && (
        <div
          className={
            llmButtons.length > 0
              ? "mt-2 pt-2 border-t border-[var(--border-color)]"
              : ""
          }
        >
          <ActionSection
            title="Quick Actions"
            titleClass="text-emerald-400"
            Icon={Zap}
            buttons={fastButtons}
            runAction={runAction}
          />
        </div>
      )}
    </>
  );
}

/**
 * Actions list panel rendered inside FloatingChat (ADR-036).
 *
 * Shows available actions for the current page. Clicking an action delegates to
 * the current prepared-draft or direct-dispatch action runner.
 */
export default function ActionsListView(props: ActionsListViewProps) {
  return (
    <Suspense fallback={null}>
      <ActionsListViewInner {...props} />
    </Suspense>
  );
}

function ActionsListViewInner({ onBack }: ActionsListViewProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentTab = readSearchParam(searchParams, "tab");

  const { buttons, loading } = usePageActionsData({ pathname, currentTab });
  const { runAction } = useActionRunner();

  const llmButtons = filterButtonsByDispatch(buttons, "ai");
  const fastButtons = filterButtonsByDispatch(buttons, "fire");

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border-color)] bg-[var(--bg-secondary)]">
        <div className="flex items-center gap-2">
          <button type="button"
            onClick={onBack}
            className="p-1 rounded-md hover:bg-[var(--bg-primary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            title="Back to terminal"
            aria-label="Back to terminal"
          >
            <ArrowLeft className="size-4" />
          </button>
          <Sparkles className="size-4 text-purple-400" />
          <span className="text-sm font-semibold text-[var(--text-primary)]">
            Available Actions
          </span>
          {pathname && pathname !== "/" && (
            <span className="ml-auto text-[10px] text-[var(--text-muted)] font-mono">
              {pathname}
            </span>
          )}
        </div>
      </div>

      {/* Action list */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-1 custom-scrollbar">
        <ActionsBody
          loading={loading}
          llmButtons={llmButtons}
          fastButtons={fastButtons}
          runAction={runAction}
        />
      </div>
    </div>
  );
}
