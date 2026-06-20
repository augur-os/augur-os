/**
 * ConfigPage showIf — conditional block visibility tests.
 *
 * Tests that blocks with showIf.blockHasData are hidden when the referenced
 * block has no data, and shown when it does. Blocks without showIf always render.
 */

import React from "react";
import { render, screen, act } from "@testing-library/react";
import "@testing-library/jest-dom";

// ---------------------------------------------------------------------------
// Mocks — must be declared before any imports that use them
// ---------------------------------------------------------------------------

// Track useBlockData calls by mcp_tool to return different data per block
const mockBlockData: Record<string, { data: unknown; loading: boolean; error: string | null }> = {};

jest.mock("@/lib/blocks/useBlockData", () => ({
  useBlockData: (dataSource: { mcpTool?: string } | undefined) => {
    const tool = dataSource?.mcpTool ?? "__none__";
    return mockBlockData[tool] ?? { data: null, loading: false, error: null, refetch: jest.fn(), invalidate: jest.fn() };
  },
}));

// Mock block components — render a simple div with data-testid
jest.mock("@/lib/blocks/block-resolver", () => ({
  BLOCK_COMPONENTS: new Proxy(
    {},
    {
      get: (_target, prop) => {
        if (prop === "__esModule") return false;
        // Return a simple component for every block type
        return function MockBlock(props: { instanceId: string; data?: unknown }) {
          return <div data-testid={`block-${props.instanceId}`}>mock-block</div>;
        };
      },
    },
  ),
}));

jest.mock("@/lib/blocks/custom-block-registry", () => ({
  CUSTOM_BLOCK_COMPONENTS: {},
}));

jest.mock("@/lib/stores/modeStore", () => ({
  useModeStore: (selector: (s: { mode: string }) => unknown) =>
    selector({ mode: "normal" }),
}));

jest.mock("lucide-react", () => {
  const MockIcon = ({ className }: { className?: string }) => (
    <span className={className} data-testid="icon" />
  );
  return new Proxy(
    {},
    {
      get: (_target, prop) => {
        if (prop === "__esModule") return true;
        return MockIcon;
      },
    },
  );
});

jest.mock("@/components/ErrorBoundary", () => ({
  ErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/lib/self-heal-event", () => ({
  emitClientError: jest.fn(),
}));

// Mock React Query provider — useBlockData is already mocked, but some
// transitive imports may need QueryClient
jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(() => ({ data: null, isLoading: false, error: null, refetch: jest.fn() })),
  useQueryClient: jest.fn(() => ({
    invalidateQueries: jest.fn(),
    // showIf reads block data from the query cache. Mirror the same
    // mockBlockData the rest of the suite drives, keyed off the mcp_tool
    // segment of the block-data query key (["block-data", mcpTool, ...]).
    getQueryData: jest.fn((queryKey: unknown) => {
      const tool = Array.isArray(queryKey) ? (queryKey[1] as string) : undefined;
      const entry = tool ? mockBlockData[tool] : undefined;
      return entry ? { data: entry.data } : undefined;
    }),
    getQueryCache: jest.fn(() => ({ subscribe: jest.fn(() => jest.fn()) })),
  })),
  QueryClient: jest.fn(),
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { ConfigPage } from "@/components/plugin/ConfigPage";
import { hasNonEmptyData } from "@/components/plugin/ConfigPage";
import type { PageConfig, BlockConfig } from "@/lib/blocks/flow-types";

// ---------------------------------------------------------------------------
// hasNonEmptyData unit tests
// ---------------------------------------------------------------------------

