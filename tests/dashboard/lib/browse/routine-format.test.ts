import { formatCadence, formatRelativeTime, humanizeTokens } from "@/lib/browse/routine-format";

describe("routine-format helpers", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(Date.parse("2026-05-11T10:00:00Z"));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("formats cadence by cadence type", () => {
    expect(formatCadence({ type: "interval", spec: "every 12h" })).toBe("every 12h");
    expect(formatCadence({ type: "cron", spec: "0 3 * * *" })).toBe("0 3 * * *");
    expect(formatCadence({ type: "logon", spec: "ignored" })).toBe("on logon");
    expect(formatCadence({ type: "event", spec: "triggered by daemon-service or other" })).toBe(
      "triggered by daemon-service or other",
    );
  });

  it("formats relative time without hiding missing data", () => {
    expect(formatRelativeTime(null)).toBe("never");
    expect(formatRelativeTime(undefined)).toBe("never");
    expect(formatRelativeTime("not-a-date")).toBe("never");
    expect(formatRelativeTime("2026-05-11T09:59:30Z")).toBe("just now");
    expect(formatRelativeTime("2026-05-11T09:30:00Z")).toBe("30m ago");
    expect(formatRelativeTime("2026-05-11T05:00:00Z")).toBe("5h ago");
    expect(formatRelativeTime("2026-05-08T10:00:00Z")).toBe("3d ago");
  });

  it("humanizes token counts", () => {
    expect(humanizeTokens(null)).toBe("—");
    expect(humanizeTokens(undefined)).toBe("—");
    expect(humanizeTokens(42)).toBe("42");
    expect(humanizeTokens(250_000)).toBe("250K");
    expect(humanizeTokens(2_500_000)).toBe("2.5M");
  });
});
