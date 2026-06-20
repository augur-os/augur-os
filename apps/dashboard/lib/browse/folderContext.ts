export type FolderContextScope = "all" | "brain" | "detected" | "unassigned";

export interface ActiveFolderContext {
  scope: FolderContextScope;
  label: string;
  brain_id?: string | null;
  project_root?: string | null;
  root?: string | null;
  state?: string | null;
}

export interface FolderContextOption {
  id: string;
  scope: FolderContextScope | "action";
  label: string;
  brain_id?: string | null;
  state?: string | null;
  count?: number | null;
  badge?: string | null;
  disabled?: boolean;
}

export interface FolderContextResponse {
  success?: boolean;
  context?: ActiveFolderContext | null;
  options?: FolderContextOption[] | null;
  repaired?: boolean;
  error?: string | null;
}

type FolderContextItem = {
  metadata?: Record<string, unknown>;
};

export function defaultFolderContext(): ActiveFolderContext {
  return { scope: "all", label: "All Brains" };
}

export function selectedFolderLabel(context: ActiveFolderContext | null | undefined): string {
  if (!context || context.scope === "all") return "All Brains";
  return context.label || context.brain_id || "Brain";
}

export function buildFolderContextOptions(response: FolderContextResponse | null | undefined): FolderContextOption[] {
  const source = response?.options?.length
    ? response.options
    : [{ id: "all", scope: "all" as const, label: "All Brains", state: "ready" }];
  const mapped: FolderContextOption[] = source.map((option): FolderContextOption => ({
    ...option,
    badge: option.badge || badgeForState(option.state),
    disabled: option.state === "missing" ? true : option.disabled,
  }));
  if (!mapped.some((option) => option.id === "add-folder")) {
    mapped.push({
      id: "add-folder",
      scope: "action",
      label: "+ Add folder",
      state: "ready",
    });
  }
  return mapped;
}

export function itemMatchesFolderContext(
  item: FolderContextItem,
  context: ActiveFolderContext | null | undefined,
): boolean {
  if (!context || context.scope === "all") return true;
  const metadata = item.metadata ?? {};
  const attachedBrainIds = metadataList(metadata.attachedBrainIds || metadata.attached_brain_ids);
  const indexStatus = metadata.indexStatus || metadata.index_status || "";
  if (context.scope === "unassigned") {
    return indexStatus === "unassigned";
  }
  if (context.scope !== "brain" || !context.brain_id) return false;
  if (context.state === "unregistered" || context.state === "missing") return false;
  if (indexStatus === "unassigned") return false;
  if (attachedBrainIds.length > 0) {
    return attachedBrainIds.includes(context.brain_id);
  }
  return metadata.brain_id === context.brain_id;
}

function badgeForState(state: string | null | undefined): string | null {
  if (state === "repairable") return "Repair";
  if (state === "unregistered") return "Initialize";
  if (state === "missing") return "Missing";
  return null;
}

function metadataList(raw: unknown): string[] {
  if (!raw) return [];
  if (Array.isArray(raw)) {
    return raw
      .flatMap((entry) => metadataList(entry))
      .filter(Boolean);
  }
  const text = String(raw).trim();
  if (!text) return [];
  try {
    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) {
      return parsed.flatMap((entry) => metadataList(entry)).filter(Boolean);
    }
  } catch {
    // Fall through to comma-list parsing for Python reprs and plain metadata.
  }
  return text
    .replace(/^\[/, "")
    .replace(/\]$/, "")
    .split(",")
    .map((entry) => entry.trim().replace(/^['"]|['"]$/g, ""))
    .filter(Boolean);
}
