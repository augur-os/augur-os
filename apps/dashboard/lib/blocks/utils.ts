/** Generate a short random ID for block instances (client-side safe) */
export function randomUUID(): string {
  return Math.random().toString(36).slice(2, 10);
}

/** Derive a deterministic view ID for a hub's overview user-blocks canvas. */
export function getHubViewId(hubId: string): string {
  return `hub-${hubId}-overview`;
}

/** Parse a canonical hub overview view ID back into its hub ID. */
export function parseHubViewId(viewId: string): string | null {
  const match = /^hub-(.+)-overview$/.exec(viewId);
  return match?.[1] ?? null;
}
