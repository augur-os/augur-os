"use client";

import { useMemo, useState } from "react";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import { mcpCall } from "@/lib/mcp/client";
import {
  AlertTriangle,
  CheckCircle,
  FileCog,
  FolderOpen,
  Loader2,
  RefreshCw,
  Server,
  Wifi,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SettingsCard } from "@/components/ui/SettingsCard";

interface McpServer {
  name: string;
  status?: string;
  issues?: string[];
}

interface McpClientReport {
  configPath: string;
  exists: boolean;
  servers: McpServer[];
  error?: string;
}

interface McpRuntimeSummary {
  transport?: {
    transport?: string;
    host?: string;
    port?: number;
  };
  candidate?: {
    client?: string;
    name?: string;
  };
  processMatches?: Array<{ pid: number }>;
  portOpen?: boolean;
}

interface McpSummary {
  staleMcpConfig?: boolean;
  migrationInProgress?: boolean;
  dataDir?: string;
  clients?: Record<string, unknown>;
  runtime?: McpRuntimeSummary;
}

const CLIENT_LABELS: Record<string, string> = {
  claudeDesktop: "Claude Desktop",
  cursor: "Cursor",
  codex: "Codex",
  claudeCode: "Claude Code",
  gemini: "Gemini",
  opencode: "OpenCode",
  antigravity: "Antigravity",
};

const CLIENT_RUNTIME_IDS: Record<string, string> = {
  claudeDesktop: "claude-desktop",
  cursor: "cursor",
  codex: "codex",
  claudeCode: "claude-code",
  gemini: "gemini",
  opencode: "opencode",
  antigravity: "antigravity",
};

function isMcpClientReport(value: unknown): value is McpClientReport {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<McpClientReport>;
  return (
    typeof candidate.configPath === "string" &&
    typeof candidate.exists === "boolean" &&
    Array.isArray(candidate.servers)
  );
}

function configParentPath(configPath: string): string {
  if (!configPath) return configPath;
  return configPath.replace(/[\\/][^\\/]+$/, "");
}

async function openSystemPath(pathToOpen: string): Promise<void> {
  if (!pathToOpen) return;
  await mcpCall("system-open", { path: pathToOpen });
}

async function openClientRuntimeFolder(clientId: string): Promise<void> {
  if (!clientId) return;
  await mcpCall("open-client-runtime-folder", { clientId });
}

interface McpClientCardProps {
  clientKey: string;
  report: McpClientReport;
  openingPath: string | null;
  onOpenPath: (pathToOpen: string) => void;
  onOpenRuntimeFolder: (clientId: string) => void;
}

function McpClientCard({
  clientKey,
  report,
  openingPath,
  onOpenPath,
  onOpenRuntimeFolder,
}: McpClientCardProps) {
  const issueCount = report.servers.filter(
    (server) => server.status && server.status !== "ok",
  ).length;
  const isHealthy = report.exists && !report.error && issueCount === 0;
  const clientLabel = CLIENT_LABELS[clientKey] || clientKey;
  const configTarget = report.exists
    ? report.configPath
    : configParentPath(report.configPath);
  const runtimeClientId = CLIENT_RUNTIME_IDS[clientKey];
  const runtimeLoadingKey = runtimeClientId
    ? `runtime:${runtimeClientId}`
    : null;

  return (
    <SettingsCard
      icon={FileCog}
      title={clientLabel}
      subtitle={report.configPath}
      isPath
      variant={
        report.error
          ? "error"
          : isHealthy
            ? "success"
            : report.exists
              ? "warning"
              : "muted"
      }
      badge={report.exists ? "Configured" : "Missing"}
      secondaryBadge={`${report.servers.length} servers`}
      action={
        <div className="flex items-center gap-1">
          {runtimeClientId ? (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => onOpenRuntimeFolder(runtimeClientId)}
              disabled={openingPath === runtimeLoadingKey}
              title="Reveal runtime folder"
              aria-label={`Reveal ${clientLabel} runtime folder`}
            >
              {openingPath === runtimeLoadingKey ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <FolderOpen className="size-3.5" />
              )}
            </Button>
          ) : null}
          {report.configPath ? (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => onOpenPath(configTarget)}
              disabled={openingPath === configTarget}
              title={report.exists ? "Open config file" : "Open config folder"}
              aria-label={
                report.exists
                  ? `Open ${clientLabel} config file`
                  : `Open ${clientLabel} config folder`
              }
            >
              {openingPath === configTarget ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <FileCog className="size-3.5" />
              )}
            </Button>
          ) : null}
        </div>
      }
    >
      {report.error ? (
        <p className="text-xs text-[var(--accent-danger)]">{report.error}</p>
      ) : report.servers.length === 0 ? (
        <p className="text-xs text-[var(--text-muted)]">
          No MCP servers configured.
        </p>
      ) : (
        <div className="space-y-1.5">
          {report.servers.slice(0, 4).map((server) => {
            const hasIssue = Boolean(
              server.status && server.status !== "ok",
            );
            return (
              <div
                key={`${clientKey}-${server.name}`}
                className="text-xs rounded-md bg-[var(--bg-hover)] px-2 py-1 flex items-center justify-between gap-2"
              >
                <span className="truncate text-[var(--text-primary)] font-mono" title={server.name}>
                  {server.name}
                </span>
                {hasIssue ? (
                  <span className="inline-flex items-center" title="Has issues">
                    <AlertTriangle className="size-3 text-[var(--accent-warning)] flex-shrink-0" aria-hidden="true" />
                    <span className="sr-only">Has issues</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center" title="Healthy">
                    <CheckCircle className="size-3 text-[var(--accent-success)] flex-shrink-0" aria-hidden="true" />
                    <span className="sr-only">Healthy</span>
                  </span>
                )}
              </div>
            );
          })}
          {report.servers.length > 4 && (
            <p className="text-xs text-[var(--text-muted)] text-center">
              +{report.servers.length - 4} more
            </p>
          )}
        </div>
      )}
    </SettingsCard>
  );
}

