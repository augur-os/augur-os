import { handleArtifactMessage, type ArtifactBridgeDeps } from "@/lib/artifacts/bridge";
const src = {} as Window;
function deps(over: Partial<ArtifactBridgeDeps> = {}): ArtifactBridgeDeps {
  return {
    slug: "demo", ownerSkill: "rag", expectedSource: src,
    openChat: jest.fn(),
    listSkillActions: jest.fn(async () => ({ actions: [{ id: "rag-reindex", dispatch: "fire", mcp_tools: ["reindex-browse-category"] }] })),
    runAction: jest.fn(async () => {}),
    ...over,
  };
}
const evt = (over: Partial<MessageEvent>): MessageEvent => ({ source: src, origin: "null", data: {}, ...over } as MessageEvent);

test("rejects message from a different window source", async () => {
  const d = deps();
  const r = await handleArtifactMessage(evt({ source: {} as Window, data: { type: "augur:ask", prompt: "hi" } }), d);
  expect(r).toEqual({ handled: false, reason: "source" });
  expect(d.openChat).not.toHaveBeenCalled();
});
test("rejects non-opaque origin", async () => {
  const r = await handleArtifactMessage(evt({ origin: "https://evil.example", data: { type: "augur:ask", prompt: "hi" } }), deps());
  expect(r.reason).toBe("origin");
});
test("augur:ask opens chat with the prompt", async () => {
  const d = deps();
  const r = await handleArtifactMessage(evt({ data: { type: "augur:ask", prompt: "  summarize this  " } }), d);
  expect(r).toEqual({ handled: true });
  expect(d.openChat).toHaveBeenCalledWith({ mode: "ide", initialPrompt: "summarize this", draft: true, context: { page: "artifact", slug: "demo" } });
});
test("augur:runAction dispatches a declared owning-skill action", async () => {
  const d = deps();
  const r = await handleArtifactMessage(evt({ data: { type: "augur:runAction", actionId: "rag-reindex" } }), d);
  expect(r).toEqual({ handled: true });
  expect(d.runAction).toHaveBeenCalledWith(expect.objectContaining({ id: "rag-reindex" }));
});
test("augur:runAction rejects an action not declared by the owning skill", async () => {
  const d = deps();
  const r = await handleArtifactMessage(evt({ data: { type: "augur:runAction", actionId: "other-skill-secret" } }), d);
  expect(r.reason).toBe("not-declared");
  expect(d.runAction).not.toHaveBeenCalled();
});
test("augur:runAction is disabled when artifact has no owning skill", async () => {
  const r = await handleArtifactMessage(evt({ data: { type: "augur:runAction", actionId: "x" } }), deps({ ownerSkill: undefined }));
  expect(r.reason).toBe("no-owner-skill");
});
