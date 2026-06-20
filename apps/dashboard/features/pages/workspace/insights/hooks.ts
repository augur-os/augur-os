"use client";

import { useState } from "react";
import { mcpCall } from "@/lib/mcp/client";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import type { BrainInsightsResponse, InsightsNotice } from "./types";

function resultMessage(value: unknown, fallback: string) {
  if (value && typeof value === "object" && "message" in value) {
    const message = (value as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
  }
  return fallback;
}

export function useBrainInsights() {
  const query = useMcpQuery<BrainInsightsResponse>(["brain-insights"], "brain-insights", "live");
  const [wikiUpdateRunning, setWikiUpdateRunning] = useState(false);
  const [notice, setNotice] = useState<InsightsNotice>(null);

  const errors = [
    ...(query.data?.success === false && query.data.error ? [query.data.error] : []),
    ...(query.data?.errors ?? []),
  ];
  const responseError = query.data?.success === false && errors.length === 0 ? "Brain Insights MCP query failed." : null;
  const latestRuns = query.data?.latest_runs ?? [];
  const wikiStatus = query.data?.wiki_status ?? null;
  const askOutcomes = query.data?.retained_ask_outcomes ?? query.data?.ask_outcomes ?? [];
  const askClusters = query.data?.retained_ask_clusters ?? query.data?.ask_clusters ?? [];
  const wikiUpdateAction = wikiStatus?.actions?.find((action) => action.id === "prepare-incremental-batch") ?? null;

  const runWikiUpdate = async () => {
    if (!wikiUpdateAction?.tool) {
      setNotice({ type: "warning", message: "No wiki update MCP action is available right now." });
      return false;
    }
    setWikiUpdateRunning(true);
    setNotice(null);
    try {
      const result = await mcpCall<{ success?: boolean; message?: string; error?: string }>(
        wikiUpdateAction.tool,
        wikiUpdateAction.inputs ?? {},
      );
      if (result?.success === false) {
        throw new Error(result.error || result.message || `${wikiUpdateAction.tool} failed`);
      }
      setNotice({
        type: "success",
        message: resultMessage(result, "Wiki update batch prepared. Agent synthesis and apply still need to run."),
      });
      query.refetch();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setNotice({ type: "error", message: `${wikiUpdateAction.tool} failed: ${message}` });
      return false;
    } finally {
      setWikiUpdateRunning(false);
    }
  };

  return {
    ...query,
    error: query.error || responseError,
    errors,
    latestRuns,
    wikiStatus,
    askOutcomes,
    askClusters,
    wikiUpdateAction,
    wikiUpdateRunning,
    notice,
    runWikiUpdate,
  };
}
