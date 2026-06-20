/**
 * Zod validation schemas for skill dashboard config (ADR-187).
 *
 * Validates at scan time so malformed skill metadata produces clear errors
 * with file path and field name, instead of silent defaults at runtime.
 */

import { z } from "zod";

// =============================================================================
// Tab / Page Schema
// =============================================================================

/**
 * Schema for a page definition contributed by a skill.
 * Maps to PageDefinition in types.ts.
 */
export const PageSchema = z.object({
  id: z.string().min(1, "Page id must be a non-empty string"),
  title: z.string().min(1, "Page title must be a non-empty string"),
  icon: z.string().optional(),
  order: z.number().int().min(0).max(999).optional(),
  group: z.string().optional(),
  purpose: z.string().optional(),
  keywords: z.array(z.string()).optional(),
  state: z.enum(["mock", "dev", "mature"]).optional(),
});

// =============================================================================
// Hub Definition Schema
// =============================================================================

/**
 * Schema for the hub block in skill metadata.
 * Maps to HubDefinition in types.ts.
 *
 * ADR-187 Phase 2: adds `owner` field for explicit hub ownership.
 */
export const HubSchema = z.object({
  id: z.string().min(1, "Hub id must be a non-empty string"),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  icon: z.string().optional(),
  category: z.string().optional(),
  owner: z.boolean().default(false),
  nav_label: z.string().optional(),
  nav_route: z.string().optional(),
  nav_hidden: z.boolean().optional(),
  nav_order: z.number().int().optional(),
  overview: z
    .object({
      search: z.boolean().optional(),
      layout: z.enum(["masonry", "grid", "stack"]).optional(),
      empty_state: z.string().optional(),
    })
    .optional(),
  max_tabs: z.number().int().min(1).optional(),
  iconBg: z.string().optional(),
  iconColor: z.string().optional(),
  titleGradient: z
    .object({
      from: z.string(),
      to: z.string(),
    })
    .optional(),
});

// =============================================================================
// Contribution Block Schema
// =============================================================================

const ContributionSchema = z.looseObject({
  // ADR-218: Accept both array (legacy) and map (new) format for pages
  pages: z
    .union([z.array(PageSchema), z.record(z.string(), z.unknown())])
    .optional(),
  widgets: z
    .array(
      z.object({
        id: z.string().min(1),
        title: z.string().min(1),
        component: z.string().min(1),
        size: z.enum(["full", "half", "third", "quarter"]),
        priority: z.number().int(),
        data_source: z.string().optional(),
        refresh_interval: z.number().int().min(0).optional(),
      }),
    )
    .optional(),
  search: z
    .object({
      index_fields: z.array(z.string()),
      display_fields: z.array(z.string()).optional(),
    })
    .optional(),
});

// =============================================================================
// Nav Mode Schema
// =============================================================================

export const NavModeSchema = z.enum(["inline", "nested", "hidden"]).optional();

// =============================================================================
// Top-level skill config schema (tab-related fields only)
// =============================================================================

/**
 * Validates the tab-related subset of the skill config.
 * Does NOT validate the entire file — only fields relevant to
 * hub assembly and tab registry generation.
 */
const SkillConfigTabSchema = z.looseObject({
  // ADR-802 Phase 2: discovery no longer derives contributes_to (the legacy
  // x-augur-hub gate is removed). The field is optional and validated only
  // when still present on legacy configs.
  contributes_to: z.string().min(1, "contributes_to is required").optional(),
  hub: HubSchema.optional(),
  contributions: ContributionSchema.optional(),
  nav_mode: NavModeSchema,
});

// =============================================================================
// Validation Functions
// =============================================================================

export interface SkillConfigValidationError {
  path: string;
  field: string;
  message: string;
}

/**
 * Validate skill config tab-related fields.
 *
 * Returns null if valid, or an array of validation errors.
 * Uses Zod's safeParse to collect all errors, not just the first.
 */
export function validateSkillConfig(
  config: unknown,
  filePath: string,
): SkillConfigValidationError[] | null {
  const result = SkillConfigTabSchema.safeParse(config);
  if (result.success) return null;

  return result.error.issues.map((issue) => ({
    path: filePath,
    field: issue.path.join("."),
    message: issue.message,
  }));
}

/**
 * Format validation errors for console output.
 */
export function formatValidationErrors(errors: SkillConfigValidationError[]): string {
  return errors
    .map((e) => `  ${e.path}: field "${e.field}" — ${e.message}`)
    .join("\n");
}
