"use client";

import { useCallback, useState } from "react";
import { mcpCall } from "@/lib/mcp/client";
import type {
  CapabilityInventoryReport,
  CapabilityPolicyApplyResult,
  CapabilityPolicyDraft,
  CapabilityPolicyDraftRequest,
} from "./types";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function useCapabilityPolicy() {
  const [report, setReport] = useState<CapabilityInventoryReport | null>(null);
  const [draft, setDraft] = useState<CapabilityPolicyDraft | null>(null);
  const [applyResult, setApplyResult] = useState<CapabilityPolicyApplyResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await mcpCall<CapabilityInventoryReport>("capability-inventory-report", {});
      if (next.ok === false) {
        throw new Error(next.error || "Capability report failed");
      }
      setReport(next);
      return next;
    } catch (err) {
      setError(errorMessage(err, "Capability report failed"));
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const draftPolicy = useCallback(async (request: CapabilityPolicyDraftRequest) => {
    setLoading(true);
    setError(null);
    setDraft(null);
    setApplyResult(null);
    try {
      const next = await mcpCall<CapabilityPolicyDraft>("capability-policy-draft", {
        action: request.action,
        capability_ids: request.capabilityIds,
        params: request.params,
      });
      if (next.ok === false) {
        throw new Error(next.error || "Capability policy draft failed");
      }
      setDraft(next);
      return next;
    } catch (err) {
      setDraft(null);
      setError(errorMessage(err, "Capability policy draft failed"));
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const applyDraft = useCallback(async (draftOverride?: CapabilityPolicyDraft) => {
    const activeDraft = draftOverride ?? draft;
    if (!activeDraft) {
      throw new Error("No capability policy draft to apply");
    }
    setLoading(true);
    setError(null);
    setApplyResult(null);
    try {
      const next = await mcpCall<CapabilityPolicyApplyResult>("capability-policy-apply", { draft: activeDraft });
      if (next.ok === false) {
        throw new Error(next.error || "Capability policy apply failed");
      }
      setApplyResult(next);
      return next;
    } catch (err) {
      setApplyResult(null);
      setError(errorMessage(err, "Capability policy apply failed"));
      throw err;
    } finally {
      setLoading(false);
    }
  }, [draft]);

  const clearDraft = useCallback(() => {
    setDraft(null);
    setApplyResult(null);
    setError(null);
  }, []);

  return {
    report,
    draft,
    applyResult,
    loading,
    error,
    refreshReport,
    draftPolicy,
    applyDraft,
    clearDraft,
  };
}
