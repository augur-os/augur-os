"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import { mcpCall } from "@/lib/mcp/client";
import { useActionRunner } from "@/hooks/useActionRunner";
import type { SecuritySettings } from "@/lib/remote/types";

export interface SecurityFinding {
  file: string;
  line: number;
  severity: "HIGH" | "MEDIUM" | "LOW";
  category: string;
  description: string;
  confidence: number;
  recommendation?: string;
  exploit_scenario?: string;
  source: "claude" | "scanner";
}

export interface AuditReport {
  timestamp: string;
  source: "claude" | "scanner" | "combined";
  analysis_summary: {
    files_reviewed: number;
    high_severity: number;
    medium_severity: number;
    low_severity: number;
  };
  findings: SecurityFinding[];
}

export interface AuditLog {
  timestamp: string;
  action: string;
  user?: string;
  resource?: string;
  organization_id?: string;
  success: boolean;
  details?: Record<string, unknown>;
}

interface SecurityTabState {
  logs: AuditLog[];
  loading: boolean;
  exporting: boolean;
  filters: AuditFilters;
  security: SecuritySettings;
  saving: boolean;
  hasChanges: boolean;
  auditReport: AuditReport | null;
  scanning: boolean;
  expandedRow: number | null;
}

type SecurityTabAction = {
  type: "set-field";
  field: keyof SecurityTabState;
  value: unknown;
};

const DEFAULT_FILTERS = {
  start_date: "",
  end_date: "",
  action: "",
  user: "",
};

const DEFAULT_SECURITY: SecuritySettings = {
  requireExplicitConsent: true,
  warnOnPii: true,
  blockOnSecrets: true,
  sensitiveFolders: [],
};

const INITIAL_SECURITY_TAB_STATE: SecurityTabState = {
  logs: [],
  loading: true,
  exporting: false,
  filters: DEFAULT_FILTERS,
  security: DEFAULT_SECURITY,
  saving: false,
  hasChanges: false,
  auditReport: null,
  scanning: false,
  expandedRow: null,
};

export type AuditFilters = typeof DEFAULT_FILTERS;

