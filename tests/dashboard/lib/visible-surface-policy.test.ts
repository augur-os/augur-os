import {
  mayUseVisibleSurface,
  resolveVisibleSurfacePolicy,
} from "@/lib/visible-surface-policy";

describe("visible surface policy", () => {
  const originalEnv = process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;

  afterEach(() => {
    if (originalEnv === undefined) {
      delete process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;
    } else {
      process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY = originalEnv;
    }
  });

  it("defaults to visible allowed unless the explicit deny policy is set", () => {
    delete process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;
    expect(resolveVisibleSurfacePolicy()).toBe("visible_allowed");

    process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY = "anything-else";
    expect(resolveVisibleSurfacePolicy()).toBe("visible_allowed");
  });

  it("allows only user-triggered visible actions when visible surfaces are allowed", () => {
    expect(mayUseVisibleSurface("navigate", "user-triggered", "visible_allowed")).toBe(true);
    expect(mayUseVisibleSurface("send-ide-prompt", "user-triggered", "visible_allowed")).toBe(true);
    expect(mayUseVisibleSurface("open-window", "validation", "visible_allowed")).toBe(false);
    expect(mayUseVisibleSurface("navigate", "self-heal", "visible_allowed")).toBe(false);
  });

  it("denies all visible actions when visible mutations are disabled", () => {
    process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY = "no_visible_mutation";

    expect(resolveVisibleSurfacePolicy()).toBe("no_visible_mutation");
    expect(mayUseVisibleSurface("navigate", "validation")).toBe(false);
    expect(mayUseVisibleSurface("send-ide-prompt", "user-triggered")).toBe(false);
    expect(mayUseVisibleSurface("open-window", "self-heal")).toBe(false);
  });
});
