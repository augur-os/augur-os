/**
 * Mount Plugins — Discovery ownership resolution
 *
 * Resolves whether a skill is a primary hub owner or an extension
 * contributor, deriving its mount path and ownership key.
 *
 * Split out of discovery.ts (WS5 decomposition) — moved verbatim.
 */

import type { DashboardYaml } from "../../lib/plugin-discovery";
import { normalizeRouteSegment } from "./discovery.shared";

// ============================================================================
// Ownership Resolution
// ============================================================================

/**
 * Resolve whether a skill is a primary hub owner or an extension contributor.
 *
 * Primary skills have a hub.id field and own the top-level route.
 * Extension skills contribute pages under a parent hub as sub-routes.
 */
export function resolveOwnership(
  config: DashboardYaml,
  configPath: string,
  bundle: string,
  skill: string,
): {
  role: "primary" | "extension";
  extendsHubId: string | null;
  routePrefix: string | null;
  mountPath: string;
  ownershipKey: string;
} {
  const hubId = normalizeRouteSegment(config.contributes_to);
  if (!hubId) {
    throw new Error(`Missing contributes_to in ${configPath}.`);
  }

  // ADR-187: Explicit ownership. A skill with hub.id is primary unless owner: false.
  const hasHubBlock = !!config.hub?.id;
  const isPrimary = hasHubBlock && config.hub?.owner !== false;

  if (isPrimary) {
    return {
      role: "primary",
      extendsHubId: null,
      routePrefix: skill,
      mountPath: `${hubId}/${skill}`,
      ownershipKey: `primary:${hubId}`,
    };
  }

  // Contributing skill: mount under hub as sub-route
  return {
    role: "extension",
    extendsHubId: hubId,
    routePrefix: skill,
    mountPath: `${hubId}/${skill}`,
    ownershipKey: `contributor:${hubId}:${skill}`,
  };
}
