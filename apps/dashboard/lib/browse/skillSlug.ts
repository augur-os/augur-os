/**
 * Client-safe helpers for normalising skill slugs/ids that arrive from URLs.
 *
 * Browse skill cards emit capability ids in the form `skill:<source>:<name>`
 * (see `src/lib/index/_scanners_knowledge.py`). Both the `/browse/[skill]`
 * route param and the `/browse?skill=<id>` query param can carry these raw
 * ids; colons land percent-encoded in URLs, may survive the round-trip, and
 * downstream consumers (the skill-meta API, BLOCK_REGISTRY filters) expect a
 * bare folder name.
 *
 * Keep this file dependency-free so client components (`useSkillDetail`,
 * card-href builders) can import it without dragging in `fs`. The server-side
 * `lib/server/skillsLookup` re-exports these symbols for backward compat.
 */

export function normalizeSlug(value: string): string {
  return value.trim().toLowerCase().replace(/_/g, "-");
}

export type ParsedSkillSlug = {
  /** Clean, lookup-ready skill name (last segment of a colon-prefixed id, decoded). */
  name: string;
  /** Source root parsed from `skill:<source>:<name>` ids, when present. */
  sourceRoot: string | null;
  /** True when the input was a colon-prefixed capability id rather than a bare name. */
  hadPrefix: boolean;
};

export function parseSkillSlug(raw: string): ParsedSkillSlug {
  let decoded = raw;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    decoded = raw;
  }
  if (!decoded.includes(":")) {
    return { name: decoded, sourceRoot: null, hadPrefix: false };
  }
  const segments = decoded.split(":").filter((segment) => segment.length > 0);
  if (segments.length >= 3 && segments[0].toLowerCase() === "skill") {
    return {
      name: segments[segments.length - 1],
      sourceRoot: segments[1] || null,
      hadPrefix: true,
    };
  }
  return { name: segments[segments.length - 1], sourceRoot: null, hadPrefix: true };
}
