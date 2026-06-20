export type ItemStatusValue = "done" | "pending" | "skipped" | "regressed";
export type PhaseId = "foundation" | "knowledge" | "personalization";
export type WidgetState = "card" | "bar" | "chip" | "alert";
export type ActionType = "command" | "route" | "mcp";

export interface ItemAction {
  type: ActionType;
  label: string;
  command?: string;
  route?: string;
  mcp_tool?: string;
}

export interface ItemStatus {
  id: string;
  label: string;
  description: string;
  status: ItemStatusValue;
  action: ItemAction;
  last_checked: string;
  details?: string;
}

export interface PhaseStatus {
  id: PhaseId;
  label: string;
  total: number;
  completed: number;
  pct: number;
  items: ItemStatus[];
}

export interface SetupStatus {
  version: 1;
  computed_at: string;
  total: number;
  completed: number;
  pct: number;
  state: WidgetState;
  ever_completed: boolean;
  phases: PhaseStatus[];
}
