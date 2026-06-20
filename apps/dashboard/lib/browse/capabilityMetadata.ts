import type { BrowseItem } from "./types";

const CAPABILITY_KEY_ALIASES: Record<string, string[]> = {
  management: ["capabilityManagement", "management"],
  scope: ["capabilityScope", "scope"],
};

export function capabilityMetadataValue(
  metadata: BrowseItem["metadata"] | undefined,
  key: string,
): string | undefined {
  if (!metadata) return undefined;
  const keys = CAPABILITY_KEY_ALIASES[key] ?? [key];
  for (const candidate of keys) {
    const value = metadata[candidate]?.trim();
    if (value) return value;
  }
  return undefined;
}

export function capabilityMetadataList(
  metadata: BrowseItem["metadata"] | undefined,
  key: string,
): string[] {
  return (capabilityMetadataValue(metadata, key) ?? "")
    .split(",")
    .flatMap((part) => {
      const trimmed = part.trim();
      return trimmed ? [trimmed] : [];
    });
}

export function formatCapabilityLabel(value: string): string {
  return value
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function hasCapabilityMetadata(item: BrowseItem): boolean {
  return Boolean(item.metadata?.capabilityId);
}
