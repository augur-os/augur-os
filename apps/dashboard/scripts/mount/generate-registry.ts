/**
 * Mount Plugins — Catch-All Registry Generator
 *
 * Generates registry.ts + catch-all page.tsx files for each hub that has
 * convention-based or manifest-declared pages. This replaces individually
 * mounted page.tsx copies with a single [[...slug]] catch-all route per hub.
 *
 * Phase: Runs after page mounting (Phase 4b) in mount-plugins.ts.
 *
 * Generated files:
 *   apps/dashboard/app/{hub}/[[...slug]]/registry.ts
 *   apps/dashboard/app/{hub}/[[...slug]]/page.tsx
 *
 * Note: Hub root page.tsx is NOT generated — the optional catch-all
 * [[...slug]] handles the base /{hub} route. A sibling page.tsx would
 * conflict with Next.js App Router optional catch-all specificity rules.
 *
 * The registry maps slug paths to dynamic imports of the original skill
 * source files. The catch-all page.tsx uses next/dynamic to render the
 * matching page component.
 */

import fs from "fs/promises";
import path from "path";
import { FEATURES_DIR } from "../lib/path-utils";

// ============================================================================
// Types
// ============================================================================

/** A single page entry collected during Phase 4b scanning. */
export interface RegistryPageEntry {
  /** Hub this page belongs to (e.g. "brain", "studio"). */
  hubId: string;
  /** Slug path within the hub (e.g. "knowledge/memory", "workbench"). */
  slug: string;
  /**
   * Absolute path to the directory containing page.tsx in plugin source.
   * Used to compute the relative import path from the catch-all directory.
   */
  sourceDir: string;
  /**
   * Override the computed import path. When set, used directly instead of
   * deriving from sourceDir. Used for YAML config-driven page wrappers
   * that live in lib/configs/ rather than under @/features/pages/.
   */
  importPathOverride?: string;
}

/** Registry data for a single hub, ready for file generation. */
interface HubRegistryData {
  hubId: string;
  defaultPath: string | null;
  entries: Array<{ slug: string; importPath: string }>;
}

function toPosixPath(filePath: string): string {
  return filePath.split(path.sep).join("/");
}

// ============================================================================
// Page Collection Helpers
// ============================================================================

/**
 * Recursively find all page.tsx files under a directory and return their
 * slug paths relative to the base directory.
 *
 * For example, given baseDir = features/pages/workspace and
 * a file at features/pages/workspace/memory/page.tsx,
 * returns [{ slug: "memory", sourceDir: ".../brain/memory" }].
 */
async function findPagesRecursive(
  dir: string,
  basePath: string,
): Promise<Array<{ slug: string; sourceDir: string }>> {
  const results: Array<{ slug: string; sourceDir: string }> = [];

  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });

    // Check if this directory itself has a page.tsx
    const hasPage = entries.some(
      (e) => !e.isDirectory() && e.name === "page.tsx",
    );
    if (hasPage && basePath) {
      results.push({ slug: basePath, sourceDir: dir });
    }

    // Recurse into subdirectories
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      if (entry.name === "components" || entry.name === "hooks" || entry.name === "lib") continue;
      if (entry.name.startsWith(".")) continue;

      const subPath = basePath ? `${basePath}/${entry.name}` : entry.name;
      const subResults = await findPagesRecursive(
        path.join(dir, entry.name),
        subPath,
      );
      results.push(...subResults);
    }
  } catch {
    // Directory not readable
  }

  return results;
}

/**
 * Collect page entries from a convention-based hub directory.
 *
 * Scans feature page roots recursively for page.tsx files
 * and returns RegistryPageEntry[] with slugs relative to the hub.
 */
export async function collectConventionPages(
  hubDir: string,
  hubId: string,
  manifestSourceDirs: Set<string>,
  liveSkills?: Set<string>,
  declaredFeaturePages?: Map<string, string>,
): Promise<RegistryPageEntry[]> {
  const entries: RegistryPageEntry[] = [];

  try {
    const skillDirs = await fs.readdir(hubDir, { withFileTypes: true });

    for (const skillEntry of skillDirs) {
      if (!skillEntry.isDirectory()) continue;
      const skillName = skillEntry.name;
      const isLiveSkill = liveSkills?.has(skillName);
      const isDeclaredFeaturePage =
        declaredFeaturePages?.has(skillName) ||
        declaredFeaturePages?.has(`${hubId}/${skillName}`);

      if (liveSkills && !isLiveSkill && !isDeclaredFeaturePage) continue;

      const sourceDir = path.join(hubDir, skillName);

      // Skip dirs already handled by manifest
      if (manifestSourceDirs.has(sourceDir)) continue;

      const pages = await findPagesRecursive(sourceDir, skillName);
      for (const page of pages) {
        entries.push({
          hubId,
          slug: page.slug,
          sourceDir: page.sourceDir,
        });
      }
    }
  } catch {
    // Hub directory not readable
  }

  return entries;
}

