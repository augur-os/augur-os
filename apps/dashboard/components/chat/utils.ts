// eslint-disable-next-line no-restricted-imports -- ADR-490: bridge file re-exports types from moved chat module
import type {
  MagicContextItem,
  MagicInsightItem,
  MagicContextPayload,
  FloatingChatCliProcess,
} from "@/features/components/chat/types";

export function isMacPlatform() {
  return (
    typeof navigator !== "undefined" && navigator.platform?.includes("Mac")
  );
}

export { formatFileSize } from "@/lib/utils/format";

export function formatAge(modifiedMs: number): string {
  const ageMs = Date.now() - modifiedMs;
  const minutes = Math.floor(ageMs / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function matchesFileQuery(
  file: { name: string; relativePath: string },
  query: string,
): boolean {
  const q = query.toLowerCase();
  return (
    file.name.toLowerCase().includes(q) ||
    file.relativePath.toLowerCase().includes(q)
  );
}

export const TOOL_BUTTON_BASE_CLASS =
  "inline-flex h-8 items-center gap-1.5 rounded-full px-2.5 text-[11px] font-medium transition-colors";
export const TOOL_BUTTON_ACTIVE_CLASS =
  "border border-[var(--accent-primary)]/20 bg-[var(--accent-primary)]/12 text-[var(--accent-primary)]";
export const TOOL_BUTTON_IDLE_CLASS =
  "border border-transparent bg-transparent text-[var(--text-muted)] hover:bg-[var(--bg-primary)] hover:text-[var(--text-primary)]";

const MAGIC_IMPROVEMENT_PROMPT_LINES = [
  "Suggest improvements in these categories:",
  "1. Data structure - missing fields, new schemas",
  "2. Use cases - new workflows this page could support",
  "3. Action buttons - new actions to add",
  "4. Organization - tab restructuring, grouping",
  "5. Workflows - new chains or modifications",
  "6. Integration - cross-skill connections",
  "",
  "For each: [Category] Title - Description (Effort: small/medium/large, Impact: low/medium/high)",
];

function joinContextLabels(items?: MagicContextItem[]) {
  return (items || [])
    .flatMap((item) => {
      const label = item.label || item.id;
      return label ? [label] : [];
    })
    .join(", ");
}

function joinPendingInsights(items?: MagicInsightItem[]) {
  return (items || [])
    .map((item) => `- ${item.title}: ${item.description}`)
    .join("\n");
}

function appendContextSummaryLines(lines: string[], ctx: MagicContextPayload) {
  const tabsList = joinContextLabels(ctx.tabs);
  const actionsList = joinContextLabels(ctx.actions);
  const dataFiles = (ctx.dataFiles || []).join(", ");

  if (tabsList) lines.push(`Tabs: ${tabsList}`);
  if (actionsList) lines.push(`Actions: ${actionsList}`);
  if (dataFiles) lines.push(`Data files: ${dataFiles}`);
}

function appendPendingInsights(
  lines: string[],
  pendingInsights?: MagicInsightItem[],
) {
  const pending = joinPendingInsights(pendingInsights);
  if (!pending) return;
  lines.push("", "Daemon insights:", pending);
}

export function buildMagicPrompt(pathname: string, ctx: MagicContextPayload) {
  const lines = [
    "Analyze this dashboard page and suggest concrete improvements:",
    "",
    `Page: ${pathname}`,
    `Skill: ${ctx.skill ?? "unknown"}`,
  ];

  appendContextSummaryLines(lines, ctx);

  const usage = ctx.usageStats;
  lines.push(
    `Usage: ${usage?.views_7d ?? 0} views this week, ${usage?.views_30d ?? 0} this month`,
  );

  appendPendingInsights(lines, ctx.pendingInsights);
  lines.push("", ...MAGIC_IMPROVEMENT_PROMPT_LINES);
  return lines.join("\n");
}

const FOCUS_CONTEXT_START = "<!--FOCUS_CONTEXT_START-->";
const FOCUS_CONTEXT_END = "<!--FOCUS_CONTEXT_END-->";

function extractFocusFromMessage(content: string): {
  focusBlock: string | null;
  cleanContent: string;
  skillName: string | null;
} {
  const startIdx = content.indexOf(FOCUS_CONTEXT_START);
  const endIdx = content.indexOf(FOCUS_CONTEXT_END);
  if (startIdx === -1 || endIdx === -1) {
    return { focusBlock: null, cleanContent: content, skillName: null };
  }
  const focusBlock = content
    .slice(startIdx + FOCUS_CONTEXT_START.length, endIdx)
    .trim();
  const cleanContent = (
    content.slice(0, startIdx) +
    content.slice(endIdx + FOCUS_CONTEXT_END.length)
  ).trim();

  const skillMatch = focusBlock.match(/^Skill:\s*(.+)$/m);
  const skillName = skillMatch ? skillMatch[1].trim() : null;

  return { focusBlock, cleanContent, skillName };
}

export function getActiveCliId(isRunning: boolean, cliId?: string | null) {
  if (!isRunning) return null;
  return cliId ?? null;
}

export function getCliStatusLabel(cliProcess: FloatingChatCliProcess | null) {
  return cliProcess?.status ?? "idle";
}
