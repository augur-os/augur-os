"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { mcpCall } from "@/lib/mcp/client";
import { mayUseVisibleSurface } from "@/lib/visible-surface-policy";

type McpServerInfo = {
  name: string;
  command: string;
  args: string[];
  cwd?: string;
  envKeys: string[];
  status: string;
  issues: string[];
};

type McpClientReport = {
  configPath: string;
  exists: boolean;
  servers: McpServerInfo[];
  augurServers: McpServerInfo[];
  error?: string;
};

type McpSummary = {
  generatedAt: string;
  clients?: {
    claudeDesktop?: McpClientReport;
    cursor?: McpClientReport;
    claudeCode?: McpClientReport;
    codex?: McpClientReport;
    opencode?: McpClientReport;
    antigravity?: McpClientReport;
    gemini?: McpClientReport;
  };
  runtime: {
    candidate: {
      client: string;
      name: string;
      command: string;
      args: string[];
    } | null;
    transport: {
      transport: string;
      host: string;
      port: number;
    };
    processMatches: Array<{ pid: number; command: string }>;
    portOpen?: boolean;
  };
  migrationInProgress?: boolean;
  staleMcpConfig?: boolean;
};

type McpHealthState = {
  data: McpSummary | null;
  isLoading: boolean;
  error: string | null;
  hasIssues: boolean;
  issues: Array<{ client: string; server: string; problems: string[] }>;
  lastChecked: Date | null;
};

const TOAST_ID = "mcp-health-warning";
const LIGHTWEIGHT_DIAGNOSTICS_ARGS: Record<string, unknown> = {
  params: {
    include_processes: true,
    include_configs: false,
  },
};
const FULL_DIAGNOSTICS_ARGS: Record<string, unknown> = {
  params: {
    include_processes: true,
    include_configs: true,
  },
};

const CLIENT_LABELS: Record<string, string> = {
  claudeDesktop: "Claude Desktop",
  cursor: "Cursor",
  claudeCode: "Claude Code",
  codex: "Codex",
  opencode: "OpenCode",
  antigravity: "Antigravity",
  gemini: "Gemini",
};

function isAugurServer(name: string): boolean {
  return name === "augur" || name.startsWith("augur-");
}

function shouldReportClientError(report: McpClientReport): boolean {
  if (!report.error) return false;
  if (
    (report.error === "Config file not found." ||
      report.error === "Augur MCP not configured.") &&
    report.augurServers.length === 0
  ) {
    return false;
  }
  return true;
}

export function extractIssues(data: McpSummary) {
  const issues: Array<{ client: string; server: string; problems: string[] }> = [];

  const checkClient = (client: string, report: McpClientReport) => {
    const clientError = report.error;
    if (clientError && shouldReportClientError(report)) {
      issues.push({ client, server: "(config)", problems: [clientError] });
    }
    for (const server of report.servers) {
      if (isAugurServer(server.name) && server.issues.length > 0) {
        issues.push({ client, server: server.name, problems: server.issues });
      }
    }
  };

  const clients = data.clients;
  if (!clients) return issues;

  for (const [key, label] of Object.entries(CLIENT_LABELS)) {
    const report = clients[key as keyof NonNullable<McpSummary["clients"]>];
    if (report) checkClient(label, report);
  }

  return issues;
}

async function fetchMcpSummary(includeConfigs: boolean): Promise<McpSummary> {
  return mcpCall<McpSummary>(
    "get-mcp-diagnostics",
    includeConfigs ? FULL_DIAGNOSTICS_ARGS : LIGHTWEIGHT_DIAGNOSTICS_ARGS,
  );
}

