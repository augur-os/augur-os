/**
 * Page Builder Types (ADR-190)
 *
 * Types for the page builder state, block instances, and block manifests.
 */

/**
 * Full state of a page being built/edited.
 */
export interface PageBuilderState {
  /** Page display name */
  name: string;
  /** URL slug (auto-generated from name) */
  slug: string;
  /** Target hub ID */
  hub: string;
  /** Lucide icon name */
  icon: string;
  /** Target skill to write generated files into */
  targetSkill: string;
  /** Block instances on the canvas */
  blocks: BlockInstance[];
}

/**
 * A single block placed on the canvas.
 */
export interface BlockInstance {
  /** Unique instance ID (UUID) */
  id: string;
  /** Block type ID (references BlockManifest.id) */
  blockType: string;
  /** Configured props for this instance */
  props: Record<string, unknown>;
  /** Layout position and size */
  layout: BlockLayout;
}

/**
 * Layout position and dimensions for a block on the canvas.
 */
export interface BlockLayout {
  /** Column position */
  col: number;
  /** Row position */
  row: number;
  /** Width in grid units */
  w: number;
  /** Height in grid units */
  h: number;
}

/**
 * Block manifest — the full descriptor for a block type.
 * Used by the block palette and registry.
 */
export interface BlockManifest {
  /** Unique block type identifier */
  id: string;
  /** Display name */
  name: string;
  /** Lucide icon name */
  icon: string;
  /** Block category */
  category: 'content' | 'data' | 'communication' | 'automation' | 'custom';
  /** Render strategy */
  render: 'form' | 'table' | 'card' | 'chart' | 'markdown' | 'timeline' | 'custom';
  /** Block source type */
  source: 'mcp' | 'plugin';
  /** MCP tool name (when source is 'mcp') */
  mcpTool?: string;
  /** MCP server name (when source is 'mcp') */
  mcpServer?: string;
  /** Relative path to React component (when source is 'plugin') */
  component?: string;
  /** Configurable props schema */
  props?: BlockPropSchema[];
}

/**
 * Schema for a single configurable prop on a block.
 */
export interface BlockPropSchema {
  /** Property name */
  name: string;
  /** Property type */
  type: 'string' | 'number' | 'boolean' | 'file-path' | 'select';
  /** Default value */
  default?: string | number | boolean;
  /** Whether the prop is required */
  required?: boolean;
  /** Options for select type */
  options?: string[];
}

/**
 * Response from the save API.
 */
export interface SaveResponse {
  success: boolean;
  pageUrl?: string;
  filesCreated?: string[];
  error?: string;
}

/**
 * Response from the blocks discovery API.
 */
export interface BlocksResponse {
  blocks: BlockManifest[];
  categories: Record<string, BlockManifest[]>;
}

/**
 * A page record in the pages list.
 */
export interface PageRecord {
  /** Page slug */
  slug: string;
  /** Display name */
  name: string;
  /** Target hub */
  hub: string;
  /** Icon name */
  icon: string;
  /** Number of blocks */
  blockCount: number;
  /** Creation timestamp */
  createdAt: string;
  /** Target skill */
  targetSkill: string;
}

/**
 * Reusable page template loaded from the skill vault templates store.
 */
export interface PageBuilderTemplate {
  id: string;
  name: string;
  description?: string;
  hub: string;
  icon?: string;
  targetSkill?: string;
  blocks: Array<{
    blockType: string;
    props?: Record<string, unknown>;
  }>;
}

/**
 * Saved page draft loaded from the skill vault drafts store.
 */
export interface PageBuilderDraft extends PageBuilderState {
  id: string;
  updatedAt: string;
}
