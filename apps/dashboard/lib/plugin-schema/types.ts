/**
 * TypeScript types for skill dashboard config.
 *
 * These types define the structure of plugin-defined dashboard configurations.
 * Plugins declare their UI in SKILL.md frontmatter via `x-augur-config`.
 */

import type { DispatchMode } from "@/lib/actions/types";
import type { WorkspacePage } from "@/lib/plugin-discovery/scanner";

// =============================================================================
// Core Types
// =============================================================================

/**
 * Root schema for skill dashboard config (v3.0, ADR-128).
 *
 * Skills declare `contributes_to` and `contributions` to participate in
 * assembled hubs. One skill per hub defines the `hub:` block (primary).
 */
export interface DashboardYaml {
  /** Schema version (must be '3.0') */
  version: string;
  /** Skill identifier */
  skill?: string;
  /** Hub ID this skill contributes to (required) */
  contributes_to: string;
  /** Hub definition — only ONE skill per hub defines this (primary skill) */
  hub: HubDefinition;
  /** Contribution declarations */
  contributions?: ContributionBlock;
  /** Cross-hub widget contributions */
  cross_hub?: CrossHubContribution[];
  /** Legacy tab definitions kept for older dashboard YAML configs */
  tabs: TabDefinition[];
  /** Tab group definitions for organizing tabs */
  tab_groups?: Array<{ id: string; label: string }>;
  /** Modal definitions (optional) */
  modals?: Record<string, ModalDefinition>;
  /** Action button definitions (optional) */
  actions?: ActionDefinition[];
  /** Item-level action definitions — appear in detail panel (optional, ADR-032) */
  item_actions?: ItemActionDefinition[];
  /** Bridge configuration — external data source connections (ADR-086) */
  bridge?: {
    enabled: boolean;
  };
  /** Dashboard mode */
  mode?: string;
  /** MCP tool configuration */
  mcp?: {
    tools?: string[];
    max_tools?: number;
  };
  /** MCP tools shorthand list */
  mcp_tools?: string[];
  /** Dashboard page route declarations from x-augur-dashboard-pages frontmatter */
  dashboard_pages?: WorkspacePage[];
  /** Plugin dependencies */
  dependencies?: {
    required?: string[];
    optional?: string[];
  };
  /** Plugin data directory */
  data_dir?: string;
  /** Navigation mode: how this skill's pages appear in navigation (ADR-136) */
  nav_mode?: "inline" | "nested" | "hidden";
}

/**
 * Hub (page) definition.
 */
export interface HubDefinition {
  /** Unique hub identifier (URL slug) */
  id: string;
  /** Display title */
  title: string;
  /** Subtitle/description shown under title */
  subtitle: string;
  /** Lucide icon name */
  icon: string;
  /** Whether this skill owns the hub (ADR-187). Exactly one per hub must be true. */
  owner?: boolean;
  /** Optional gradient colors for title */
  titleGradient?: {
    from: string;
    to: string;
  };
  /** Icon background color class */
  iconBg?: string;
  /** Icon color class */
  iconColor?: string;
  /** Navigation category (ADR-105: derived from bundle dir) */
  category?: string;
  /** Custom navigation label */
  nav_label?: string;
  /** Custom navigation route */
  nav_route?: string;
  /** Hide from navigation */
  nav_hidden?: boolean;
  /** Sidebar ordering weight (lower = earlier). Increment by 10 for spacing. */
  nav_order?: number;
  /** Overview page configuration (v3.0, only on hub-owning skill) */
  overview?: OverviewConfig;
  /** Maximum visible tabs before overflow (default: 6) */
  max_tabs?: number;
}

/**
 * Tab definition within a hub.
 */
export interface TabDefinition {
  /** Tab identifier */
  id: string;
  /** Display label */
  label: string;
  /** Lucide icon name */
  icon: string;
  /** Whether this is the default (overview) tab */
  default?: boolean;
  /** Custom href (defaults to /hub/tab) */
  href?: string;
  /** Sections within this tab */
  sections: SectionDefinition[];
}

// =============================================================================
// Section Types
// =============================================================================

/**
 * Union of all section types.
 */
export type SectionDefinition =
  | MetricsGridSection
  | DataTableSection
  | ChartSection
  | TimelineSection
  | FormSection
  | MarkdownSection
  | CustomSection;

/**
 * Base properties for all sections.
 */
interface BaseSectionDefinition {
  /** Section type discriminator */
  type: string;
  /** Optional section title */
  title?: string;
}

/**
 * Grid of metric cards.
 */
export interface MetricsGridSection extends BaseSectionDefinition {
  type: "metrics-grid";
  /** Number of columns (default: 4) */
  columns?: number;
  /** Metric definitions */
  metrics: MetricDefinition[];
}

