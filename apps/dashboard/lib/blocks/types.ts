/** The 22 canonical block types */
export type BlockType =
  | "stat-card"
  | "stat-grid"
  | "data-list"
  | "data-table"
  | "action-bar"
  | "card-grid"
  | "chart"
  | "markdown"
  | "calendar"
  | "activity-feed"
  | "notes"
  | "embed"
  | "ops-board"
  | "progress"
  | "kanban"
  | "tabbed"
  | "health"
  | "vault-notes"
  | "custom-sources"
  | "file-list"
  | "data-preview"
  | "widget"
  | "metrics-dashboard";

/** Config field definition for light config UI */
export interface ConfigField {
  type: "string" | "number" | "boolean" | "enum";
  default?: string | number | boolean | string[];
  options?: string[];
  label?: string;
  placeholder?: string;
}

/** Config schema — maps field names to their definitions */
export type ConfigSchema = Record<string, ConfigField>;

/** Data source for a block — MCP tool only (apiRoute pattern removed, see block migration) */
export interface DataSource {
  mcpTool?: string;
}

/** D14: Per-item action declared in skill config row_actions[] */
export interface RowAction {
  id: string;
  icon: string;
  label: string;
  dispatch: 'fire' | 'modal' | 'ide' | 'navigate';
  mcp_tool?: string;
  payload_fields?: string[];
  /** Static args merged into the MCP tool call alongside payload fields */
  static_args?: Record<string, unknown>;
  confirm?: boolean;
  confirm_message?: string;
  href_template?: string;
  /** Form fields — when present, clicking opens ActionFormModal instead of direct dispatch */
  fields?: import("@/lib/plugin-schema/types").FormField[];
  /** Block IDs to refetch after successful form submission */
  refetch?: string[];
  /** Dangerous action guard — user must type this exact string to enable submit */
  confirmText?: string;
}

/** D15: Editable field declared in skill config editable_fields[] */
export interface EditableField {
  field: string;
  type: 'text' | 'select' | 'number' | 'markdown' | 'toggle';
  save_action: string;
  options?: string[];
  min?: number;
  max?: number;
  placeholder?: string;
}

/** Inline action on a stat-card — fires an MCP tool (e.g. "Sync now" → rag-sync) */
export interface StatCardAction {
  label: string;
  mcp_tool: string;
}

/** ADR-274 Tier 1: Search definition */
export interface BlockSearch {
  enabled: boolean;
  fields?: string[];
  placeholder?: string;
}

/** ADR-274 Tier 1: Filter definition */
export interface BlockFilter {
  field: string;
  type: 'pills' | 'dropdown';
  label?: string;
  values?: string[];
  colors?: Record<string, string>;
}

/** ADR-274 Tier 1: Quick-add field */
export interface BlockQuickAddField {
  name: string;
  type: string;
  required?: boolean;
  placeholder?: string;
  options?: string[];
}

/** ADR-274 Tier 1: Quick-add definition */
export interface BlockQuickAdd {
  enabled: boolean;
  fields: BlockQuickAddField[];
  action: string;
}

/** ADR-274 Tier 1: Group-by definition */
export interface BlockGroupBy {
  field: string;
  collapsedDefault?: boolean;
  showCount?: boolean;
  sort?: string;
}

/** ADR-274 Tier 2: Progress definition */
export interface BlockProgress {
  valueField: string;
  maxField: string;
  labelField: string;
  format?: string;
  colorRule?: string;
}

/** ADR-274 Tier 2: Chart definition
 *
 * Chart type guide:
 *   area  — Real-time/streaming data, trend data with 20% opacity fill
 *   line  — Time-series forecasts, multi-series comparisons (dots on hover only)
 *   bar   — Categorical comparisons, rankings, discrete buckets
 *   pie   — Part-of-whole breakdowns
 *   donut — Pie with center cutout for summary stat overlay
 *
 * Color accepts named values (cyan, emerald, amber, rose) or hex.
 */
export interface BlockChart {
  type: string;
  xField: string;
  yField: string;
  /** Named color (cyan, emerald, amber, rose, etc.) or hex value */
  color?: string;
  /** Chart height in px (default: 300) */
  height?: number;
}

/** ADR-274 Tier 3: Kanban on-move action */
export interface BlockKanbanOnMove {
  action: string;
  idField: string;
  statusField: string;
}

/** ADR-274 Tier 3: Kanban definition */
export interface BlockKanban {
  columnField: string;
  columns: string[];
  cardTitleField: string;
  cardSubtitleField?: string;
  onMove?: BlockKanbanOnMove;
}

/** ADR-274 Tier 3: Tab definition */
export interface BlockTab {
  id: string;
  label: string;
  source: string;
}

/** Block manifest — declared by plugins in skill config contributions.blocks[] */
export interface BlockManifest {
  id: string;
  type: BlockType;
  title: string;
  icon: string;
  expandTo?: string;
  configSchema: ConfigSchema;
  dataSource?: DataSource;
  hub: string;
  skill: string;
  category?: string;
  rowActions?: RowAction[];
  editableFields?: EditableField[];
  /** Inline stat-card action (e.g. "Sync now") — merged into the block config */
  action?: StatCardAction;
  // ADR-274 Tier 1
  search?: BlockSearch;
  filters?: BlockFilter[];
  quickAdd?: BlockQuickAdd;
  groupBy?: BlockGroupBy;
  // ADR-274 Tier 2
  viewModes?: string[];
  defaultView?: string;
  progress?: BlockProgress;
  chart?: BlockChart;
  // ADR-274 Tier 3
  exportEnabled?: boolean;
  kanban?: BlockKanban;
  tabs?: BlockTab[];
}

/** Block instance — a placed block within a view */
export interface BlockInstance {
  instanceId: string;
  blockId: string;
  config: Record<string, unknown>;
  position: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
}

/** Props passed to every block component */
export interface BlockProps<TConfig = Record<string, unknown>> {
  instanceId: string;
  config: TConfig;
  dataSource?: DataSource;
  mode: "compact" | "full";
  onExpand?: () => void;
  onConfigure?: () => void;
  /** Data passed from BlockRenderer (lifted useBlockData) */
  data?: unknown;
  /** Loading state passed from BlockRenderer */
  loading?: boolean;
  /** Error string passed from BlockRenderer */
  error?: string | null;
  rowActions?: RowAction[];
  editableFields?: EditableField[];
  // ADR-274 manifest fields
  search?: BlockSearch;
  filters?: BlockFilter[];
  quickAdd?: BlockQuickAdd;
  groupBy?: BlockGroupBy;
  viewModes?: string[];
  defaultView?: string;
  exportEnabled?: boolean;
}

/** A user view — a canvas of block instances */
export interface View {
  id: string;
  title: string;
  icon?: string;
  pinned: boolean;
  createdAt: string;
  updatedAt: string;
  layout: {
    columns: number;
    rowHeight: number;
  };
  blocks: BlockInstance[];
}
