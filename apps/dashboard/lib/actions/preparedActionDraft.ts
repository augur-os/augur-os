import type { DispatchMode } from "@/lib/actions/types";

export type PreparedActionDispatch = Extract<
  DispatchMode,
  "ide" | "chat" | "oneshot" | "auto"
>;

export type PreparedActionDraft = {
  id: string;
  label: string;
  description?: string;
  prompt: string;
  page: string;
  tier: "fast" | "standard" | "deep";
  dispatch: PreparedActionDispatch;
  recommendedAgent?: string;
  createdAt: string;
};

const PREPARED_ACTION_DISPATCHES = new Set<DispatchMode>([
  "ide",
  "chat",
  "oneshot",
  "auto",
]);

export function isPreparedActionDispatch(
  dispatch: DispatchMode,
): dispatch is PreparedActionDispatch {
  return PREPARED_ACTION_DISPATCHES.has(dispatch);
}

export function composePreparedActionPrompt(
  draft: Pick<PreparedActionDraft, "prompt">,
  userRemarks: string,
): string {
  const remarks = userRemarks.trim();
  if (!remarks) return draft.prompt;

  return [remarks, "", "--- SYSTEM PROMPT ---", "", draft.prompt].join("\n");
}
