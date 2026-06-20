/**
 * Shared types for the Skill Meta API route (ADR-272 / ADR-453).
 *
 * Extracted from route.ts as part of WS5 behavior-preserving decomposition.
 * No public API change: route.ts re-assembles these into the same response.
 */

import type { SkillMeta, DataSource } from "@/components/plugin/sections/types";

export type { SkillMeta, DataSource };

// Property access is validated at runtime via fallback defaults in each collector.
export type AugurYaml = Record<string, any>;
export type SkillOwnership = "augur" | "external" | "adopted";
export type SkillUpstream = Record<string, string>;
export type SkillMetaSkill = Omit<SkillMeta["skill"], "upstream"> & {
  ownership: SkillOwnership;
  upstream?: SkillUpstream;
  source?: string;
};
export type SkillStatusPayload = {
  ownership?: SkillOwnership;
  source?: string;
  upstream?: SkillUpstream;
  location?: string;
  isNewToDashboard?: boolean;
  updateAvailable?: boolean;
  latestUpstreamCommit?: string;
};
export type MarkdownSkillContent = {
  id: string;
  label: string;
  description?: string;
  icon?: string;
  body: string;
};
export type SkillRuntimeLocation = {
  skillDir: string;
  skillReadDir: string;
  skillFilePath: string;
  structuredSkill: boolean;
};
export type SkillLocationRoots = {
  sharedSkillRoots: string[];
  privateSkillRoots: string[];
  repoRootSkillRoots: string[];
};
