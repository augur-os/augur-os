import type { BlockType, ConfigSchema } from "@/lib/blocks/types";

// --- Block state reported by components ---

export type RenderState = "loading" | "error" | "ready" | "empty";

export interface BlockState {
  blockId: string;
  instanceId: string;
  type: BlockType;
  mounted: boolean;
  renderState: RenderState;
  config: Record<string, unknown>;
  data: unknown;
  error?: string;
  lastUpdated: number;
}

// --- Error types ---

export type WebMCPErrorCode =
  | "NOT_FOUND"
  | "INVALID_CONFIG"
  | "UNMOUNTED"
  | "FETCH_FAILED"
  | "INVALID_ACTION";

export interface WebMCPError {
  error: true;
  code: WebMCPErrorCode;
  message: string;
  blockId?: string;
  details?: Record<string, unknown>;
}

// --- Tool input/output types ---

export interface BlocksDiscoverInput {
  hub?: string;
  type?: BlockType;
  search?: string;
  mounted?: boolean;
}

export interface BlockManifestResult {
  id: string;
  type: BlockType;
  title: string;
  hub: string;
  configSchema: ConfigSchema;
  mounted: boolean;
  actions: string[];
}

export interface BlocksDiscoverOutput {
  blocks: BlockManifestResult[];
}

export interface BlocksReadInput {
  blockId: string;
  config?: Record<string, unknown>;
  includeState?: boolean;
}

export interface BlocksReadOutput {
  blockId: string;
  mounted: boolean;
  renderState: RenderState;
  config: Record<string, unknown>;
  data: unknown;
  renderInfo?: {
    rowCount?: number;
    visibleColumns?: string[];
  };
  lastUpdated: number;
  error?: string;
}

export interface BlocksConfigureInput {
  blockId: string;
  instanceId?: string;
  config: Record<string, unknown>;
  waitForSettle?: boolean;
}

export interface BlocksConfigureOutput {
  success: true;
  blockId: string;
  previousConfig: Record<string, unknown>;
  newConfig: Record<string, unknown>;
  renderState: RenderState;
  settled: boolean;
}

export interface BlocksActInput {
  blockId: string;
  action: string;
  args?: Record<string, unknown>;
}

export interface BlocksActOutput {
  success: true;
  action: string;
  blockId: string;
  result?: unknown;
}

// --- Page state ---

export interface PageState {
  pageId: string;
  skillId: string;
  hub: string;
  path: string;
  mounted: boolean;
  renderState: RenderState;
  blocks: string[]; // blockIds on this page
  lastUpdated: number;
}

// --- Page tool I/O types ---

export interface PagesDiscoverInput {
  hub?: string;
  mounted?: boolean;
}

export interface PageManifestResult {
  id: string;
  hub: string;
  title: string;
  path: string;
  mounted: boolean;
  blocks: string[];
}

export interface PagesDiscoverOutput {
  pages: PageManifestResult[];
}

export interface PagesReadInput {
  pageId: string;
  includeBlocks?: boolean;
}

export interface PagesReadOutput {
  pageId: string;
  mounted: boolean;
  path: string;
  activeTab?: string;
  blocks?: Array<{
    blockId: string;
    renderState: RenderState;
    data?: unknown;
  }>;
}

// --- View state ---

export interface ViewState {
  viewId: string;
  title: string;
  mounted: boolean;
  editing: boolean;
  blocks: Array<{
    instanceId: string;
    blockId: string;
    position: { x: number; y: number; w: number; h: number };
  }>;
  layout: { columns: number; rowHeight: number };
  lastUpdated: number;
}

// --- View tool I/O types ---

export interface ViewsManageInput {
  action: "create" | "read" | "update" | "delete" | "list";
  viewId?: string;
  title?: string;
  layout?: { columns: number; rowHeight: number };
  icon?: string;
  pinned?: boolean;
}

export interface ViewsManageOutput {
  success: true;
  view?: unknown;
  views?: unknown[];
}

export interface ViewsComposeInput {
  viewId: string;
  action: "add" | "remove" | "move";
  blockId?: string;
  instanceId?: string;
  position?: { x: number; y: number; w: number; h: number };
  config?: Record<string, unknown>;
}

export interface ViewsComposeOutput {
  success: true;
  view?: unknown;
}

// --- Navigation state ---

export interface NavigationState {
  path: string;
  hub: string | null;
  activeTab: string | null;
  breadcrumbs: string[];
  availableTabs: Array<{ label: string; href: string }>;
}

export interface NavigationGotoInput {
  path: string;
}

export interface NavigationGotoOutput {
  success: true;
  previousPath: string;
  newPath: string;
  hub: string | null;
}

export type NavigationStateInput = Record<string, never>;

