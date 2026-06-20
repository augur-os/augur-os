"use client";

import { useMemo, useState } from "react";
import { mcpCall } from "@/lib/mcp/client";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import type { BrainInboxResponse, EmailAction, InboxAction, InboxActionState, InboxNotice } from "./types";

const ACTION_TOOL: Record<InboxAction, string> = {
  scan: "inbox-scan-folder",
  consume: "inbox-consume-folder",
  purge: "inbox-purge-folder",
};

const ACTION_LABEL: Record<InboxAction, string> = {
  scan: "Scan",
  consume: "Consume",
  purge: "Purge to Trash",
};

const EMAIL_ACTION_TOOL: Record<EmailAction, string> = {
  scan: "email-drop-scan-source",
  consume: "email-drop-consume-source",
  wiki: "wiki-update",
};

const EMAIL_ACTION_LABEL: Record<EmailAction, string> = {
  scan: "Mail Drop scan",
  consume: "Mail Drop consume",
  wiki: "Wiki update",
};

function responseMessage(value: unknown, fallback: string) {
  if (value && typeof value === "object" && "message" in value) {
    const message = (value as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
  }
  return fallback;
}

export function useBrainInbox() {
  const query = useMcpQuery<BrainInboxResponse>(["brain-inbox"], "inbox-folders", "live", {
    args: { action: "list" },
  });
  const [actionState, setActionState] = useState<InboxActionState>(null);
  const [notice, setNotice] = useState<InboxNotice>(null);

  const responseError = query.data?.success === false ? query.data.error || "Brain Inbox MCP query failed." : null;
  const folders = useMemo(
    () => (query.data?.success === false ? [] : query.data?.folders ?? []),
    [query.data],
  );
  const emailLatestRuns = useMemo(
    () => (query.data?.success === false ? [] : query.data?.email_drop_latest_runs ?? []),
    [query.data],
  );
  const emailSources = useMemo(
    () => {
      if (query.data?.success === false) {
        return [];
      }
      const latestRunBySource = new Map(
        emailLatestRuns.map((run) => [run.source_id, run]),
      );
      return (query.data?.mail_drop_sources ?? query.data?.email_sources ?? []).map(
        (source) => ({
          ...source,
          latest_run: latestRunBySource.get(source.id) ?? null,
        }),
      );
    },
    [emailLatestRuns, query.data],
  );
  const sourceLanes = useMemo(
    () => (query.data?.success === false ? [] : query.data?.source_lanes ?? []),
    [query.data],
  );
  const vaultTargets = useMemo(
    () => (query.data?.success === false ? [] : query.data?.vault_targets ?? []),
    [query.data],
  );
  const discoveredVaults = useMemo(
    () => (query.data?.success === false ? [] : query.data?.discovered_vaults ?? []),
    [query.data],
  );
  const routingQueue = useMemo(
    () => (query.data?.success === false ? [] : query.data?.routing_queue ?? []),
    [query.data],
  );
  const latestUnifiedRuns = useMemo(
    () => (query.data?.success === false ? [] : query.data?.latest_unified_runs ?? []),
    [query.data],
  );
  const totals = useMemo(
    () =>
      folders.reduce(
        (next, folder) => ({
          newFiles: next.newFiles + folder.counts.new_files,
          documents: next.documents + folder.counts.document_candidates,
          trash: next.trash + folder.counts.trash_candidates,
          failed: next.failed + folder.counts.failed,
        }),
        { newFiles: 0, documents: 0, trash: 0, failed: 0 },
      ),
    [folders],
  );

  const runFolderAction = async (folderId: string, action: InboxAction) => {
    setActionState({ folderId, action });
    setNotice(null);
    try {
      const result = await mcpCall<{ success?: boolean; partial?: boolean; status?: string; message?: string; error?: string }>(ACTION_TOOL[action], {
        folder_id: folderId,
      });
      if (result?.success === false && !result.partial) {
        throw new Error(result.error || result.message || `${ACTION_LABEL[action]} failed`);
      }
      if (result?.partial) {
        setNotice({
          type: "warning",
          message: responseMessage(result, `${ACTION_LABEL[action]} partially completed. Review run details.`),
        });
      } else {
        setNotice({ type: "success", message: responseMessage(result, `${ACTION_LABEL[action]} completed.`) });
      }
      query.refetch();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setNotice({ type: "error", message: `${ACTION_LABEL[action]} failed: ${message}` });
      return false;
    } finally {
      setActionState(null);
    }
  };

  const addFolder = async (path: string, name?: string) => {
    setActionState({ folderId: "new", action: "scan" });
    setNotice(null);
    try {
      const result = await mcpCall<{ success?: boolean; message?: string; error?: string }>("inbox-folders", {
        action: "add",
        path,
        name: name?.trim() || undefined,
      });
      if (result?.success === false) {
        throw new Error(result.error || result.message || "Add folder failed");
      }
      setNotice({ type: "success", message: responseMessage(result, "Folder added.") });
      query.refetch();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setNotice({ type: "error", message: `Add folder failed: ${message}` });
      return false;
    } finally {
      setActionState(null);
    }
  };

  const addEmailSource = async (params: {
    displayName: string;
    path: string;
  }) => {
    setActionState({ folderId: "email:new", action: "scan" });
    setNotice(null);
    try {
      const result = await mcpCall<{ success?: boolean; message?: string; error?: string }>("email-drop-sources", {
        action: "add",
        name: params.displayName.trim() || "Mail Drop",
        path: params.path.trim(),
      });
      if (result?.success === false) {
        throw new Error(result.error || result.message || "Add Mail Drop source failed");
      }
      setNotice({ type: "success", message: responseMessage(result, "Mail Drop source added.") });
      query.refetch();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setNotice({ type: "error", message: `Add Mail Drop source failed: ${message}` });
      return false;
    } finally {
      setActionState(null);
    }
  };

  const runEmailAction = async (sourceId: string, action: EmailAction) => {
    setActionState({ folderId: `email:${sourceId}`, action });
    setNotice(null);
    try {
      const args = action === "wiki" ? { limit: 20 } : { source_id: sourceId };
      const result = await mcpCall<{ success?: boolean; partial?: boolean; message?: string; error?: string }>(
        EMAIL_ACTION_TOOL[action],
        args,
      );
      if (result?.success === false && !result.partial) {
        throw new Error(result.error || result.message || `${EMAIL_ACTION_LABEL[action]} failed`);
      }
      if (result?.partial) {
        setNotice({
          type: "warning",
          message: responseMessage(result, `${EMAIL_ACTION_LABEL[action]} partially completed. Review run details.`),
        });
      } else {
        setNotice({ type: "success", message: responseMessage(result, `${EMAIL_ACTION_LABEL[action]} completed.`) });
      }
      query.refetch();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setNotice({ type: "error", message: `${EMAIL_ACTION_LABEL[action]} failed: ${message}` });
      return false;
    } finally {
      setActionState(null);
    }
  };

  const registerVault = async (candidateId: string) => {
    setNotice(null);
    try {
      const result = await mcpCall<{ success?: boolean; error?: string }>("inbox-register-vault", {
        candidate_id: candidateId,
      });
      if (result?.success === false) {
        throw new Error(result.error || "Register vault failed");
      }
      setNotice({ type: "success", message: "Vault registered." });
      query.refetch();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setNotice({ type: "error", message: `Register vault failed: ${message}` });
      return false;
    }
  };

  const discoverVaults = async (searchRoot?: string) => {
    setNotice(null);
    try {
      const args = searchRoot?.trim() ? { search_root: searchRoot.trim() } : {};
      const result = await mcpCall<{ success?: boolean; error?: string }>("inbox-discover-vaults", args);
      if (result?.success === false) {
        throw new Error(result.error || "Vault discovery failed");
      }
      setNotice({ type: "success", message: "Vault discovery completed." });
      query.refetch();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setNotice({ type: "error", message: `Vault discovery failed: ${message}` });
      return false;
    }
  };

  const routePacket = async (packetId: string) => {
    setNotice(null);
    try {
      const result = await mcpCall<{ success?: boolean; error?: string }>("inbox-route-packets", {
        packet_id: packetId,
      });
      if (result?.success === false) {
        throw new Error(result.error || "Route packet failed");
      }
      setNotice({ type: "success", message: "Packet route refreshed." });
      query.refetch();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setNotice({ type: "error", message: `Route packet failed: ${message}` });
      return false;
    }
  };

  const consumePacket = async (packetId: string) => {
    setNotice(null);
    try {
      const result = await mcpCall<{ success?: boolean; error?: string }>("inbox-consume-packets", {
        packet_id: packetId,
      });
      if (result?.success === false) {
        throw new Error(result.error || "Consume packet failed");
      }
      setNotice({ type: "success", message: "Packet consumed." });
      query.refetch();
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setNotice({ type: "error", message: `Consume packet failed: ${message}` });
      return false;
    }
  };

  const refresh = () => {
    setNotice(null);
    query.refetch();
  };

  return {
    ...query,
    error: query.error || responseError,
    folders,
    emailSources,
    sourceLanes,
    vaultTargets,
    discoveredVaults,
    routingQueue,
    latestUnifiedRuns,
    totals,
    runStatus: query.data?.run_status ?? null,
    actionState,
    notice,
    addFolder,
    addEmailSource,
    refresh,
    runFolderAction,
    runEmailAction,
    registerVault,
    discoverVaults,
    routePacket,
    consumePacket,
  };
}
