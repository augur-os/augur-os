/**
 * @jest-environment jsdom
 */
import { act, renderHook } from "@testing-library/react";

const mockMcpCall = jest.fn();

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

function makeDraft(id: string) {
  return {
    ok: true,
    draft_id: id,
    base_hash: "hash-1",
    entries: { "skill:geo-audit": { export_to: ["claude"] } },
    diff: "diff text",
    impact: { removed_from: { "skill:geo-audit": ["codex"] } },
  };
}

describe("useCapabilityPolicy", () => {
  beforeEach(() => {
    mockMcpCall.mockReset();
  });

  it("refreshReport loads and stores the capability inventory report", async () => {
    const report = {
      ok: true,
      counts: { total: 1 },
      records: [{ id: "skill:geo-audit" }],
    };
    mockMcpCall.mockResolvedValueOnce(report);

    const { useCapabilityPolicy } = await import("@/lib/browse/useCapabilityPolicy");
    const { result } = renderHook(() => useCapabilityPolicy());

    await act(async () => {
      await result.current.refreshReport();
    });

    expect(mockMcpCall).toHaveBeenCalledWith("capability-inventory-report", {});
    expect(result.current.report).toEqual(report);
    expect(result.current.error).toBeNull();
  });

  it("draftPolicy drafts and stores a reviewed policy change", async () => {
    const draft = makeDraft("draft-1");
    mockMcpCall.mockResolvedValueOnce(draft);

    const { useCapabilityPolicy } = await import("@/lib/browse/useCapabilityPolicy");
    const { result } = renderHook(() => useCapabilityPolicy());

    await act(async () => {
      await result.current.draftPolicy({
        action: "keep_only_in_client",
        capabilityIds: ["skill:geo-audit"],
        params: { target_client: "claude" },
      });
    });

    expect(mockMcpCall).toHaveBeenCalledWith("capability-policy-draft", {
      action: "keep_only_in_client",
      capability_ids: ["skill:geo-audit"],
      params: { target_client: "claude" },
    });
    expect(result.current.draft).toEqual(draft);
  });

  it("draftPolicy clears a stale draft when the next draft fails", async () => {
    const draft = makeDraft("draft-1");
    mockMcpCall.mockResolvedValueOnce(draft);
    mockMcpCall.mockResolvedValueOnce({ ok: false, error: "draft failed" });

    const { useCapabilityPolicy } = await import("@/lib/browse/useCapabilityPolicy");
    const { result } = renderHook(() => useCapabilityPolicy());

    await act(async () => {
      await result.current.draftPolicy({
        action: "keep_only_in_client",
        capabilityIds: ["skill:geo-audit"],
        params: { target_client: "claude" },
      });
    });
    await act(async () => {
      await expect(result.current.draftPolicy({
        action: "keep_only_in_client",
        capabilityIds: ["skill:geo-audit"],
        params: { target_client: "codex" },
      })).rejects.toThrow("draft failed");
    });

    expect(result.current.draft).toBeNull();
    expect(result.current.error).toBe("draft failed");
  });

  it("applyDraft applies and stores the active draft", async () => {
    const draft = makeDraft("draft-1");
    const applyResult = {
      ok: true,
      policy_hash: "hash-2",
      applied_capabilities: ["skill:geo-audit"],
    };
    mockMcpCall.mockResolvedValueOnce(draft);
    mockMcpCall.mockResolvedValueOnce(applyResult);

    const { useCapabilityPolicy } = await import("@/lib/browse/useCapabilityPolicy");
    const { result } = renderHook(() => useCapabilityPolicy());

    await act(async () => {
      await result.current.draftPolicy({
        action: "keep_only_in_client",
        capabilityIds: ["skill:geo-audit"],
        params: { target_client: "claude" },
      });
    });
    await act(async () => {
      await result.current.applyDraft();
    });

    expect(mockMcpCall).toHaveBeenLastCalledWith("capability-policy-apply", {
      draft,
    });
    expect(result.current.applyResult).toEqual(applyResult);
  });

  it("applyDraft accepts an immediate draftPolicy result override", async () => {
    const draft = makeDraft("draft-1");
    const applyResult = {
      ok: true,
      policy_hash: "hash-2",
      applied_capabilities: ["skill:geo-audit"],
    };
    mockMcpCall.mockResolvedValueOnce(draft);
    mockMcpCall.mockResolvedValueOnce(applyResult);

    const { useCapabilityPolicy } = await import("@/lib/browse/useCapabilityPolicy");
    const { result } = renderHook(() => useCapabilityPolicy());

    await act(async () => {
      const nextDraft = await result.current.draftPolicy({
        action: "keep_only_in_client",
        capabilityIds: ["skill:geo-audit"],
        params: { target_client: "claude" },
      });
      await result.current.applyDraft(nextDraft);
    });

    expect(mockMcpCall).toHaveBeenLastCalledWith("capability-policy-apply", {
      draft,
    });
    expect(result.current.applyResult).toEqual(applyResult);
  });

  it("applyDraft clears a stale apply result when the next apply fails", async () => {
    const draft = makeDraft("draft-1");
    const applyResult = {
      ok: true,
      policy_hash: "hash-2",
      applied_capabilities: ["skill:geo-audit"],
    };
    mockMcpCall.mockResolvedValueOnce(draft);
    mockMcpCall.mockResolvedValueOnce(applyResult);
    mockMcpCall.mockResolvedValueOnce({ ok: false, error: "apply failed" });

    const { useCapabilityPolicy } = await import("@/lib/browse/useCapabilityPolicy");
    const { result } = renderHook(() => useCapabilityPolicy());

    await act(async () => {
      const nextDraft = await result.current.draftPolicy({
        action: "keep_only_in_client",
        capabilityIds: ["skill:geo-audit"],
        params: { target_client: "claude" },
      });
      await result.current.applyDraft(nextDraft);
    });
    await act(async () => {
      await expect(result.current.applyDraft(draft)).rejects.toThrow("apply failed");
    });

    expect(result.current.applyResult).toBeNull();
    expect(result.current.error).toBe("apply failed");
  });
});
