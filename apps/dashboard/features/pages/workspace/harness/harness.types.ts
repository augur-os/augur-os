export type Capability = {
  id: string;
  type: string;
  label: string;
  hub: string | null;
  owner_skill: string | null;
  source_path: string;
  summary: string;
  tags: string[];
  status: string;
};

export type Diagnostic = {
  id: string;
  severity: "info" | "warning" | "error";
  family: string;
  reason: string;
  affected_capability_ids: string[];
  source_path: string;
  recommended_action: { kind: string; label: string };
};

export type HarnessSnapshot = {
  generated_at: string;
  capabilities: Capability[];
  relationships: unknown[];
  diagnostics: Diagnostic[];
  provenance: {
    source_counts?: Record<string, number>;
    partial_failures?: unknown[];
  };
};

export type HarnessResponse = {
  success: boolean;
  state: "missing" | "ready";
  snapshot: HarnessSnapshot | null;
  actions: { kind: string; label: string; direct: boolean }[];
};

export type ManagerActionState = {
  enabled: boolean;
  tool: string;
  reason: string | null;
};

export type ManagerRow = {
  id: string;
  capability_type: string;
  name: string;
  owner: string;
  owner_label: string;
  winner_tier: string;
  winner_tier_label: string;
  winner_brain_id: string;
  winner_path: string;
  summary?: string;
  tiers: {
    tier: string;
    tier_label: string;
    brain_id: string;
    path: string;
    status: "effective" | "shadowed";
    owner: string;
  }[];
  shadowed: string[];
  shadowed_entries: {
    tier: string;
    tier_label: string;
    brain_id: string;
    path: string;
  }[];
  actions: {
    promote: ManagerActionState;
    demote: ManagerActionState;
  };
};

export type ManagerGroup = {
  label: string;
  entries: ManagerRow[];
  effective: number;
  shadowed: string[];
};

export type ManagerSnapshot = {
  generated_at: string;
  tiers: string[];
  tier_details: {
    key: string;
    label: string;
    brain_id: string;
    root: string;
    writable: boolean;
  }[];
  groups: Record<string, ManagerGroup>;
};

export type ManagerResponse = {
  success: boolean;
  state?: "ready";
  snapshot?: ManagerSnapshot;
  groups?: Record<string, ManagerGroup>;
  tier_details?: ManagerSnapshot["tier_details"];
  tiers?: string[];
  generated_at?: string;
};

export interface BrainHarnessUiState {
  isRefreshing: boolean;
  refreshError: string | null;
  managerActionError: string | null;
  managerBusyId: string | null;
  capabilityQuery: string;
  capabilityType: string;
  managerTier: string;
}

export type BrainHarnessAction = {
  type: "set-field";
  field: keyof BrainHarnessUiState;
  value: unknown;
};
