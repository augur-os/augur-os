/**
 * Plugin Discovery — Types
 *
 * Core types for the plugin discovery pipeline.
 * Re-exports canonical types from plugin-schema for convenience.
 */

import type { DashboardYaml, PluginDashboard } from "../plugin-schema/types";

export type { DashboardYaml, PluginDashboard };

/**
 * Discovered skill configuration from SKILL.md frontmatter.
 *
 * Returned by scanSkillConfigs(). The config field contains the
 * normalized skill config — consumers can access hub, tabs, mcp, dependencies, etc.
 */
export interface SkillConfig {
  /** Bundle (hub) directory name */
  bundle: string;
  /** Skill directory name */
  skill: string;
  /** Parsed skill config content */
  config: DashboardYaml;
  /** Absolute path to the canonical metadata file */
  path: string;
  /** Whether skill has augur/api/ directory */
  hasApi: boolean;
  /** Whether skill has augur/lib/ directory */
  hasLib: boolean;
}