/**
 * Individual metric card definition.
 */
export interface MetricDefinition {
  /** Unique metric identifier */
  id: string;
  /** Display label */
  label: string;
  /** Data source (mcp://, /api/, or static:) */
  source: string;
  /** JavaScript expression to transform data (e.g., "data.length") */
  transform?: string;
  /** Lucide icon name */
  icon?: string;
  /** Color theme (e.g., "amber", "blue", "green") */
  color?: string;
  /** Link to navigate to on click */
  href?: string;
}

/**
 * Sortable data table with actions.
 */
export interface DataTableSection extends BaseSectionDefinition {
  type: "data-table";
  /** Data source */
  source: string;
  /** Column definitions */
  columns: ColumnDefinition[];
  /** Row actions (legacy TableAction[] system) */
  actions?: TableAction[];
  /** Pagination settings */
  pagination?: {
    pageSize: number;
  };
  /** Empty state configuration */
  emptyState?: {
    icon?: string;
    message: string;
    action?: {
      label: string;
      type: "modal" | "link";
      modal?: string;
      href?: string;
    };
  };
  /** D14: Per-item actions with dispatch modes (richer than legacy actions[]) */
  row_actions?: Array<{
    id: string;
    icon: string;
    label: string;
    dispatch: "fire" | "modal" | "ide" | "navigate";
    mcp_tool?: string;
    payload_fields?: string[];
    confirm?: boolean;
    confirm_message?: string;
    href_template?: string;
  }>;
  /** D15: Inline editable fields */
  editable_fields?: Array<{
    field: string;
    type: "text" | "select" | "number" | "markdown" | "toggle";
    save_action: string;
    options?: string[];
    min?: number;
    max?: number;
  }>;
}

/**
 * Table column definition.
 */
export interface ColumnDefinition {
  /** Field name in data object */
  field: string;
  /** Display header */
  label: string;
  /** Column type for rendering */
  type?:
    | "text"
    | "date"
    | "relative-time"
    | "severity-badge"
    | "status"
    | "link"
    | "number"
    | "boolean";
  /** Whether column is sortable */
  sortable?: boolean;
  /** Column width (CSS value) */
  width?: string;
  /** Custom render format */
  format?: string;
}

/**
 * Table row action.
 */
export interface TableAction {
  /** Action type */
  type: "edit" | "delete" | "view" | "custom";
  /** MCP tool to call */
  tool?: string;
  /** Modal to open */
  modal?: string;
  /** Link to navigate to */
  href?: string;
  /** Confirmation message (for destructive actions) */
  confirmMessage?: string;
  /** Action label */
  label?: string;
  /** Lucide icon name */
  icon?: string;
}

/**
 * Chart visualization.
 */
export interface ChartSection extends BaseSectionDefinition {
  type: "chart";
  /** Chart type */
  chartType: "line" | "bar" | "pie" | "area" | "donut";
  /** Data source */
  source: string;
  /** X-axis field */
  xAxis: string;
  /** Y-axis field */
  yAxis: string;
  /** Field to group/color by */
  groupBy?: string;
  /** Chart height in pixels */
  height?: number;
  /** Chart colors */
  colors?: string[];
}

/**
 * Chronological timeline display.
 */
export interface TimelineSection extends BaseSectionDefinition {
  type: "timeline";
  /** Data source */
  source: string;
  /** Field containing date */
  dateField: string;
  /** Field containing title */
  titleField: string;
  /** Field containing description */
  descriptionField?: string;
  /** Field containing event type */
  typeField?: string;
  /** Color mapping for event types */
  typeColors?: Record<string, string>;
}

/**
 * Input form that calls MCP tool on submit.
 */
export interface FormSection extends BaseSectionDefinition {
  type: "form";
  /** MCP tool to call on submit */
  action: string;
  /** Form fields */
  fields: FormField[];
  /** Submit button label */
  submitLabel?: string;
  /** Success message */
  successMessage?: string;
}

/**
 * Static markdown content.
 */
export interface MarkdownSection extends BaseSectionDefinition {
  type: "markdown";
  /** Inline markdown content */
  content?: string;
  /** Path to markdown file */
  file?: string;
}

/**
 * Custom React component (escape hatch).
 */
export interface CustomSection extends BaseSectionDefinition {
  type: "custom";
  /** npm package containing the component */
  package: string;
  /** Entry point/export name */
  entry: string;
  /** Props to pass to the component */
  props?: Record<string, unknown>;
}

// =============================================================================
// Modal Types
// =============================================================================

/**
 * Modal dialog definition.
 */
