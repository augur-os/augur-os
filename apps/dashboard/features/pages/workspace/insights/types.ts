export type InsightSource = {
  path?: string | null;
  title?: string | null;
  kind?: string | null;
};

export type BrainInsight = {
  title: string;
  summary?: string | null;
  sources?: Array<string | InsightSource>;
  next_actions?: string[];
  impact_score?: number | null;
  confidence?: number | null;
  priority?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type BrainInsightsRun = {
  id: string;
  status?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  airplane_mode?: boolean;
  files_seen?: number;
  files_moved?: number;
  files_indexed?: number;
  files_skipped?: number;
  files_failed?: number;
  files_needing_review?: number;
  cloud_calls?: number;
  local_agent_calls?: number;
  insights?: BrainInsight[];
};

export type WikiStatusAction = {
  id: string;
  priority?: string | null;
  tool?: string | null;
  command?: string | null;
  reason?: string | null;
  inputs?: Record<string, unknown> | null;
};

export type WikiStructureStatus = {
  ok?: boolean;
  pages?: number;
  hubs?: number;
  missing_required?: unknown[];
  missing_links?: unknown[];
  orphan_pages?: unknown[];
  broken_links?: unknown[];
  schema_violations?: unknown[];
};

export type WikiCompilerStatus = {
  sources_total?: number;
  sources_compiled_with_concepts?: number;
  sources_pending_or_changed?: number;
  sources_stale_or_missing?: number;
  current?: boolean;
  by_kind?: Record<string, number>;
  pending_by_kind?: Record<string, number>;
  pending_by_family?: Record<string, number>;
};

export type WikiCoverageFamily = {
  family?: string | null;
  total?: number;
  compiled_with_concepts?: number;
  uncovered?: number;
};

export type WikiCoverageStatus = {
  concept_coverage_ratio?: number;
  top_uncovered_source_families?: WikiCoverageFamily[];
};

export type WikiIndexStatus = {
  indexed?: boolean;
  wiki_rag_entries?: number;
  demo_query?: string | null;
  demo_hit_count?: number;
  demo_ready?: boolean;
  demo_hits?: Array<{
    file?: string | null;
    content?: string | null;
    line?: string | null;
    scope?: string | null;
  }>;
};

export type WikiBatchStatus = {
  batch_count?: number;
  last_batch_created?: string | null;
  needs_update?: boolean;
};

export type WikiCompoundingHealth = {
  target_sources_per_page?: string | null;
  concept_page_count?: number;
  average_sources_per_concept_page?: number;
  thin_page_count?: number;
  orphan_page_count?: number;
  duplicate_concept_cluster_count?: number;
};

export type BrainInsightsWikiStatus = {
  verdict?: string | null;
  healthy?: boolean;
  structure?: WikiStructureStatus | null;
  compiler?: WikiCompilerStatus | null;
  coverage?: WikiCoverageStatus | null;
  index?: WikiIndexStatus | null;
  batches?: WikiBatchStatus | null;
  compounding_health?: WikiCompoundingHealth | null;
  actions?: WikiStatusAction[];
};

export type AskOutcome = {
  question?: string | null;
  summary?: string | null;
};

export type AskCluster = {
  id?: string | null;
  label?: string | null;
  summary?: string | null;
  questions?: string[];
};

export type BrainInsightsResponse = {
  success: boolean;
  latest_runs?: BrainInsightsRun[];
  wiki_status?: BrainInsightsWikiStatus | null;
  retained_ask_outcomes?: AskOutcome[];
  retained_ask_clusters?: AskCluster[];
  ask_outcomes?: AskOutcome[];
  ask_clusters?: AskCluster[];
  errors?: string[];
  error?: string | null;
};

export type InsightsNotice = {
  type: "success" | "warning" | "error";
  message: string;
} | null;
