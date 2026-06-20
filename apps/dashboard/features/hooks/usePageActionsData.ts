"use client";

import type { ActionDef } from "@/hooks/useActionRunner";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";

export interface ListShortcut {
  id: string;
  name: string;
  description: string;
  context: string;
}

export interface SlashCommand {
  id: string;
  name: string;
  description: string;
  category?: string;
  scope?: "global" | "page" | "hub";
  applicablePages?: string[];
  applicableHubs?: string[];
}

export interface DataContext {
  path: string | null;
  lastUpdated: string | null;
}

export interface PageActionsData {
  buttons: ActionDef[];
  shortcuts: ListShortcut[];
  commands: SlashCommand[];
  dataContext: DataContext;
  loading: boolean;
}

interface UsePageActionsDataOptions {
  pathname: string | null;
  currentTab?: string | null;
}

interface RegistryResponse {
  buttons?: ActionDef[];
  shortcuts?: ListShortcut[];
  dataContext?: DataContext;
}

interface WorkflowsResponse {
  commands?: SlashCommand[];
}

function selectRegistry(raw: unknown): RegistryResponse {
  if (!raw || typeof raw !== "object") return {};
  return raw as RegistryResponse;
}

function selectWorkflows(raw: unknown): WorkflowsResponse {
  if (!raw || typeof raw !== "object") return {};
  return raw as WorkflowsResponse;
}

/**
 * Hook to fetch page action data (buttons, shortcuts, chains, commands).
 * Uses React Query via useMcpQuery with hub-scoped cache keys and
 * "config" preset (600s staleTime) — registry data changes rarely.
 */
export function usePageActionsData({
  pathname,
  currentTab,
}: UsePageActionsDataOptions): PageActionsData {
  const hub = pathname?.split("/").filter(Boolean)[0] || "";

  // Build params — registry needs full page path for filtering, but cache key is hub-scoped
  const registryParams: Record<string, string> = { page: pathname || "/" };
  if (currentTab) {
    registryParams.tab = currentTab;
  }

  const workflowsParams: Record<string, string> = {
    page: pathname || "/",
    hub,
  };

  const { data: registryData, loading: registryLoading } =
    useMcpQuery<RegistryResponse>(
      ["registry", hub, currentTab ?? ""],
      "list-skills",
      "config",
      { args: registryParams, select: selectRegistry },
    );

  const { data: workflowsData, loading: workflowsLoading } =
    useMcpQuery<WorkflowsResponse>(
      ["workflows", hub],
      "list-commands",
      "config",
      { args: workflowsParams, select: selectWorkflows },
    );

  const loading = registryLoading || workflowsLoading;

  return {
    buttons: registryData?.buttons ?? [],
    shortcuts: registryData?.shortcuts ?? [],
    commands: workflowsData?.commands ?? [],
    dataContext: registryData?.dataContext ?? { path: null, lastUpdated: null },
    loading,
  };
}
