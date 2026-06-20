"use client";

import type { McpTool } from "./types";

const GENERIC_RESULT_PATTERN =
  /\b(overview|summary|notes?|docs?|documentation|reference|guide|general|info|untitled)\b/;

function lowSignalPenalty(text: string, query: string) {
  if (!query.trim()) return 0;
  return GENERIC_RESULT_PATTERN.test(text.toLowerCase()) ? 12 : 0;
}

export interface BrowseIndexItemLike {
  id: string;
  title: string;
  description: string;
  hub: string;
  source_path?: string;
  metadata?: Record<string, string>;
}

export interface KnowledgeResultLike {
  title: string;
  snippet: string;
  source: string;
  filePath: string;
}

export interface FileResultLike {
  name: string;
  relativePath: string;
}

export interface BrowseSearchResultsLike {
  skills: BrowseIndexItemLike[];
  vault: BrowseIndexItemLike[];
  wiki: BrowseIndexItemLike[];
  documents: BrowseIndexItemLike[];
  actions: BrowseIndexItemLike[];
}

export interface StandardSearchResultsLike {
  knowledge: KnowledgeResultLike[];
  files: FileResultLike[];
  logs: FileResultLike[];
}

export interface RankedBrowseTopResult {
  key: string;
  category: keyof BrowseSearchResultsLike;
  item: BrowseIndexItemLike;
}

export interface RankedStandardTopResult {
  key: string;
  category: keyof StandardSearchResultsLike;
  item: KnowledgeResultLike | FileResultLike;
}

export interface SkillActionLike {
  id: string;
  label: string;
  description?: string;
  dispatch?: string;
}

export interface PromptWorkflowLike {
  id: string;
  title: string;
  description: string;
  hub: string;
  source_path?: string;
}

export interface ActionPaletteStreamInput {
  showAnalyzePage: boolean;
  pendingInsightCount: number;
  skillActions: SkillActionLike[];
  pageTools: McpTool[];
  prompts: PromptWorkflowLike[];
  workflows: PromptWorkflowLike[];
}

export interface RankedActionPaletteItem {
  key: string;
  category: "analyze" | "skill-action" | "tool" | "prompt" | "workflow";
  label: string;
  description?: string;
  value: string;
  dispatch?: string;
  hub?: string;
}

export function scoreActionLikeItem(
  label: string,
  description: string | undefined,
  query: string,
) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return 0;

  const lowerLabel = label.toLowerCase();
  const lowerDescription = (description || "").toLowerCase();

  if (lowerLabel === normalizedQuery) return 120;
  if (lowerLabel.startsWith(normalizedQuery)) return 90;
  if (lowerLabel.includes(normalizedQuery)) return 70;
  if (lowerDescription.includes(normalizedQuery)) return 35;
  return 0;
}

