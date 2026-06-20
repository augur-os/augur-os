import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createQueryWrapper } from "../helpers/component-test-utils";

const mockRunAction = jest.fn().mockResolvedValue({ type: "success", message: "Done" });
jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({ runAction: mockRunAction, isExecuting: false }),
}));

jest.mock("@/lib/blocks/useBlockData", () => ({
  useBlockData: () => ({
    data: [
      { id: "1", title: "Software Engineer", company: "Acme", status: "active" },
      { id: "2", title: "Product Manager", company: "Beta", status: "inbox" },
    ],
    loading: false,
    error: null,
  }),
}));

jest.mock("@/lib/blocks/custom-block-registry", () => ({
  CUSTOM_BLOCK_COMPONENTS: {},
}));

jest.mock("@/lib/stores/modeStore", () => ({
  useModeStore: (sel: any) => sel({ mode: "standard" }),
}));

// Mock block-resolver to return ActionBarBlock directly (not via next/dynamic)
// This lets us test the full ConfigPage → ActionBarBlock → modal flow synchronously
jest.mock("@/lib/blocks/block-resolver", () => {
  const ActionBarBlock = require("@/components/blocks/types/ActionBarBlock").default;
  return {
    BLOCK_COMPONENTS: {
      "action-bar": ActionBarBlock,
      "data-table": function MockDataTable() {
        return <div data-testid="mock-data-table">data-table</div>;
      },
    },
    resolveBlockComponent: (type: string) => null,
    getBlockManifest: () => null,
  };
});

jest.mock("lucide-react", () => {
  const MockIcon = ({ className }: { className?: string }) => (
    <span className={className} data-testid="mock-icon" />
  );
  return new Proxy(
    {},
    {
      get: (_target: object, prop: string | symbol) => {
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

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(() => ({ data: null, isLoading: false, error: null, refetch: jest.fn() })),
  useQueryClient: jest.fn(() => ({
    invalidateQueries: jest.fn(),
    getQueryData: jest.fn(),
    getQueryCache: jest.fn(() => ({ subscribe: jest.fn(() => jest.fn()) })),
  })),
  QueryClient: jest.fn(),
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { ConfigPage } from "@/components/plugin/ConfigPage";
import type { PageConfig } from "@/lib/blocks/flow-types";

const { Wrapper } = createQueryWrapper();

describe("YAML page with modal form (integration)", () => {
  beforeEach(() => { mockRunAction.mockClear(); });

  it("action-bar button with fields opens form modal and dispatches", async () => {
    const user = userEvent.setup();
    const config: PageConfig = {
      title: "Pipeline",
      icon: "Briefcase",
      hub: "career",
      route: "pipeline",
      blocks: [
        {
          type: "action-bar",
          actions: [
            {
              id: "add-job",
              label: "Add Job",
              dispatch: "fire",
              mcp_tool: "add-career-job",
              fields: [
                { name: "title", label: "Job Title", type: "text", required: true },
                { name: "company", label: "Company", type: "text", required: true },
              ],
            },
          ],
        },
        {
          type: "data-table",
          mcp_tool: "list-career-jobs",
          search: { enabled: true, fields: ["title", "company"] },
        },
      ],
    };

    render(<ConfigPage config={config} skillId="career" />, { wrapper: Wrapper });

    // Click "Add Job" button — should open modal
    await user.click(screen.getByText("Add Job"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText("Job Title")).toBeInTheDocument();
    expect(screen.getByLabelText("Company")).toBeInTheDocument();

    // Fill form and submit
    await user.type(screen.getByLabelText("Job Title"), "Designer");
    await user.type(screen.getByLabelText("Company"), "DesignCo");
    await user.click(screen.getByRole("button", { name: /run action/i }));

    await waitFor(() => {
      expect(mockRunAction).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "add-job",
          dispatch: "fire",
          args: expect.objectContaining({
            title: "Designer",
            company: "DesignCo",
          }),
        }),
      );
    });
  });
});
