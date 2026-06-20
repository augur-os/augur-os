import { NextRequest, NextResponse } from "next/server";
import { PROVIDER_REGISTRY } from "@/lib/remote/providers";
import type { ExecutionMode } from "@/lib/remote/types";

interface AgentInfo {
  id: string;
  name: string;
  icon: string;
  health: "healthy" | "degraded" | "offline" | "unhealthy";
  type: "ide" | "cli" | "sdk" | "api" | "browser" | "utility";
  execution_mode?: "local" | "api";
  capabilities?: string[];
  config_ref?: string;
  provider?: {
    hasApiKey: boolean;
    defaultModel?: string;
  };
}

// Default local agents per ADR-005 + ADR-020: Unified Agent Execution Protocol
const LOCAL_AGENTS: AgentInfo[] = [
  {
    id: "cursor",
    name: "Cursor",
    icon: "code",
    health: "healthy",
    type: "ide",
    execution_mode: "local",
    capabilities: ["code", "terminal", "mcp"],
  },
  {
    id: "vscode",
    name: "VS Code",
    icon: "code",
    health: "healthy",
    type: "ide",
    execution_mode: "local",
    capabilities: ["code", "terminal", "extensions"],
  },
  {
    id: "antigravity",
    name: "Antigravity",
    icon: "zap",
    health: "healthy",
    type: "browser",
    execution_mode: "local",
    capabilities: ["browser", "web-scraping", "screenshot"],
  },
  {
    id: "claude-code",
    name: "Claude Code",
    icon: "terminal",
    health: "healthy",
    type: "cli",
    execution_mode: "local",
    capabilities: ["code", "terminal", "mcp", "bash"],
  },
  {
    id: "claude-sdk",
    name: "Claude SDK",
    icon: "sparkles",
    health: "healthy",
    type: "sdk",
    execution_mode: "local",
    capabilities: ["code", "reasoning", "analysis"],
  },
];

// API provider agents - derived from provider registry
function getApiAgents(): AgentInfo[] {
  const providers = Object.values(PROVIDER_REGISTRY).filter((p) => p.available);

  return providers.map((provider) => {
    // Check if API key is configured
    const envVar = provider.apiKeyEnv;
    const hasApiKey = !!process.env[envVar];

    return {
      id: provider.id,
      name: `${provider.name}`,
      icon: provider.icon.toLowerCase(),
      health: hasApiKey ? "healthy" : "unhealthy",
      type: "api" as const,
      execution_mode: "api" as const,
      capabilities: ["code", "reasoning", "analysis"],
      config_ref: `providers.${provider.id}`,
      provider: {
        hasApiKey,
        defaultModel: provider.defaultModel,
      },
    };
  });
}

const isTestEnv = process.env.NODE_ENV === "test";
const IDE_STATUS_CACHE_TTL_MS = 15000;
let cachedIdeStatus: { expiresAt: number; value: unknown | null } | null = null;
let ideStatusInflight: Promise<unknown | null> | null = null;

export function __resetIdeStatusCacheForTests() {
  cachedIdeStatus = null;
  ideStatusInflight = null;
}

function parseMode(request: NextRequest): ExecutionMode {
  const mode = request.nextUrl.searchParams.get("mode") as ExecutionMode | null;
  return mode || "local";
}

async function fetchIdeStatus(baseUrl: string): Promise<unknown | null> {
  const now = Date.now();
  if (cachedIdeStatus && cachedIdeStatus.expiresAt > now) {
    return cachedIdeStatus.value;
  }
  if (ideStatusInflight) {
    return ideStatusInflight;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 3000);

  try {
    ideStatusInflight = fetch(`${baseUrl}/api/ide/status`, {
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    })
      .then(async (statusRes) => {
        if (!statusRes.ok) {
          return null;
        }
        return await statusRes.json();
      })
      .catch(() => null)
      .finally(() => {
        ideStatusInflight = null;
      });

    const value = await ideStatusInflight;
    cachedIdeStatus = {
      value,
      expiresAt: Date.now() + IDE_STATUS_CACHE_TTL_MS,
    };
    return value;
  } finally {
    clearTimeout(timeoutId);
  }
}

function isAgentAvailable(status: any, agent: AgentInfo): boolean {
  const availableIdes = Array.isArray(status?.available_ides)
    ? status.available_ides
    : [];
  return (
    availableIdes.includes(agent.name) || status?.active_ide === agent.name
  );
}

function applyIdeHealth(
  localAgents: AgentInfo[],
  status: unknown,
): AgentInfo[] {
  if (!status || typeof status !== "object") {
    return localAgents;
  }

  return localAgents.map((agent) => {
    if (agent.type !== "ide" && agent.type !== "cli") {
      return agent;
    }

    return {
      ...agent,
      health: isAgentAvailable(status, agent) ? "healthy" : "offline",
    };
  });
}

async function withUpdatedLocalAgents(
  localAgents: AgentInfo[],
  baseUrl: string,
): Promise<AgentInfo[]> {
  try {
    const status = await fetchIdeStatus(baseUrl);
    return applyIdeHealth(localAgents, status);
  } catch (error) {
    if (!isTestEnv) {
      console.warn(
        "[agents/available] IDE status check failed, using defaults:",
        error instanceof Error ? error.message : "Unknown error",
      );
    }
    return localAgents;
  }
}

function selectAgents(
  mode: ExecutionMode,
  localAgents: AgentInfo[],
  apiAgents: AgentInfo[],
): AgentInfo[] {
  switch (mode) {
    case "api":
      return apiAgents;
    case "auto":
      return [...localAgents, ...apiAgents];
    case "local":
    default:
      return localAgents;
  }
}

function compareAutoExecutionMode(a: AgentInfo, b: AgentInfo): number {
  if (a.execution_mode === b.execution_mode) return 0;
  return a.execution_mode === "local" ? -1 : 1;
}

function compareHealth(a: AgentInfo, b: AgentInfo): number {
  if (a.health === b.health) return 0;
  return a.health === "healthy" ? -1 : 1;
}

function compareAgents(
  a: AgentInfo,
  b: AgentInfo,
  mode: ExecutionMode,
): number {
  if (mode === "auto") {
    const modeComparison = compareAutoExecutionMode(a, b);
    if (modeComparison !== 0) return modeComparison;
  }

  const healthComparison = compareHealth(a, b);
  if (healthComparison !== 0) return healthComparison;
  return a.name.localeCompare(b.name);
}

function sortAgents(agents: AgentInfo[], mode: ExecutionMode): AgentInfo[] {
  return agents.sort((a, b) => compareAgents(a, b, mode));
}

export async function GET(request: NextRequest) {
  const mode = parseMode(request);
  const baseUrl = request.nextUrl.origin;
  const localAgents =
    mode === "api"
      ? [...LOCAL_AGENTS]
      : await withUpdatedLocalAgents([...LOCAL_AGENTS], baseUrl);
  const apiAgents = getApiAgents();
  const agents = sortAgents(selectAgents(mode, localAgents, apiAgents), mode);
  const hasConfiguredApiProviders = apiAgents.some(
    (a) => a.provider?.hasApiKey,
  );

  return NextResponse.json({
    agents,
    mode,
    hasConfiguredApiProviders,
  });
}
