// Compiled to scripts/dist/validate-nav-alignment.mjs by build-scripts.mjs
/**
 * Nav Alignment Validation Script
 *
 * Validates that the filesystem structure matches the navigation and registry.
 * Supersedes validate-tab-registry.ts (ADR-109 Phase 8).
 *
 * Run via: npm run validate-nav
 *   or: npx tsx apps/dashboard/scripts/validate-nav-alignment.ts
 *
 * Assertions:
 * 1. Every SKILL.md hub.id → appears in generated-registry
 * 2. Every generated-registry entry → has a routable hub surface or generated route source
 * 3. No orphaned app/ directories (not core shell AND not plugin-mounted)
 * 4. ADR-121 ownership model is valid (primary/extension constraints)
 * 5. Plugin bundles match the canonical required/optional set
 * 6. No stale PLUGIN_BUNDLES references in key build scripts
 */

import * as fs from "fs/promises";
import * as fsSync from "fs";
import * as path from "path";
import * as yaml from "js-yaml";
import { fileURLToPath } from "url";
import {
  discoverRepoRoot,
  discoverBundlesAsync,
} from "../lib/plugin-discovery";

// ESM-compatible __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROJECT_ROOT = discoverRepoRoot(__dirname);

import { getDashboardRoot } from "./lib/path-utils";
const DASHBOARD_ROOT = getDashboardRoot(__dirname);

const PLUGINS_DIR = path.join(PROJECT_ROOT, "plugins");
const APP_DIR = path.join(DASHBOARD_ROOT, "app");
const GENERATED_REGISTRY_PATH = path.join(
  DASHBOARD_ROOT,
  "lib",
  "tabs",
  "generated-registry.ts",
);

// Directories that are part of the core shell (not plugin-mounted, not orphaned)
const CORE_SHELL_DIRS = new Set([
  "", // root index
  "settings",
  "skills",
  "api",
  "fonts",
  "(auth)",
  "(core)",
]);

// Canonical plugin bundles under repo-root plugins/. The MVP release tree omits
// the full augur skill bundle, while development checkouts keep it available.
const REQUIRED_PLUGIN_BUNDLES = new Set(["agents", "lib", "obsidian", "vscode"]);
const OPTIONAL_PLUGIN_BUNDLES = new Set(["augur"]);

// Registry hub IDs that intentionally redirect to a different app/ path via nav_route.
// These skills have SKILL.md metadata (hub.id + tabs) but no dashboard/ folder, so
// mount-plugins.ts skips them and they are served by a core shell page instead.
const REDIRECT_REGISTRY_IDS = new Set<string>([
  // (admin/settings plugin removed — Settings is a core shell page at apps/dashboard/app/settings/)
]);

// Key build scripts to check for stale PLUGIN_BUNDLES (hardcoded array, not comments)
const BUILD_SCRIPTS_TO_CHECK = [
  path.join(DASHBOARD_ROOT, "scripts", "generate-tab-registry.ts"),
  path.join(DASHBOARD_ROOT, "scripts", "mount-plugins.ts"),
  path.join(DASHBOARD_ROOT, "scripts", "generate-page-manifest.ts"),
];

// ---------------------------------------------------------------------------
// Terminal colors
// ---------------------------------------------------------------------------

const colors = {
  reset: "\x1b[0m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
  bold: "\x1b[1m",
};

function c(color: keyof typeof colors, message: string): string {
  return `${colors[color]}${message}${colors.reset}`;
}

async function directoryHasFile(dir: string): Promise<boolean> {
  let entries: fsSync.Dirent[];
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return false;
  }

  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue;
    const entryPath = path.join(dir, entry.name);
    if (entry.isFile()) return true;
    if (entry.isDirectory() && (await directoryHasFile(entryPath))) return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

interface SkillFrontmatter {
  "x-augur-hub"?: string;
  "x-augur-config"?: {
    hub?: {
      id?: string;
      title?: string;
    };
  };
  [key: string]: unknown;
}

interface DashboardOwnership {
  hubId: string;
  role: "primary" | "extension";
  extendsHubId?: string;
  routePrefix?: string;
}

