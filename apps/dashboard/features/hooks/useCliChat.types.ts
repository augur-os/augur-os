// ---------------------------------------------------------------------------
// ADR-535: localStorage-based chat auto-save
// ---------------------------------------------------------------------------

export const CHAT_STORAGE_KEY = "augur_chat_messages";
export const CHAT_META_KEY = "augur_chat_meta";
export const MAX_STORED_MESSAGES = 200;
export const SAVE_DEBOUNCE_MS = 1000;

export interface ChatStorageMeta {
  cliId: string;
  savedAt: number;
}

export interface CliConfig {
  cli_id: string;
  label: string;
  cmd: string[];
  category: "remote" | "local" | "ide";
  group: string;
  available: boolean;
  enabled: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
}

export interface SessionConflictInfo {
  sessionId?: string;
  owner?: {
    surface?: string;
    pid?: number;
    host?: string;
    cli_id?: string;
    [key: string]: unknown;
  };
}

export const COMMAND_LIKE_HINT_RE =
  /\b(ollama|brew|winget|run|open|npm|pnpm|npx|yarn|uv|python|python3|docker|curl)\b/i;
