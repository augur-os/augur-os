/**
 * Mount Plugins — Shared Types
 *
 * Types used across the mount-plugins pipeline: discovery, resolution,
 * copying, and orchestration.
 */

export interface DiscoveredPlugin {
  bundle: string;
  skill: string;
  hubId: string;
  role: "primary" | "extension";
  extendsHubId: string | null;
  routePrefix: string | null;
  mountPath: string;
  ownershipKey: string;
  dashboardPath: string | null; // Path to dashboard/ folder
  apiPath: string | null; // Path to api/ folder
  libPath: string | null; // Path to lib/ folder (ADR-026)
  configPath: string; // Path to canonical skill metadata
  source: "core" | "user" | "client";
  dependencies: {
    required: string[];
    optional: string[];
  };
}

export interface MountResult {
  hubId: string;
  mountPath: string;
  role: "primary" | "extension";
  type: "dashboard" | "api";
  sourcePath: string;
  targetPath: string;
  success: boolean;
  error?: string;
}

/**
 * Runtime configuration resolved at startup from CLI flags,
 * environment variables, and path resolution.
 */
export interface MountConfig {
  repoRoot: string;
  dashboardRoot: string;
  appDir: string;
  corePluginsDir: string;
  userPluginsDir: string | null;
  clientSkillDirs: Record<string, string>; // client-id → absolute path
  pluginCacheDir: string | null; // ~/.claude/plugins/cache/ (ADR-430 gap 5)
  isDryRun: boolean;
  isClean: boolean;
  isVerbose: boolean;
  devHubFilter: Set<string> | null;
}

/** ADR-272: Custom data source declaration in skill config */
export interface DataSourceDecl {
  id: string;
  type: 'mcp_tool' | 'api_route' | 'file';
  source: string;
  display: string;
  title: string;
  config?: Record<string, unknown>;
}

/** ADR-272: Hub headline block contribution in skill config */
export interface HeadlineBlockDecl {
  type: string;
  title: string;
  data_source: { mcp_tool?: string; api_route?: string };
}
