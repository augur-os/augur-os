/**
 * Remote LLM Providers - Type Definitions
 *
 * Core types for the remote providers system including provider configurations,
 * security settings, and execution contexts.
 *
 * Extended by ADR-020 to support unified agent execution protocol.
 */

// =============================================================================
// Execution Mode Types (ADR-020)
// =============================================================================

/**
 * Execution mode determines how the prompt is sent to an agent
 */
export type ExecutionMode =
  | "local" // Paste to local agent GUI (Cursor, Claude Code, etc.)
  | "api" // Direct API call via configured provider
  | "auto"; // System selects best available

/**
 * Agent type classification
 */
export type AgentType = "ide" | "cli" | "sdk" | "browser" | "api" | "utility";

/**
 * Agent health status
 */
export type AgentHealth = "healthy" | "degraded" | "unhealthy" | "offline";

/**
 * Unified agent target (ADR-020)
 * Represents any execution target - local IDE, remote API, or utility
 */
export interface AgentTarget {
  id: string;
  name: string;
  type: AgentType;
  execution_mode: ExecutionMode;
  capabilities: string[];
  health: AgentHealth;
  icon: string;
  description?: string;
  /** For API agents, reference to provider config */
  config_ref?: string;
}

/**
 * Observation configuration for local agents
 */
export interface ObservationConfig {
  enabled: boolean;
  type: "mcp-state" | "file-watch" | "git-commit" | "none";
  watch_paths?: string[];
  completion_signal?: string;
  timeout_ms: number;
  poll_interval_ms: number;
}

/**
 * Unified execution request (ADR-020)
 */
export interface ExecutionRequest {
  prompt: string;
  agent: AgentTarget;
  mode: ExecutionMode;
  observation?: ObservationConfig;
  /** Optional user message prepended to system prompt */
  userMessage?: string;
  /** Action context */
  actionId?: string;
}

/**
 * Unified execution result (ADR-020)
 */
export interface UnifiedExecutionResult {
  status: "sent" | "completed" | "copied" | "error" | "timeout";
  message?: string;
  response?: string;
  error?: string;
  /** For API calls, includes cost/token info */
  cost?: number;
  tokens?: { input: number; output: number };
  durationMs?: number;
}

// =============================================================================
// Provider Types
// =============================================================================

export type ProviderId =
  | "glama"
  | "openrouter"
  | "anthropic"
  | "openai"
  | "gemini"
  | "groq"
  | "together"
  | "custom";

export type AuthMethod = "oauth" | "manual";

export interface ProviderPricing {
  /** Cost per 1M input tokens in USD */
  inputPer1M: number;
  /** Cost per 1M output tokens in USD */
  outputPer1M: number;
  /** Model name this pricing applies to (for display) */
  model: string;
}

export interface ProviderDefinition {
  id: ProviderId;
  name: string;
  description: string;
  authMethod: AuthMethod;
  /** Base URL for API calls */
  baseUrl: string;
  /** OAuth authorization URL (only for oauth auth method) */
  oauthUrl?: string;
  /** Default model to use */
  defaultModel: string;
  /** Example pricing (for default model) */
  pricing: ProviderPricing;
  /** Environment variable name for API key */
  apiKeyEnv: string;
  /** Whether this provider is available (can be disabled globally) */
  available: boolean;
  /** Icon to display (lucide-react icon name) */
  icon: string;
  /** Brand color for UI accent */
  brandColor: string;
  /** Provider website URL */
  websiteUrl?: string;
}

export interface ProviderConfig {
  id: ProviderId;
  enabled: boolean;
  /** Reference to environment variable (not the actual key!) */
  apiKeyEnv: string;
  /** Whether the API key is configured (has value in env) */
  hasApiKey: boolean;
  /** Default model override */
  defaultModel?: string;
  /** Last successful connection test */
  lastTested?: string;
  /** OAuth access token (for oauth providers, encrypted) */
  oauthToken?: string;
}