export default function McpControlPanel() {
  const {
    data: summary,
    loading,
    error,
    refetch: loadSummary,
  } = useMcpQuery<McpSummary>("mcp-summary", "get-mcp-diagnostics", "config");

  const [openingPath, setOpeningPath] = useState<string | null>(null);

  const clients = useMemo(() => {
    const collected: Array<{ key: string; report: McpClientReport }> = [];
    for (const [clientKey, value] of Object.entries(summary?.clients || {})) {
      if (clientKey === "oauthClients" || !isMcpClientReport(value)) continue;
      collected.push({ key: clientKey, report: value });
    }
    return collected;
  }, [summary]);

  const totalConfiguredServers = useMemo(
    () =>
      clients.reduce(
        (total, client) => total + client.report.servers.length,
        0,
      ),
    [clients],
  );

  const totalIssues = useMemo(
    () =>
      clients.reduce(
        (total, client) =>
          total +
          client.report.servers.filter(
            (server) => server.status && server.status !== "ok",
          ).length,
        0,
      ),
    [clients],
  );

  const openPath = async (pathToOpen: string) => {
    try {
      setOpeningPath(pathToOpen);
      await openSystemPath(pathToOpen);
    } finally {
      setOpeningPath(null);
    }
  };

  const openRuntimeFolder = async (clientId: string) => {
    const loadingKey = `runtime:${clientId}`;
    try {
      setOpeningPath(loadingKey);
      await openClientRuntimeFolder(clientId);
    } finally {
      setOpeningPath(null);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-24 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] animate-pulse"
            />
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="h-40 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <SettingsCard
        icon={XCircle}
        title="MCP Diagnostics Unavailable"
        subtitle={error}
        variant="error"
        action={
          <Button variant="ghost" size="sm" onClick={loadSummary} aria-label="Retry loading MCP diagnostics">
            <RefreshCw className="size-3.5" />
          </Button>
        }
      />
    );
  }

  const runtimeTransport = summary?.runtime?.transport;
  const runtimeProcessCount = summary?.runtime?.processMatches?.length || 0;
  const runtimeOnline =
    summary?.runtime?.portOpen === true || runtimeProcessCount > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            MCP Configuration
          </h3>
          <p className="text-xs text-[var(--text-muted)]">
            Open client config files, verify runtime status, and fix stale
            mounts.
          </p>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={loadSummary} aria-label="Refresh MCP configuration">
          <RefreshCw className="size-4" />
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <SettingsCard
          icon={Wifi}
          title="Runtime"
          subtitle={
            runtimeTransport
              ? `${runtimeTransport.transport || "stdio"} · ${runtimeTransport.host || "127.0.0.1"}:${runtimeTransport.port || "n/a"}`
              : "No runtime transport discovered"
          }
          variant={runtimeOnline ? "success" : "warning"}
          badge={runtimeOnline ? "Online" : "Offline"}
          value={`${runtimeProcessCount}`}
          valueLabel="Processes"
        />
        <SettingsCard
          icon={Server}
          title="Configured Servers"
          subtitle="Total MCP servers across detected clients"
          variant={totalIssues > 0 ? "warning" : "info"}
          value={`${totalConfiguredServers}`}
          valueLabel="Servers"
        />
        <SettingsCard
          icon={AlertTriangle}
          title="Action Required"
          subtitle={
            summary?.staleMcpConfig
              ? "Some clients still point to an old project path."
              : "No stale MCP root paths detected."
          }
          variant={summary?.staleMcpConfig ? "warning" : "success"}
          badge={summary?.staleMcpConfig ? "Stale Config" : "Clean"}
          value={`${totalIssues}`}
          valueLabel="Issues"
          action={
            summary?.dataDir ? (
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => openPath(summary.dataDir || "")}
                disabled={openingPath === summary.dataDir}
                title="Open Augur root folder"
                aria-label="Open Augur root folder"
              >
                {openingPath === summary.dataDir ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <FolderOpen className="size-3.5" />
                )}
              </Button>
            ) : undefined
          }
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {clients.map(({ key, report }) => (
          <McpClientCard
            key={`${key}-${report.configPath}`}
            clientKey={key}
            report={report}
            openingPath={openingPath}
            onOpenPath={openPath}
            onOpenRuntimeFolder={openRuntimeFolder}
          />
        ))}
      </div>

      {clients.length === 0 && (
        <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-6 text-center">
          <Server className="size-6 text-[var(--text-muted)] mx-auto mb-2" />
          <p className="text-sm text-[var(--text-muted)]">
            No MCP client configuration files were detected.
          </p>
        </div>
      )}

      {summary?.migrationInProgress && (
        <p className="text-xs text-[var(--accent-warning)] px-1">
          MCP migration is currently in progress. Avoid editing config files
          until it completes.
        </p>
      )}
    </div>
  );
}
