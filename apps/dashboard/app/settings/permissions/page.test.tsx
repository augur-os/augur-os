import { render, waitFor } from "@testing-library/react";
import Page from "./page";

// Mock fetch for PermissionsTab
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("PermissionsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockResolvedValue({
      json: () =>
        Promise.resolve({ ok: true, permissions: [], platform: "darwin" }),
    });
  });

  it("renders without crashing", async () => {
    render(<Page />);
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });
    expect(true).toBeTruthy();
  });
});
