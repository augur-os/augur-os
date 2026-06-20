/**
 * @jest-environment node
 */

import fs from "fs";
import path from "path";

jest.mock("@/lib/blocks/generated-block-registry", () => ({
  BLOCK_LIST: [
    {
      id: "brain:notes",
      title: "Notes",
      hub: "workspace",
      category: "knowledge",
      icon: "Notebook",
    },
    {
      id: "command:actions",
      title: "Actions",
      hub: "command",
      category: "operations",
      icon: "Zap",
    },
  ],
}));

describe("GET /api/blocks/catalog", () => {
  it("exposes the block registry as a JSON array", async () => {
    const routePath = path.join(
      process.cwd(),
      "app/api/blocks/catalog/route.ts",
    );

    if (!fs.existsSync(routePath)) {
      expect(fs.existsSync(routePath)).toBe(true);
      return;
    }

    const { GET } = await import("@/app/api/blocks/catalog/route");
    const res = await GET();
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body).toEqual([
      expect.objectContaining({ id: "brain:notes", title: "Notes" }),
      expect.objectContaining({ id: "command:actions", title: "Actions" }),
    ]);
  });
});
