"use client";

/**
 * React hook for MCP tool mutations (POST-style operations).
 *
 * Replaces useCachedMutation / useAction for routes that map to MCP tools.
 * Calls mcpCall() directly instead of fetching proxy routes.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { mcpCall } from "./client";

// ── Types ───────────────────────────────────────────────────────────────────

export interface McpMutationOpts<TResult> {
  /** Args merged into every mutate() call (body overrides on collision) */
  staticArgs?: Record<string, unknown>;
  /** React Query cache keys to invalidate after success */
  invalidates?: string[];
  /** Transform the raw MCP response before returning */
  select?: (raw: unknown) => TResult;
  /** Called after a successful mutation with the (possibly transformed) result */
  onSuccess?: (result: TResult) => void;
}

export interface McpMutationResult<TBody, TResult> {
  mutate: (body?: TBody) => Promise<TResult>;
  loading: boolean;
  error: string | null;
}

// ── Hook ────────────────────────────────────────────────────────────────────

export function useMcpMutation<TResult = unknown, TBody = Record<string, unknown>>(
  tool: string,
  opts?: McpMutationOpts<TResult>,
): McpMutationResult<TBody, TResult> {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const staticArgs = opts?.staticArgs;
  const invalidates = opts?.invalidates;
  const select = opts?.select;
  const onSuccess = opts?.onSuccess;

  const mutate = useCallback(
    async (body?: TBody): Promise<TResult> => {
      setLoading(true);
      setError(null);
      try {
        const args: Record<string, unknown> = {
          ...(staticArgs ?? {}),
          ...((body as Record<string, unknown>) ?? {}),
        };

        const raw = await mcpCall<unknown>(tool, args);
        const result = select ? select(raw) : (raw as TResult);

        // Invalidate related query caches
        if (invalidates) {
          for (const key of invalidates) {
            queryClient.invalidateQueries({ queryKey: [key] });
          }
        }

        onSuccess?.(result);
        return result;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [tool, staticArgs, invalidates, select, onSuccess, queryClient],
  );

  return { mutate, loading, error };
}
