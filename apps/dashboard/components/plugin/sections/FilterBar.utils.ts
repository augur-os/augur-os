export function filterByPills<T extends Record<string, unknown>>(
  items: T[],
  field: string,
  activeValues: Set<string>,
): T[] {
  if (activeValues.size === 0) return items;
  return items.filter((item) => {
    const val = item[field];
    return val != null && activeValues.has(String(val));
  });
}
