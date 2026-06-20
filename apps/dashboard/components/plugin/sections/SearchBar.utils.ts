export function filterBySearch<T extends Record<string, unknown>>(
  items: T[],
  searchText: string,
  fields: string[],
): T[] {
  if (!searchText.trim()) return items;
  const lower = searchText.toLowerCase();
  return items.filter((item) =>
    fields.some((field) => {
      const val = item[field];
      return val != null && String(val).toLowerCase().includes(lower);
    }),
  );
}
