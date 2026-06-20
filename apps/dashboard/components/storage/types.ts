export interface SizeAlert {
  category: string;
  level: "warning" | "critical" | "large_file";
  size_mb: number;
}

export interface Recommendation {
  id: string;
  message: string;
  auto_fixable: boolean;
}

export interface PathCategory {
  id: string;
  path: string;
  git_root?: string;
  size_mb: number;
  gitignored: boolean;
  subdirs: string[];
}

export interface RagPluginIndex {
  skill: string;
  path: string;
  size_mb: number;
}

export interface RagIndex {
  path: string;
  size_mb: number;
  project_count: number;
  exists: boolean;
  plugins?: RagPluginIndex[];
}

export interface PathConfig {
  success: boolean;
  core: PathCategory;
  data: PathCategory;
  plugins: PathCategory;
  runtime: PathCategory;
  is_monorepo: boolean;
  repo_count: number;
  alerts?: SizeAlert[];
  recommendations?: Recommendation[];
  rag_index?: RagIndex;
}

export interface CleanupResult {
  success: boolean;
  dry_run: boolean;
  cleaned: string[];
  freed_mb: number;
  errors: string[];
}
