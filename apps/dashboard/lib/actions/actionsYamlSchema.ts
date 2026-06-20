/**
 * Unified augur/actions.yaml schema — TS mirror of src/lib/actions/action_schema.py (ADR-807).
 *
 * Pure validation: takes an already-parsed YAML/JSON object (no fs access) and
 * returns validated UnifiedAction[]. Same VALID_* sets, same field names, and
 * the same error messages as the Python loader.
 */

export const VALID_KINDS = new Set(["ai", "mcp"]);
export const VALID_DISPATCH = new Set(["fire", "oneshot", "ide", "chat", "modal"]);
export const VALID_SURFACES = new Set(["card", "page", "html"]);

export interface UnifiedAction {
  id: string;
  label: string;
  kind: string;
  dispatch: string;
  surfaces: string[];
  mcp_tool: string | null;
  template: string | null;
  icon: string | null;
  categories: string[];
  args: Record<string, unknown>;
  when: Record<string, unknown>;
  confirm: string | null;
  modal: string | null;
  schedule: Record<string, unknown> | null;
}

function setStr(s: Set<string>): string {
  // Mirror Python's "{'a', 'b'}" set repr for message parity (sorted for stability).
  return `{${[...s].sort().map((v) => `'${v}'`).join(", ")}}`;
}

export function parseActionsYaml(doc: unknown): UnifiedAction[] {
  const raw = (doc ?? {}) as Record<string, unknown>;
  const items = (raw.actions ?? []) as Array<Record<string, unknown>>;
  const out: UnifiedAction[] = [];
  const seen = new Set<string>();

  for (let i = 0; i < items.length; i++) {
    const it = (items[i] ?? {}) as Record<string, unknown>;
    const aid = it.id as string | undefined;
    if (!aid) {
      throw new Error(`actions.yaml: action #${i} missing id`);
    }
    if (seen.has(aid)) {
      throw new Error(`actions.yaml: duplicate action id '${aid}'`);
    }
    seen.add(aid);

    const kind = it.kind as string | undefined;
    if (!kind || !VALID_KINDS.has(kind)) {
      throw new Error(`actions.yaml:${aid}: kind must be one of ${setStr(VALID_KINDS)}`);
    }
    const dispatch = (it.dispatch as string | undefined) ?? "ide";
    if (!VALID_DISPATCH.has(dispatch)) {
      throw new Error(`actions.yaml:${aid}: dispatch must be one of ${setStr(VALID_DISPATCH)}`);
    }
    const surfaces = (it.surfaces as string[] | undefined) ?? ["card"];
    if (!surfaces.length || surfaces.some((s) => !VALID_SURFACES.has(s))) {
      throw new Error(`actions.yaml:${aid}: surfaces must be subset of ${setStr(VALID_SURFACES)}`);
    }
    const mcpTool = (it.mcp_tool as string | undefined) ?? null;
    const template = (it.template as string | undefined) ?? null;
    const categories = (it.categories as string[] | undefined) ?? [];
    const schedule = (it.schedule as Record<string, unknown> | undefined) ?? null;

    if (dispatch === "fire" && !(kind === "mcp" && mcpTool)) {
      throw new Error(`actions.yaml:${aid}: dispatch 'fire' requires kind 'mcp' + mcp_tool`);
    }
    if (kind === "ai" && !template) {
      throw new Error(`actions.yaml:${aid}: kind 'ai' requires template`);
    }
    if (surfaces.includes("card") && !categories.length) {
      throw new Error(`actions.yaml:${aid}: surfaces[card] requires categories`);
    }
    if (schedule && !(dispatch === "fire" && kind === "mcp" && mcpTool)) {
      throw new Error(`actions.yaml:${aid}: schedule requires dispatch 'fire' + kind 'mcp' + mcp_tool`);
    }

    out.push({
      id: aid,
      label: (it.label as string | undefined) ?? aid,
      kind,
      dispatch,
      surfaces,
      mcp_tool: mcpTool,
      template,
      icon: (it.icon as string | undefined) ?? null,
      categories,
      args: (it.args as Record<string, unknown> | undefined) ?? {},
      when: (it.when as Record<string, unknown> | undefined) ?? {},
      confirm: (it.confirm as string | undefined) ?? null,
      modal: (it.modal as string | undefined) ?? null,
      schedule,
    });
  }

  return out;
}
