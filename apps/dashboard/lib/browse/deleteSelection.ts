import type { BrowseItem, ViewMode } from "@/lib/browse/types";

interface TriageResult {
  trash: string[];
  sweep: string[];
  blocked: { id: string; reason: string }[];
}

interface TrashResult {
  trashed: string[];
  refused: { path: string; reason: string }[];
}

export interface DeleteSelectionDeps {
  callTool: <T>(tool: string, args: Record<string, unknown>) => Promise<T>;
  confirm: (summary: string) => Promise<boolean>;
  reindexCategory: (viewMode: ViewMode) => Promise<void>;
  // null when the current view mode has no sweep action (e.g. wiki, archive)
  dispatchSweep: ((items: BrowseItem[]) => Promise<void>) | null;
  onInfo: (msg: string) => void;
  onError: (msg: string) => void;
}

export async function runDeleteSelection(
  items: BrowseItem[],
  viewMode: ViewMode,
  deps: DeleteSelectionDeps,
): Promise<{ trashed: number; swept: number; blocked: { id: string; reason: string }[] }> {
  const empty = { trashed: 0, swept: 0, blocked: [] as { id: string; reason: string }[] };
  try {
    const triage = await deps.callTool<TriageResult>("browse-delete-triage", {
      items: items.map((i) => ({ id: i.id, path: i.path ?? "", category: viewMode })),
    });
    const summary =
      `Move ${triage.trash.length} to Trash (reversible)` +
      (triage.sweep.length ? ` · send ${triage.sweep.length} to Sweep for review` : "") +
      (triage.blocked.length ? ` · ${triage.blocked.length} can't be deleted here` : "") + ".";
    if (!(await deps.confirm(summary))) return empty;

    const byId = new Map(items.map((i) => [i.id, i]));
    const trashPaths = triage.trash.map((id) => byId.get(id)?.path ?? "").filter(Boolean);
    let trashed = 0;
    if (trashPaths.length) {
      const res = await deps.callTool<TrashResult>("browse-trash", { paths: trashPaths });
      // sidecars are excluded from the user-facing count
      trashed = res.trashed.filter((p) => !p.endsWith(".meta.yaml")).length;
      if (res.refused.length) deps.onError(`${res.refused.length} item(s) could not be trashed.`);
      // sweep path handles its own reindex after the sweep completes
      await deps.reindexCategory(viewMode);
    }
    let swept = 0;
    const extraBlocked: { id: string; reason: string }[] = [];
    if (triage.sweep.length) {
      if (deps.dispatchSweep) {
        await deps.dispatchSweep(triage.sweep.map((id) => byId.get(id)).filter(Boolean) as BrowseItem[]);
        swept = triage.sweep.length;
      } else {
        // No sweep action for this view mode — surface items as blocked instead of crashing
        for (const id of triage.sweep) {
          extraBlocked.push({ id, reason: "no sweep available for this view" });
        }
        deps.onInfo(`${triage.sweep.length} item(s) need review and can't be removed from the ${viewMode} tab.`);
      }
    }
    const allBlocked = [...triage.blocked, ...extraBlocked];
    if (triage.blocked.length) deps.onInfo(`${triage.blocked.length} item(s) skipped.`);
    return { trashed, swept, blocked: allBlocked };
  } catch (e) {
    deps.onError(e instanceof Error ? e.message : "Delete failed.");
    return empty;
  }
}
