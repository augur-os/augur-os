import type {
  buildBrowseResultStream,
  buildBrowseTopResults,
  buildStandardResultStream,
  buildStandardTopResults,
} from "./panelRanking";

export interface SearchButtonProps {
  isOperationMode: boolean;
  pathname: string;
  isOpen: boolean;
  onToggle: () => void;
  onAttachFile: (filePath: string) => void;
  chatContainerRef: React.RefObject<HTMLDivElement | null>;
  portalRef: React.RefObject<HTMLDivElement | null>;
  popoverRef: React.RefObject<HTMLDivElement | null>;
}

export type SearchScope = "skill" | "all";

export interface FileResult {
  name: string;
  relativePath: string;
  absolutePath: string;
  size: number;
  modified: number;
  extension: string;
  isDirectory: boolean;
}

export interface SearchResults {
  knowledge: KnowledgeResult[];
  files: FileResult[];
  logs: FileResult[];
}

export interface KnowledgeResult {
  title: string;
  snippet: string;
  source: string;
  filePath: string;
}

export interface RagSearchResult {
  file_path?: string;
  file?: string;
  scope?: string;
  content?: string;
}

/** RAG browse-index result shape */
export interface BrowseIndexItem {
  id: string;
  title: string;
  description: string;
  hub: string;
  source_path?: string;
  metadata?: Record<string, string>;
}

export interface BrowseSearchResults {
  skills: BrowseIndexItem[];
  vault: BrowseIndexItem[];
  wiki: BrowseIndexItem[];
  documents: BrowseIndexItem[];
  actions: BrowseIndexItem[];
}

export const EMPTY_RESULTS: SearchResults = {
  knowledge: [],
  files: [],
  logs: [],
};

export const EMPTY_BROWSE_RESULTS: BrowseSearchResults = {
  skills: [],
  vault: [],
  wiki: [],
  documents: [],
  actions: [],
};

/** Categories to search in parallel on /browse */
export const BROWSE_SEARCH_CATEGORIES = ["skills", "vault", "wiki", "documents"] as const;

export type SearchParamsReader = Pick<URLSearchParams, "get">;

export interface SearchUiState {
  query: string;
  scope: SearchScope;
  results: SearchResults;
  browseResults: BrowseSearchResults;
  loading: boolean;
  hasSearched: boolean;
  showOverflow: boolean;
}

export type SearchUiAction =
  | { type: "set-query"; query: string }
  | { type: "set-scope"; scope: SearchScope }
  | { type: "reset" }
  | { type: "hide-overflow" }
  | { type: "start-search" }
  | { type: "clear-standard" }
  | { type: "clear-browse" }
  | { type: "standard-results"; results: SearchResults }
  | { type: "browse-results"; browseResults: BrowseSearchResults }
  | { type: "standard-error" }
  | { type: "browse-error" }
  | { type: "toggle-overflow" };

export const INITIAL_SEARCH_UI_STATE: SearchUiState = {
  query: "",
  scope: "skill",
  results: EMPTY_RESULTS,
  browseResults: EMPTY_BROWSE_RESULTS,
  loading: false,
  hasSearched: false,
  showOverflow: false,
};

export interface SearchButtonPopoverProps {
  chatContainerRef: React.RefObject<HTMLDivElement | null>;
  portalRef: React.RefObject<HTMLDivElement | null>;
  inputRef: React.RefObject<HTMLInputElement | null>;
  state: {
    query: string;
    scope: SearchScope;
    loading: boolean;
    hasSearched: boolean;
    showOverflow: boolean;
    isBrowse: boolean;
    browseSkill: string | null;
    scopeSkillLabel: string;
    totalResults: number;
  };
  browseTopResults: ReturnType<typeof buildBrowseTopResults>;
  browseOverflowResults: ReturnType<typeof buildBrowseResultStream>;
  standardTopResults: ReturnType<typeof buildStandardTopResults>;
  standardOverflowResults: ReturnType<typeof buildStandardResultStream>;
  onQueryChange: (query: string) => void;
  onScopeChange: (scope: SearchScope) => void;
  onToggleOverflow: () => void;
  onAttachFile: (filePath: string) => void;
}
