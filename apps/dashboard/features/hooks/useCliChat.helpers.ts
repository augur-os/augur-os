import { type CliId } from "@/lib/stores/chatStore";
import {
  CHAT_STORAGE_KEY,
  CHAT_META_KEY,
  MAX_STORED_MESSAGES,
  COMMAND_LIKE_HINT_RE,
  type ChatMessage,
  type ChatStorageMeta,
} from "./useCliChat.types";

export function loadStoredMessages(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Validate shape: each entry must have role, content, timestamp
    return parsed.filter(
      (m: unknown): m is ChatMessage =>
        typeof m === "object" &&
        m !== null &&
        "role" in m &&
        "content" in m &&
        "timestamp" in m,
    );
  } catch {
    return [];
  }
}

export function saveMessagesToStorage(
  messages: ChatMessage[],
  cliId: string,
): void {
  try {
    // Trim to last N messages to avoid localStorage quota issues
    const toSave = messages.slice(-MAX_STORED_MESSAGES);
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(toSave));
    localStorage.setItem(
      CHAT_META_KEY,
      JSON.stringify({ cliId, savedAt: Date.now() } satisfies ChatStorageMeta),
    );
  } catch {
    // localStorage full or unavailable — non-critical
  }
}

export function clearStoredMessages(): void {
  try {
    localStorage.removeItem(CHAT_STORAGE_KEY);
    localStorage.removeItem(CHAT_META_KEY);
  } catch {
    // non-critical
  }
}

export function formatSetupHint(hint: unknown): string | null {
  if (typeof hint !== "string") return null;
  const trimmed = hint.trim();
  if (!trimmed) return null;
  if (!COMMAND_LIKE_HINT_RE.test(trimmed)) return trimmed;
  return `\`\`\`bash\n${trimmed}\n\`\`\``;
}

export function buildStartErrorMessage(
  cliId: CliId,
  data: any,
  status: number,
): string {
  const base = `Failed to start ${cliId}: ${data?.error ?? "Unknown error"}`;
  if (status !== 409) return base;

  const setupHint = formatSetupHint(data?.setup_hint);
  if (!setupHint) return base;
  return `${base}\n\nSetup hint:\n${setupHint}`;
}

export function isTransientConfigFetchError(
  error: unknown,
  signal?: AbortSignal,
): boolean {
  if (signal?.aborted) return true;
  if (error instanceof DOMException && error.name === "AbortError") return true;
  if (error instanceof TypeError && /Failed to fetch/i.test(error.message)) {
    return true;
  }
  return /AbortError|Failed to fetch/i.test(String(error));
}

/**
 * ADR-116: Fetch with exponential backoff retry.
 * Retries on network errors and 5xx responses.
 */
export function isNonRetriableStatus(status: number): boolean {
  return status >= 400 && status < 500;
}

export function shouldRetry(attempt: number, maxRetries: number): boolean {
  return attempt < maxRetries - 1;
}
