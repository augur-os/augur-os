/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

import type { SetupStatus } from "@/features/setup/types";

const mockMcpCall = jest.fn();

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

function status(overrides: Partial<SetupStatus> = {}): SetupStatus {
  return {
    version: 1,
    computed_at: "2026-05-30T00:00:00Z",
    total: 12,
    completed: 11,
    pct: 92,
    state: "alert",
    ever_completed: true,
    phases: [],
    ...overrides,
  };
}

beforeEach(() => {
  mockMcpCall.mockReset();
});

it("refreshes cached setup alerts before rendering the sidebar chip", async () => {
  mockMcpCall
    .mockResolvedValueOnce(status())
    .mockResolvedValueOnce(status({ completed: 12, pct: 100, state: "chip" }));

  const { SetupWidget } = await import("@/features/setup/SetupWidget");

  render(<SetupWidget variant="sidebar" />);

  await waitFor(() => expect(mockMcpCall).toHaveBeenCalledTimes(2));

  expect(mockMcpCall).toHaveBeenNthCalledWith(1, "get-setup-status", { skip_cache: false });
  expect(mockMcpCall).toHaveBeenNthCalledWith(2, "get-setup-status", { skip_cache: true });
  expect(screen.getByRole("button", { name: "Setup complete" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Setup needs attention" })).not.toBeInTheDocument();
});