function securityTabReducer(
  state: SecurityTabState,
  action: SecurityTabAction,
): SecurityTabState {
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

export function useSecurityTabController() {
  const [state, dispatch] = useReducer(securityTabReducer, INITIAL_SECURITY_TAB_STATE);
  const securityInitializedRef = useRef(false);
  const { runAction, isExecuting } = useActionRunner();
  const {
    data: providersData,
    loading: securityLoading,
    refetch: refreshSecuritySettings,
  } = useMcpQuery<{ security?: SecuritySettings }>(
    "security-providers",
    "get-settings",
    "config",
    { args: { scope: "remote-providers" } },
  );
  const setStateField = useCallback(
    <K extends keyof SecurityTabState,>(
      field: K,
      value:
        | SecurityTabState[K]
        | ((previous: SecurityTabState[K]) => SecurityTabState[K]),
    ) => {
      dispatch({ type: "set-field", field, value });
    },
    [],
  );

  useEffect(() => {
    if (!providersData?.security || securityInitializedRef.current) {
      return;
    }
    const timer = window.setTimeout(() => {
      setStateField("security", { ...DEFAULT_SECURITY, ...providersData.security });
      securityInitializedRef.current = true;
    }, 0);
    return () => window.clearTimeout(timer);
  }, [providersData, setStateField]);

  const refetchAuditReport = useCallback(async () => {
    try {
      const data = await mcpCall<AuditReport | { status?: string }>(
        "get-security-report",
        {},
      );
      // The loader returns a {status: "no_report" | "error"} sentinel when no
      // report exists. Only a payload with analysis_summary is a real report;
      // storing the sentinel would crash the summary cards / "Last audit" line.
      const isReport =
        !!data &&
        typeof data === "object" &&
        "analysis_summary" in data &&
        !!(data as AuditReport).analysis_summary;
      setStateField("auditReport", isReport ? (data as AuditReport) : null);
    } catch {
      // Report may not exist yet.
      setStateField("auditReport", null);
    }
  }, [setStateField]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refetchAuditReport();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refetchAuditReport]);

  const loadLogs = useCallback(
    async (activeFilters: AuditFilters) => {
      try {
        setStateField("loading", true);
        const args: Record<string, unknown> = { limit: 100 };
        if (activeFilters.start_date) args.start_date = activeFilters.start_date;
        if (activeFilters.end_date) args.end_date = activeFilters.end_date;
        if (activeFilters.action) args.action = activeFilters.action;
        if (activeFilters.user) args.user = activeFilters.user;
        const data = await mcpCall<{ ok?: boolean; logs?: AuditLog[] }>("query-audit-log", args);
        if (data.ok && data.logs) {
          setStateField("logs", data.logs);
        }
      } catch (err) {
        console.error("Failed to load audit logs:", err);
      } finally {
        setStateField("loading", false);
      }
    },
    [setStateField],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadLogs(DEFAULT_FILTERS);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadLogs]);

  const handleExport = useCallback(
    async (format: "json" | "csv") => {
      setStateField("exporting", true);
      try {
        const data = await mcpCall<{ ok?: boolean; content?: unknown; file?: string }>("file-write", {
          action: "export-audit",
          start_date: state.filters.start_date || undefined,
          end_date: state.filters.end_date || undefined,
          format,
        });
        if (data.ok) {
          const blob = new Blob(
            [
              format === "json"
                ? JSON.stringify(data.content, null, 2)
                : String(data.content ?? ""),
            ],
            { type: format === "json" ? "application/json" : "text/csv" },
          );
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement("a");
          anchor.href = url;
          anchor.download = data.file ?? "audit-export";
          anchor.click();
          URL.revokeObjectURL(url);
        }
      } catch (err) {
        console.error("Failed to export audit logs:", err);
      } finally {
        setStateField("exporting", false);
      }
    },
    [setStateField, state.filters],
  );

  const handleSaveAiSettings = useCallback(async () => {
    setStateField("saving", true);
    try {
      await mcpCall("set-config", { security: state.security });
      setStateField("hasChanges", false);
    } catch (err) {
      console.error("Failed to save settings:", err);
    } finally {
      setStateField("saving", false);
    }
  }, [setStateField, state.security]);

  const toggleSecurity = useCallback(
    (key: keyof SecuritySettings) => {
      if (typeof state.security[key] !== "boolean") {
        return;
      }
      setStateField("security", (previous) => ({
        ...previous,
        [key]: !previous[key],
      }));
      setStateField("hasChanges", true);
    },
    [setStateField, state.security],
  );

  const handleAiReview = useCallback(() => {
    void runAction({
      id: "security-review",
      label: "AI Security Review",
      description:
        "Run Claude /security-review for deep vulnerability analysis",
      dispatch: "ide",
      icon: "ShieldAlert",
      page: "/settings/privacy",
    });
  }, [runAction]);

  const handleQuickScan = useCallback(async () => {
    setStateField("scanning", true);
    try {
      await mcpCall("run-security-scan", {});
      refetchAuditReport();
    } catch (err) {
      console.error("Quick scan failed:", err);
    } finally {
      setStateField("scanning", false);
    }
  }, [refetchAuditReport, setStateField]);

  const updateFilters = useCallback(
    (patch: Partial<AuditFilters>) => {
      setStateField("filters", (previous) => ({ ...previous, ...patch }));
    },
    [setStateField],
  );

  const clearFilters = useCallback(() => {
    setStateField("filters", DEFAULT_FILTERS);
    void loadLogs(DEFAULT_FILTERS);
  }, [loadLogs, setStateField]);

  return {
    ...state,
    clearFilters,
    handleAiReview,
    handleExport,
    handleQuickScan,
    handleSaveAiSettings,
    isExecuting,
    loadLogs,
    refreshSecuritySettings,
    securityLoading,
    setExpandedRow: (row: number | null) => setStateField("expandedRow", row),
    toggleSecurity,
    updateFilters,
  };
}

export type SecurityTabController = ReturnType<typeof useSecurityTabController>;
