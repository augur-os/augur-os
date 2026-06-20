import { render, screen } from '@testing-library/react';
import { createQueryWrapper } from '../../../helpers/component-test-utils';

const mockUseBlockData = jest.fn(() => ({
  data: null,
  loading: false,
  error: null,
  invalidate: jest.fn(),
  refetch: jest.fn(),
}));

// Mock useActionRunner for ActionBarBlock config-actions test
jest.mock('@/hooks/useActionRunner', () => ({
  useActionRunner: () => ({ runAction: jest.fn(), isExecuting: false }),
}));

// Mock useBlockData so blocks don't fire real fetches
jest.mock('@/lib/blocks/useBlockData', () => ({
  useBlockData: (...args: unknown[]) => mockUseBlockData(...args),
}));

const BLOCK_TYPES = [
  'StatCardBlock', 'StatGridBlock', 'DataListBlock', 'DataTableBlock',
  'ActionBarBlock', 'CardGridBlock', 'ChartBlock', 'MarkdownBlock',
  'CalendarBlock', 'ActivityFeedBlock', 'NotesBlock', 'EmbedBlock',
  'OpsBoardBlock', 'ProgressBlock',
];

const { queryClient, Wrapper } = createQueryWrapper();

describe('Block type components', () => {
  afterEach(() => {
    queryClient.clear();
    mockUseBlockData.mockReset();
    mockUseBlockData.mockReturnValue({
      data: null,
      loading: false,
      error: null,
      invalidate: jest.fn(),
      refetch: jest.fn(),
    });
  });

  for (const name of BLOCK_TYPES) {
    it(`${name} renders without crashing`, async () => {
      const mod = await import(`@/components/blocks/types/${name}`);
      const Component = mod.default;
      render(
        <Component
          instanceId="test-1"
          config={{}}
          mode="compact"
          onExpand={jest.fn()}
        />,
        { wrapper: Wrapper },
      );
      expect(document.body.innerHTML.length).toBeGreaterThan(0);
    });
  }
});

describe("StatGridBlock object payloads", () => {
  it("renders object-shaped MCP status payloads as stats", async () => {
    mockUseBlockData.mockReturnValueOnce({
      data: {
        vault_exists: true,
        obsidian_configured: false,
        note_count: 12,
        total_size_bytes: 2048,
      },
      loading: false,
      error: null,
      invalidate: jest.fn(),
      refetch: jest.fn(),
    });

    const mod = await import("@/components/blocks/types/StatGridBlock");
    const StatGridBlock = mod.default;
    render(
      <StatGridBlock
        instanceId="vault-status"
        config={{ title: "Vault Health Signals" }}
        dataSource={{ mcpTool: "vault-status" }}
        mode="compact"
      />,
      { wrapper: Wrapper },
    );

    expect(screen.queryByText("No stats")).not.toBeInTheDocument();
    expect(screen.getByText("Note Count")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("Vault")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
  });
});

describe("ActionBarBlock config actions", () => {
  it("renders actions from config.actions when no MCP data", async () => {
    const mod = await import("@/components/blocks/types/ActionBarBlock");
    const ActionBarBlock = mod.default;
    render(
      <ActionBarBlock
        instanceId="test-ab"
        config={{
          title: "Actions",
          actions: [
            { id: "run", label: "Run Task", dispatch: "fire" },
          ],
        }}
        mode="compact"
      />,
      { wrapper: Wrapper },
    );
    expect(screen.getByText("Run Task")).toBeInTheDocument();
  });

  it("renders direct action buttons as touch-sized controls", async () => {
    const mod = await import("@/components/blocks/types/ActionBarBlock");
    const ActionBarBlock = mod.default;
    render(
      <ActionBarBlock
        instanceId="test-ab-touch"
        config={{
          title: "Actions",
          actions: [
            { id: "scaffold", label: "Scaffold Vault", dispatch: "fire", mcp_tool: "vault-scaffold" },
          ],
        }}
        mode="compact"
      />,
      { wrapper: Wrapper },
    );

    expect(screen.getByRole("button", { name: /scaffold vault/i })).toHaveClass("min-h-[44px]");
  });
});