interface AssertionResult {
  name: string;
  passed: boolean;
  details: string[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// discoverBundlesAsync imported from ../lib/plugin-discovery (ADR-126 consolidation)

/**
 * Find all skill metadata files under a plugins directory, excluding paths
 * that contain /data/ (backups, generated artefacts, etc.).
 */
async function findDashboardSkillFiles(pluginsDir: string): Promise<string[]> {
  const results: string[] = [];
  let bundles: string[];

  try {
    const entries = await fs.readdir(pluginsDir, { withFileTypes: true });
    bundles = entries
      .filter((e) => e.isDirectory() && !e.name.startsWith("."))
      .map((e) => e.name);
  } catch {
    return [];
  }

  for (const bundle of bundles) {
    const skillsDir = path.join(pluginsDir, bundle, "skills");
    let skills: string[];

    try {
      const entries = await fs.readdir(skillsDir, { withFileTypes: true });
      skills = entries.filter((e) => e.isDirectory()).map((e) => e.name);
    } catch {
      continue;
    }

    for (const skill of skills) {
      const skillPath = path.join(skillsDir, skill, "SKILL.md");
      if (fsSync.existsSync(skillPath)) {
        results.push(skillPath);
      }
    }
  }

  return results;
}

/**
 * Parse ADR-121 ownership fields from SKILL.md frontmatter.
 */
async function parseDashboardOwnership(
  skillPath: string,
): Promise<DashboardOwnership | null> {
  try {
    const content = await fs.readFile(skillPath, "utf8");
    const match = /^---\n([\s\S]*?)\n---/.exec(content);
    if (!match?.[1]) return null;
    const parsed = yaml.load(match[1]) as SkillFrontmatter;

    const hubId = parsed?.["x-augur-hub"];
    if (!hubId) return null;

    const isPrimary = !!parsed["x-augur-config"]?.hub?.id;
    return {
      hubId,
      role: isPrimary ? "primary" : "extension",
      extendsHubId: isPrimary ? undefined : hubId,
      routePrefix: undefined,
    };
  } catch {
    return null;
  }
}

/**
 * Extract all hub IDs registered in generated-registry.ts.
 * The file exports pluginTabRegistry: TabRegistry = { ... }
 * We read the JSON object literal directly via regex (same pattern as existing validate-tab-registry.ts).
 */
function parseGeneratedRegistry(content: string): Set<string> {
  // TODO_BUG(auto-memory-leak): unbounded-cache — Module-level Map/Set without MAX size guard — grows without bound
  const ids = new Set<string>();

  // Match the pluginTabRegistry assignment block
  const jsonMatch =
    /export const pluginTabRegistry: TabRegistry = (\{[\s\S]*?\});/.exec(
      content,
    );
  if (!jsonMatch || !jsonMatch[1]) return ids;

  try {
    const registry = JSON.parse(jsonMatch[1]) as Record<string, unknown>;
    for (const key of Object.keys(registry)) {
      ids.add(key);
    }
  } catch {
    // If JSON.parse fails, fall back to key extraction via regex
    const keyPattern = /"([^"]+)":\s*\{/g;
    let match;
    while ((match = keyPattern.exec(jsonMatch[1])) !== null) {
      ids.add(match[1]);
    }
  }

  return ids;
}

/**
 * Check whether a file content contains a hardcoded PLUGIN_BUNDLES array definition
 * (not just a comment mentioning the name).
 *
 * A stale reference is: `const PLUGIN_BUNDLES = [` or `PLUGIN_BUNDLES = [`
 * where the right-hand side is an array literal (not a function call).
 */
