/** Shared types for the Add Skill modal sub-flows. */

export type SecurityStatus = 'pass' | 'review' | 'danger';

export interface SecurityCheck {
  id: string;
  label: string;
  status: SecurityStatus;
  detail: string;
}

export interface Overlap {
  incoming_skill: string;
  existing_skill: string;
  type: string;
  conflicting_tools: string[];
}

export interface SourceInfo {
  author?: string;
  avatar_url?: string;
  stars?: number;
  license?: string;
  url?: string;
}

export interface BundleSkill {
  name: string;
  path: string;
  description: string;
}

export const HUB_IDS = [
  'adaptive',
  'brain',
  'career',
  'command',
  'life',
  'studio',
] as const;

export type HubId = (typeof HUB_IDS)[number];
