/**
 * Pure decision logic for the global MCP status banner.
 *
 * Extracted from McpStatusBanner so the cold-start behavior is unit-testable.
 *
 * Background: the dashboard MCP bridge spawns a Python backend that takes tens
 * of seconds to boot (imports + registering ~114 tools across 62 skills). The
 * old banner only knew ok/down/checking, so during a normal cold start the
 * health probe failed and it flashed a red "MCP server is down — data
 * unavailable" — alarming during what is just startup. This adds a calm
 * "starting" state: during the boot grace window (before the first successful
 * connect) probe failures render as "MCP starting…", and the red "down" alarm
 * is reserved for a genuine outage (startup that never succeeds past the grace
 * window, or a drop after a prior successful connect).
 */

export type McpBannerState = "ok" | "starting" | "down" | "checking";

/**
 * How long after mount, with no successful connect yet, we treat failures as
 * "starting" rather than "down". Sized to comfortably cover an observed cold
 * start (~tens of seconds, worst case ~50s on a loaded Windows box) so a normal
 * boot never flashes the red alarm.
 */
export const STARTUP_GRACE_MS = 90_000;

/** Consecutive failures required before alarming once outside the grace window. */
export const FAILURE_THRESHOLD = 2;

export interface BannerDecisionInput {
  /** Outcome of the most recent health probe. */
  outcome: "ok" | "failure";
  /** Consecutive failure count, including the current probe if it failed. */
  consecutiveFailures: number;
  /** Whether a probe has ever succeeded since mount. */
  hasConnectedEver: boolean;
  /** Milliseconds since the banner mounted. */
  elapsedMs: number;
  startupGraceMs?: number;
  failureThreshold?: number;
}

/**
 * Decide the banner state for a probe outcome. Pure and synchronous.
 */
export function decideMcpBannerState(input: BannerDecisionInput): McpBannerState {
  const graceMs = input.startupGraceMs ?? STARTUP_GRACE_MS;
  const threshold = input.failureThreshold ?? FAILURE_THRESHOLD;

  if (input.outcome === "ok") {
    return "ok";
  }

  // Failure. A backend that has never connected and is still inside the boot
  // grace window is starting up, not down — stay calm.
  const stillStartingUp = !input.hasConnectedEver && input.elapsedMs < graceMs;
  if (stillStartingUp) {
    return "starting";
  }

  // Outside startup (grace elapsed, or it had connected before): only alarm
  // after enough consecutive failures to rule out a transient probe race.
  if (input.consecutiveFailures >= threshold) {
    return "down";
  }
  return "checking";
}
