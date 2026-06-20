/**
 * ADR-272: Shared types for skill-meta API and section components.
 *
 * SkillMeta is the central data structure returned by the skill-meta
 * API route and consumed by every section renderer on the auto-page.
 */

export interface SkillMeta {
  skill: {
    id: string;
    title: string;
    icon: string;
    hub: string;
    state: 'dev' | 'mature' | 'stable';
    isNewToDashboard?: boolean;
    ownership?: 'augur' | 'external' | 'adopted';
    source?: string;
    upstream?: string | Record<string, string>;
    updateAvailable?: boolean;
  };
  health: {
    status: 'healthy' | 'degraded' | 'error' | 'unknown';
    lastCheck: string;
    errors24h: number;
    uptime?: string;
  };
  stats: Array<{ key: string; value: string | number; icon?: string; color?: string }>;
  actions: Array<{
    id: string;
    title: string;
    description: string;
    icon?: string;
    dispatch: string;
    primary?: boolean;
    chips?: string[];
  }>;
  prompts: Array<{
    id: string;
    label: string;
    description?: string;
    prompt: string;
    icon?: string;
  }>;
  commands: Array<{
    id: string;
    label: string;
    description?: string;
    command: string;
    icon?: string;
  }>;
  vaultNotes: Array<{ name: string; modified: string; preview: string }>;
  documents: Array<{ name: string; type: string; size: number; modified: string }>;
  assets: Array<{ name: string; type: string; purpose: string; overridden?: boolean }>;
  dataFiles: Array<{
    name: string;
    type: 'yaml' | 'json' | 'md';
    count: number;
    preview: Array<Record<string, unknown>>;
  }>;
  config: Array<{ key: string; value: unknown; editable: boolean }>;
  mcpTools: Array<{ name: string; description: string; schema: Record<string, unknown> }>;
  blocks: Array<{ id: string; title: string; icon: string; type: string; expandTo?: string }>;
  customSources: DataSource[];
  _errors: Record<string, { message: string; retryable: boolean }>;
}

// ── Filter definition for data sources (ADR-274 D1) ──────────────────
export interface FilterDefinition {
  field: string;
  type: 'pills' | 'dropdown' | 'toggle';
  values?: string[];
  colors?: Record<string, string>;
}

// ── Search definition for data sources (ADR-274 D1) ──────────────────
export interface SearchDefinition {
  enabled: boolean;
  fields?: string[];
  placeholder?: string;
}

// ── Quick-add field definition (ADR-274 D2) ──────────────────────────
export interface QuickAddField {
  name: string;
  type: 'text' | 'select' | 'number' | 'date';
  required?: boolean;
  placeholder?: string;
  options?: string[];
}

export interface QuickAddDefinition {
  enabled: boolean;
  fields: QuickAddField[];
  action: string;
}

// ── Group-by definition (ADR-274 D3) ─────────────────────────────────
export interface GroupByDefinition {
  field: string;
  collapsed_default?: boolean;
  show_count?: boolean;
  sort?: 'alphabetical' | 'count-desc' | 'custom';
}

// ── Computed stat definition (ADR-274 D4) ────────────────────────────
export interface ComputedStatDefinition {
  label: string;
  value: string;
  format?: 'currency' | 'percentage' | 'number';
  icon?: string;
  color_rule?: string;
}

// ── View mode definition (ADR-274 D5) ────────────────────────────────
export type ViewMode = 'list' | 'grid' | 'card';

// ── Progress definition (ADR-274 D6) ─────────────────────────────────
export interface ProgressDefinition {
  value_field: string;
  max_field: string;
  label_field: string;
  format?: 'currency' | 'percentage' | 'number';
  color_rule?: string;
}

// ── Gallery definition (ADR-274 D7) ──────────────────────────────────
export interface GalleryDefinition {
  columns?: number;
  group_by?: string;
  lightbox?: boolean;
  show_caption?: boolean;
}

