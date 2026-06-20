"use client";

import type { ReactNode } from "react";
import { useEffect, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import type { BrowseItem, CapabilityPolicyDraft } from "@/lib/browse/types";
import { useCapabilityPolicy } from "@/lib/browse/useCapabilityPolicy";
import {
  capabilityMetadataList,
  capabilityMetadataValue,
} from "@/lib/browse/capabilityMetadata";
import { CapabilityDriftBadge } from "@/features/browse/CapabilityDriftBadge";

interface CapabilityPolicyPanelProps {
  item: BrowseItem;
  onClose: () => void;
  onApplied: () => void;
}

const AI_CLIENTS = [
  { id: "claude", label: "Claude" },
  { id: "codex", label: "Codex" },
  { id: "gemini", label: "Gemini" },
  { id: "opencode", label: "OpenCode" },
] as const;

const EXPOSURE_AI_CLIENTS = [
  ...AI_CLIENTS,
  { id: "cursor", label: "Cursor" },
  { id: "copilot", label: "Copilot" },
] as const;

const CLI_PRIMARY_SURFACES = new Set(["mcp", "command", "workflow", "cli"]);

interface CapabilityPolicyAction {
  id: string;
  label: string;
  action: string;
  params: Record<string, unknown>;
  disabled?: boolean;
  tone?: "primary" | "secondary";
}

function buildPolicyActions(
  metadata: BrowseItem["metadata"],
  currentExposure: string[],
): CapabilityPolicyAction[] {
  const actions: CapabilityPolicyAction[] = [];
  const exposureSet = new Set(currentExposure.map((client) => client.toLowerCase()));
  const exposedAiClients = EXPOSURE_AI_CLIENTS.filter((client) => exposureSet.has(client.id));
  const nonAiExposure = currentExposure.filter((surface) => {
    const normalized = surface.toLowerCase();
    return !EXPOSURE_AI_CLIENTS.some((client) => client.id === normalized);
  });
  const management = capabilityMetadataValue(metadata, "management");
  const shouldOfferAiPlacement =
    metadata?.primarySurface === "skill" || exposedAiClients.length > 0;

  const addAction = (action: CapabilityPolicyAction) => {
    if (actions.some((existing) => existing.id === action.id)) return;
    actions.push(action);
  };

  if (shouldOfferAiPlacement) {
    for (const client of AI_CLIENTS) {
      addAction({
        id: `keep-only-${client.id}`,
        label: `Keep only in ${client.label}`,
        action: "keep_only_in_client",
        params: { target_client: client.id },
        tone: "primary",
      });
    }
  }

  addAction({
    id: "move-to-cli-only",
    label: "Move to CLI only",
    action: "move_to_cli_only",
    params: {},
    disabled: !(
      metadata?.ownerKind === "augur" &&
      management === "generated" &&
      CLI_PRIMARY_SURFACES.has(metadata?.primarySurface ?? "")
    ),
  });

  for (const client of exposedAiClients) {
    addAction({
      id: `block-from-${client.id}`,
      label: `Block from ${client.label}`,
      action: "block_from_clients",
      params: { clients: [client.id] },
    });
  }

  if (exposedAiClients.length >= 2) {
    addAction({
      id: "approve-current-clients",
      label: "Approve current clients",
      action: "approve_multi_client",
      params: { clients: exposedAiClients.map((client) => client.id) },
    });
  }

  if (
    currentExposure.length > 0 &&
    (metadata?.classificationStatus === "unclassified" || nonAiExposure.length > 0)
  ) {
    addAction({
      id: "approve-current-exposure",
      label: "Approve current exposure",
      action: "approve_current_exposure",
      params: {},
    });
  }

  if (metadata?.ownerKind === "external") {
    addAction({
      id: "mark-external-unmanaged",
      label: "Mark external unmanaged",
      action: "mark_external_unmanaged",
      params: {},
    });
  }

  if (metadata?.ownerKind === "external" || management === "unmanaged") {
    addAction({
      id: "adopt-under-augur-policy",
      label: "Adopt under Augur policy",
      action: "adopt_under_augur_policy",
      params: {},
    });
  }

  if (metadata?.classificationStatus !== "unclassified") {
    addAction({
      id: "leave-unclassified",
      label: "Leave unclassified",
      action: "leave_unclassified",
      params: {},
    });
  }

  return actions;
}

function impactLines(draft: CapabilityPolicyDraft | null, capabilityId?: string): string[] {
  if (!draft?.impact) return [];
  const lines: string[] = [];
  const removedFrom = capabilityId ? draft.impact.removed_from?.[capabilityId] : undefined;
  if (removedFrom?.length) {
    lines.push(`Removed from ${removedFrom.join(", ")}`);
  }
  const addedTo = capabilityId ? draft.impact.added_to?.[capabilityId] : undefined;
  if (addedTo?.length) {
    lines.push(`Added to ${addedTo.join(", ")}`);
  }
  if (draft.impact.gemini_delta) {
    lines.push(`Gemini delta ${draft.impact.gemini_delta > 0 ? "+" : ""}${draft.impact.gemini_delta}`);
  }
  if (draft.impact.opencode_delta) {
    lines.push(`OpenCode delta ${draft.impact.opencode_delta > 0 ? "+" : ""}${draft.impact.opencode_delta}`);
  }
  return lines;
}

function draftIncludesCapability(
  draft: CapabilityPolicyDraft | null,
  capabilityId?: string,
): draft is CapabilityPolicyDraft {
  if (!draft || !capabilityId) return false;
  return draft.capability_ids?.includes(capabilityId) ?? false;
}

function InlineMetadataCard({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  const display = typeof value === "string" ? (value || "unknown") : value;
  return (
    <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
      <dt className="font-semibold text-[var(--text-muted)]">{label}</dt>
      <dd className="mt-1 break-words text-[var(--text-primary)]">{display}</dd>
    </div>
  );
}

function formatMetadataList(values: string[]): string {
  return values.length ? values.join(", ") : "none";
}

const noopSubscribe = () => () => {};

export function CapabilityPolicyPanel({ item, onClose, onApplied }: CapabilityPolicyPanelProps) {
  const {
    draft,
    loading,
    error,
    draftPolicy,
    applyDraft,
    clearDraft,
  } = useCapabilityPolicy();
  const capabilityId = item.metadata?.capabilityId;
  const [localErrorState, setLocalErrorState] = useState<{
    capabilityId?: string;
    message: string | null;
  }>({ message: null });
  const [reviewedDraftState, setReviewedDraftState] = useState<{
    capabilityId?: string;
    draft: CapabilityPolicyDraft | null;
  }>({ draft: null });
  const mounted = useSyncExternalStore(noopSubscribe, () => true, () => false);

  const localError = localErrorState.capabilityId === capabilityId ? localErrorState.message : null;
  const reviewedDraft =
    reviewedDraftState.capabilityId === capabilityId ? reviewedDraftState.draft : null;
  const ownerKind = item.metadata?.ownerKind;
  const currentExposure = capabilityMetadataList(item.metadata, "currentExposure");
  const management = capabilityMetadataValue(item.metadata, "management") ?? "unknown";
  const policyScope = capabilityMetadataValue(item.metadata, "scope") ?? "unknown";
  const primarySurface = item.metadata?.primarySurface ?? "unknown";
  const preferredClient = item.metadata?.preferredClient ?? "none";
  const exportTo = capabilityMetadataList(item.metadata, "exportTo");
  const drift = capabilityMetadataList(item.metadata, "drift");
  const sourcePaths = capabilityMetadataList(item.metadata, "sourcePaths");
  const policyActions = buildPolicyActions(item.metadata, currentExposure);
  const activeDraft = draftIncludesCapability(reviewedDraft, capabilityId)
    ? reviewedDraft
    : draftIncludesCapability(draft, capabilityId)
      ? draft
      : null;
  const lines = impactLines(activeDraft, capabilityId);
  const disabled = !capabilityId || loading;

  const setCurrentLocalError = (message: string | null) => {
    setLocalErrorState({ capabilityId, message });
  };

  const setCurrentReviewedDraft = (nextDraft: CapabilityPolicyDraft | null) => {
    setReviewedDraftState({ capabilityId, draft: nextDraft });
  };

  useEffect(() => {
    clearDraft();
  }, [capabilityId, clearDraft]);

  const runDraft = async (
    action: string,
    params: Record<string, unknown>,
  ) => {
    if (!capabilityId) return;
    setCurrentLocalError(null);
    setCurrentReviewedDraft(null);
    clearDraft();
    try {
      const nextDraft = await draftPolicy({
        action,
        capabilityIds: [capabilityId],
        params,
      });
      setCurrentReviewedDraft(draftIncludesCapability(nextDraft, capabilityId) ? nextDraft : null);
    } catch (err) {
      setCurrentReviewedDraft(null);
      setCurrentLocalError(err instanceof Error ? err.message : "Policy draft failed");
    }
  };

  const apply = async () => {
    if (!activeDraft) return;
    setCurrentLocalError(null);
    try {
      await applyDraft(activeDraft);
      onApplied();
    } catch (err) {
      setCurrentLocalError(err instanceof Error ? err.message : "Policy apply failed");
    }
  };

  const close = () => {
    clearDraft();
    setCurrentLocalError(null);
    setCurrentReviewedDraft(null);
    onClose();
  };

  const panel = (
    <aside
      className="fixed inset-y-4 right-4 z-[90] flex w-[min(92vw,420px)] flex-col rounded-2xl border border-[var(--border-color)] bg-[var(--bg-primary)] shadow-2xl"
      aria-label="Capability policy review"
    >
      <div className="flex items-start gap-3 border-b border-[var(--border-color)] p-4">
        <div className="min-w-0 flex-1">
          <div className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
            Reviewed Apply
          </div>
          <h2 className="mt-1 truncate text-lg font-semibold text-[var(--text-primary)]">
            {item.title}
          </h2>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            {capabilityId ?? "No capability id"}
          </p>
        </div>
        <button
          type="button"
          onClick={close}
          className="rounded-lg p-1.5 text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
          aria-label="Close capability policy panel"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <dl className="grid grid-cols-2 gap-3 text-xs">
          <InlineMetadataCard label="Owner" value={ownerKind ?? "unknown"} />
          <InlineMetadataCard label="Management" value={management} />
          <InlineMetadataCard label="Policy scope" value={policyScope} />
          <InlineMetadataCard label="Surface" value={primarySurface} />
          <InlineMetadataCard label="Current exposure" value={formatMetadataList(currentExposure)} />
          <InlineMetadataCard label="Expected export" value={formatMetadataList(exportTo)} />
          <InlineMetadataCard label="Preferred client" value={preferredClient} />
          <InlineMetadataCard
            label="Drift"
            value={drift.length > 0 ? <CapabilityDriftBadge drift={drift} /> : "—"}
          />
        </dl>

        {sourcePaths.length > 0 ? (
          <section className="mt-4 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3">
            <h3 className="text-xs font-semibold text-[var(--text-muted)]">Source paths</h3>
            <ul className="mt-2 space-y-1 text-xs text-[var(--text-secondary)]">
              {sourcePaths.map((path) => (
                <li key={path} className="break-all font-mono">{path}</li>
              ))}
            </ul>
          </section>
        ) : null}

        <div className="mt-4 grid gap-2">
          {policyActions.map((policyAction) => (
            <button
              key={policyAction.id}
              type="button"
              disabled={disabled || policyAction.disabled}
              onClick={() => void runDraft(policyAction.action, policyAction.params)}
              className={
                policyAction.tone === "primary"
                  ? "min-h-[38px] rounded-lg border border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10 px-3 py-2 text-sm font-semibold text-[var(--accent-primary)] transition-colors hover:bg-[var(--accent-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                  : "min-h-[38px] rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              }
            >
              {policyAction.label}
            </button>
          ))}
        </div>

        {(error || localError) && (
          <div className="mt-4 rounded-xl border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 p-3 text-sm text-[var(--accent-danger)]">
            {localError ?? error}
          </div>
        )}

        {activeDraft && (
          <section className="mt-5">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Impact</h3>
            {lines.length > 0 ? (
              <ul className="mt-2 space-y-1 text-sm text-[var(--text-secondary)]">
                {lines.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-[var(--text-muted)]">No client exposure changes.</p>
            )}
            <pre className="mt-3 max-h-56 overflow-auto rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
              {activeDraft.diff || "No policy file diff."}
            </pre>
          </section>
        )}
      </div>

      <div className="border-t border-[var(--border-color)] p-4">
        <button
          type="button"
          disabled={!activeDraft || loading}
          onClick={() => void apply()}
          className="min-h-[40px] w-full rounded-lg border border-[var(--accent-success)]/30 bg-[var(--accent-success)]/10 px-3 py-2 text-sm font-semibold text-[var(--accent-success)] transition-colors hover:bg-[var(--accent-success)]/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Apply policy change
        </button>
      </div>
    </aside>
  );

  return mounted ? createPortal(panel, document.body) : panel;
}