// ============================================================================
// Registry Building
// ============================================================================

/**
 * Build structured registry data for each hub from collected page entries.
 *
 * Groups entries by hub, computes relative import paths from the catch-all
 * directory, and determines the default redirect path for each hub.
 *
 * @param entries All collected page entries across hubs
 * @param hubDefaults Map of hubId -> default redirect path (e.g. brain -> /brain/memory)
 * @param appDir Absolute path to apps/dashboard/app/
 * @param repoRoot Absolute path to the repository root
 */
export function buildHubRegistries(
  entries: RegistryPageEntry[],
  hubDefaults: Record<string, string>,
  _appDir: string,
  _repoRoot: string,
): HubRegistryData[] {
  // Group by hub
  const byHub = new Map<string, RegistryPageEntry[]>();
  for (const entry of entries) {
    const list = byHub.get(entry.hubId) || [];
    list.push(entry);
    byHub.set(entry.hubId, list);
  }

  const result: HubRegistryData[] = [];

  for (const [hubId, hubEntries] of byHub) {
    const registryEntries = hubEntries
      .map((entry) => {
        return {
          slug: entry.slug,
          importPath: entry.importPathOverride
            ?? `@/${FEATURES_DIR}/pages/${toPosixPath(path.join(hubId, entry.slug, "page"))}`,
        };
      })
      .sort((a, b) => a.slug.localeCompare(b.slug));

    result.push({
      hubId,
      defaultPath: hubDefaults[hubId] || null,
      entries: registryEntries,
    });
  }

  return result.sort((a, b) => a.hubId.localeCompare(b.hubId));
}


// ============================================================================
// File Generation
// ============================================================================

function generateCatchAllPageContent(hubId: string): string {
  const overviewImport =
    hubId === "workspace"
      ? "import { BrainOverviewHome } from '@/features/pages/workspace/overview/BrainOverviewHome';"
      : "";
  const overviewBranch =
    hubId === "workspace" ? "return <BrainOverviewHome />;" : "notFound();";

  return `import { createElement, type ComponentType } from 'react';
import dynamic from 'next/dynamic';
import { notFound } from 'next/navigation';
import { PAGES } from './registry';
${overviewImport}

const DYNAMIC_PAGES: Record<string, ComponentType> = Object.fromEntries(
  Object.entries(PAGES).map(([path, loader]) => [
    path,
    dynamic(loader, {
      loading: () => (
        <div className="space-y-4 animate-pulse min-h-[200px] p-4">
          <div className="h-6 w-48 rounded-lg bg-[var(--bg-secondary)]" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="h-32 rounded-xl bg-[var(--bg-secondary)]" />
            <div className="h-32 rounded-xl bg-[var(--bg-secondary)]" />
          </div>
          <div className="h-24 rounded-xl bg-[var(--bg-secondary)]" />
        </div>
      ),
    }),
  ]),
);

function renderDynamicPage(path: string) {
  const page = DYNAMIC_PAGES[path];
  return page ? createElement(page) : null;
}

interface HubPageProps {
  params: Promise<{
    slug?: string[];
  }>;
}

export default async function HubPage(props: HubPageProps) {
  const { slug } = await props.params;
  const path = slug?.join('/') ?? '';

  if (!path) {
    ${overviewBranch}
  }

  const page = renderDynamicPage(path);
  if (!page) {
    notFound();
  }

  return page;
}
`;
}

function generateOverviewRootPageContent(hubId: string): string {
  if (hubId === "workspace") {
    return `import { BrainOverviewHome } from '@/features/pages/workspace/overview/BrainOverviewHome';

export default function HubOverviewRootPage() {
  return <BrainOverviewHome />;
}
`;
  }

  return `import { notFound } from 'next/navigation';

export default function FallbackHubRootPage() {
  notFound();
}
`;
}

