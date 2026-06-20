const PREFERRED_KEY_FIELDS = [
  "id",
  "key",
  "slug",
  "name",
  "title",
  "label",
  "path",
  "href",
  "url",
] as const;

function stableStringify(value: unknown): string {
  if (value === null) return "null";
  if (typeof value !== "object") return String(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;

  const record = value as Record<string, unknown>;
  return `{${Object.keys(record)
    .sort()
    .map((key) => `${key}:${stableStringify(record[key])}`)
    .join(",")}}`;
}

export function stableRenderKey(value: unknown, fallback = "item"): string {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const record = value as Record<string, unknown>;
    for (const field of PREFERRED_KEY_FIELDS) {
      const fieldValue = record[field];
      if (fieldValue !== null && fieldValue !== undefined && fieldValue !== "") {
        return `${field}:${String(fieldValue)}`;
      }
    }
  }

  const serialized = stableStringify(value);
  return serialized ? `${fallback}:${serialized}` : fallback;
}

export function keyedRenderItems<T>(
  items: readonly T[],
  getKey: (item: T) => string = (item) => stableRenderKey(item),
): Array<{ item: T; key: string }> {
  const seen = new Map<string, number>();
  return items.map((item) => {
    const baseKey = getKey(item);
    const count = seen.get(baseKey) ?? 0;
    seen.set(baseKey, count + 1);
    return { item, key: count === 0 ? baseKey : `${baseKey}#${count}` };
  });
}
