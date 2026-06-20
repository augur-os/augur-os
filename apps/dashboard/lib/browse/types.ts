import type { BrowseDisplayMode } from "./displayModeTypes";

export type ViewMode =
  | "notes"
  | "prompts"
  | "documents"
  | "wiki"
  | "skills"
  | "adrs"
  | "integrations"
  | "background-routines"
  | "archive"
  | "pages"
  | "agent-profiles"
  | "commands"
  | "mcp-servers"
  | "mcp-tools"
  | "api-routes"
  | "scripts"
  | "tests"
  | "logs"
  | "system-metadata";

export type BrowseActionType =
  | "navigate"
  | "open-file"
  | "run-mcp"
  | "run-action"
  | "copy"
  | "configure"
  | "cli-help"
  | "mcp-tool"
  | "reveal-file"
  | "extract-and-open-adr";

export type BrowsePageKind = "live" | "saved" | "generated";
export type BrowsePageKindFilter = "all" | BrowsePageKind;
export type NoteTypeFilter =
  | "url"
  | "file"
  | "thought"
  | "voice-memo"
  | "meeting"
  | "image"
  | "prompt";

export const NOTE_TYPE_FILTERS: NoteTypeFilter[] = [
  "url",
  "file",
  "thought",
  "voice-memo",
  "meeting",
  "image",
  "prompt",
];

export type NoteDomain = string;

export type NoteSource = string;

export type NoteClassificationConfidence = "high" | "medium" | "low";

export type NoteStatus = string;

export const RETIRED_VIEW_MODES: Record<string, { view: ViewMode; type?: string }> = {
  inbox: { view: "notes" },
  sources: { view: "notes", type: "url,file" },
  // ADR-805 Model A: Workflows were absorbed into Skills.
  workflows: { view: "skills" },
};

export interface BrowsePrimaryAction {
  label: string;
  type: BrowseActionType;
  target: string;
  args?: Record<string, unknown>;
}

export interface BrowseCardAction {
  id: string;
  label: string;
  icon?: string;          // lucide icon name
  type: BrowseActionType;
  target: string;
  args?: Record<string, unknown>;
  variant?: 'default' | 'danger'; // danger renders red-tinted button
}

export interface CLIToolStatus {
  name: string;
  installed: boolean;
  version: string | null;
  configured: boolean | null;
  install_hint: string;
  homepage?: string;
}

export type SkillOwnership = "augur" | "external" | "adopted" | "user";

export interface CapabilityRecommendedAction {
  id: string;
  label: string;
  params: Record<string, unknown>;
}

export interface CapabilityReportRecord {
  id: string;
  type: string;
  owner_kind: string;
  management: string;
  scope: string;
  primary_surface: string;
  preferred_client: string;
  export_to: string[];
  classification_status: string;
  source_paths: string[];
  current_exposure: string[];
  drift: string[];
  metadata?: Record<string, string>;
  recommended_action?: CapabilityRecommendedAction;
}

export interface CapabilityInventoryReport {
  ok: boolean;
  counts: {
    total: number;
    by_type?: Record<string, number>;
    by_owner?: Record<string, number>;
    by_management?: Record<string, number>;
    by_status?: Record<string, number>;
    by_drift?: Record<string, number>;
    gemini_exposed?: number;
    opencode_exposed?: number;
  };
  duplicate_clusters?: Array<{
    id: string;
    type: string;
    owner_kind: string;
    current_exposure: string[];
  }>;
  records?: CapabilityReportRecord[];
  error?: string;
}

export interface CapabilityPolicyDraftRequest {
  action: string;
  capabilityIds: string[];
  params: Record<string, unknown>;
}

export interface CapabilityPolicyDraft {
  ok: boolean;
  draft_id?: string;
  base_hash?: string;
  action?: string;
  capability_ids?: string[];
  entries?: Record<string, Record<string, unknown>>;
  diff?: string;
  impact?: {
    removed_from?: Record<string, string[]>;
    added_to?: Record<string, string[]>;
    gemini_delta?: number;
    opencode_delta?: number;
  };
  error?: string;
}