// ── Row action (modal detail) definition (ADR-274 D8) ────────────────
export interface RowActionSection {
  field: string;
  render: 'markdown' | 'key-value' | 'text';
}

export interface RowActionDefinition {
  type: 'modal';
  title_field: string;
  sections: RowActionSection[];
}

// ── Chart definition (ADR-274 D9) ────────────────────────────────────
//
// Chart type selection guide:
//   area  — Real-time/streaming data, or trend data with filled backdrop.
//           Renders with 20% opacity fill, no dots, strokeWidth 2.
//   line  — Time-series forecasts or multi-series comparisons.
//           Clean lines with no dots (hover-only activeDot).
//   bar   — Categorical comparisons, rankings, discrete buckets.
//   pie   — Part-of-whole breakdowns (budget splits, status distributions).
//   donut — Same as pie but with center cutout for summary stat overlay.
//
// Color accepts named colors (cyan, emerald, amber, rose, etc.) or hex.
// Default palette: cyan (#00f0ff), emerald, amber, rose.
export interface ChartDefinition {
  type: 'bar' | 'line' | 'area' | 'pie' | 'donut';
  x_field: string;
  y_field: string;
  /** Named color (cyan, emerald, amber, rose, etc.) or hex value */
  color?: string;
  /** Chart height in px (default: 300) */
  height?: number;
}

// ── Export definition (ADR-274 D10) ──────────────────────────────────
export interface ExportDefinition {
  enabled: boolean;
  format?: 'csv' | 'json';
  filename?: string;
}

// ── Kanban definition (ADR-274 D12) ──────────────────────────────────
export interface KanbanDefinition {
  column_field: string;
  columns: string[];
  card_title_field: string;
  card_subtitle_field?: string;
  on_move?: {
    action: string;
    payload?: {
      id_field: string;
      status_field: string;
    };
  };
}

// ── Tab definition for tabbed sections (ADR-274 D13) ─────────────────
export interface TabbedSectionTab {
  id: string;
  label: string;
  source: string;
}

// ── Extended DataSource with ADR-274 capabilities ────────────────────
export interface DataSource {
  id: string;
  type: 'mcp_tool' | 'api_route' | 'file';
  source: string;
  display: string;
  title: string;
  config?: Record<string, unknown>;
  // ADR-274 D1: Search & Filtering
  search?: SearchDefinition;
  filters?: FilterDefinition[];
  // ADR-274 D2: Inline Quick-Add
  quick_add?: QuickAddDefinition;
  // ADR-274 D3: Grouping
  group_by?: GroupByDefinition;
  // ADR-274 D4: Computed Stats
  stats?: ComputedStatDefinition[];
  // ADR-274 D5: View Mode Toggles
  view_modes?: ViewMode[];
  default_view?: ViewMode;
  // ADR-274 D6: Progress Bars
  progress?: ProgressDefinition;
  // ADR-274 D7: Image Gallery
  gallery?: GalleryDefinition;
  // ADR-274 D8: Modal Detail Views
  row_action?: RowActionDefinition;
  // ADR-274 D9: Charts
  chart?: ChartDefinition;
  // ADR-274 D10: CSV Export
  export?: ExportDefinition;
  // ADR-274 D12: Kanban Board
  kanban?: KanbanDefinition;
  // ADR-274 D13: Tabbed Sections
  tabs?: TabbedSectionTab[];
  /** D14: Per-item actions with dispatch modes (extends D8 row_action) */
  row_actions?: Array<{
    id: string;
    icon: string;
    label: string;
    dispatch: 'fire' | 'modal' | 'ide' | 'navigate';
    mcp_tool?: string;
    payload_fields?: string[];
    confirm?: boolean;
    confirm_message?: string;
    href_template?: string;
  }>;
  /** D15: Inline editable fields */
  editable_fields?: Array<{
    field: string;
    type: 'text' | 'select' | 'number' | 'markdown' | 'toggle';
    save_action: string;
    options?: string[];
    min?: number;
    max?: number;
  }>;
}

export interface SectionProps {
  skillMeta: SkillMeta;
}
