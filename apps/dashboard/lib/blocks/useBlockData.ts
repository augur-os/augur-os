"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { DataSource } from "./types";

export interface BlockDataMeta {
  source?: string;       // "vault" | "seed" | "default"
  vaultStatus?: string;  // "ok" | "missing_dir" | "no_file" | "empty_file"
}

interface UseBlockDataResult<T = unknown> {
  data: T | null;
  loading: boolean;
  error: string | null;
  meta: BlockDataMeta;
  refetch: () => void;
  invalidate: () => void;
}

/**
 * Per-block-type stale times (ms).
 * Default: 5 minutes. Override for time-sensitive or static block types.
 */
const STALE_TIMES: Record<string, number> = {
  calendar: 60_000,
  "activity-feed": 30_000,
  "stat-card": 600_000,
  "stat-grid": 600_000,
  notes: Infinity,
  "ops-board": 120_000,
};

const DEFAULT_STALE_TIME = 300_000;

/**
 * Unwrap nested data envelopes from MCP tool responses.
 *
 * MCP tools often return {key: [...actual data...]} where the key varies
 * (stories, resumes, notes, documents, etc.). Block components expect the
 * inner array directly. This function extracts it when the response is a
 * dict with a single array-valued key, or when it has a well-known data key.
 *
 * Rules:
 * - {items: [...]} → extract items (common convention)
 * - {singleKey: [...]} → extract the array (single-key dict with array value)
 * - {connected: false, ...} → keep as-is (connection status response)
 * - {value: X, label: Y} → keep as-is (stat-card data)
 * - {multiple: keys} where no key is an array → keep as-is
 */
export function unwrapToolData(data: unknown): unknown {
  if (!data || typeof data !== "object" || Array.isArray(data)) return data;

  const obj = data as Record<string, unknown>;

  // Preserve connection status responses (Google blocks "not connected" state)
  if ("connected" in obj) return data;

  // Preserve error responses
  if ("error" in obj && obj.error === true) return data;

  // Preserve markdown/document payloads such as
  // {content, editable, generated, path}; MarkdownBlock reads the metadata.
  if ("content" in obj && typeof obj.content === "string") return data;

  // Unwrap MCP success envelope: {success: true, data: ...} → extract data
  if ("success" in obj && "data" in obj && obj.success === true) {
    return unwrapToolData(obj.data);
  }

  // Unwrap {success: true, KEY: [...], count?: N} — single array alongside metadata
  if ("success" in obj && obj.success === true) {
    const metaKeys = new Set(["success", "count", "total", "page", "hasMore", "source", "vault_status"]);
    const arrayEntries = Object.entries(obj).filter(
      ([k, v]) => !metaKeys.has(k) && Array.isArray(v)
    );
    if (arrayEntries.length === 1) {
      return arrayEntries[0][1];
    }
  }

  const keys = Object.keys(obj);

  // Single-key dict with array value → unwrap
  if (keys.length === 1) {
    const value = obj[keys[0]];
    if (Array.isArray(value)) return value;
  }

  // Check for well-known data keys containing arrays
  const dataKeys = [
    "items", "data", "results", "entries", "rows", "records", "list",
    "stories", "resumes", "notes", "documents", "files", "skills",
    "agents", "events", "actions", "tools", "sessions", "jobs",
    "startups", "categories", "accounts", "transactions", "logs",
    "templates", "projects", "opportunities", "organizations",
    "teams", "ideas", "candidates", "commits", "notifications",
    "inbox", "services", "plugins", "automations", "providers",
    "emails", "memos", "loops", "battlecards", "investor_qa",
    "competitor_landscape", "lights", "scenes", "reminders",
  ];
  for (const key of dataKeys) {
    if (key in obj && Array.isArray(obj[key])) return obj[key];
  }

  // Check for "total" + one array key pattern (e.g., {stories: [...], total: 5})
  const arrayKeys = keys.filter((k) => Array.isArray(obj[k]));
  const nonArrayKeys = keys.filter((k) => !Array.isArray(obj[k]));
  if (
    arrayKeys.length === 1 &&
    nonArrayKeys.every((k) => k === "total" || k === "count" || k === "page" || k === "hasMore")
  ) {
    return obj[arrayKeys[0]];
  }

  // Dict with all scalar values → convert to [{value, label}] for stat-grid/stat-card
  // e.g., {inbox: 5, active: 12, archive: 3} → [{value: 5, label: "inbox"}, ...]
  const allScalar = keys.every((k) => {
    const v = obj[k];
    return typeof v === "string" || typeof v === "number" || typeof v === "boolean";
  });
  if (allScalar && keys.length >= 2 && keys.length <= 12) {
    return keys.map((k) => ({ value: obj[k], label: k }));
  }

  return data;
}

interface FetchBlockDataResult {
  data: unknown;
  meta: BlockDataMeta;
}

async function fetchBlockData(
  dataSource: DataSource,
  config?: Record<string, unknown> | object,
): Promise<FetchBlockDataResult> {
  const response = await fetch("/api/blocks/data", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tool: dataSource.mcpTool,
      args: config || {},
    }),
  });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }

  const result = await response.json();

  // Layer 1: extract .data from API envelope {success, data}
  let raw = result;
  if (result && typeof result === "object" && "data" in result) {
    raw = result.data;
  }

  // Extract source/vault_status metadata BEFORE unwrap strips the envelope
  const rawObj = typeof raw === "object" && raw !== null ? (raw as Record<string, unknown>) : {};
  const meta: BlockDataMeta = {
    source: typeof rawObj.source === "string" ? rawObj.source : undefined,
    vaultStatus: typeof rawObj.vault_status === "string" ? rawObj.vault_status : undefined,
  };

  // Layer 2: unwrap MCP tool response envelope {key: [...actual data...]}
  return { data: unwrapToolData(raw), meta };
}

/**
 * Fetch data for a block from its declared dataSource, with React Query caching.
 *
 * - Same mcpTool + same params across blocks = one shared fetch (deduplication)
 * - Stale-while-revalidate: shows cached data instantly, refreshes in background
 * - Keeps previous data on error (stale data + error badge pattern)
 * - Retries 3x with exponential backoff on failure
 */
export function useBlockData<T = unknown>(
  dataSource?: DataSource,
  config?: Record<string, unknown> | object,
  blockType?: string,
  refreshSignal = 0,
): UseBlockDataResult<T> {
  const queryClient = useQueryClient();

  const sourceKey = dataSource?.mcpTool || "";
  const configKey = config ? JSON.stringify(config) : "";
  const queryKey = ["block-data", sourceKey, configKey, refreshSignal];

  const staleTime = blockType
    ? (STALE_TIMES[blockType] ?? DEFAULT_STALE_TIME)
    : DEFAULT_STALE_TIME;

  const enabled = !!dataSource && !!dataSource.mcpTool;

  const { data: queryResult, isLoading, error, refetch } = useQuery({
    queryKey,
    queryFn: () => fetchBlockData(dataSource!, config),
    staleTime,
    enabled,
    placeholderData: (prev: FetchBlockDataResult | undefined) => prev,
  });

  return {
    data: (queryResult?.data as T) ?? null,
    loading: isLoading,
    error: error
      ? error instanceof Error
        ? error.message
        : String(error)
      : null,
    meta: queryResult?.meta ?? {},
    refetch: () => {
      refetch();
    },
    invalidate: () => {
      queryClient.invalidateQueries({ queryKey: ["block-data", sourceKey] });
    },
  };
}
