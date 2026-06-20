/**
 * @jest-environment jsdom
 */
import { renderHook } from "@testing-library/react";

const mockUseQuery = jest.fn();
const mockMcpCall = jest.fn();

jest.mock("@tanstack/react-query", () => ({
  keepPreviousData: "keep-previous-data",
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

import { useMcpQuery } from "@/lib/mcp/useMcpQuery";

describe("useMcpQuery", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseQuery.mockReturnValue({
      data: { enabled: true },
      status: "success",
      error: null,
      refetch: jest.fn(),
    });
  });

  it("passes refetchInterval through to React Query", () => {
    renderHook(() =>
      useMcpQuery<{ enabled: boolean }>(
        "airplane-status",
        "get-local-backend-status",
        "static",
        { refetchInterval: 5000 },
      ),
    );

    expect(mockUseQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["airplane-status", "get-local-backend-status"],
        refetchInterval: 5000,
      }),
    );
  });
});
