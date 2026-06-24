import { selectionActionsForViewMode } from "@/lib/browse/selectionActions";

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));

describe("delete selection action", () => {
  it("appears on user-content tabs", () => {
    for (const vm of ["notes", "documents", "pages", "wiki", "archive"] as const) {
      expect(selectionActionsForViewMode(vm).some((a) => a.id === "delete")).toBe(true);
    }
  });

  it("is absent on code/system tabs", () => {
    for (const vm of ["skills", "commands", "adrs", "mcp-tools", "tests"] as const) {
      expect(selectionActionsForViewMode(vm).some((a) => a.id === "delete")).toBe(false);
    }
  });
});