describe("hasNonEmptyData", () => {
  it("returns false for null", () => {
    expect(hasNonEmptyData(null)).toBe(false);
  });

  it("returns false for undefined", () => {
    expect(hasNonEmptyData(undefined)).toBe(false);
  });

  it("returns false for empty array", () => {
    expect(hasNonEmptyData([])).toBe(false);
  });

  it("returns true for non-empty array", () => {
    expect(hasNonEmptyData([1, 2])).toBe(true);
  });

  it("returns false for empty object", () => {
    expect(hasNonEmptyData({})).toBe(false);
  });

  it("returns true for non-empty object", () => {
    expect(hasNonEmptyData({ a: 1 })).toBe(true);
  });

  it("returns true for truthy scalar (string)", () => {
    expect(hasNonEmptyData("hello")).toBe(true);
  });

  it("returns true for truthy scalar (number)", () => {
    expect(hasNonEmptyData(42)).toBe(true);
  });

  it("returns true for zero (truthy in this context — non-null)", () => {
    expect(hasNonEmptyData(0)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// ConfigPage showIf integration tests
// ---------------------------------------------------------------------------

describe("ConfigPage showIf", () => {
  beforeEach(() => {
    // Reset mock data
    Object.keys(mockBlockData).forEach((key) => delete mockBlockData[key]);
  });

  function makeConfig(blocks: BlockConfig[]): PageConfig {
    return {
      title: "Test Page",
      icon: "LayoutDashboard",
      hub: "test",
      route: "/test",
      blocks,
    };
  }

  it("hides block when showIf.blockHasData references a block with no data", () => {
    // stats block returns null (no data)
    mockBlockData["get-stats"] = { data: null, loading: false, error: null };
    // details block has data but should be hidden because stats has no data
    mockBlockData["get-details"] = { data: [{ id: 1 }], loading: false, error: null };

    const config = makeConfig([
      { type: "stat-grid", id: "stats", mcp_tool: "get-stats", size: "full" },
      {
        type: "data-table",
        mcp_tool: "get-details",
        size: "full",
        showIf: { blockHasData: "stats" },
        title: "Details",
      },
    ]);

    render(<ConfigPage config={config} />);

    // Stats block should render (no showIf condition)
    expect(screen.getByTestId("block-flow-stat-grid-0")).toBeInTheDocument();

    // Details block should NOT render because stats has no data
    expect(screen.queryByTestId("block-flow-data-table-1")).not.toBeInTheDocument();
  });

  it("shows block when showIf.blockHasData references a block with data", () => {
    // stats block returns data
    mockBlockData["get-stats"] = { data: [{ value: 42 }], loading: false, error: null };
    // details block
    mockBlockData["get-details"] = { data: [{ id: 1 }], loading: false, error: null };

    const config = makeConfig([
      { type: "stat-grid", id: "stats", mcp_tool: "get-stats", size: "full" },
      {
        type: "data-table",
        mcp_tool: "get-details",
        size: "full",
        showIf: { blockHasData: "stats" },
        title: "Details",
      },
    ]);

    render(<ConfigPage config={config} />);

    // Both blocks should render
    expect(screen.getByTestId("block-flow-stat-grid-0")).toBeInTheDocument();
    expect(screen.getByTestId("block-flow-data-table-1")).toBeInTheDocument();
  });

  it("always renders blocks without showIf regardless of other block data", () => {
    // No data for any block
    mockBlockData["get-stats"] = { data: null, loading: false, error: null };
    mockBlockData["get-list"] = { data: null, loading: false, error: null };

    const config = makeConfig([
      { type: "stat-grid", id: "stats", mcp_tool: "get-stats", size: "full" },
      { type: "data-list", mcp_tool: "get-list", size: "full", title: "Always Visible" },
    ]);

    render(<ConfigPage config={config} />);

    // Both blocks should render — neither has showIf
    expect(screen.getByTestId("block-flow-stat-grid-0")).toBeInTheDocument();
    expect(screen.getByTestId("block-flow-data-list-1")).toBeInTheDocument();
  });

  it("hides block when referenced block has empty array data", () => {
    // stats returns empty array
    mockBlockData["get-stats"] = { data: [], loading: false, error: null };
    mockBlockData["get-details"] = { data: [{ id: 1 }], loading: false, error: null };

    const config = makeConfig([
      { type: "stat-grid", id: "stats", mcp_tool: "get-stats", size: "full" },
      {
        type: "data-table",
        mcp_tool: "get-details",
        size: "full",
        showIf: { blockHasData: "stats" },
        title: "Details",
      },
    ]);

    render(<ConfigPage config={config} />);

    // Details should be hidden — stats has empty array
    expect(screen.queryByTestId("block-flow-data-table-1")).not.toBeInTheDocument();
  });

  it("hides block when referenced block has empty object data", () => {
    // stats returns empty object
    mockBlockData["get-stats"] = { data: {}, loading: false, error: null };
    mockBlockData["get-details"] = { data: [{ id: 1 }], loading: false, error: null };

    const config = makeConfig([
      { type: "stat-grid", id: "stats", mcp_tool: "get-stats", size: "full" },
      {
        type: "data-table",
        mcp_tool: "get-details",
        size: "full",
        showIf: { blockHasData: "stats" },
        title: "Details",
      },
    ]);

    render(<ConfigPage config={config} />);

    // Details should be hidden — stats has empty object
    expect(screen.queryByTestId("block-flow-data-table-1")).not.toBeInTheDocument();
  });

  it("shows block when showIf references a block with object data", () => {
    // stats returns non-empty object
    mockBlockData["get-stats"] = { data: { total: 10, active: 5 }, loading: false, error: null };
    mockBlockData["get-details"] = { data: [{ id: 1 }], loading: false, error: null };

    const config = makeConfig([
      { type: "stat-grid", id: "stats", mcp_tool: "get-stats", size: "full" },
      {
        type: "data-table",
        mcp_tool: "get-details",
        size: "full",
        showIf: { blockHasData: "stats" },
        title: "Details",
      },
    ]);

    render(<ConfigPage config={config} />);

    // Both should render
    expect(screen.getByTestId("block-flow-stat-grid-0")).toBeInTheDocument();
    expect(screen.getByTestId("block-flow-data-table-1")).toBeInTheDocument();
  });
});
