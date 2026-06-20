import {
  Settings,
  Compass,
  Brain,
} from "lucide-react";
import type { ComponentType } from "react";

export type NavCategory = string;

export type NavSubItem = {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  skillId: string;
  pageCount: number;
};

export type NavItem = {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  tooltip?: string;
  category?: NavCategory; // For mode-aware filtering
  children?: NavSubItem[]; // Two-level sidebar (ADR-136)
};

export type NavSection = {
  label: string;
  items: NavItem[];
  priority?: "primary" | "secondary" | "tertiary";
};

// Static tooltips for the two fixed surfaces.
const STATIC_TOOLTIPS: Record<string, string> = {
  "/browse": "Browse - explore skills, blocks, and capabilities",
  "/workspace": "Workspace — knowledge, memory, search, and document management",
  "/settings": "Settings - configuration and preferences",
};

/**
 * Two fixed surfaces (hub concept removed):
 *   - Browse  (/browse)    — file-card discovery surface
 *   - Workspace (/workspace) — the single page surface
 *
 * There is no hub taxonomy or per-skill hub assignment anymore. Skills
 * declare their `/workspace/*` pages via `x-augur-dashboard-pages` and
 * mount-plugins assembles the single `workspace` registry directly.
 */
const SECTIONS: NavSection[] = [
  {
    label: "Browse",
    items: [{ href: "/browse", label: "Browse", icon: Compass }],
  },
  {
    label: "Apps",
    priority: "primary",
    items: [{ href: "/workspace", label: "Workspace", icon: Brain }],
  },
];

/**
 * Get nav sections. The `devModeEnabled` parameter is retained for call-site
 * compatibility but no longer filters anything — both surfaces are always shown.
 */
export function getEnabledSections(
  _devModeEnabled: boolean = false,
): NavSection[] {
  return SECTIONS;
}

export const FOOTER_ITEMS: NavItem[] = [
  { href: "/settings", label: "Settings", icon: Settings },
];

/**
 * Tooltip map for sidebar hover tooltips for the fixed surfaces.
 */
export const TOOLTIP_MAP: Record<string, string> = { ...STATIC_TOOLTIPS };
