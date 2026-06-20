import {
  SELECTION_ACTIONS,
  selectionActionsForViewMode,
} from "@/lib/browse/selectionActions";
import type { BrowseItem } from "@/lib/browse/types";

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));
import { mcpCall } from "@/lib/mcp/client";

function noteItem(id: string): BrowseItem {
  return {
    id,
    title: `Note ${id}`,
    description: "",
    hub: "workspace",
    primaryAction: { label: "Open", type: "open-file", target: `notes/${id}.md` },
    path: `notes/${id}.md`,
    metadata: { source_path: `notes/${id}.md`, journey_category: "sources", source_root: "private" },
  };
}

describe("selectionActionsForViewMode", () => {
  it("offers send-to-chat everywhere", () => {
    for (const vm of ["notes", "skills", "api-routes", "documents"] as const) {
      expect(selectionActionsForViewMode(vm).map((a) => a.id)).toContain("send-to-chat");
    }
  });

  it("offers summarize on content tabs only", () => {
    expect(selectionActionsForViewMode("notes").map((a) => a.id)).toContain("summarize");
    expect(selectionActionsForViewMode("documents").map((a) => a.id)).toContain("summarize");
    expect(selectionActionsForViewMode("skills").map((a) => a.id)).not.toContain("summarize");
  });

  it("offers sweep on notes documents and pages", () => {
    expect(selectionActionsForViewMode("notes").map((a) => a.id)).toContain("sweep");
    expect(selectionActionsForViewMode("documents").map((a) => a.id)).toContain("sweep");
    expect(selectionActionsForViewMode("pages").map((a) => a.id)).toContain("sweep");
  });
});

describe("send-to-chat / summarize build", () => {
  const send = SELECTION_ACTIONS.find((a) => a.id === "send-to-chat")!;
  const summarize = SELECTION_ACTIONS.find((a) => a.id === "summarize")!;

  it("send-to-chat bundles items with the default placeholder", async () => {
    const result = await send.build([noteItem("a")], "notes");
    expect(result.initialPrompt).toContain("Selected 1 item from Browse · Notes:");
    expect(result.initialPrompt).toContain("<describe what you'd like to do with these>");
  });

  it("summarize injects a synthesis instruction", async () => {
    const result = await summarize.build([noteItem("a"), noteItem("b")], "notes");
    expect(result.initialPrompt).toContain("Summarize and synthesize");
    expect(result.initialPrompt).not.toContain("<describe what");
  });
});

describe("sweep build", () => {
  const sweep = SELECTION_ACTIONS.find((a) => a.id === "sweep")!;
  beforeEach(() => (mcpCall as jest.Mock).mockReset());

  it("creates a selection and returns the sweep prompt", async () => {
    (mcpCall as jest.Mock).mockResolvedValue({ success: true, selection_id: "sel-123", refusal_count: 0 });
    const result = await sweep.build([noteItem("a"), noteItem("b")], "notes");
    expect(mcpCall).toHaveBeenCalledWith("hygiene-create-selection", expect.objectContaining({
      targets: expect.any(Array),
    }));
    expect(result.initialPrompt).toContain("Selection id: sel-123");
    expect(result.dropped).toBe(0);
  });

  it("returns an empty prompt and drops all when nothing is archivable", async () => {
    const bare: BrowseItem = {
      id: "x", title: "X", description: "", hub: "workspace",
      primaryAction: { label: "Open", type: "open-file", target: "" },
    };
    const result = await sweep.build([bare], "notes");
    expect(result.initialPrompt).toBe("");
    expect(result.dropped).toBe(1);
    expect(mcpCall).not.toHaveBeenCalled();
  });

  it("throws when selection creation fails", async () => {
    (mcpCall as jest.Mock).mockResolvedValue({ success: false, error: "boom" });
    await expect(sweep.build([noteItem("a")], "notes")).rejects.toThrow("boom");
  });
});
