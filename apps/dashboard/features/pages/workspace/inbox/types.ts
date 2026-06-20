export type InboxFolderCounts = {
  new_files: number;
  document_candidates: number;
  trash_candidates: number;
  failed: number;
};

export type InboxFolder = {
  id: string;
  name: string;
  path: string;
  enabled: boolean;
  counts: InboxFolderCounts;
  last_scan_at?: string | null;
  last_run_status?: string | null;
};

export type EmailSourceCounts = {
  pending_files: number;
  email_native: number;
  archives: number;
  degraded: number;
  unsupported: number;
  contained_messages: number;
  attachments: number;
  article_links: number;
  failed: number;
};

export type EmailSource = {
  id: string;
  type: "email_drop_folder";
  name: string;
  path: string;
  enabled: boolean;
  formats: string[];
  batch_limit: number;
  batch_order: "newest_first" | "oldest_first" | string;
  after_success_action?: string | null;
  after_success_target?: string | null;
  counts: EmailSourceCounts;
  last_scan_at?: string | null;
  last_consume_run_id?: string | null;
  last_run_status?: string | null;
  health_state?: string | null;
  health_error?: string | null;
  latest_run?: EmailDropRun | null;
};

export type EmailDropRun = {
  id: string;
  source_id: string;
  status: string;
  artifacts_seen?: number;
  files_moved?: number;
  packets_created?: number;
  archives_seen?: number;
  degraded_files_seen?: number;
  files_skipped?: number;
  files_failed?: number;
  attachments_seen?: number;
  links_seen?: number;
  wiki_update_marked?: boolean;
};

export type InboxFileResult = {
  source_path: string;
  final_path?: string | null;
  source_card_path?: string | null;
  extracted_path?: string | null;
  content_type: string;
  extraction_method: string;
  hardware_backend: string;
  confidence: string;
  route?: string | null;
  renamed_to?: string | null;
  rag_indexed: boolean;
  status: string;
  local_agent_used?: boolean;
  cloud_used?: boolean;
  escalation_reason?: string | null;
  cloud_provider?: string | null;
  cloud_model?: string | null;
  content_hash?: string | null;
  review_reason?: string | null;
  error?: string | null;
};

export type InboxRun = {
  id: string;
  status: string;
  airplane_mode?: boolean;
  files_seen?: number;
  files_moved?: number;
  files_indexed?: number;
  files_skipped?: number;
  files_failed?: number;
  files_needing_review?: number;
  cloud_calls?: number;
  local_agent_calls?: number;
  file_results?: InboxFileResult[];
};

export type InboxSourceLane = {
  id: string;
  type: string;
  name: string;
  domain: string;
  drop_root: string;
  write_modes: string[];
  default_target_vault: string;
  allowed_targets: string[];
  enabled: boolean;
  health_state?: string | null;
  health_error?: string | null;
};

export type InboxVaultTarget = {
  id: string;
  kind: string;
  name: string;
  vault_root: string;
  docs_root: string;
  default: boolean;
  writable: boolean;
};

export type InboxVaultCandidate = {
  candidate_id: string;
  kind: string;
  name: string;
  vault_root: string;
  docs_root: string;
  reason: string;
  status: string;
  writable: boolean;
};

export type InboxRoutingQueueItem = {
  packet_id: string;
  title: string;
  source_id: string;
  status: string;
  failure_state?: string | null;
  packet_dir: string;
};

export type UnifiedInboxRun = {
  id: string;
  status: string;
  source_id: string;
  moved: number;
  archived: number;
  questions: number;
};

export type BrainInboxResponse = {
  success: boolean;
  folders: InboxFolder[];
  mail_drop_sources?: EmailSource[];
  email_sources?: EmailSource[];
  email_drop_latest_runs?: EmailDropRun[];
  latest_runs?: InboxRun[];
  source_lanes?: InboxSourceLane[];
  vault_targets?: InboxVaultTarget[];
  discovered_vaults?: InboxVaultCandidate[];
  routing_queue?: InboxRoutingQueueItem[];
  latest_unified_runs?: UnifiedInboxRun[];
  run_status?: {
    state?: string | null;
    message?: string | null;
    updated_at?: string | null;
  } | null;
  error?: string | null;
};

export type InboxAction = "scan" | "consume" | "purge";
export type EmailAction = "scan" | "consume" | "wiki";

export type InboxActionState = {
  folderId: string;
  action: InboxAction | EmailAction;
} | null;

export type InboxNotice = {
  type: "success" | "warning" | "error";
  message: string;
} | null;
