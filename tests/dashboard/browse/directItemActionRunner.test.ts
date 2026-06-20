import { runDirectItemAction } from "@/lib/browse/directItemActionRunner";
import type { DirectItemAction } from "@/lib/browse/itemActions";

const item = {
  id: "note-1",
  title: "Research Note",
  path: "/vault/notes/research.md",
  hub: "workspace",
  metadata: {
    owner: "ingest",
  },
};

describe("runDirectItemAction", () => {
  it("resolves item placeholders, calls the MCP tool, and invalidates declared keys", async () => {
    const action: DirectItemAction = {
      id: "note-enrich",
      label: "Enrich",
      icon: "Sparkles",
      kind: "direct",
      tool: "enrich-article",
      args: {
        note_path: "{path}",
        label: "{title}",
        owner: "{metadata.owner}",
      },
      invalidates: ["browse-index", "knowledge-documents"],
    };
    const callTool = jest.fn().mockResolvedValue({ success: true });
    const invalidate = jest.fn();

    const result = await runDirectItemAction(action, item, { callTool, invalidate });

    expect(result.status).toBe("success");
    expect(callTool).toHaveBeenCalledWith("enrich-article", {
      note_path: "/vault/notes/research.md",
      label: "Research Note",
      owner: "ingest",
    });
    expect(invalidate).toHaveBeenCalledTimes(2);
    expect(invalidate).toHaveBeenNthCalledWith(1, "browse-index");
    expect(invalidate).toHaveBeenNthCalledWith(2, "knowledge-documents");
  });

  it("does not call a confirmed action when the user cancels", async () => {
    const action: DirectItemAction = {
      id: "document-index",
      label: "Index",
      icon: "RefreshCw",
      kind: "direct",
      tool: "index-documents",
      confirm: true,
    };
    const callTool = jest.fn();

    const result = await runDirectItemAction(action, item, {
      callTool,
      confirm: jest.fn(() => false),
    });

    expect(result.status).toBe("cancelled");
    expect(callTool).not.toHaveBeenCalled();
  });

  it("reports MCP false-success responses as action errors without invalidating", async () => {
    const action: DirectItemAction = {
      id: "skill-audit",
      label: "Audit",
      icon: "Search",
      kind: "direct",
      tool: "scan-skill-structure",
      invalidates: ["skill-health"],
    };
    const callTool = jest.fn().mockResolvedValue({ success: false, error: "scanner failed" });
    const invalidate = jest.fn();

    const result = await runDirectItemAction(action, item, { callTool, invalidate });

    expect(result.status).toBe("error");
    expect(result.error?.message).toBe("scanner failed");
    expect(invalidate).not.toHaveBeenCalled();
  });

  it("does not report LLM-assisted payloads as completed direct mutations", async () => {
    const action: DirectItemAction = {
      id: "note-enrich",
      label: "Enrich",
      icon: "Sparkles",
      kind: "direct",
      tool: "enrich-article",
      invalidates: ["browse-index"],
    };
    const callTool = jest.fn().mockResolvedValue({
      needs_llm: true,
      task: "enrich-article",
      submit_tool: "submit-enrich-article-result",
    });
    const invalidate = jest.fn();
    const onSuccess = jest.fn();
    const onError = jest.fn();

    const result = await runDirectItemAction(action, item, {
      callTool,
      invalidate,
      onSuccess,
      onError,
    });

    expect(result.status).toBe("error");
    expect(result.error?.message).toContain("requires AI handoff");
    expect(invalidate).not.toHaveBeenCalled();
    expect(onSuccess).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(expect.stringContaining("requires AI handoff"), undefined);
  });
});
