export type VisibleSurfacePolicy = "visible_allowed" | "no_visible_mutation";
export type VisibleSurfaceAction = "navigate" | "send-ide-prompt" | "open-window";
export type VisibleSurfaceReason = "user-triggered" | "validation" | "self-heal";

export function resolveVisibleSurfacePolicy(): VisibleSurfacePolicy {
  const raw = process.env.NEXT_PUBLIC_AUGUR_VISIBILITY_POLICY;
  return raw === "no_visible_mutation" ? "no_visible_mutation" : "visible_allowed";
}

export function mayUseVisibleSurface(
  _action: VisibleSurfaceAction,
  reason: VisibleSurfaceReason,
  policy: VisibleSurfacePolicy = resolveVisibleSurfacePolicy(),
): boolean {
  if (policy === "no_visible_mutation") {
    return false;
  }

  return reason === "user-triggered";
}
