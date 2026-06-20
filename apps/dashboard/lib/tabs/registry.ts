import type { HubConfig, TabRegistry } from "./types";

// Try to import generated registry (created by scripts/generate-tab-registry.ts)
// This enables faster synchronous lookups without filesystem access
let generatedRegistry: TabRegistry | null = null;
let generatedHubs: string[] = [];
try {
  // Dynamic require for build-time generated file

  const generated = require("./generated-registry");
  generatedRegistry = generated.pluginTabRegistry;
  generatedHubs = generated.pluginManagedHubs || [];
} catch {
  // Generated registry not available - will use async discovery
}

/**
 * Core shell tab registry.
 *
 * Contains ONLY the settings hub, which is a core shell page.
 * All other hubs are plugin-provided via skill metadata and appear
 * in the generated registry (lib/tabs/generated-registry.ts).
 *
 * ADR-109: Hardcoded hub entries removed in favour of filesystem-driven discovery.
 */
export const coreTabRegistry: TabRegistry = {
  settings: {
    title: "Settings",
    subtitle: "Configure your Augur preferences and capabilities",
    basePath: "/settings",
    tabs: [
      { id: "general", label: "Workspace", icon: "Settings", href: "/settings" },
      {
        id: "ai",
        label: "AI & Models",
        icon: "Cloud",
        href: "/settings/ai",
      },
      {
        id: "integrations",
        label: "Connections",
        icon: "Package",
        href: "/settings/integrations",
      },
      {
        id: "appearance",
        label: "Appearance",
        icon: "Layout",
        href: "/settings/appearance",
      },
      {
        id: "privacy",
        label: "Privacy & Security",
        icon: "Shield",
        href: "/settings/privacy",
      },
    ],
  },
};

/**
 * Get hub configuration by key.
 *
 * Checks generated registry first (from skill metadata),
 * then falls back to hardcoded registry.
 */
export function getHubConfig(hubKey: string): HubConfig | undefined {
  // Check generated registry first (plugin configs take precedence)
  if (generatedRegistry?.[hubKey]) {
    return generatedRegistry[hubKey];
  }
  return coreTabRegistry[hubKey];
}

/**
 * Check if a hub is managed by plugin metadata.
 *
 * Synchronous check using generated registry.
 */
export function isPluginManagedHub(hubKey: string): boolean {
  return generatedHubs.includes(hubKey);
}

/**
 * Get the complete merged registry (generated + hardcoded).
 *
 * Synchronous version using pre-generated registry.
 */
export function getCompleteRegistry(): TabRegistry {
  return {
    ...coreTabRegistry,
    ...(generatedRegistry || {}),
  };
}

/**
 * Get all hub keys
 */
export function getHubKeys(): string[] {
  return Object.keys(coreTabRegistry);
}

/**
 * Type-safe hub key type
 */
export type HubKey = keyof typeof coreTabRegistry;

// Server-only functions (getMergedTabRegistry, getHubConfigWithPlugins)
// moved to ./registry-server.ts to avoid bundling fs in client code
