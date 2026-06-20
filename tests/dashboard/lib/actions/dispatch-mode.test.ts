import {
  normalizeDispatchMode,
  resolveAutoDispatchMode,
} from "@/lib/actions/dispatch-mode";

describe("dispatch-mode helpers", () => {
  it("normalizes deprecated api dispatch to oneshot", () => {
    expect(normalizeDispatchMode("api")).toBe("oneshot");
  });

  it("leaves supported dispatch modes unchanged", () => {
    expect(normalizeDispatchMode("ide")).toBe("ide");
    expect(normalizeDispatchMode("chat")).toBe("chat");
    expect(normalizeDispatchMode("oneshot")).toBe("oneshot");
  });

  it("prefers ide for auto dispatch when an IDE is available", () => {
    expect(resolveAutoDispatchMode({ hasIde: true })).toBe("ide");
  });

  it("falls back to oneshot when no IDE is available", () => {
    expect(resolveAutoDispatchMode({ hasIde: false })).toBe("oneshot");
  });
});
