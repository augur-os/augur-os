import { toast } from "sonner";
import { mcpCall } from "@/lib/mcp/client";
import type { BrowsePrimaryAction, BrowseCardAction } from "@/lib/browse/types";

interface RouterLike {
  push: (target: string) => void;
}

export interface BrowseChatResult {
  actionId: string;
  actionLabel: string;
  resultText: string;
  prompt: string;
}

interface ExecuteBrowseActionOptions {
  router?: RouterLike;
  onRunMcp?: (target: string) => void;
  onCliHelp?: (target: string) => Promise<void>;
  onChatResult?: (result: BrowseChatResult) => void;
}

function actionIdFor(action: BrowsePrimaryAction | BrowseCardAction): string {
  return "id" in action && typeof action.id === "string" ? action.id : action.target;
}

export async function executeBrowseAction(
  action: BrowsePrimaryAction | BrowseCardAction,
  { router, onRunMcp, onCliHelp, onChatResult }: ExecuteBrowseActionOptions,
) {
  const { type, target } = action;

  switch (type) {
    case "navigate":
    case "configure":
      router?.push(target);
      break;
    case "open-file":
      try {
        const info = await mcpCall<{ exists?: boolean; status?: string; message?: string }>("file-info", { path: target }, { fallback: { exists: false } });
        if (info.status === "error") {
          toast.error(info.message || `Cannot access: ${target.split("/").pop()}`);
          break;
        }
        if (!info.exists) {
          toast.error(`File not found: ${target.split("/").pop()}`);
          break;
        }
        const data = await mcpCall<{ success: boolean; error?: string }>("open-file", { path: target });
        if (!data.success) toast.error(data.error || "Failed to open file");
      } catch {
        toast.error("Failed to open file");
      }
      break;
    case "extract-and-open-adr":
      // ADR-608 Phase 2: archived ADRs live in zip bundles. POST to
      // /api/adrs/extract, then reuse the open-file MCP tool with the
      // returned path (same UX as live ADRs).
      try {
        const response = await fetch("/api/adrs/extract", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ adr_number: target }),
        });
        const payload = (await response.json().catch(() => ({}))) as {
          path?: string;
          error?: string;
        };
        if (!response.ok || !payload.path) {
          toast.error(payload.error || "Failed to extract archived ADR");
          break;
        }
        const data = await mcpCall<{ success: boolean; error?: string }>("open-file", {
          path: payload.path,
        });
        if (!data.success) toast.error(data.error || "Failed to open file");
      } catch {
        toast.error("Failed to extract archived ADR");
      }
      break;
    case "reveal-file":
      try {
        const info = await mcpCall<{ exists?: boolean; status?: string; message?: string }>("file-info", { path: target }, { fallback: { exists: false } });
        if (info.status === "error") {
          toast.error(info.message || `Cannot access: ${target.split("/").pop()}`);
          break;
        }
        if (!info.exists) {
          toast.error(`File not found: ${target.split("/").pop()}`);
          break;
        }
        const data = await mcpCall<{ success?: boolean; error?: string }>("reveal-in-finder", { path: target });
        if (data.success === false) toast.error(data.error || "Failed to reveal file");
      } catch {
        toast.error("Failed to reveal in Finder");
      }
      break;
    case "run-mcp":
      onRunMcp?.(target);
      break;
    case "run-action":
      onRunMcp?.(target);
      break;
    case "mcp-tool":
      try {
        const data = await mcpCall<{
          success?: boolean;
          error?: string;
          message?: string;
          action_label?: string;
          chat_output?: string;
          prompt?: string;
        }>(target, action.args ?? {});
        if (data.success === false) {
          toast.error(data.error || data.message || `${target} failed`);
        } else if (typeof data.chat_output === "string" && data.chat_output.trim() && onChatResult) {
          onChatResult({
            actionId: actionIdFor(action),
            actionLabel: data.action_label || action.label || target,
            resultText: data.chat_output.trim(),
            prompt: data.prompt || target,
          });
          toast.success(data.message || `${target} completed`);
        } else {
          toast.success(data.message || `${target} completed`);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : `${target} failed`;
        toast.error(message);
      }
      break;
    case "copy":
      try {
        await navigator.clipboard.writeText(target);
        toast.success("Copied to clipboard");
      } catch {
        toast.error("Failed to copy");
      }
      break;
    case "cli-help":
      if (onCliHelp) {
        await onCliHelp(target);
      }
      break;
    default:
      break;
  }
}
