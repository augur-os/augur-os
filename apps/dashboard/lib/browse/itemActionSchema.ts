export type ItemActionKind = "ai" | "direct";

export interface ItemActionWhen {
  noteTypes?: string[];
  fileExtensions?: string[];
  mediaKinds?: string[];
}

export interface ItemActionDef {
  id: string;
  label: string;
  icon: string;
  kind: ItemActionKind;
  template?: string;
  tool?: string;
  args?: Record<string, string>;
  confirm?: boolean;
  invalidates?: string[];
  when?: ItemActionWhen;
}

export interface BrowseActionsDoc {
  categories: Record<string, ItemActionDef[]>;
}

export type BrowseActionsValidationResult =
  | { ok: true; doc: BrowseActionsDoc }
  | { ok: false; errors: string[] };

interface ValidationContext {
  validCategories: Set<string>;
  validIcons: Set<string>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return isRecord(value) && Object.values(value).every((entry) => typeof entry === "string");
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === "string");
}

function requireString(
  action: Record<string, unknown>,
  field: keyof ItemActionDef,
  path: string,
  errors: string[],
): string {
  const value = action[field];
  if (typeof value !== "string" || !value.trim()) {
    errors.push(`${path}: ${String(field)} must be a non-empty string`);
    return "";
  }
  return value;
}

export function validateBrowseActionsDoc(
  doc: unknown,
  ctx: ValidationContext,
): BrowseActionsValidationResult {
  const errors: string[] = [];
  const normalized: BrowseActionsDoc = { categories: {} };

  if (!isRecord(doc)) {
    return { ok: false, errors: ["document must be an object"] };
  }
  if (!isRecord(doc.categories)) {
    return { ok: false, errors: ["categories must be an object"] };
  }

  for (const [category, rawActions] of Object.entries(doc.categories)) {
    const categoryPath = `categories.${category}`;
    if (!ctx.validCategories.has(category)) {
      errors.push(`${categoryPath}: unknown category`);
    }
    if (!Array.isArray(rawActions)) {
      errors.push(`${categoryPath}: must be an array`);
      continue;
    }

    const seenIds = new Set<string>();
    const actions: ItemActionDef[] = [];
    for (const [index, rawAction] of rawActions.entries()) {
      const actionId =
        isRecord(rawAction) && typeof rawAction.id === "string" && rawAction.id.trim()
          ? rawAction.id
          : String(index);
      const actionPath = `${categoryPath}.${actionId}`;
      if (!isRecord(rawAction)) {
        errors.push(`${categoryPath}[${index}]: action must be an object`);
        continue;
      }

      const id = requireString(rawAction, "id", actionPath, errors);
      const label = requireString(rawAction, "label", actionPath, errors);
      const icon = requireString(rawAction, "icon", actionPath, errors);
      const rawKind = requireString(rawAction, "kind", actionPath, errors);
      const kind = rawKind === "ai" || rawKind === "direct" ? rawKind : null;

      if (id) {
        if (seenIds.has(id)) errors.push(`${actionPath}: duplicate action id "${id}"`);
        seenIds.add(id);
      }
      if (icon && !ctx.validIcons.has(icon)) {
        errors.push(`${actionPath}: unknown icon "${icon}"`);
      }
      if (!kind) {
        errors.push(`${actionPath}: kind must be "ai" or "direct"`);
      }

      const template = rawAction.template;
      const tool = rawAction.tool;
      if (kind === "ai" && (typeof template !== "string" || !template.trim())) {
        errors.push(`${actionPath}: ai action requires template`);
      }
      if (kind === "direct" && (typeof tool !== "string" || !tool.trim())) {
        errors.push(`${actionPath}: direct action requires tool`);
      }

      if (rawAction.args !== undefined && !isStringRecord(rawAction.args)) {
        errors.push(`${actionPath}: args must be a string map`);
      }
      if (rawAction.confirm !== undefined && typeof rawAction.confirm !== "boolean") {
        errors.push(`${actionPath}: confirm must be boolean`);
      }
      if (rawAction.invalidates !== undefined && !isStringArray(rawAction.invalidates)) {
        errors.push(`${actionPath}: invalidates must be a string array`);
      }

      let when: ItemActionWhen | undefined;
      if (rawAction.when !== undefined) {
        if (!isRecord(rawAction.when)) {
          errors.push(`${actionPath}: when must be an object`);
        } else {
          const nextWhen: ItemActionWhen = {};
          const rawNoteTypes = rawAction.when.noteTypes;
          if (rawNoteTypes !== undefined) {
            if (!isStringArray(rawNoteTypes) || rawNoteTypes.some((entry) => !entry.trim())) {
              errors.push(`${actionPath}: when.noteTypes must be a string array`);
            } else {
              nextWhen.noteTypes = rawNoteTypes.map((entry) => entry.trim().toLowerCase().replace(/[\s_]+/g, "-"));
            }
          }

          const rawFileExtensions = rawAction.when.fileExtensions;
          if (rawFileExtensions !== undefined) {
            if (!isStringArray(rawFileExtensions) || rawFileExtensions.some((entry) => !entry.trim())) {
              errors.push(`${actionPath}: when.fileExtensions must be a string array`);
            } else {
              nextWhen.fileExtensions = rawFileExtensions.map((entry) => entry.trim().toLowerCase().replace(/^\./, ""));
            }
          }

          const rawMediaKinds = rawAction.when.mediaKinds;
          if (rawMediaKinds !== undefined) {
            if (!isStringArray(rawMediaKinds) || rawMediaKinds.some((entry) => !entry.trim())) {
              errors.push(`${actionPath}: when.mediaKinds must be a string array`);
            } else {
              nextWhen.mediaKinds = rawMediaKinds.map((entry) => entry.trim().toLowerCase().replace(/[\s_]+/g, "-"));
            }
          }

          when = Object.keys(nextWhen).length > 0 ? nextWhen : undefined;
        }
      }

      if (id && label && icon && kind) {
        actions.push({
          id,
          label,
          icon,
          kind,
          ...(typeof template === "string" ? { template } : {}),
          ...(typeof tool === "string" ? { tool } : {}),
          ...(isStringRecord(rawAction.args) ? { args: rawAction.args } : {}),
          ...(typeof rawAction.confirm === "boolean" ? { confirm: rawAction.confirm } : {}),
          ...(isStringArray(rawAction.invalidates) ? { invalidates: rawAction.invalidates } : {}),
          ...(when ? { when } : {}),
        });
      }
    }
    normalized.categories[category] = actions;
  }

  if (errors.length > 0) return { ok: false, errors };
  return { ok: true, doc: normalized };
}
