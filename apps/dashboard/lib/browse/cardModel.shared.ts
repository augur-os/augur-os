export function splitMetadataList(raw: string | undefined): string[] {
  if (!raw) return [];
  return raw
    .replace(/^\[/, "")
    .replace(/\]$/, "")
    .split(",")
    .flatMap((entry) => {
      const trimmed = entry.trim().replace(/^['"]|['"]$/g, "");
      return trimmed ? [trimmed] : [];
    });
}