export interface CapabilityPolicyApplyResult {
  ok: boolean;
  policy_hash?: string;
  applied_capabilities?: string[];
  error?: string;
}

export type CapabilityProfileSectionKind =
  | "summary"
  | "tools"
  | "actions"
  | "prompts"
  | "commands"
  | "integrations"
  | "health";

export interface CapabilityProfileItem {
  label: string;
  description?: string;
  metadata?: Record<string, string>;
}

export interface CapabilityProfileSection {
  id: string;
  title: string;
  kind: CapabilityProfileSectionKind;
  items: CapabilityProfileItem[];
}

export interface SkillUpstream {
  source?: string;
  path?: string;
  repo?: string;
  ref?: string;
  version?: string;
  subpath?: string;
  [key: string]: string | undefined;
}

export interface BrowseItem {
  id: string;
  title: string;
  description: string;
  icon?: string;
  typeBadge?: string;
  path?: string;
  tags?: string[];
  primaryAction: BrowsePrimaryAction;
  actions?: BrowseCardAction[];
  // Known metadata fields: ownership, source tag, category, plugin, masterClient,
  // skillType, skillTags, pageTags, kind ("live" | "saved" | "generated"),
  // capabilityId, ownerKind, management,
  // classificationStatus, primarySurface, preferredClient, exportTo,
  // currentExposure, drift
  metadata?: Record<string, string>;
  cliTools?: CLIToolStatus[];
}

export type BrowseCategoryGroup = 'content' | 'system' | 'dev';
export type JourneyGroup =
  | 'context'
  | 'prompt'
  | 'loop'
  | 'capabilities'
  | 'diagnostics'
  | 'reference';

export type BrowseJourneyGroup = JourneyGroup;

const BROWSE_GROUP_LABELS: Record<BrowseCategoryGroup, string> = {
  content: "Content",
  system: "System",
  dev: "Dev",
};

export const JOURNEY_GROUP_LABELS: Record<JourneyGroup, string> = {
  context: "CONTEXT ENGINEERING",
  prompt: "PROMPT ENGINEERING",
  loop: "LOOP ENGINEERING",
  capabilities: "CAPABILITIES",
  diagnostics: "DIAGNOSTICS",
  reference: "REFERENCE",
};

// One-line tooltips for the three concept groups (spec §3.1); dev groups have none.
export const JOURNEY_GROUP_SUBTITLES: Partial<Record<JourneyGroup, string>> = {
  context: "What the AI knows",
  prompt: "How you instruct it",
  loop: "How it runs without you",
};

export const JOURNEY_GROUP_ORDER: JourneyGroup[] = [
  "context",
  "prompt",
  "loop",
  "capabilities",
  "diagnostics",
  "reference",
];

const JOURNEY_GROUP_RANK = new Map<JourneyGroup, number>(
  JOURNEY_GROUP_ORDER.map((group, index) => [group, index]),
);

export type BrowseCategoryTier = "primary" | "more";

export interface BrowseCategory {
  id: ViewMode;
  label: string;
  singularLabel: string; // e.g. "Skill", "Prompt" — used for "New Skill" button
  icon: string;
  devOnly: boolean;
  group: BrowseCategoryGroup;
  journey_group: JourneyGroup;
  journey_order: number;
  // "primary" surfaces as a pill in the always-visible row; "more" lives
  // inside the grouped "More ▾" popover. Edit this field to change the split.
  tier: BrowseCategoryTier;
  defaultDisplayMode?: BrowseDisplayMode;
}

