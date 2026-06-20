import type { LucideIcon } from "lucide-react";
import type { CliId } from "@/lib/stores/chatStore";

export interface SuggestedAction {
  label: string;
  toolName: string;
  // SVG icon component (not an emoji/text string) so suggested-action chips
  // stay on the shared icon system — enforces the no-emoji-icons rule.
  icon?: LucideIcon;
}

export interface McpTool {
  name: string;
  description?: string;
}

export interface SlashCommand {
  id: string;
  name: string;
  description: string;
  category?: string;
}

export interface FloatingChatCliProcess {
  cliId: string;
  status: "running" | "waiting" | "error" | "exited";
  pid?: number;
}

export interface FloatingChatConfig {
  cli_id: string;
  label: string;
  category: "remote" | "local" | "ide";
  group: string;
  available: boolean;
  enabled: boolean;
}

export interface FloatingChatMessage {
  role: string;
  content: string;
}

export interface FloatingChatAttachedFile {
  stagedPath: string;
  originalName: string;
  size: number;
}

export interface MagicContextItem {
  id?: string;
  label?: string;
}

export interface MagicInsightItem {
  title?: string;
  description?: string;
}

export interface MagicUsageStats {
  views_7d?: number;
  views_30d?: number;
}

export interface MagicContextPayload {
  skill?: string;
  tabs?: MagicContextItem[];
  actions?: MagicContextItem[];
  dataFiles?: string[];
  usageStats?: MagicUsageStats;
  pendingInsights?: MagicInsightItem[];
}

export type ChatViewType =
  | "chat"
  | "terminal"
  | "action-dialog"
  | "actions-list";

export { type CliId };
