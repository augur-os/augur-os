/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { WikiMaintenancePanel } from "@/features/pages/workspace/memory/components/WikiMaintenancePanel";

const mockMcpCall = jest.fn();
const mockRunAction = jest.fn();

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({
    runAction: (...args: unknown[]) => mockRunAction(...args),
    isExecuting: false,
    lastActionId: null,
    result: null,
  }),
}));

describe("WikiMaintenancePanel", () => {
  beforeEach(() => {
    mockMcpCall.mockReset().mockResolvedValue({
      success: true,
      message: "Prepared 20 source cards for concept extraction.",
    });
    mockRunAction.mockReset();
  });

  it("runs the bounded wiki-update MCP action instead of opening an IDE prompt", async () => {
    render(
      <WikiMaintenancePanel
        summary={{
          avgQualityScore: 94.5,
          rewriteCandidates: 0,
          avgOutgoingLinksPerPage: 1.99,
          isolatedPages: 39,
        }}
        candidates={[]}
        totalCandidates={0}
        isLoading={false}
        error={null}
        onRefresh={jest.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /update wiki/i }));

    await waitFor(() => {
      expect(mockMcpCall).toHaveBeenCalledWith("wiki-update", { limit: 20 });
    });
    expect(mockRunAction).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("Prepared 20 source cards");
  });
});
