"use client";

import { Check, CloudUpload, Loader2, AlertTriangle } from "lucide-react";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import { useMcpMutation } from "@/lib/mcp/useMcpMutation";

interface VaultSyncStatusData {
  vault_configured: boolean;
  synced: boolean;
  uncommitted: number;
  unpushed: number;
  behind: number;
  has_upstream: boolean;
  detail: string;
}

interface VaultSyncResult {
  success: boolean;
  conflict: boolean;
  message: string;
}

export function VaultSyncStatus() {
  const { data, loading, refetch } = useMcpQuery<VaultSyncStatusData>(
    "vault-sync-status", // cache key
    "vault-sync-status", // MCP tool
    "device", // preset: refetchOnWindowFocus true, 10s stale
  );

  const { mutate: sync, loading: syncing, error } = useMcpMutation<VaultSyncResult>(
    "vault-sync",
    { invalidates: ["vault-sync-status"], onSuccess: () => refetch() },
  );

  // Hidden until we know there is a vault repo.
  if (!data || !data.vault_configured) return null;

  if (data.synced && !syncing) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground/70">
        <Check className="h-3.5 w-3.5" /> Vault synced
      </span>
    );
  }

  const count = data.uncommitted + data.unpushed;

  return (
    <div className="inline-flex items-center gap-2">
      {error ? (
        <span className="inline-flex items-center gap-1 text-xs text-red-500" title={error}>
          <AlertTriangle className="h-3.5 w-3.5" /> Sync failed
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 text-xs text-amber-500">
          <CloudUpload className="h-3.5 w-3.5" /> {count} unsynced
        </span>
      )}
      <button
        type="button"
        disabled={syncing || loading}
        onClick={() => { void sync(); }}
        className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-xs hover:bg-accent disabled:opacity-50"
      >
        {syncing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CloudUpload className="h-3.5 w-3.5" />}
        {syncing ? "Syncing…" : "Sync"}
      </button>
    </div>
  );
}
