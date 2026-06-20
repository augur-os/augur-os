import {
  decideMcpBannerState,
  STARTUP_GRACE_MS,
  FAILURE_THRESHOLD,
} from "@/components/mcpBannerState";

/**
 * The banner used to only know ok/down/checking, so a normal cold start (the
 * Python MCP backend takes tens of seconds to boot) flashed a scary red
 * "MCP server is down" during startup. These tests pin the new "starting"
 * state: calm during the boot grace window, red "down" only for a real outage.
 */
describe("decideMcpBannerState", () => {
  const base = {
    consecutiveFailures: 1,
    hasConnectedEver: false,
    elapsedMs: 1_000,
  };

  it("returns ok on a successful probe regardless of prior failures", () => {
    expect(
      decideMcpBannerState({ ...base, outcome: "ok", consecutiveFailures: 5 }),
    ).toBe("ok");
  });

  it("shows 'starting' (not 'down') on failure during the boot grace window before first connect", () => {
    expect(
      decideMcpBannerState({
        ...base,
        outcome: "failure",
        hasConnectedEver: false,
        elapsedMs: 5_000,
      }),
    ).toBe("starting");
  });

  it("stays 'starting' even past the failure threshold while still in the grace window", () => {
    expect(
      decideMcpBannerState({
        outcome: "failure",
        consecutiveFailures: FAILURE_THRESHOLD + 3,
        hasConnectedEver: false,
        elapsedMs: STARTUP_GRACE_MS - 1,
      }),
    ).toBe("starting");
  });

  it("escalates to 'down' when startup never succeeds past the grace window", () => {
    expect(
      decideMcpBannerState({
        outcome: "failure",
        consecutiveFailures: FAILURE_THRESHOLD,
        hasConnectedEver: false,
        elapsedMs: STARTUP_GRACE_MS + 1,
      }),
    ).toBe("down");
  });

  it("does not alarm before the failure threshold once past the grace window", () => {
    expect(
      decideMcpBannerState({
        outcome: "failure",
        consecutiveFailures: 1,
        hasConnectedEver: false,
        elapsedMs: STARTUP_GRACE_MS + 1,
      }),
    ).toBe("checking");
  });

  it("treats a drop after a prior successful connect as a real outage ('down'), even within the grace window", () => {
    expect(
      decideMcpBannerState({
        outcome: "failure",
        consecutiveFailures: FAILURE_THRESHOLD,
        hasConnectedEver: true,
        elapsedMs: 2_000,
      }),
    ).toBe("down");
  });

  it("still debounces a post-connect blip below the threshold to 'checking'", () => {
    expect(
      decideMcpBannerState({
        outcome: "failure",
        consecutiveFailures: 1,
        hasConnectedEver: true,
        elapsedMs: 2_000,
      }),
    ).toBe("checking");
  });
});
