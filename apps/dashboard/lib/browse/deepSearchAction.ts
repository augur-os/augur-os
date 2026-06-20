import type { ActionDef } from "@/lib/actions/types";
import type { BrowseItem } from "@/lib/browse/types";

export type BrowseDeepSearchState = {
  query: string;
  activeCategoryId: string;
  activeCategoryLabel: string;
  filters: Record<string, string | null | undefined>;
  sortBy: string;
  searched: boolean;
  error?: string | null;
  results: BrowseItem[];
  resultLimit?: number;
};

function nonEmpty(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim().replace(/\s+/g, " ");
  return trimmed.length > 0 ? trimmed : null;
}

function formatFilters(filters: Record<string, string | null | undefined>): string {
  const entries = Object.entries(filters)
    .map(([key, value]) => [nonEmpty(key), nonEmpty(value)] as const)
    .filter((entry): entry is readonly [string, string] => Boolean(entry[0]) && Boolean(entry[1]));

  if (entries.length === 0) return "- none";

  return entries.map(([key, value]) => `- ${key}: ${value}`).join("\n");
}

function resultSourcePath(item: BrowseItem): string {
  return (
    nonEmpty(item.metadata?.source_path)
    ?? nonEmpty(item.primaryAction?.target)
    ?? nonEmpty(item.path)
    ?? "unknown"
  );
}

function resultScore(item: BrowseItem): string {
  const score = nonEmpty(item.metadata?.score);
  const provenance = nonEmpty(item.metadata?.provenance);

  if (score && provenance) return `score ${score}; provenance ${provenance}`;
  if (score) return `score ${score}`;
  if (provenance) return `provenance ${provenance}`;
  return "score unavailable";
}

function formatResult(item: BrowseItem, index: number): string {
  const tags = item.tags
    ?.map(nonEmpty)
    .filter((tag): tag is string => Boolean(tag))
    .join(", ") || "none";

  return [
    `${index + 1}. ${nonEmpty(item.title) ?? "Untitled"}`,
    `   Description: ${nonEmpty(item.description) ?? "none"}`,
    `   Type: ${nonEmpty(item.typeBadge) ?? "unknown"}`,
    `   Tags: ${tags}`,
    `   Source: ${resultSourcePath(item)}`,
    `   Retrieval: ${resultScore(item)}`,
  ].join("\n");
}

export function buildBrowseDeepSearchPrompt(state: BrowseDeepSearchState): string {
  const query = nonEmpty(state.query) ?? "";
  const activeCategoryLabel = nonEmpty(state.activeCategoryLabel) ?? "Unknown";
  const activeCategoryId = nonEmpty(state.activeCategoryId) ?? "unknown";
  const sortBy = nonEmpty(state.sortBy) ?? "default";
  const retrievalError = nonEmpty(state.error);
  const resultLimit = state.resultLimit ?? 8;
  const topResults = state.results.slice(0, resultLimit);
  const resultBlock = topResults.length > 0
    ? topResults.map(formatResult).join("\n\n")
    : "No top results are available from the current Browse state. Start by running or broadening retrieval, then inspect likely source folders.";

  return [
    "# Browse Deep Search",
    "",
    "Use the active native AI client to reason deeper over this Browse search. Browse already performed fast local retrieval when noted below; do not assume missing files are absent without checking source paths or retrieval again.",
    "",
    `Query: ${query}`,
    `Active category: ${activeCategoryLabel} (${activeCategoryId})`,
    `Sort: ${sortBy}`,
    `Fast local search already ran: ${state.searched ? "yes" : "no"}`,
    retrievalError ? `Retrieval error: ${retrievalError}` : "Retrieval error: none",
    "",
    "Active filters:",
    formatFilters(state.filters),
    "",
    `Top results (limited to ${resultLimit}):`,
    resultBlock,
    "",
    "Instructions:",
    "- inspect the most relevant sources before answering.",
    "- Use the listed source paths as starting points when available.",
    "- If the top results are weak, broaden retrieval across adjacent Browse categories and source folders.",
    "- Return a concise answer with cited files or explain what could not be found.",
  ].join("\n");
}

export function buildBrowseDeepSearchAction(state: BrowseDeepSearchState): ActionDef {
  return {
    id: "browse.deep-search",
    label: "Ask AI",
    description: "Investigate this Browse search using the query and top results.",
    dispatch: "ide",
    page: "browse",
    tier: "deep",
    prompt: buildBrowseDeepSearchPrompt(state),
  };
}
