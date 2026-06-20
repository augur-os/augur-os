/**
 * @jest-environment node
 */

const mockStorage = {
  get: jest.fn(),
  getOrCreateHubOverview: jest.fn(),
  update: jest.fn(),
  delete: jest.fn(),
};

jest.mock("@/lib/blocks/view-storage", () => ({
  ViewStorage: jest.fn(() => mockStorage),
}));

describe("GET /api/views/[id]", () => {
  beforeEach(() => {
    jest.resetModules();
    mockStorage.get.mockReset();
    mockStorage.getOrCreateHubOverview.mockReset();
    mockStorage.update.mockReset();
    mockStorage.delete.mockReset();
  });

  it("auto-creates canonical hub overview views instead of returning 404", async () => {
    mockStorage.get.mockReturnValue(null);
    mockStorage.getOrCreateHubOverview.mockReturnValue({
      id: "hub-life-overview",
      title: "life Overview",
      pinned: false,
      createdAt: "2026-04-07T11:00:00.000Z",
      updatedAt: "2026-04-07T11:00:00.000Z",
      layout: { columns: 12, rowHeight: 80 },
      blocks: [],
    });

    const { GET } = await import("@/app/api/views/[id]/route");
    const res = await GET(new Request("http://localhost/api/views/hub-life-overview"), {
      params: Promise.resolve({ id: "hub-life-overview" }),
    });
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(mockStorage.get).toHaveBeenCalledWith("hub-life-overview");
    expect(mockStorage.getOrCreateHubOverview).toHaveBeenCalledWith(
      "hub-life-overview",
    );
    expect(body.id).toBe("hub-life-overview");
  });

  it("still returns 404 for non-canonical missing views", async () => {
    mockStorage.get.mockReturnValue(null);

    const { GET } = await import("@/app/api/views/[id]/route");
    const res = await GET(new Request("http://localhost/api/views/custom-missing"), {
      params: Promise.resolve({ id: "custom-missing" }),
    });

    expect(res.status).toBe(404);
    expect(mockStorage.getOrCreateHubOverview).not.toHaveBeenCalled();
  });
});
