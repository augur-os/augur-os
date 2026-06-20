/**
 * @jest-environment node
 */
import { describe, it, expect, beforeEach, afterEach, jest } from "@jest/globals";
import { StateRegistry } from "@/lib/webmcp/state-registry";
import { navigationGotoExecute, navigationStateExecute } from "@/lib/webmcp/tools/navigation";
import type { NavigationState } from "@/lib/webmcp/types";

const makeNav = (overrides: Partial<NavigationState> = {}): NavigationState => ({
  path: "/career/companies",
  hub: "career",
  activeTab: "companies",
  breadcrumbs: ["career", "companies"],
  availableTabs: [
    { label: "Companies", href: "/career/companies" },
    { label: "Jobs", href: "/career/jobs" },
  ],
  ...overrides,
});

describe("navigation.goto", () => {
  let registry: StateRegistry;
  let mockRouter: { push: ReturnType<typeof jest.fn> };

  beforeEach(() => {
    registry = new StateRegistry();
    mockRouter = { push: jest.fn() };
    (global as any).window = { __webmcpRouter: mockRouter };
  });

  afterEach(() => {
    delete (global as any).window;
  });

  it("returns FETCH_FAILED when router is not available", async () => {
    (global as any).window = {};
    const result = await navigationGotoExecute({ path: "/finance" }, registry);
    expect(result).toMatchObject({ error: true, code: "FETCH_FAILED" });
  });

  it("calls router.push with the given path", async () => {
    registry.reportNavigation(makeNav());
    const result = await navigationGotoExecute({ path: "/finance/accounts" }, registry);
    expect(mockRouter.push).toHaveBeenCalledWith("/finance/accounts");
    expect(result).toMatchObject({
      success: true,
      newPath: "/finance/accounts",
      previousPath: "/career/companies",
      hub: "finance",
    });
  });

  it("uses '/' as previousPath when no navigation state is set", async () => {
    const result = await navigationGotoExecute({ path: "/ai" }, registry);
    expect(result).toMatchObject({
      success: true,
      previousPath: "/",
      newPath: "/ai",
      hub: "ai",
    });
  });

  it("extracts hub as first path segment", async () => {
    const result = await navigationGotoExecute({ path: "/health/metrics" }, registry);
    expect((result as any).hub).toBe("health");
  });

  it("returns null hub for root path", async () => {
    const result = await navigationGotoExecute({ path: "/" }, registry);
    expect((result as any).hub).toBeNull();
  });
});

describe("navigation.state", () => {
  let registry: StateRegistry;

  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("returns FETCH_FAILED when no navigation state is set", async () => {
    const result = await navigationStateExecute({}, registry);
    expect(result).toMatchObject({ error: true, code: "FETCH_FAILED" });
  });

  it("returns navigation state when set", async () => {
    const nav = makeNav();
    registry.reportNavigation(nav);
    const result = await navigationStateExecute({}, registry);
    expect(result).toMatchObject({
      path: "/career/companies",
      hub: "career",
      activeTab: "companies",
      breadcrumbs: ["career", "companies"],
    });
  });

  it("returns updated state after reportNavigation is called again", async () => {
    registry.reportNavigation(makeNav());
    registry.reportNavigation(makeNav({ path: "/finance", hub: "finance", activeTab: null }));
    const result = await navigationStateExecute({}, registry);
    expect((result as any).hub).toBe("finance");
    expect((result as any).path).toBe("/finance");
  });

  it("returns null navigation after clear()", async () => {
    registry.reportNavigation(makeNav());
    registry.clear();
    const result = await navigationStateExecute({}, registry);
    expect(result).toMatchObject({ error: true, code: "FETCH_FAILED" });
  });
});
