import type { LucideIcon } from "lucide-react";

/**
 * Tab configuration for a single tab within a hub.
 *
 * ADR-218: Tabs are path-based links discovered from the filesystem.
 * Registry tabs always have string icon names; client-only tabs may use LucideIcon/ReactNode.
 */
export type TabItem = {
  /** Unique identifier for the tab */
  id?: string;
  /** Display label shown in the tab bar */
  label: string;
  /** Lucide icon - string name (registry) or component/JSX (client-only) */
  icon?: string | LucideIcon | React.ReactNode;
  /** Full href path for the tab */
  href?: string;
  /** Ordering weight (lower = earlier). Increment by 10 for spacing. */
  order?: number;
  /** If true, tab only shows in development mode */
  devOnly?: boolean;
  /** Optional badge count/label shown on the tab (e.g., unread notifications) */
  badge?: number | string;
  /** Skill ID that provides this tab (for customize API). Only present in registry tabs. */
  skillId?: string;
  /** Where this page comes from — determines visibility tier */
  pageSource?: "tsx" | "yaml" | "auto";
};

/**
 * A tab that groups multiple skill sub-pages into a dropdown.
 * Skills with 2+ tabs at the same URL depth become grouped.
 */
export interface GroupedTab extends TabItem {
  /** Sub-pages within this skill group */
  children: TabItem[];
}

/** Union type for flat tabs and grouped tabs */
export type TabEntry = TabItem | GroupedTab;

/**
 * Block navigation item for the Blocks dropdown in HubTabBar.
 * Sourced from contributions.blocks in skill config.
 */
export type BlockNavItem = {
  /** Block identifier */
  id: string;
  /** Display label */
  label: string;
  /** Lucide icon name */
  icon: string;
  /** Skill that provides this block (used for grouping) */
  skill: string;
  /** Route to navigate to when clicked (from block's expandTo) */
  expandTo?: string;
  /** Block render type (form, table, card, etc.) */
  blockType: string;
};

/**
 * Hub configuration containing all tabs and metadata
 */
export type HubConfig = {
  /** Display title for the hub */
  title: string;
  /** Subtitle/description for the hub header */
  subtitle?: string;
  /** Base path for the hub (e.g., '/dev') */
  basePath: string;
  /** Ordered list of tabs for this hub */
  tabs: TabEntry[];
  /** Overflow tabs shown in "More" dropdown (tabs beyond hub.max_tabs, default 6) */
  overflow?: TabEntry[];
  /** Block items for the Blocks dropdown */
  blocks?: BlockNavItem[];
  /** YAML config pages — shown in hub overflow navigation and page customization */
  configPages?: TabItem[];
  /** Auto-generated pages for the Auto dropdown */
  autoPages?: TabItem[];
  /** Source of this config (for debugging/tracing) */
  source?: "plugin" | "hardcoded";
  /** Plugin bundle ID (if source is 'plugin') */
  pluginId?: string;
  /** Skill ID within the plugin (if source is 'plugin') */
  skillId?: string;
  /** All skills contributing pages to this hub (ADR-187 Phase 3) */
  contributors?: string[];
};

/**
 * The complete tab registry mapping hub keys to their configurations
 */
export type TabRegistry = Record<string, HubConfig>;

/**
 * Plugin nav item for dynamic sidebar generation (ADR-058).
 * Generated from skill metadata at build time.
 */
export type PluginNavItem = {
  /** Hub ID from skill config (e.g., "career", "daemon") */
  hubId: string;
  /** Hub title (e.g., "Career Hub") */
  title: string;
  /** Hub subtitle for tooltip */
  subtitle?: string;
  /** Lucide icon name (e.g., "Briefcase") */
  icon: string;
  /** Category determines sidebar section: personal, business, productivity, system */
  category: string;
  /** Hub-level mode: "dev" means only visible in dev mode */
  mode?: string;
  /** Override sidebar label (default: hub title) */
  navLabel?: string;
  /** Override route (default: /{hubId}) */
  navRoute?: string;
  /** Hide from nav, keep page accessible via URL */
  navHidden?: boolean;
  /** Sidebar ordering weight (lower = earlier). Increment by 10 for spacing. */
  navOrder?: number;
  /** Nested skill sub-items for two-level sidebar (ADR-136) */
  children?: PluginNavSubItem[];
};

/**
 * Sub-item for nested skills in sidebar (ADR-136).
 * Appears under a hub's collapsible group.
 */
export type PluginNavSubItem = {
  /** Skill identifier */
  skillId: string;
  /** Display label in sidebar */
  label: string;
  /** Lucide icon name */
  icon: string;
  /** Full href path (e.g., /career/content) */
  href: string;
  /** Number of pages in this skill (for display) */
  pageCount: number;
};

/**
 * Standalone skill nav item for sidebar "Extensions" section (ADR-165).
 * Generated from skill config at build time. Skills that belong to a hub
 * (via contributes_to + hub: block) are excluded — they appear in hub nav.
 */
export type SkillNavItem = {
  /** Skill slug (directory name) */
  slug: string;
  /** Display label */
  label: string;
  /** Lucide icon name */
  icon: string;
  /** Sidebar category: Tools | Integrations | System */
  category: string;
  /** Route path */
  route: string;
};

/**
 * Validation result for tab registry checks
 */
export type TabValidationResult = {
  hub: string;
  tab: string;
  href: string;
  status: "valid" | "missing_folder" | "orphan_folder";
  message: string;
};