export function sortToolsByRelevance(
  tools: McpTool[],
  query: string,
  preferredSegments: string[],
) {
  return tools.toSorted((a, b) => {
    const aName = a.name.toLowerCase();
    const bName = b.name.toLowerCase();
    const aDesc = (a.description || "").toLowerCase();
    const bDesc = (b.description || "").toLowerCase();

    const aPreferred = preferredSegments.some(
      (segment) => aName.includes(segment) || aDesc.includes(segment),
    )
      ? 40
      : 0;
    const bPreferred = preferredSegments.some(
      (segment) => bName.includes(segment) || bDesc.includes(segment),
    )
      ? 40
      : 0;

    const scoreDiff =
      scoreActionLikeItem(a.name, a.description, query) + aPreferred -
      (scoreActionLikeItem(b.name, b.description, query) + bPreferred);

    if (scoreDiff !== 0) return scoreDiff > 0 ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
}

export function dedupeTools(tools: McpTool[]) {
  const seen = new Set<string>();
  return tools.filter((tool) => {
    const key = tool.name.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function scoreBrowseItem(
  item: BrowseIndexItemLike,
  query: string,
  selectedSkill?: string | null,
) {
  const normalizedQuery = query.trim().toLowerCase();
  const title = item.title.toLowerCase();
  const description = item.description.toLowerCase();
  const skill = selectedSkill?.toLowerCase();

  let score = 0;
  if (normalizedQuery) {
    if (title === normalizedQuery) score += 120;
    else if (title.startsWith(normalizedQuery)) score += 90;
    else if (title.includes(normalizedQuery)) score += 70;
    else if (description.includes(normalizedQuery)) score += 35;
  }

  if (skill) {
    if (item.id.toLowerCase() === skill) score += 40;
    if (item.hub.toLowerCase() === skill) score += 25;
    if ((item.metadata?.skill || "").toLowerCase() === skill) score += 35;
  }

  if (item.source_path) score += 5;
  score -= lowSignalPenalty(item.title, normalizedQuery);
  return score;
}

export function sortBrowseItems(
  items: BrowseIndexItemLike[],
  query: string,
  selectedSkill?: string | null,
) {
  return items.toSorted((a, b) => {
    const scoreDiff =
      scoreBrowseItem(b, query, selectedSkill) -
      scoreBrowseItem(a, query, selectedSkill);
    if (scoreDiff !== 0) return scoreDiff;
    return a.title.localeCompare(b.title);
  });
}

export function rankKnowledgeResult(item: KnowledgeResultLike, query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return 0;

  const title = item.title.toLowerCase();
  const snippet = item.snippet.toLowerCase();
  const filePath = item.filePath.toLowerCase();

  let score = 0;

  if (title === normalizedQuery) score = 120;
  else if (title.startsWith(normalizedQuery)) score = 90;
  else if (title.includes(normalizedQuery)) score = 70;
  else if (filePath.includes(normalizedQuery)) score = 50;
  else if (snippet.includes(normalizedQuery)) score = 30;

  if (score === 0) return 0;
  return score - lowSignalPenalty(item.title, normalizedQuery);
}

export function rankFileResult(file: FileResultLike, query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return 0;

  const name = file.name.toLowerCase();
  const relativePath = file.relativePath.toLowerCase();
  const readableName = file.name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ");

  let score = 0;

  if (name === normalizedQuery) score = 120;
  else if (name.startsWith(normalizedQuery)) score = 90;
  else if (name.includes(normalizedQuery)) score = 70;
  else if (relativePath.includes(normalizedQuery)) score = 40;

  if (score === 0) return 0;
  return score - lowSignalPenalty(readableName, normalizedQuery);
}

export function buildBrowseTopResults(
  grouped: BrowseSearchResultsLike,
  query: string,
  selectedSkill?: string | null,
  limit = 4,
): RankedBrowseTopResult[] {
  return buildBrowseResultStream(grouped, query, selectedSkill)
    .slice(0, limit);
}

export function buildBrowseResultStream(
  grouped: BrowseSearchResultsLike,
  query: string,
  selectedSkill?: string | null,
): RankedBrowseTopResult[] {
  const categoryWeights: Record<keyof BrowseSearchResultsLike, number> = selectedSkill
    ? { actions: 40, vault: 32, wiki: 24, documents: 16, skills: 12 }
    : { skills: 38, actions: 30, vault: 24, wiki: 18, documents: 14 };

  return (Object.entries(grouped) as Array<
    [keyof BrowseSearchResultsLike, BrowseIndexItemLike[]]
  >)
    .flatMap(([category, items]) =>
      items.map((item, index) => ({
        key: `${category}:${item.id}:${index}`,
        category,
        item,
        score:
          scoreBrowseItem(item, query, selectedSkill) + categoryWeights[category],
      })),
    )
    .sort((a, b) => b.score - a.score || a.item.title.localeCompare(b.item.title))
    .map(({ key, category, item }) => ({ key, category, item }));
}

export function buildStandardTopResults(
  grouped: StandardSearchResultsLike,
  query: string,
  limit = 4,
): RankedStandardTopResult[] {
  return buildStandardResultStream(grouped, query).slice(0, limit);
}

export function buildStandardResultStream(
  grouped: StandardSearchResultsLike,
  query: string,
): RankedStandardTopResult[] {
  const categoryWeights: Record<keyof StandardSearchResultsLike, number> = {
    knowledge: 36,
    files: 20,
    logs: 8,
  };

  const scoredKnowledge = grouped.knowledge.map((item, index) => ({
    key: `knowledge:${item.filePath}:${index}`,
    category: "knowledge" as const,
    item,
    score: rankKnowledgeResult(item, query) + categoryWeights.knowledge,
  }));
  const scoredFiles = grouped.files.map((item, index) => ({
    key: `files:${item.relativePath}:${index}`,
    category: "files" as const,
    item,
    score: rankFileResult(item, query) + categoryWeights.files,
  }));
  const scoredLogs = grouped.logs.map((item, index) => ({
    key: `logs:${item.relativePath}:${index}`,
    category: "logs" as const,
    item,
    score: rankFileResult(item, query) + categoryWeights.logs,
  }));

  return [...scoredKnowledge, ...scoredFiles, ...scoredLogs]
    .sort((a, b) => b.score - a.score)
    .map(({ key, category, item }) => ({ key, category, item }));
}

export function buildActionPaletteStream(
  input: ActionPaletteStreamInput,
  query: string,
): RankedActionPaletteItem[] {
  const normalizedQuery = query.trim().toLowerCase();
  const items: Array<RankedActionPaletteItem & { score: number }> = [];
  const genericToolPattern = /\b(generic|helper|common|utility|util|misc|tool)\b/;
  let strongActionMatchCount = 0;

  if (input.showAnalyzePage) {
    const label = "Analyze Page";
    const description = "Suggest improvements for this page";
    const actionScore = scoreActionLikeItem(label, description, normalizedQuery);
    const baseScore =
      normalizedQuery && actionScore === 0
        ? -1
        : 0;
    if (baseScore >= 0) {
      if (actionScore >= 70) strongActionMatchCount += 1;
      items.push({
        key: "analyze:page",
        category: "analyze",
        label,
        description:
          input.pendingInsightCount > 0
            ? `${description} (${input.pendingInsightCount} pending)`
            : description,
        value: "__analyze_page__",
        score: 110 + actionScore,
      });
    }
  }

  input.skillActions.forEach((action, index) => {
    const score = scoreActionLikeItem(action.label, action.description, normalizedQuery);
    if (normalizedQuery && score === 0) return;
    if (score >= 70) strongActionMatchCount += 1;
    items.push({
      key: `skill-action:${action.id}:${index}`,
      category: "skill-action",
      label: action.label,
      description: action.description,
      value: `/${action.id}`,
      dispatch: action.dispatch,
      score: 90 + score,
    });
  });

  input.prompts.forEach((prompt, index) => {
    const score = scoreActionLikeItem(prompt.title, prompt.description, normalizedQuery);
    if (normalizedQuery && score === 0) return;
    if (score >= 70) strongActionMatchCount += 1;
    items.push({
      key: `prompt:${prompt.id}:${index}`,
      category: "prompt",
      label: prompt.title,
      description: prompt.description,
      value: prompt.source_path || prompt.id,
      hub: prompt.hub,
      score: 64 + score,
    });
  });

  input.workflows.forEach((workflow, index) => {
    const score = scoreActionLikeItem(workflow.title, workflow.description, normalizedQuery);
    if (normalizedQuery && score === 0) return;
    if (score >= 70) strongActionMatchCount += 1;
    items.push({
      key: `workflow:${workflow.id}:${index}`,
      category: "workflow",
      label: workflow.title,
      description: workflow.description,
      value: workflow.source_path || workflow.id,
      hub: workflow.hub,
      score: 60 + score,
    });
  });

  input.pageTools.forEach((tool, index) => {
    const score = scoreActionLikeItem(tool.name, tool.description, normalizedQuery);
    if (normalizedQuery && score === 0) return;
    const namedScore = scoreActionLikeItem(tool.name, "", normalizedQuery);
    const genericTool = genericToolPattern.test(
      `${tool.name} ${tool.description || ""}`.toLowerCase(),
    );
    if (
      normalizedQuery &&
      strongActionMatchCount > 0 &&
      genericTool &&
      namedScore < 70
    ) {
      return;
    }
    items.push({
      key: `tool:${tool.name}:${index}`,
      category: "tool",
      label: tool.name,
      description: tool.description,
      value: tool.name,
      score: 52 + score + Math.min(namedScore, 24),
    });
  });

  return items
    .sort((a, b) => b.score - a.score || a.label.localeCompare(b.label))
    .map(({ score: _score, ...item }) => item);
}
