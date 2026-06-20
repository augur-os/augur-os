'use client';

import { useMemo, useReducer } from "react";
import { useActionRunner } from "@/hooks/useActionRunner";
import { mcpCall } from "@/lib/mcp/client";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import { capabilityLabelFromId, normalizeManagerSnapshot } from "./harness.helpers";
import type {
  BrainHarnessAction,
  BrainHarnessUiState,
  Capability,
  HarnessResponse,
  ManagerResponse,
  ManagerRow,
} from "./harness.types";

const DEFAULT_CAPABILITY_LIMIT = 24;

const INITIAL_BRAIN_HARNESS_STATE: BrainHarnessUiState = {
  isRefreshing: false,
  refreshError: null,
  managerActionError: null,
  managerBusyId: null,
  capabilityQuery: "",
  capabilityType: "all",
  managerTier: "effective",
};

function brainHarnessReducer(
  state: BrainHarnessUiState,
  action: BrainHarnessAction,
): BrainHarnessUiState {
  if (action.type !== "set-field") {
    return state;
  }
  const previous = state[action.field];
  const next =
    typeof action.value === "function"
      ? (action.value as (value: typeof previous) => unknown)(previous)
      : action.value;
  return { ...state, [action.field]: next };
}

export function useBrainHarnessController() {
  const [state, dispatch] = useReducer(brainHarnessReducer, INITIAL_BRAIN_HARNESS_STATE);
  const { runAction, isExecuting } = useActionRunner();
  const { data, loading, error, refetch } = useMcpQuery<HarnessResponse>(["brain-harness-snapshot"], "get-brain-harness-snapshot", "config");
  const {
    data: managerData,
    loading: managerLoading,
    error: managerError,
    refetch: refetchManager,
  } = useMcpQuery<ManagerResponse>(["harness-manager-snapshot"], "harness-manager-snapshot", "config");
  const setStateField = <K extends keyof BrainHarnessUiState>(
    field: K,
    value:
      | BrainHarnessUiState[K]
      | ((previous: BrainHarnessUiState[K]) => BrainHarnessUiState[K]),
  ) => dispatch({ type: "set-field", field, value });
  const snapshot = data?.snapshot ?? null;
  const managerSnapshot = normalizeManagerSnapshot(managerData);
  const groupedCapabilities = useMemo(() => {
    const groups: Record<string, Capability[]> = {};
    for (const capability of snapshot?.capabilities ?? []) {
      groups[capability.type] = [...(groups[capability.type] ?? []), capability];
    }
    return groups;
  }, [snapshot]);
  const capabilityTypes = useMemo(
    () =>
      Object.entries(groupedCapabilities)
        .map(([type, items]) => ({ type, count: items.length }))
        .sort((left, right) => left.type.localeCompare(right.type)),
    [groupedCapabilities],
  );
  const filteredCapabilities = useMemo(() => {
    const query = state.capabilityQuery.trim().toLowerCase();
    return (snapshot?.capabilities ?? []).filter((capability) => {
      if (state.capabilityType !== "all" && capability.type !== state.capabilityType) {
        return false;
      }
      if (!query) return true;
      return [
        capability.id,
        capability.type,
        capability.label,
        capability.hub,
        capability.owner_skill,
        capability.source_path,
        capability.summary,
        capability.tags.join(" "),
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query));
    });
  }, [state.capabilityQuery, state.capabilityType, snapshot]);
  const hasCapabilityFilter = state.capabilityType !== "all" || state.capabilityQuery.trim().length > 0;
  const visibleCapabilities = hasCapabilityFilter
    ? filteredCapabilities
    : filteredCapabilities.slice(0, DEFAULT_CAPABILITY_LIMIT);
  const hiddenCapabilityCount = filteredCapabilities.length - visibleCapabilities.length;
  const mappedCount = (snapshot?.capabilities ?? []).filter((capability) => capability.status === "mapped").length;
  const capabilityLabelById = useMemo(() => {
    const labels = new Map<string, string>();
    for (const capability of snapshot?.capabilities ?? []) {
      labels.set(capability.id, capability.label);
    }
    return labels;
  }, [snapshot]);
  const affectedCapabilities = useMemo(() => {
    const labels = new Set<string>();
    for (const diagnostic of snapshot?.diagnostics ?? []) {
      for (const id of diagnostic.affected_capability_ids) {
        labels.add(capabilityLabelById.get(id) ?? capabilityLabelFromId(id));
      }
    }
    return Array.from(labels).slice(0, 8);
  }, [capabilityLabelById, snapshot]);
  const managerTierOptions = useMemo(
    () => [
      { key: "effective", label: "Effective" },
      ...(managerSnapshot?.tier_details ?? []).map((tier) => ({ key: tier.key, label: tier.label })),
    ],
    [managerSnapshot],
  );
  const visibleManagerGroups = useMemo(() => {
    const groups = managerSnapshot?.groups ?? {};
    return Object.entries(groups).flatMap(([key, group]) => {
      const rows = group.entries.filter((row) => {
        if (state.managerTier === "effective") return true;
        return row.tiers.some((tier) => tier.tier === state.managerTier);
      });
      return rows.length > 0 ? [{ key, group, rows }] : [];
    });
  }, [managerSnapshot, state.managerTier]);
  const managerTotals = useMemo(() => {
    const groups = Object.values(managerSnapshot?.groups ?? {});
    return {
      effective: groups.reduce((sum, group) => sum + group.effective, 0),
      shadowed: groups.reduce((sum, group) => sum + group.shadowed.length, 0),
    };
  }, [managerSnapshot]);

  const handleRefresh = async () => {
    setStateField("isRefreshing", true);
    setStateField("refreshError", null);
    try {
      await mcpCall("refresh-brain-harness-snapshot", {});
      await Promise.all([refetch(), refetchManager()]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setStateField("refreshError", `Failed to refresh harness snapshot: ${message}`);
    } finally {
      setStateField("isRefreshing", false);
    }
  };

  const handleRepair = () => {
    runAction({
      id: "brain-harness-repair",
      label: "Ask IDE agent to repair",
      description: "Repair diagnostics from the Brain Harness snapshot.",
      dispatch: "ide",
      page: "/workspace/harness",
      prompt: "Repair Brain Harness diagnostics using the current snapshot payload and ADR-552 guidance.",
    });
  };

  const handleManagerAction = async (row: ManagerRow, action: "promote" | "demote") => {
    const actionState = row.actions[action];
    if (!actionState.enabled) return;
    setStateField("managerBusyId", `${action}:${row.id}`);
    setStateField("managerActionError", null);
    try {
      if (action === "demote") {
        await mcpCall("harness-demote-capability", {
          capability_type: row.capability_type,
          name: row.name,
          target_client: "codex",
          target_scope: "local",
          remove_source: false,
        });
      } else {
        await mcpCall("harness-promote-capability", {
          capability_type: row.capability_type,
          name: row.name,
          source_path: row.winner_path,
          target_tier: "project",
          remove_source: false,
        });
      }
      await refetchManager();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setStateField("managerActionError", `Harness manager action failed: ${message}`);
    } finally {
      setStateField("managerBusyId", null);
    }
  };

  return {
    ...state,
    affectedCapabilities,
    capabilityTypes,
    error,
    filteredCapabilities,
    handleManagerAction,
    handleRefresh,
    handleRepair,
    hiddenCapabilityCount,
    isExecuting,
    loading,
    managerError,
    managerLoading,
    managerSnapshot,
    managerTierOptions,
    managerTotals,
    mappedCount,
    setCapabilityQuery: (value: string) => setStateField("capabilityQuery", value),
    setCapabilityType: (value: string) => setStateField("capabilityType", value),
    setManagerTier: (value: string) => setStateField("managerTier", value),
    snapshot,
    visibleCapabilities,
    visibleManagerGroups,
  };
}

export type BrainHarnessController = ReturnType<typeof useBrainHarnessController>;