function hasHardcodedPluginBundles(content: string): boolean {
  // Match assignment like: PLUGIN_BUNDLES = [ or PLUGIN_BUNDLES: string[] = [
  const assignmentPattern = /PLUGIN_BUNDLES\s*(?::\s*\w+(?:\[\])?)?\s*=\s*\[/;
  return assignmentPattern.test(content);
}

function hasHubRouteSource(hubDir: string): boolean {
  return (
    fsSync.existsSync(path.join(hubDir, "page.tsx")) ||
    fsSync.existsSync(path.join(hubDir, "[[...slug]]", "page.tsx")) ||
    fsSync.existsSync(path.join(hubDir, "[[...slug]]", "registry.ts"))
  );
}

// ---------------------------------------------------------------------------
// Assertions
// ---------------------------------------------------------------------------

async function assert1_dashboardYamlsInRegistry(): Promise<AssertionResult> {
  const name =
    "Assert 1: Every SKILL.md hub.id appears in generated-registry";
  const details: string[] = [];
  let passed = true;

  // Read generated registry
  let registryContent = "";
  try {
    registryContent = await fs.readFile(GENERATED_REGISTRY_PATH, "utf8");
  } catch {
    return {
      name,
      passed: false,
      details: [
        `FAIL: Cannot read generated-registry at ${GENERATED_REGISTRY_PATH}`,
      ],
    };
  }

  const registryIds = parseGeneratedRegistry(registryContent);
  const skillFiles = await findDashboardSkillFiles(PLUGINS_DIR);

  for (const skillPath of skillFiles) {
    const ownership = await parseDashboardOwnership(skillPath);
    if (!ownership) {
      details.push(
        `  SKIP (no hub.id): ${skillPath.replace(PROJECT_ROOT + "/", "")}`,
      );
      continue;
    }

    if (ownership.role === "extension") {
      details.push(
        `  SKIP (extension): ${skillPath.replace(PROJECT_ROOT + "/", "")}`,
      );
      continue;
    }

    const hubId = ownership.hubId;

    if (!registryIds.has(hubId)) {
      details.push(
        `  MISSING in registry: hub.id="${hubId}" from ${skillPath.replace(PROJECT_ROOT + "/", "")}`,
      );
      passed = false;
    } else {
      details.push(`  OK: hub.id="${hubId}"`);
    }
  }

  return { name, passed, details };
}

async function assert2_registryEntriesHaveMountedDirs(): Promise<AssertionResult> {
  const name =
    "Assert 2: Every generated-registry entry has a routable hub surface";
  const details: string[] = [];
  let passed = true;

  let registryContent = "";
  try {
    registryContent = await fs.readFile(GENERATED_REGISTRY_PATH, "utf8");
  } catch {
    return {
      name,
      passed: false,
      details: [
        `FAIL: Cannot read generated-registry at ${GENERATED_REGISTRY_PATH}`,
      ],
    };
  }

  const registryIds = parseGeneratedRegistry(registryContent);

  for (const hubId of registryIds) {
    // Skip registry entries that intentionally use nav_route to redirect elsewhere
    if (REDIRECT_REGISTRY_IDS.has(hubId)) {
      details.push(
        `  OK (redirect): ${hubId} → served by alternate core shell dir`,
      );
      continue;
    }

    const hubDir = path.join(APP_DIR, hubId);
    if (!fsSync.existsSync(hubDir)) {
      details.push(
        `  OK (generated): app/${hubId}/ is produced by mount-plugins catch-all generation`,
      );
      continue;
    }

    if (hasHubRouteSource(hubDir)) {
      details.push(`  OK: app/${hubId}/`);
    } else {
      details.push(`  MISSING route source: app/${hubId}/`);
      passed = false;
    }
  }

  return { name, passed, details };
}

async function assert3_noOrphanedAppDirs(): Promise<AssertionResult> {
  const name = "Assert 3: No orphaned app/ directories";
  const details: string[] = [];
  const passed = true;

  let appEntries: string[];
  let registryIds = new Set<string>();
  try {
    const entries = await fs.readdir(APP_DIR, { withFileTypes: true });
    appEntries = entries.filter((e) => e.isDirectory()).map((e) => e.name);
    try {
      registryIds = parseGeneratedRegistry(
        await fs.readFile(GENERATED_REGISTRY_PATH, "utf8"),
      );
    } catch {
      registryIds = new Set<string>();
    }
  } catch {
    return {
      name,
      passed: false,
      details: [`FAIL: Cannot read app/ directory at ${APP_DIR}`],
    };
  }

  for (const dirName of appEntries) {
    // Core shell dirs are fine
    if (CORE_SHELL_DIRS.has(dirName)) {
      details.push(`  OK (core shell): app/${dirName}/`);
      continue;
    }

    if (
      registryIds.has(dirName) &&
      hasHubRouteSource(path.join(APP_DIR, dirName))
    ) {
      details.push(`  OK (generated hub route): app/${dirName}/`);
      continue;
    }

    // Plugin-mounted dirs have a .plugin-mount marker
    const mountMarker = path.join(APP_DIR, dirName, ".plugin-mount");
    if (fsSync.existsSync(mountMarker)) {
      details.push(`  OK (plugin-mounted): app/${dirName}/`);
      continue;
    }

    // Everything else is potentially orphaned — warn but don't fail
    details.push(
      `  WARN (orphaned): app/${dirName}/ — not core shell and no .plugin-mount marker`,
    );
    // Orphaned dirs are warnings only (don't fail) per spec
  }

  return { name, passed, details };
}

async function assert4_ownershipModel(): Promise<AssertionResult> {
  const name = "Assert 4: ADR-121 ownership model is valid (primary/extension)";
  const details: string[] = [];
  let passed = true;

  const skillFiles = await findDashboardSkillFiles(PLUGINS_DIR);
  // TODO_BUG(auto-memory-leak): unbounded-cache — Module-level Map/Set without MAX size guard — grows without bound
  const primaries = new Map<string, string>(); // hubId -> source path
  const extensions: Array<{
    source: string;
    extendsHubId: string;
    routePrefix: string;
  }> = [];
  // TODO_BUG(auto-memory-leak): unbounded-cache — Module-level Map/Set without MAX size guard — grows without bound
  const extensionPrefixes = new Map<string, Map<string, string>>(); // extends -> prefix -> source

  for (const skillPath of skillFiles) {
    const ownership = await parseDashboardOwnership(skillPath);
    if (!ownership) continue;
    const relativePath = skillPath.replace(PROJECT_ROOT + "/", "");

    if (ownership.role === "primary") {
      if (primaries.has(ownership.hubId)) {
        details.push(
          `  DUPLICATE primary hub.id="${ownership.hubId}" found in:`,
        );
        details.push(`    - ${primaries.get(ownership.hubId)}`);
        details.push(`    - ${relativePath}`);
        passed = false;
      } else {
        primaries.set(ownership.hubId, relativePath);
      }
      continue;
    }

    const extendsHubId = (ownership.extendsHubId ?? "").trim();
    const routePrefix = (ownership.routePrefix ?? "").trim();

    // Contributors have extendsHubId (= contributes_to) but no routePrefix
    // They mount under the hub using their skill name
    if (extendsHubId && !routePrefix) {
      extensions.push({ source: relativePath, extendsHubId, routePrefix: "" });
      continue;
    }

    if (!extendsHubId || !routePrefix) {
      details.push(
        `  INVALID extension config: ${relativePath} (missing contributes_to)`,
      );
      passed = false;
      continue;
    }

    if (!extensionPrefixes.has(extendsHubId)) {
      extensionPrefixes.set(extendsHubId, new Map());
    }
    const prefixes = extensionPrefixes.get(extendsHubId)!;
    const existing = prefixes.get(routePrefix);
    if (existing) {
      details.push(
        `  DUPLICATE extension routePrefix "${routePrefix}" for hub "${extendsHubId}":`,
      );
      details.push(`    - ${existing}`);
      details.push(`    - ${relativePath}`);
      passed = false;
    } else {
      prefixes.set(routePrefix, relativePath);
    }

    extensions.push({ source: relativePath, extendsHubId, routePrefix });
  }

  for (const extension of extensions) {
    if (!primaries.has(extension.extendsHubId)) {
      details.push(
        `  MISSING primary for extension (${extension.source}): contributes_to="${extension.extendsHubId}"`,
      );
      passed = false;
    } else {
      details.push(
        `  OK extension: ${extension.source} -> /${extension.extendsHubId}/${extension.routePrefix}`,
      );
    }
  }

  for (const hubId of primaries.keys()) {
    details.push(`  OK primary: hub.id="${hubId}"`);
  }

  return { name, passed, details };
}

async function assert5_bundleCount(): Promise<AssertionResult> {
  const name = "Assert 5: Plugin bundles match canonical set";
  const details: string[] = [];
  let passed = true;

  const discovered = await discoverBundlesAsync(PLUGINS_DIR);
  const bundles: string[] = [];
  for (const bundle of discovered) {
    if (await directoryHasFile(path.join(PLUGINS_DIR, bundle))) {
      bundles.push(bundle);
    }
  }
  const bundleSet = new Set(bundles);
  const missingRequired = [...REQUIRED_PLUGIN_BUNDLES].filter(
    (bundle) => !bundleSet.has(bundle),
  );
  const unexpected = bundles.filter(
    (bundle) => !REQUIRED_PLUGIN_BUNDLES.has(bundle) && !OPTIONAL_PLUGIN_BUNDLES.has(bundle),
  );

  if (missingRequired.length > 0 || unexpected.length > 0) {
    passed = false;
    if (missingRequired.length > 0) {
      details.push(`  FAIL: Missing required bundles: ${missingRequired.join(", ")}`);
    }
    if (unexpected.length > 0) {
      details.push(`  FAIL: Unexpected non-empty bundles: ${unexpected.join(", ")}`);
    }
    details.push("  Bundles found:");
  } else {
    details.push(`  OK: Required bundles present (${[...REQUIRED_PLUGIN_BUNDLES].join(", ")})`);
    const presentOptional = [...OPTIONAL_PLUGIN_BUNDLES].filter((bundle) => bundleSet.has(bundle));
    if (presentOptional.length > 0) {
      details.push(`  OK: Optional development bundles present (${presentOptional.join(", ")})`);
    }
  }
  for (const bundle of bundles) {
    details.push(`    - ${bundle}`);
  }

  return { name, passed, details };
}

async function assert6_noStalePluginBundles(): Promise<AssertionResult> {
  const name =
    "Assert 6: No stale PLUGIN_BUNDLES hardcoded array in key build scripts";
  const details: string[] = [];
  let passed = true;

  for (const scriptPath of BUILD_SCRIPTS_TO_CHECK) {
    const relativePath = scriptPath.replace(PROJECT_ROOT + "/", "");
    if (!fsSync.existsSync(scriptPath)) {
      details.push(`  SKIP (not found): ${relativePath}`);
      continue;
    }

    let content = "";
    try {
      content = await fs.readFile(scriptPath, "utf8");
    } catch {
      details.push(`  SKIP (unreadable): ${relativePath}`);
      continue;
    }

    if (hasHardcodedPluginBundles(content)) {
      details.push(
        `  STALE: ${relativePath} contains hardcoded PLUGIN_BUNDLES array`,
      );
      passed = false;
    } else {
      details.push(`  OK: ${relativePath}`);
    }
  }

  return { name, passed, details };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  console.log(c("bold", "=".repeat(64)));
  console.log(
    c("cyan", c("bold", "  Nav Alignment Validation (ADR-109 Phase 8)")),
  );
  console.log(c("bold", "=".repeat(64)));
  console.log();
  console.log(`  Project root : ${PROJECT_ROOT}`);
  console.log(`  Dashboard    : ${DASHBOARD_ROOT}`);
  console.log(`  Plugins      : ${PLUGINS_DIR}`);
  console.log(`  App dir      : ${APP_DIR}`);
  console.log();

  const assertions = [
    assert1_dashboardYamlsInRegistry,
    assert2_registryEntriesHaveMountedDirs,
    assert3_noOrphanedAppDirs,
    assert4_ownershipModel,
    assert5_bundleCount,
    assert6_noStalePluginBundles,
  ];

  const results: AssertionResult[] = [];

  for (const assertFn of assertions) {
    const result = await assertFn();
    results.push(result);

    const status = result.passed ? c("green", "PASS") : c("red", "FAIL");
    console.log(`[${status}] ${result.name}`);

    // Always show failures; show OK lines only in verbose mode
    const showVerbose =
      process.argv.includes("--verbose") || process.argv.includes("-v");
    for (const line of result.details) {
      const isWarn = line.includes("WARN");
      const isFail =
        line.includes("FAIL") ||
        line.includes("MISSING") ||
        line.includes("DUPLICATE") ||
        line.includes("STALE");
      const isSkip = line.includes("SKIP");

      if (isFail) {
        console.log(c("red", line));
      } else if (isWarn) {
        console.log(c("yellow", line));
      } else if (isSkip) {
        console.log(c("yellow", line));
      } else if (showVerbose) {
        console.log(line);
      }
    }
    console.log();
  }

  // Summary
  console.log(c("bold", "=".repeat(64)));
  console.log(c("cyan", c("bold", "  Summary")));
  console.log(c("bold", "=".repeat(64)));
  console.log();

  const failures = results.filter((r) => !r.passed);
  const passed = results.filter((r) => r.passed);

  console.log(`  ${c("green", `PASS: ${passed.length}/${results.length}`)}`);

  if (failures.length > 0) {
    console.log(`  ${c("red", `FAIL: ${failures.length}/${results.length}`)}`);
    console.log();
    console.log(c("red", "  Failed assertions:"));
    for (const f of failures) {
      console.log(c("red", `    - ${f.name}`));
    }
    console.log();
    console.log(c("red", "Validation FAILED\n"));
    process.exit(1);
  } else {
    console.log();
    console.log(c("green", "Validation PASSED\n"));
    process.exit(0);
  }
}

main().catch((err) => {
  console.error(
    c(
      "red",
      `\nUnhandled error: ${err instanceof Error ? err.message : String(err)}\n`,
    ),
  );
  process.exit(1);
});
