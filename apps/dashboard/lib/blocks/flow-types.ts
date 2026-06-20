import type { BlockType, BlockSearch, BlockFilter, BlockGroupBy, RowAction, BlockQuickAdd, ConfigSchema } from "./types";

export type BlockSize = "full" | "half" | "third";

/** showIf expression — controls conditional block visibility */
export type ShowIfExpression =
  | { blockHasData: string }
  | { configFlag: string };

export interface BlockConfig {
  type: BlockType | "custom";
  /** Optional block identifier — used by refetch and showIf references */
  id?: string;
  mcp_tool?: string;
  component?: string;
  size?: BlockSize;
  scope?: "hub" | "skill";
  skill_id?: string;
  manifest_id?: string;
  search?: BlockSearch;
  filters?: BlockFilter[];
  row_actions?: RowAction[];
  quick_add?: BlockQuickAdd;
  group_by?: BlockGroupBy;
  view_modes?: string[];
  default_view?: string;
  export_enabled?: boolean;
  config_schema?: ConfigSchema;
  /** Conditional visibility — block only renders when expression is truthy */
  showIf?: ShowIfExpression;
  [key: string]: unknown;
}

export interface PageConfig {
  title: string;
  icon: string;
  hub: string;
  route: string;
  order?: number;
  /** Optional one-line description rendered under the page title. */
  description?: string;
  blocks: BlockConfig[];
}

export const SIZE_FRACTIONS: Record<BlockSize, number> = {
  full: 1,
  half: 0.5,
  third: 1 / 3,
};
