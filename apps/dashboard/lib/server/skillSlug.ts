/**
 * Skill Slug Normalization
 *
 * Provides canonical slug normalization for skill identifiers.
 * Consolidates 3 different implementations that existed across routes.
 */

/** Pattern for valid skill slugs: lowercase alphanumeric with hyphens */
const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]*$/;

/**
 * Normalize a skill identifier to canonical slug form.
 *
 * Transformations applied:
 * 1. Trim whitespace
 * 2. Convert to lowercase
 * 3. Replace underscores with hyphens
 * 4. Replace spaces with hyphens
 * 5. Remove non-alphanumeric characters (except hyphens)
 * 6. Collapse multiple hyphens
 * 7. Trim leading/trailing hyphens
 *
 * @param value - Raw skill name or identifier
 * @returns Normalized slug
 *
 * @example
 * ```typescript
 * normalizeSkillSlug('Project Manager')  // 'executor'
 * normalizeSkillSlug('project_manager')  // 'executor'
 * normalizeSkillSlug('My--Skill__Name')  // 'my-skill-name'
 * normalizeSkillSlug('  Test Skill  ')   // 'test-skill'
 * ```
 */
export function normalizeSkillSlug(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/_/g, "-") // underscores to hyphens
    .replace(/\s+/g, "-") // spaces to hyphens
    .replace(/[^a-z0-9-]/g, "") // remove non-alphanumeric (except hyphens)
    .replace(/-+/g, "-") // collapse multiple hyphens
    .replace(/^-+|-+$/g, ""); // trim leading/trailing hyphens
}

/**
 * Check if a value is a valid skill slug.
 *
 * Valid slugs must:
 * - Start with alphanumeric character
 * - Contain only lowercase letters, numbers, and hyphens
 * - Not be empty
 *
 * @param value - Value to check
 * @returns true if valid slug
 */
function isSafeSkillSlug(value: string): boolean {
  return SLUG_PATTERN.test(value);
}

/**
 * Find a matching skill slug from a list of candidates.
 *
 * Normalizes both the input slug and candidates for comparison.
 *
 * @param slug - Slug to find
 * @param candidates - List of possible matches
 * @returns Matching candidate or null if not found
 *
 * @example
 * ```typescript
 * const candidates = ['executor', 'developer', 'architect'];
 * matchSkillBySlug('Project_Manager', candidates)  // 'executor'
 * matchSkillBySlug('unknown', candidates)          // null
 * ```
 */
function matchSkillBySlug(
  slug: string,
  candidates: string[],
): string | null {
  const normalized = normalizeSkillSlug(slug);
  if (!normalized) return null;

  // Try exact match first
  const exactMatch = candidates.find((c) => c === normalized);
  if (exactMatch) return exactMatch;

  // Try normalized match
  return candidates.find((c) => normalizeSkillSlug(c) === normalized) || null;
}

/**
 * Generate a prompt slug from a trigger phrase.
 *
 * Used for creating prompt identifiers from skill triggers.
 *
 * @param trigger - Trigger phrase
 * @returns Slug suitable for prompt identification
 *
 * @example
 * ```typescript
 * promptSlugFromTrigger('Review Code')  // 'review-code'
 * ```
 */
export function promptSlugFromTrigger(trigger: string): string {
  return trigger.toLowerCase().replace(/\s+/g, "-");
}
