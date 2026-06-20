export type ArtifactBridgeDeps = {
  slug: string;
  ownerSkill?: string;
  expectedSource: Window | null;
  openChat: (p: { mode: string; initialPrompt: string; draft: boolean; context: Record<string, unknown> }) => void;
  listSkillActions: (skillId: string) => Promise<{ actions: Array<{ id: string } & Record<string, unknown>> }>;
  runAction: (action: { id: string } & Record<string, unknown>) => Promise<void>;
};
export type BridgeResult = { handled: boolean; reason?: string };
export async function handleArtifactMessage(event: MessageEvent, deps: ArtifactBridgeDeps): Promise<BridgeResult> {
  if (deps.expectedSource && event.source !== deps.expectedSource) return { handled: false, reason: "source" };
  if (event.origin !== "null") return { handled: false, reason: "origin" };
  const data = event.data as { type?: string; prompt?: unknown; actionId?: unknown } | null;
  if (!data || typeof data !== "object") return { handled: false, reason: "shape" };
  if (data.type === "augur:ask") {
    const prompt = String(data.prompt ?? "").trim();
    if (!prompt) return { handled: false, reason: "empty" };
    deps.openChat({ mode: "ide", initialPrompt: prompt, draft: true, context: { page: "artifact", slug: deps.slug } });
    return { handled: true };
  }
  if (data.type === "augur:runAction") {
    if (!deps.ownerSkill) return { handled: false, reason: "no-owner-skill" };
    const id = String(data.actionId ?? "");
    const { actions } = await deps.listSkillActions(deps.ownerSkill);
    const action = actions.find((a) => a.id === id);
    if (!action) return { handled: false, reason: "not-declared" };
    await deps.runAction(action);
    return { handled: true };
  }
  return { handled: false, reason: "unknown-type" };
}