export function useMcpHealth({
  enablePolling = true,
  showToasts = true,
  includeConfigs = false,
  pollInterval = 30000,
}: {
  enablePolling?: boolean;
  showToasts?: boolean;
  includeConfigs?: boolean;
  pollInterval?: number;
} = {}): McpHealthState & { refresh: () => void } {
  const previousIssuesRef = useRef<string>("");
  const hasShownInitialToast = useRef(false);

  const { data, isLoading, error, refetch } = useQuery<McpSummary>({
    queryKey: ["mcp-health-summary", includeConfigs ? "full" : "runtime"],
    queryFn: () => fetchMcpSummary(includeConfigs),
    staleTime: 120_000,
    refetchInterval: enablePolling ? pollInterval : false,
    refetchOnWindowFocus: false,
  });

  const issues = useMemo(() => (data ? extractIssues(data) : []), [data]);
  const hasIssues = issues.length > 0;

  // Toast side-effects
  useEffect(() => {
    if (!showToasts || !data) return;

    const issuesKey = JSON.stringify(issues);

    if (hasIssues) {
      if (issuesKey !== previousIssuesRef.current || !hasShownInitialToast.current) {
        const firstIssue = issues[0];
        const viewAction = mayUseVisibleSurface("navigate", "user-triggered")
          ? {
              label: "View",
              onClick: () => { window.location.href = "/brain?tab=mcp"; },
            }
          : undefined;
        const fixAction = mayUseVisibleSurface("send-ide-prompt", "user-triggered")
          ? {
              label: "Fix Now",
              onClick: async () => {
                try {
                  let promptText = "";
                  let serverContext = { root: "Unknown", home: "Unknown" };
                  try {
                    const tplJson = await mcpCall<{ ok?: boolean; template?: string; context?: { root: string; home: string } }>(
                      "file-read",
                      { promptId: "ide-config-debug" },
                      { fallback: {} },
                    );
                    if (tplJson.ok) {
                      if (tplJson.template) promptText = tplJson.template;
                      if (tplJson.context) serverContext = tplJson.context;
                    }
                  } catch {}
                  const fileSystemPaths = `- Project Root: ${serverContext.root}\n- Home: ${serverContext.home}`;
                  if (promptText) {
                    promptText = promptText
                      .replace(/{{ide_name}}/g, firstIssue.client)
                      .replace("{{config_path}}", firstIssue.server === "(config)" ? "Configuration File" : firstIssue.server)
                      .replace("{{issue_count}}", String(issues.length))
                      .replace(/{{#each issues}}([\s\S]*?){{\/each}}/, (_, block) =>
                        firstIssue.problems.map((p: string) => block.replace("{{this}}", p)).join(""))
                      .replace("{{file_system_paths}}", fileSystemPaths);
                  } else {
                    promptText = `Fix MCP config for ${firstIssue.client}. Errors: ${firstIssue.problems.join(", ")}`;
                  }
                  const result = await mcpCall<{ success?: boolean; ide?: string; error?: string }>(
                    "send-ide-prompt",
                    { prompt: promptText },
                  );
                  if (result.success) toast.success(`Sent to ${result.ide || "IDE"}`);
                  else toast.error(`Failed: ${result.error || "Unknown error"}`);
                } catch {
                  toast.error("Failed to send to IDE");
                }
              },
            }
          : undefined;
        toast.error(`MCP Issue: ${firstIssue.client} - ${firstIssue.server}`, {
          id: TOAST_ID,
          description: firstIssue.problems[0] + (issues.length > 1 ? ` (+${issues.length - 1} more)` : ""),
          duration: 15000,
          ...(viewAction ? { action: viewAction } : {}),
          ...(fixAction ? { cancel: fixAction } : {}),
        });
        hasShownInitialToast.current = true;
      }
    } else if (previousIssuesRef.current !== "[]" && hasShownInitialToast.current) {
      toast.success("MCP servers healthy", { id: TOAST_ID, duration: 3000 });
    }

    previousIssuesRef.current = issuesKey;
  }, [data, showToasts, issues, hasIssues]);

  const refresh = useCallback(() => { refetch(); }, [refetch]);

  return {
    data: data ?? null,
    isLoading,
    error: error ? (error instanceof Error ? error.message : "Unknown error") : null,
    hasIssues,
    issues,
    lastChecked: data ? new Date() : null,
    refresh,
  };
}