export interface ModalDefinition {
  /** Modal title */
  title: string;
  /** Description/subtitle */
  description?: string;
  /** MCP tool to call on submit */
  submitTool: string;
  /** Form fields */
  fields: FormField[];
  /** Submit button label */
  submitLabel?: string;
  /** Cancel button label */
  cancelLabel?: string;
}

/**
 * Form field definition.
 */
export interface FormField {
  /** Field name (form key) */
  name: string;
  /** Display label */
  label: string;
  /** Field type */
  type:
    | "text"
    | "textarea"
    | "number"
    | "date"
    | "datetime"
    | "select"
    | "multiselect"
    | "checkbox"
    | "radio"
    | "file"
    | "toggle";
  /** Whether field is required */
  required?: boolean;
  /** Default value */
  defaultValue?: string | number | boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Options for select/multiselect/radio */
  options?: SelectOption[];
  /** Accepted file types for file fields (e.g. [".csv", ".xlsx"]) */
  accept?: string[];
  /** Validation rules */
  validation?: {
    min?: number;
    max?: number;
    minLength?: number;
    maxLength?: number;
    pattern?: string;
    message?: string;
  };
  /** Help text shown below field */
  helpText?: string;
}

/**
 * Select option.
 */
export interface SelectOption {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
}

// =============================================================================
// Action Types
// =============================================================================

/**
 * Action button definition (shown in hub header).
 */
export interface ActionDefinition {
  /** Action identifier */
  id: string;
  /** Button label */
  label: string;
  /** Lucide icon name */
  icon?: string;
  /** Action type */
  type?: "modal" | "link" | "chain";
  /** Modal to open */
  modal?: string;
  /** Link to navigate to */
  href?: string;
  /** Chain to execute */
  chain?: string;
  /** Button variant */
  variant?: "default" | "outline" | "ghost";
}

/**
 * Item-level action definition (ADR-032).
 *
 * Actions scoped to a specific data item (e.g., a discovery, job, document).
 * Shown in the DetailPanel footer. Conditional on item status.
 */
export interface ItemActionDefinition {
  /** Action identifier */
  id: string;
  /** Button label */
  label: string;
  /** Optional description for tooltips/prompts */
  description?: string;
  /** Lucide icon name */
  icon?: string;
  /** Dispatch mode */
  dispatch: DispatchMode;
  /** Direct MCP tool binding for fast actions (e.g., "mcp://augur/update-discovery-status") */
  tool?: string;
  /** Static arguments merged with item data at execution time */
  args?: Record<string, unknown>;
  /** Only show action when item status matches one of these values */
  requires_status?: string[];
  /** Button variant */
  variant?: "primary" | "secondary" | "danger";
  /** Confirmation prompt before executing */
  confirmation?: string;
}

// =============================================================================
// Contribution Model Types (ADR-128: Schema v3.0)
// =============================================================================

/**
 * Widget definition for overview page composition.
 */
export interface WidgetDefinition {
  /** Widget identifier (unique within skill) */
  id: string;
  /** Display title */
  title: string;
  /** TSX component name (loaded from widget registry) */
  component: string;
  /** Widget size on the grid */
  size: "full" | "half" | "third" | "quarter";
  /** Sort priority (lower = higher on page) */
  priority: number;
  /** API endpoint for data */
  data_source?: string;
  /** Auto-refresh interval in seconds (0 = no auto-refresh) */
  refresh_interval?: number;
}

/**
 * Page definition contributed by a skill.
 * Each page becomes a tab under the hub.
 */
export interface PageDefinition {
  /** Page identifier (used as route segment) */
  id: string;
  /** Display title (used as tab label) */
  title: string;
  /** Lucide icon name */
  icon?: string;
  /** Tab ordering weight (lower = earlier). Increment by 10 for spacing. */
  order?: number;
  /** Group override: skill ID to place in that group, or '_top' for top-level */
  group?: string;
  /** Short description of the page's purpose (used by project indexer) */
  purpose?: string;
  /** Problem statement — subtitle shown below the page title (ADR-407 D2) */
  problem_statement?: string;
  /** Page type: custom (user-defined) or auto (generated from skill) */
  page_type?: "custom" | "auto";
  /** Search keywords for this page (used by project indexer) */
  keywords?: string[];
  /** Maturity state of this page */
  state?: "mock" | "dev" | "mature";
}

/**
 * Search contribution for bundle-scoped search.
 */
export interface SearchContribution {
  /** Fields to index for search */
  index_fields: string[];
  /** Fields to display in search results */
  display_fields?: string[];
}

/**
 * Block definition for the page builder (ADR-190).
 * Describes a reusable UI block backed by an MCP tool or plugin component.
 */