// =============================================================================
// Security Types
// =============================================================================

export interface SecuritySettings {
  /** Require explicit user consent before each remote execution */
  requireExplicitConsent: boolean;
  /** Warn when PII is detected in input */
  warnOnPii: boolean;
  /** Block execution when secrets/credentials detected */
  blockOnSecrets: boolean;
  /** Folders to treat as sensitive (no remote execution) */
  sensitiveFolders: string[];
}

export interface BudgetSettings {
  /** Maximum daily spend in USD */
  dailyLimitUsd: number;
  /** Maximum monthly spend in USD */
  monthlyLimitUsd: number;
  /** Show warning when this percentage of budget is used */
  warnAtPercentage: number;
}

export interface AuditSettings {
  /** Log all remote execution requests */
  logAllRequests: boolean;
  /** Log prompts sent to providers (privacy concern!) */
  logPrompts: boolean;
  /** Log responses from providers (privacy concern!) */
  logResponses: boolean;
  /** Days to retain audit logs */
  retentionDays: number;
}

// =============================================================================
// Configuration Schema (maps to remote_providers.yaml)
// =============================================================================

export interface RemoteProvidersConfig {
  providers: Record<ProviderId, ProviderConfig>;
  security: SecuritySettings;
  budget: BudgetSettings;
  audit: AuditSettings;
}

// =============================================================================
// Execution Types
// =============================================================================

export interface ActionButtonRemoteConfig {
  /** Execution mode */
  mode: "ide" | "local" | "remote";
  /** Allowed providers for remote execution */
  allowedProviders?: ProviderId[];
  /** Maximum tokens for this action */
  maxTokens?: number;
  /** Maximum cost per execution in USD */
  maxCostUsd?: number;
}

export interface ExecutionContext {
  /** The action button being executed */
  actionButton: ActionButtonRemoteConfig;
  /** Provider to use */
  provider: ProviderId;
  /** Input data/prompt */
  input: string;
  /** Estimated cost in USD */
  estimatedCost: number;
  /** Estimated token counts */
  estimatedTokens: {
    input: number;
    output: number;
  };
}

export interface ExecutionResult {
  success: boolean;
  output?: string;
  error?: string;
  /** Actual cost incurred */
  cost?: number;
  /** Actual tokens used */
  tokens?: {
    input: number;
    output: number;
  };
  /** Duration in milliseconds */
  durationMs?: number;
}

// =============================================================================
// Security Scan Types
// =============================================================================

export interface PIIMatch {
  type: string;
  value: string;
  severity: "high" | "medium";
  index: number;
}

export interface SecretMatch {
  type: string;
  value: string;
  index: number;
}

export interface SecurityScanResult {
  safe: boolean;
  pii: PIIMatch[];
  secrets: SecretMatch[];
  injections: Array<{ type: string; value: string; index: number }>;
  warnings: string[];
  blockers: string[];
}

// =============================================================================
// Usage Tracking Types
// =============================================================================

export interface UsageStats {
  /** Total cost today in USD */
  dailyCost: number;
  /** Total cost this month in USD */
  monthlyCost: number;
  /** Total tokens used today */
  dailyTokens: number;
  /** Total tokens used this month */
  monthlyTokens: number;
  /** Per-provider breakdown (partial - only providers that have been used) */
  byProvider: Partial<
    Record<
      ProviderId,
      {
        cost: number;
        tokens: number;
        requests: number;
      }
    >
  >;
}

// =============================================================================
// API Response Types
// =============================================================================

export interface ProviderListResponse {
  providers: Array<ProviderDefinition & { config?: ProviderConfig }>;
  security: SecuritySettings;
  budget: BudgetSettings;
  usage: UsageStats;
}

export interface ProviderTestResult {
  success: boolean;
  latencyMs?: number;
  model?: string;
  error?: string;
}
