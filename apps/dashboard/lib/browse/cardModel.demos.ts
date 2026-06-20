import type { SkillDemo } from "./cardModel.types";
import { splitMetadataList } from "./cardModel.shared";

/**
 * Parse the skills-index demo encoding: a comma-joined list of
 * `"Title|relative/path"` strings (the scanner mirrors the flat-string-list
 * mechanism used by client_sources so the value survives the browse-index
 * metadata flattener).
 */
export function parseSkillDemos(raw: string | undefined): SkillDemo[] {
  return splitMetadataList(raw).flatMap((entry) => {
    const sep = entry.lastIndexOf("|");
    if (sep <= 0 || sep === entry.length - 1) return [];
    const name = entry.slice(0, sep).trim();
    const path = entry.slice(sep + 1).trim();
    return name && path ? [{ name, path }] : [];
  });
}
