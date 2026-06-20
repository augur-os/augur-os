import type {
  BrowseCardAction,
  BrowseItem,
  BrowsePrimaryAction,
} from "@/lib/browse/types";
import {
  getSkillPrimaryAction,
  getSkillSecondaryActions,
} from "@/lib/browse/skill-card-ux";
import type {
  BrowseCardMetadataRow,
  BrowseCardModel,
  BrowseCardModelContext,
} from "./cardModel.types";
import { slotsFor } from "./cardModel.build.helpers";

function cloneActionValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(cloneActionValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, nestedValue]) => [
        key,
        cloneActionValue(nestedValue),
      ]),
    );
  }
  return value;
}

function cloneActionArgs(args: Record<string, unknown> | undefined): Record<string, unknown> | undefined {
  return args ? (cloneActionValue(args) as Record<string, unknown>) : undefined;
}

function copyPrimaryAction(action: BrowsePrimaryAction): BrowsePrimaryAction {
  return {
    ...action,
    ...(action.args ? { args: cloneActionArgs(action.args) } : {}),
  };
}

function copyCardAction(action: BrowseCardAction): BrowseCardAction {
  return {
    ...action,
    ...(action.args ? { args: cloneActionArgs(action.args) } : {}),
  };
}

type BrowseActionComparable = Pick<BrowsePrimaryAction, "label" | "type" | "target" | "args">;

function actionSignature(action: BrowseActionComparable): string {
  return JSON.stringify([
    action.label,
    action.type,
    action.target,
    action.args ?? null,
  ]);
}

function dedupeActions(actions: BrowseCardAction[]): BrowseCardAction[] {
  const seenIds = new Set<string>();
  const seenSignatures = new Set<string>();
  const deduped: BrowseCardAction[] = [];

  for (const action of actions) {
    if (seenIds.has(action.id)) continue;
    const signature = actionSignature(action);
    if (seenSignatures.has(signature)) continue;

    seenIds.add(action.id);
    seenSignatures.add(signature);
    deduped.push(action);
  }

  return deduped;
}

function basicFileActions(item: BrowseItem): BrowseCardAction[] {
  if (!item.path) return [];
  const existingTypesForPath = new Set(
    (item.actions ?? []).flatMap((action) =>
      action.target === item.path ? [action.type] : [],
    ),
  );
  const candidates: BrowseCardAction[] = [
    { id: `open-${item.id}`, label: "Open File", icon: "FileText", type: "open-file", target: item.path },
    { id: `reveal-${item.id}`, label: "Reveal in Finder", icon: "FolderOpen", type: "reveal-file", target: item.path },
    { id: `copy-path-${item.id}`, label: "Copy Path", icon: "Copy", type: "copy", target: item.path },
  ];
  return candidates.filter((action) => !existingTypesForPath.has(action.type));
}

/**
 * Card display rows, with values already shown as a badge removed.
 *
 * `commonSlots()` and the per-view slot builders intentionally emit each signal
 * as BOTH a badge and a metadata row so the full set survives into the detail
 * panel's `detailSections`. On the card itself that doubles the visual weight —
 * a `Hub: evals` row directly under an `evals` badge, `Type: json` under a
 * `json` badge, etc. Dedupe at the render layer (the model's `metadataRows`
 * stays complete for the detail panel) so cards keep only rows that add
 * information the badges don't already carry (Source, Modified, Path, …).
 */
export function visibleCardMetadataRows(
  model: Pick<BrowseCardModel, "badges" | "metadataRows">,
): BrowseCardMetadataRow[] {
  const badgeValues = new Set(model.badges.map((badge) => badge.label.trim().toLowerCase()));
  return model.metadataRows.filter((row) => !badgeValues.has(row.value.trim().toLowerCase()));
}

export function buildBrowseCardModel(
  item: BrowseItem,
  context: BrowseCardModelContext,
): BrowseCardModel {
  const slots = slotsFor(item, context.viewMode);
  const primaryAction = context.viewMode === "skills" ? getSkillPrimaryAction(item) : item.primaryAction;
  const primarySignature = actionSignature(primaryAction);
  const sourceOverflowActions = context.viewMode === "skills"
    ? [...getSkillSecondaryActions(item), ...(item.actions ?? [])]
    : item.actions ?? [];
  const fileOverflowActions = basicFileActions(item).filter(
    (action) => actionSignature(action) !== primarySignature,
  );
  const overflowActions = dedupeActions([
    ...fileOverflowActions,
    ...sourceOverflowActions,
  ]).map(copyCardAction);

  return {
    id: item.id,
    title: item.title,
    description: item.description,
    icon: item.icon ?? "FileText",
    path: item.path,
    badges: slots.badges,
    metadataRows: slots.metadataRows,
    primaryAction: copyPrimaryAction(primaryAction),
    overflowActions,
    detailSections: slots.detailSections,
    rawItem: item,
  };
}
