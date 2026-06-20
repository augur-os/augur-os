/**
 * @jest-environment jsdom
 */
import { render } from "@testing-library/react";
import "@testing-library/jest-dom";

const mockUseMcpHealth = jest.fn();

jest.mock("@/hooks/useMcpHealth", () => ({
  useMcpHealth: (...args: unknown[]) => mockUseMcpHealth(...args),
}));

import McpHealthProvider from "@/features/components/McpHealthProvider";

describe("McpHealthProvider", () => {
  beforeEach(() => {
    mockUseMcpHealth.mockClear();
  });

  it("keeps MCP health warnings visible to the user", () => {
    render(<McpHealthProvider />);

    expect(mockUseMcpHealth).toHaveBeenCalledWith(
      expect.objectContaining({
        enablePolling: true,
        showToasts: true,
      }),
    );
  });
});