export function compareBrowseCategoriesByJourney(
  left: BrowseCategory,
  right: BrowseCategory,
): number {
  const leftGroupRank =
    JOURNEY_GROUP_RANK.get(left.journey_group) ?? Number.MAX_SAFE_INTEGER;
  const rightGroupRank =
    JOURNEY_GROUP_RANK.get(right.journey_group) ?? Number.MAX_SAFE_INTEGER;
  if (leftGroupRank !== rightGroupRank) return leftGroupRank - rightGroupRank;
  if (left.journey_order !== right.journey_order) {
    return left.journey_order - right.journey_order;
  }
  return left.label.localeCompare(right.label);
}

export const BROWSE_CATEGORIES: BrowseCategory[] = [
  // CONTEXT ENGINEERING — what the AI knows
  { id: "notes", label: "Notes", singularLabel: "Note", icon: "BookOpen", devOnly: false, group: "content", journey_group: "context", journey_order: 1, tier: "primary" },
  { id: "documents", label: "Documents", singularLabel: "Document", icon: "FolderOpen", devOnly: false, group: "content", journey_group: "context", journey_order: 2, tier: "primary" },
  { id: "wiki", label: "Wiki", singularLabel: "Wiki Page", icon: "NotebookTabs", devOnly: false, group: "content", journey_group: "context", journey_order: 3, tier: "primary" },
  { id: "pages", label: "Pages", singularLabel: "Page", icon: "PanelsTopLeft", devOnly: false, group: "content", journey_group: "context", journey_order: 4, tier: "primary" },
  { id: "archive", label: "Archive", singularLabel: "Archived Item", icon: "Archive", devOnly: false, group: "content", journey_group: "context", journey_order: 5, tier: "more" },
  // PROMPT ENGINEERING — how you instruct it
  { id: "prompts", label: "Prompts", singularLabel: "Prompt", icon: "MessageSquare", devOnly: false, group: "content", journey_group: "prompt", journey_order: 1, tier: "primary" },
  { id: "commands", label: "Commands", singularLabel: "Command", icon: "Terminal", devOnly: false, group: "content", journey_group: "prompt", journey_order: 2, tier: "primary" },
  { id: "skills", label: "Skills", singularLabel: "Skill", icon: "Puzzle", devOnly: false, group: "content", journey_group: "prompt", journey_order: 3, tier: "primary" },
  // LOOP ENGINEERING — how it runs without you
  { id: "background-routines", label: "Routines", singularLabel: "Routine", icon: "Activity", devOnly: false, group: "content", journey_group: "loop", journey_order: 1, tier: "primary", defaultDisplayMode: "list" },
  { id: "agent-profiles", label: "Agents", singularLabel: "Agent", icon: "Bot", devOnly: false, group: "content", journey_group: "loop", journey_order: 2, tier: "primary" },
  { id: "integrations", label: "Integrations", singularLabel: "Integration", icon: "Plug", devOnly: false, group: "system", journey_group: "loop", journey_order: 3, tier: "primary" },
  // Developer tier (dev-tier collapse groups unchanged)
  { id: "mcp-tools", label: "MCP Tools", singularLabel: "Tool", icon: "Wrench", devOnly: true, group: "dev", journey_group: "capabilities", journey_order: 1, tier: "more" },
  { id: "scripts", label: "Scripts", singularLabel: "Script", icon: "Terminal", devOnly: true, group: "dev", journey_group: "capabilities", journey_order: 2, tier: "more" },
  { id: "api-routes", label: "API Routes", singularLabel: "Route", icon: "Route", devOnly: true, group: "dev", journey_group: "capabilities", journey_order: 3, tier: "more", defaultDisplayMode: "list" },
  { id: "tests", label: "Tests", singularLabel: "Test", icon: "FlaskConical", devOnly: true, group: "dev", journey_group: "capabilities", journey_order: 4, tier: "more", defaultDisplayMode: "list" },
  { id: "mcp-servers", label: "MCP Servers", singularLabel: "MCP Server", icon: "Server", devOnly: true, group: "dev", journey_group: "diagnostics", journey_order: 1, tier: "more", defaultDisplayMode: "list" },
  { id: "logs", label: "Logs", singularLabel: "Log", icon: "ScrollText", devOnly: true, group: "dev", journey_group: "diagnostics", journey_order: 2, tier: "more", defaultDisplayMode: "list" },
  { id: "system-metadata", label: "System Metadata", singularLabel: "Metadata Entry", icon: "Database", devOnly: true, group: "dev", journey_group: "diagnostics", journey_order: 3, tier: "more", defaultDisplayMode: "list" },
  { id: "adrs", label: "ADRs", singularLabel: "ADR", icon: "FileText", devOnly: true, group: "dev", journey_group: "reference", journey_order: 1, tier: "more" },
];

