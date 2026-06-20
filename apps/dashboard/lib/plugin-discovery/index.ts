/**
 * Plugin Discovery — Barrel Exports
 *
 * Single source of truth for plugin discovery across the entire codebase.
 * Replaces ~500 lines of duplicated code in 15+ files.
 */

export {
  discoverRepoRoot,
  getCorePluginsDir,
  getUserPluginsDir,
  getAllPluginDirs,
  getProjectBrainSkillsRoot,
  getClientSkillDirs,
} from "./paths";

export {
  discoverBundles,
  discoverBundlesAsync,
  resolveHubRole,
  scanSkillConfigs,
} from "./scanner";

export {
  discoverPagesFromFilesystem,
  smartLabel,
} from "./page-discovery";

export type { DiscoveredPage } from "./page-discovery";

export type { SkillConfig, DashboardYaml, PluginDashboard } from "./types";

export type {
  AssembledHub,
  WidgetDefinition,
  PageDefinition,
  ContributionBlock,
  CrossHubContribution,
  OverviewConfig,
  SearchContribution,
} from "../plugin-schema/types";