async function removeGeneratedFileIfPresent(
  filePath: string,
  predicate: (content: string) => boolean,
): Promise<void> {
  try {
    const content = await fs.readFile(filePath, "utf8");
    if (!predicate(content)) return;
    await fs.rm(filePath, { force: true });
  } catch {
    // File missing or unreadable
  }
}

/**
 * Generate registry.ts content for a hub.
 */
function generateRegistryContent(data: HubRegistryData): string {
  const defaultPathLine = data.defaultPath
    ? `'${data.defaultPath}'`
    : "null";

  const entriesBlock = data.entries
    .map(
      (e) => `  '${e.slug}': () => import('${e.importPath}'),`,
    )
    .join("\n");

  return `// AUTO-GENERATED by mount-plugins — do not edit

export const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {
${entriesBlock}
};
`;
}

/**
 * Write registry.ts and catch-all page.tsx for all hubs with page entries and
 * any assembled hub roots that still need an overview route.
 *
 * Creates:
 *   apps/dashboard/app/{hub}/[[...slug]]/registry.ts
 *   apps/dashboard/app/{hub}/[[...slug]]/page.tsx
 *
 * @param appDir Absolute path to apps/dashboard/app/
 * @param hubRegistries Registry data for each hub (from buildHubRegistries)
 * @param requiredHubIds Assembled hub IDs that should get a root catch-all even
 * if they currently have zero page entries
 */
export async function generateRegistries(
  appDir: string,
  hubRegistries: HubRegistryData[],
  requiredHubIds: string[] = [],
): Promise<void> {
  const activeHubs = new Set([
    ...hubRegistries.map((data) => data.hubId),
    ...requiredHubIds,
  ]);
  const dashboardRoot = path.dirname(appDir);

  // Remove stale generated catch-all routes for hubs that no longer have pages.
  try {
    const hubDirs = await fs.readdir(appDir, { withFileTypes: true });
    for (const entry of hubDirs) {
      if (!entry.isDirectory()) continue;
      if (activeHubs.has(entry.name)) continue;
      const hubDir = path.join(appDir, entry.name);
      const staleCatchAllDir = path.join(appDir, entry.name, "[[...slug]]");
      await fs.rm(staleCatchAllDir, { recursive: true, force: true });
      await removeGeneratedFileIfPresent(
        path.join(hubDir, "page.tsx"),
        (content) =>
          content.includes("HubOverviewRootPage") ||
          content.includes("FallbackHubRootPage"),
      );
      await removeGeneratedFileIfPresent(
        path.join(hubDir, "layout.tsx"),
        (content) =>
          content.includes("AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY") &&
          content.includes("HubTabNav"),
      );
      await fs.rm(
        path.join(dashboardRoot, ".next", "types", "app", entry.name),
        { recursive: true, force: true },
      );
      await fs.rm(
        path.join(dashboardRoot, ".next", "dev", "types", "app", entry.name),
        { recursive: true, force: true },
      );
    }
  } catch {
    // appDir may not exist yet on fresh workspaces
  }

  const registryByHub = new Map(hubRegistries.map((data) => [data.hubId, data]));
  for (const hubId of [...activeHubs].sort((a, b) => a.localeCompare(b))) {
    const data = registryByHub.get(hubId) ?? {
      hubId,
      defaultPath: null,
      entries: [],
    };
    const hubDir = path.join(appDir, data.hubId);
    const catchAllDir = path.join(hubDir, "[[...slug]]");
    const rootPagePath = path.join(hubDir, "page.tsx");
    await fs.mkdir(hubDir, { recursive: true });

    if (data.entries.length === 0) {
      await fs.rm(catchAllDir, { recursive: true, force: true });
      await fs.writeFile(
        rootPagePath,
        generateOverviewRootPageContent(data.hubId),
        "utf8",
      );
      console.log(`   [REG] /${data.hubId} (overview only)`);
      continue;
    }

    await fs.rm(rootPagePath, { force: true });
    await fs.mkdir(catchAllDir, { recursive: true });

    // Write registry.ts
    const registryPath = path.join(catchAllDir, "registry.ts");
    const registryContent = generateRegistryContent(data);
    await fs.writeFile(registryPath, registryContent, "utf8");

    // Write catch-all page.tsx
    const pagePath = path.join(catchAllDir, "page.tsx");
    await fs.writeFile(pagePath, generateCatchAllPageContent(data.hubId), "utf8");

    console.log(
      `   [REG] /${data.hubId}/[[...slug]] (${data.entries.length} pages)`,
    );
  }
}