export function partitionBrowseCategoriesByTier(
  categories: BrowseCategory[],
): { primary: BrowseCategory[]; more: BrowseCategory[] } {
  const primary: BrowseCategory[] = [];
  const more: BrowseCategory[] = [];
  for (const category of categories) {
    (category.tier === "primary" ? primary : more).push(category);
  }
  return { primary, more };
}

/** Resolved skill data for BrowseDetailPanel */
export interface SkillDetail {
  skillId: string;
  hub: string;
  title: string;
  icon: string;
  description: string;
  problemStatement?: string;
  blocks: import('@/lib/blocks/types').BlockManifest[];
  actions: SkillAction[];
  prompts: SkillPrompt[];
  commands: SkillCommand[];
  capabilityProfileSections?: CapabilityProfileSection[];
  health?: { status: string; lastCheck?: string; errors24h?: number };
  skillDoc?: string;
  qualityTier?: string;
  qualityScore?: number | string;
  masterClient?: string;
  ownership?: SkillOwnership;
  source?: string;           // raw discovery/source tag used for status + adopt flows
  upstream?: SkillUpstream;   // structured upstream metadata for adopted skills
  updateAvailable?: boolean;  // true if upstream has newer version
}

export interface SkillAction {
  id: string;
  label: string;
  icon?: string;
  description?: string;
  dispatch: string;
  mcp_tools?: string[];
}

export interface SkillPrompt {
  id: string;
  label: string;
  description?: string;
  prompt: string;
  icon?: string;
  source?: "skill" | "vault";
  sourceUrl?: string;
  placeholders?: string[];
}

export interface SkillCommand {
  id: string;
  label: string;
  description?: string;
  command: string;
  icon?: string;
}

export interface ScheduledExecutionRawSchedule {
  type?: string;
  value?: string;
  [key: string]: unknown;
}

export interface RoutineAiCost {
  cli: string;
  estimated_tokens_per_run?: number | null;
  estimated_runs_per_day?: number | null;
  estimated_tokens_per_day?: number | null;
}

export interface RoutineCadence {
  type: string;
  spec: string;
  spec_raw?: string;
  next_run_estimated?: string | null;
  interval_seconds?: number;
}

export interface Routine {
  id: string;
  display_name: string;
  source_kind: string;
  source_path: string;
  cadence: RoutineCadence;
  status: string;
  spawn_kind: string;
  config_path?: string | null;
  ai_cost?: RoutineAiCost | null;
  last_run_at: string | null;
  last_run_status?: string | null;
  last_run_log?: string | null;
  recent_runs_24h?: number | null;
  tags?: string[];
  description?: string | null;

  /** One-release compatibility fields for the former scheduled-executions detail shape. */
  title: string;
  source: string;
  kind: string;
  workspace: string;
  execution_environment?: string;
  schedule_human: string;
  raw_schedule?: ScheduledExecutionRawSchedule;
  prompt_summary: string;
  prompt_body: string;
  native_id?: string;
  model: string;
  next_run_at: string | null;
  warnings: string[];
}

/**
 * @deprecated ADR-727 renamed scheduled executions to background routines.
 * Alias preserved for one release for older imports.
 */
export type ScheduledExecutionDetail = Routine;

export interface PromptResult {
  promptId: string;
  input: string;
  answer: string;
  sessionId: string;
  cliId: string;
  durationMs: number;
  timestamp: Date;
}
