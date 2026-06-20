import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";

const DASHBOARD_SURFACE = "dashboard-pty";

export interface SessionOwner {
  session_id?: string;
  surface?: string;
  pid?: number;
  host?: string;
  cli_id?: string;
  started_at?: string;
  last_seen?: string;
  proc_start_time?: string | null;
  [key: string]: unknown;
}

export interface SessionOwnerConflictPayload {
  error: string;
  code: "SESSION_OWNED_ELSEWHERE";
  sessionId: string;
  owner: SessionOwner;
}

export class SessionOwnerConflictError extends Error {
  owner: SessionOwner;
  sessionId: string;

  constructor(sessionId: string, owner: SessionOwner) {
    super(buildSessionOwnerConflictMessage(owner));
    this.name = "SessionOwnerConflictError";
    this.sessionId = sessionId;
    this.owner = owner;
  }
}

export function isSessionOwnerConflictError(
  error: unknown,
): error is SessionOwnerConflictError {
  return error instanceof SessionOwnerConflictError;
}

function parseToolJson(raw: string, toolName: string): Record<string, unknown> {
  const text = raw.trim();
  if (!text) {
    throw new Error(`${toolName} returned an empty response`);
  }
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch (error) {
    throw new Error(`${toolName} returned invalid JSON`, { cause: error });
  }
  throw new Error(`${toolName} returned a non-object response`);
}

async function callSessionOwnerTool(
  toolName: string,
  args: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const result = await callMCPTool(toolName, args);
  const text = MCPBridge.extractText(result);
  return parseToolJson(text, toolName);
}

function ownerFrom(value: unknown): SessionOwner | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as SessionOwner;
}

function buildSessionOwnerConflictMessage(owner: SessionOwner): string {
  const surface =
    owner.surface === "native-terminal"
      ? "native terminal"
      : owner.surface === DASHBOARD_SURFACE
        ? "dashboard"
        : "another surface";
  const pid = typeof owner.pid === "number" ? ` pid ${owner.pid}` : "";
  const host =
    typeof owner.host === "string" && owner.host.length > 0
      ? ` on ${owner.host}`
      : "";
  return `Session is already open in ${surface}${pid}${host}.`;
}

export function sessionOwnerConflictPayload(
  sessionId: string,
  owner: SessionOwner,
): SessionOwnerConflictPayload {
  return {
    error: buildSessionOwnerConflictMessage(owner),
    code: "SESSION_OWNED_ELSEWHERE",
    sessionId,
    owner,
  };
}

export function isSameDashboardOwner(owner: SessionOwner, pid: number): boolean {
  return owner.surface === DASHBOARD_SURFACE && owner.pid === pid;
}

export async function claimDashboardSessionOwner({
  sessionId,
  pid,
  cliId,
}: {
  sessionId: string;
  pid: number;
  cliId: string;
}): Promise<SessionOwner | null> {
  const response = await callSessionOwnerTool("session-claim", {
    session_id: sessionId,
    surface: DASHBOARD_SURFACE,
    pid,
    cli_id: cliId,
  });

  if (response.ok === true) {
    return ownerFrom(response.owner);
  }

  const conflict = ownerFrom(response.conflict);
  if (conflict) {
    throw new SessionOwnerConflictError(sessionId, conflict);
  }

  throw new Error(`session-claim failed for ${sessionId}`);
}

export async function releaseDashboardSessionOwner({
  sessionId,
  pid,
}: {
  sessionId: string;
  pid: number;
}): Promise<boolean> {
  const response = await callSessionOwnerTool("session-release", {
    session_id: sessionId,
    surface: DASHBOARD_SURFACE,
    pid,
  });
  if (response.ok !== true) {
    throw new Error(`session-release failed for ${sessionId}`);
  }
  return response.released === true;
}

export async function releaseSessionOwner({
  sessionId,
  surface,
  pid,
}: {
  sessionId: string;
  surface: string;
  pid?: number;
}): Promise<boolean> {
  const response = await callSessionOwnerTool("session-release", {
    session_id: sessionId,
    surface,
    ...(typeof pid === "number" ? { pid } : {}),
  });
  if (response.ok !== true) {
    throw new Error(`session-release failed for ${sessionId}`);
  }
  return response.released === true;
}

export async function getSessionOwner(
  sessionId: string,
): Promise<SessionOwner | null> {
  const response = await callSessionOwnerTool("session-status", {
    session_id: sessionId,
  });
  if (response.ok !== true) {
    throw new Error(`session-status failed for ${sessionId}`);
  }
  return ownerFrom(response.owner);
}