export interface BlockDefinition {
  /** Unique block identifier */
  id: string;
  /** Display name */
  name: string;
  /** Lucide icon name */
  icon: string;
  /** Block category */
  category: "content" | "data" | "communication" | "automation" | "custom";
  /** Render strategy */
  render:
    | "form"
    | "table"
    | "card"
    | "chart"
    | "markdown"
    | "timeline"
    | "custom";
  /** Block source type */
  source: "mcp" | "plugin";
  /** MCP tool name (when source is 'mcp') */
  mcp_tool?: string;
  /** MCP server name (when source is 'mcp') */
  mcp_server?: string;
  /** Relative path to React component (when source is 'plugin') */
  component?: string;
  /** Props schema for block configuration */
  props?: BlockPropDefinition[];
  /** Navigation route when block is expanded to a full page */
  expand_to?: string;
}

/**
 * Property definition for a block's configurable props.
 */
export interface BlockPropDefinition {
  /** Property name */
  name: string;
  /** Property type */
  type: "string" | "number" | "boolean" | "file-path" | "select";
  /** Default value */
  default?: string | number | boolean;
  /** Whether the prop is required */
  required?: boolean;
  /** Options for select type */
  options?: string[];
}

/**
 * Block of contributions from a skill to its hub.
 */
export interface ContributionBlock {
  /** Widget definitions for the overview page */
  widgets?: WidgetDefinition[];
  /** Page definitions (become tabs) */
  pages?: PageDefinition[];
  /** Search configuration */
  search?: SearchContribution;
  /** Action button definitions */
  actions?: ActionDefinition[];
  /** Block definitions for the page builder (ADR-190) */
  blocks?: BlockDefinition[];
}

/**
 * Cross-hub widget contribution.
 * Allows a skill to contribute widgets to hubs outside its bundle.
 */
export interface CrossHubContribution {
  /** Target hub ID */
  hub: string;
  /** Widgets to contribute */
  widgets?: WidgetDefinition[];
}

/**
 * Overview page configuration for a hub.
 */
export interface OverviewConfig {
  /** Enable bundle-scoped search */
  search?: boolean;
  /** Widget layout style */
  layout?: "masonry" | "grid" | "stack";
  /** Message shown when no data exists */
  empty_state?: string;
}

/**
 * Assembled hub — output of the hub assembly pipeline.
 * Merges contributions from all skills that contribute to a hub.
 */
export interface AssembledHub {
  /** Hub identifier (matches contributes_to value) */
  id: string;
  /** Display title */
  title: string;
  /** Subtitle/description */
  subtitle: string;
  /** Lucide icon name */
  icon: string;
  /** Navigation category (bundle directory name) */
  category: string;
  /** Overview page configuration */
  overview: OverviewConfig;
  /** Merged widgets from all contributing skills, sorted by priority */
  widgets: (WidgetDefinition & { skill: string })[];
  /** Merged tabs from all contributing skills (overview auto-inserted as first) */
  tabs: (PageDefinition & {
    skill: string;
    /** Navigation mode for this tab's owning skill (ADR-136) */
    nav_mode: "inline" | "nested" | "hidden";
    /** Display title of the contributing skill (for tab group labels) */
    skill_title: string;
    /** Lucide icon name of the contributing skill (for sidebar sub-items) */
    skill_icon?: string;
  })[];
  /** Merged search configuration */
  search: { index_fields: string[]; display_fields: string[] };
  /** All contributing skill IDs */
  skills: string[];
  /** Skill that defines the hub: block */
  owner: string;
  /** Aggregated MCP tools from all skills */
  mcp_tools: string[];
  /** Icon background color class */
  iconBg?: string;
  /** Icon color class */
  iconColor?: string;
  /** Optional gradient colors for title */
  titleGradient?: { from: string; to: string };
  /** Custom navigation label */
  nav_label?: string;
  /** Custom navigation route */
  nav_route?: string;
  /** Hide from navigation */
  nav_hidden?: boolean;
  /** Sidebar ordering weight (lower = earlier). Computed from hub.nav_order or fallback. */
  nav_order?: number;
  /** Maximum visible tabs before overflow. From hub.max_tabs or default 6. */
  max_tabs?: number;
}

// =============================================================================
// Utility Types
// =============================================================================

/**
 * Data source types.
 *
 * - mcp://skill/tool - Calls MCP tool
 * - /api/path - Calls dashboard API route
 * - static:{"key":"value"} - Inline static data
 */
export type DataSource = string;

/**
 * Loaded plugin dashboard with metadata.
 */
export interface PluginDashboard {
  /** Plugin bundle ID */
  pluginId: string;
  /** Skill ID */
  skillId: string;
  /** Parsed dashboard configuration */
  config: DashboardYaml;
  /** Path to the canonical skill metadata file */
  path: string;
}
