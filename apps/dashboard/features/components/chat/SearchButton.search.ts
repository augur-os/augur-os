import { mcpCall } from "@/lib/mcp/client";
import { matchesFileQuery } from "@/components/chat/utils";
import { rankFileResult, rankKnowledgeResult } from "./panelRanking";
import {
  EMPTY_BROWSE_RESULTS,
  EMPTY_RESULTS,
  INITIAL_SEARCH_UI_STATE,
} from "./SearchButton.types";
import type {
  FileResult,
  KnowledgeResult,
  RagSearchResult,
  SearchParamsReader,
  SearchResults,
  SearchScope,
  SearchUiAction,
  SearchUiState,
} from "./SearchButton.types";

export function readSearchParam(searchParams: SearchParamsReader, name: string): string | null {
  return searchParams.get(name);
}

export function classifyFile(file: FileResult): keyof SearchResults {
  const rel = file.relativePath.toLowerCase();
  const ext = file.extension.toLowerCase();

  if (rel.includes("logs/") || ext === ".log") return "logs";
  if (ext === ".md" || ext === ".mdx") return "knowledge";
  return "files";
}

export function fileToKnowledge(file: FileResult): KnowledgeResult {
  return {
    title: file.name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " "),
    snippet: file.relativePath,
    source: file.extension === ".md" ? "docs" : "knowledge",
    filePath: file.absolutePath,
  };
}

export async function loadStandardSearchResults({
  searchQuery,
  scope,
  pathname,
  isOperationMode,
}: {
  searchQuery: string;
  scope: SearchScope;
  pathname: string;
  isOperationMode: boolean;
}): Promise<SearchResults> {
  const ragScopes = scope === "skill"
    ? ["knowledge", "skills"]
    : ["memory", "knowledge", "skills", "rag", "decisions"];
  if (!isOperationMode && !ragScopes.includes("decisions")) {
    ragScopes.push("decisions");
  }

  const modeParam = isOperationMode ? "operation" : "development";
  const expandParam = scope === "all" ? "hub" : "";

  const [ragResponse, vaultResponse, docsResponse, documentsResponse] =
    await Promise.all([
      mcpCall<{ results?: RagSearchResult[] }>("unified-search", {
        q: searchQuery,
        scopes: ragScopes,
      }).catch(() => ({ results: [] })),
      mcpCall<{ files?: FileResult[]; hubFiles?: FileResult[] }>("get-context-files", {
        page: pathname,
        tab: "vault",
        mode: modeParam,
        expand: expandParam,
      }).catch(() => ({ files: [], hubFiles: [] })),
      mcpCall<{ files?: FileResult[]; hubFiles?: FileResult[] }>("get-context-files", {
        page: pathname,
        tab: "docs",
        mode: modeParam,
        expand: expandParam,
      }).catch(() => ({ files: [], hubFiles: [] })),
      mcpCall<{ files?: FileResult[]; hubFiles?: FileResult[] }>("get-context-files", {
        page: pathname,
        tab: "documents",
        mode: modeParam,
        expand: expandParam,
      }).catch(() => ({ files: [], hubFiles: [] })),
    ]);

  const grouped: SearchResults = {
    knowledge: [],
    files: [],
    logs: [],
  };
  const seenPaths = new Set<string>();

  for (const result of ragResponse.results || []) {
    const filePath = result.file_path || result.file || "";
    if (seenPaths.has(filePath)) continue;
    seenPaths.add(filePath);

    grouped.knowledge.push({
      title: result.content?.slice(0, 80) || filePath.split("/").pop()?.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ") || "Untitled",
      snippet: result.content?.slice(0, 150) || filePath,
      source: result.scope || "knowledge",
      filePath,
    });
  }

  const allFiles: FileResult[] = [
    ...(vaultResponse.files || []),
    ...(docsResponse.files || []),
    ...(documentsResponse.files || []),
    ...(vaultResponse.hubFiles || []),
    ...(docsResponse.hubFiles || []),
    ...(documentsResponse.hubFiles || []),
  ];
  for (const file of allFiles) {
    if (seenPaths.has(file.absolutePath)) continue;
    seenPaths.add(file.absolutePath);
    if (matchesFileQuery(file, searchQuery)) {
      const category = classifyFile(file);
      if (category === "knowledge") {
        grouped.knowledge.push(fileToKnowledge(file));
      } else {
        grouped[category].push(file);
      }
    }
  }

  grouped.knowledge.sort(
    (a, b) =>
      rankKnowledgeResult(b, searchQuery) - rankKnowledgeResult(a, searchQuery) ||
      a.title.localeCompare(b.title),
  );
  grouped.files.sort(
    (a, b) =>
      rankFileResult(b, searchQuery) - rankFileResult(a, searchQuery) ||
      a.name.localeCompare(b.name),
  );
  grouped.logs.sort(
    (a, b) =>
      rankFileResult(b, searchQuery) - rankFileResult(a, searchQuery) ||
      a.name.localeCompare(b.name),
  );

  return grouped;
}

export function searchUiReducer(
  state: SearchUiState,
  action: SearchUiAction,
): SearchUiState {
  switch (action.type) {
    case "set-query":
      return { ...state, query: action.query };
    case "set-scope":
      return { ...state, scope: action.scope };
    case "reset":
      return INITIAL_SEARCH_UI_STATE;
    case "hide-overflow":
      return { ...state, showOverflow: false };
    case "start-search":
      return { ...state, loading: true, hasSearched: true };
    case "clear-standard":
      return { ...state, results: EMPTY_RESULTS, hasSearched: false, loading: false };
    case "clear-browse":
      return {
        ...state,
        browseResults: EMPTY_BROWSE_RESULTS,
        hasSearched: false,
        loading: false,
      };
    case "standard-results":
      return { ...state, results: action.results, loading: false };
    case "browse-results":
      return { ...state, browseResults: action.browseResults, loading: false };
    case "standard-error":
      return { ...state, results: EMPTY_RESULTS, loading: false };
    case "browse-error":
      return { ...state, browseResults: EMPTY_BROWSE_RESULTS, loading: false };
    case "toggle-overflow":
      return { ...state, showOverflow: !state.showOverflow };
    default:
      return state;
  }
}