export type NavigationStateOutput = NavigationState;

// --- Catalog tool I/O types ---

export interface CatalogSearchInput {
  query: string;
  types?: Array<"block" | "page" | "action">;
}

export interface CatalogSearchResult {
  type: "block" | "page" | "action";
  id: string;
  title: string;
  hub?: string;
  description?: string;
}

export interface CatalogSearchOutput {
  results: CatalogSearchResult[];
  total: number;
}

export interface CatalogPreviewInput {
  blockId: string;
  config?: Record<string, unknown>;
}

export interface CatalogPreviewOutput {
  blockId: string;
  type: string;
  title: string;
  data: unknown;
}

// --- Form state ---

export interface FormField {
  name: string;
  type: "string" | "number" | "boolean" | "enum" | "text";
  label?: string;
  value?: unknown;
  options?: string[];
  required?: boolean;
  placeholder?: string;
}

export interface FormState {
  formId: string;
  pageId?: string;
  fields: FormField[];
  values: Record<string, unknown>;
  dirty: boolean;
  submitting: boolean;
  lastUpdated: number;
}

// --- Form tool I/O types ---

export interface FormsDiscoverInput {
  page?: string;
}

export interface FormsDiscoverOutput {
  forms: Array<{
    formId: string;
    pageId?: string;
    fields: FormField[];
    values: Record<string, unknown>;
  }>;
}

export interface FormsFillInput {
  formId: string;
  fields: Record<string, unknown>;
}

export interface FormsFillOutput {
  success: true;
  formId: string;
  previousValues: Record<string, unknown>;
  newValues: Record<string, unknown>;
}

export interface FormsSubmitInput {
  formId: string;
}

export interface FormsSubmitOutput {
  success: true;
  formId: string;
  result?: unknown;
}

// --- Custom page descriptor ---

export interface WebMCPPageDescriptor {
  pageId: string;
  title: string;
  capabilities: string[]; // what this page can do: ["search", "filter", "create", etc.]
  sections: Array<{
    id: string;
    title: string;
    type: "data" | "form" | "chart" | "list" | "custom";
  }>;
}

// --- Agent state ---

export interface AgentBubbleState {
  bubbleId: string;
  actionId: string;
  label: string;
  status: "running" | "attention" | "complete" | "error";
  output: string;
  lastUpdated: number;
}

// --- Agent tool I/O types ---

export type AgentsListInput = Record<string, never>;

export interface AgentsListOutput {
  agents: Array<{
    bubbleId: string;
    label: string;
    status: string;
  }>;
}

export interface AgentsReadInput {
  bubbleId: string;
}

export interface AgentsReadOutput {
  bubbleId: string;
  label: string;
  status: string;
  output: string;
}

export interface AgentsInteractInput {
  bubbleId: string;
  input: string;
}

export interface AgentsInteractOutput {
  success: true;
  bubbleId: string;
}

// --- WebMCP spec types (navigator.modelContext) ---

export interface ModelContextTool {
  name: string;
  description: string;
  inputSchema?: object;
  execute: (input: unknown, client: ModelContextClient) => Promise<unknown>;
  annotations?: { readOnlyHint?: boolean };
}

export interface ModelContextClient {
  requestUserInteraction: (callback: () => Promise<unknown>) => Promise<unknown>;
}

export interface ModelContext {
  registerTool(tool: ModelContextTool): void;
  unregisterTool(name: string): void;
  // Polyfill extensions (not in spec yet)
  executeTool?(name: string, input: unknown): Promise<unknown>;
  listTools?(): Array<{
    name: string;
    description: string;
    inputSchema?: object;
    annotations?: { readOnlyHint?: boolean };
  }>;
  __polyfill?: boolean;
}

// --- Type guards ---

const VALID_RENDER_STATES: RenderState[] = ["loading", "error", "ready", "empty"];
const VALID_ERROR_CODES: WebMCPErrorCode[] = [
  "NOT_FOUND",
  "INVALID_CONFIG",
  "UNMOUNTED",
  "FETCH_FAILED",
  "INVALID_ACTION",
];

export function isBlockState(value: unknown): value is BlockState {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.blockId === "string" &&
    typeof v.instanceId === "string" &&
    typeof v.type === "string" &&
    typeof v.mounted === "boolean" &&
    typeof v.renderState === "string" &&
    VALID_RENDER_STATES.includes(v.renderState as RenderState) &&
    typeof v.config === "object" &&
    v.config !== null &&
    typeof v.lastUpdated === "number"
  );
}

export function isWebMCPError(value: unknown): value is WebMCPError {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    v.error === true &&
    typeof v.code === "string" &&
    VALID_ERROR_CODES.includes(v.code as WebMCPErrorCode) &&
    typeof v.message === "string"
  );
}
