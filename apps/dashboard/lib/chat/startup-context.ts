/**
 * ADR-157 Decision 1: Auto-Context on CLI Start
 *
 * Builds a startup context payload to inject into the CLI after spawn.
 * Caches project identity to avoid re-reading files on every start.
 *
 * @deprecated ADR-161 replaces these functions with ContextEnvelope-based
 * context injection via buildPromptFromEnvelope(). Use resolveContext() +
 * buildPromptFromEnvelope() from '@/lib/chat/context-envelope' instead.
 * These functions are retained as fallbacks for cli/route.ts backward compatibility.
 */

import path from "path";
import fs from "fs";

const AUGUR_ROOT =
  process.env.AUGUR_ROOT ||
  path.join(process.env.HOME || "", "Projects", "Augur");

interface StartupContext {
  projectIdentity: string;
  pageContext: string;
  timestamp: number;
}

// Cache project identity — it rarely changes
let cachedProjectIdentity: string | null = null;
let identityCacheTime = 0;
const IDENTITY_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * Read a brief project identity from vision.md or fallback to a default.
 */
function readProjectIdentity(): string {
  if (
    cachedProjectIdentity &&
    Date.now() - identityCacheTime < IDENTITY_CACHE_TTL
  ) {
    return cachedProjectIdentity;
  }

  const visionPath = path.join(AUGUR_ROOT, "docs", "memory", "vision.md");
  try {
    if (fs.existsSync(visionPath)) {
      const content = fs.readFileSync(visionPath, "utf-8");
      // Take the first ~500 chars as a summary
      const summary = content.slice(0, 500).split("\n").slice(0, 8).join("\n");
      cachedProjectIdentity = summary;
      identityCacheTime = Date.now();
      return summary;
    }
  } catch {
    // Fall through to default
  }

  cachedProjectIdentity =
    "Augur is a local-first personal knowledge and automation system.";
  identityCacheTime = Date.now();
  return cachedProjectIdentity;
}

/**
 * Extract hub and skill name from a page path.
 */
function parsePagePath(pagePath: string): {
  hub: string;
  skill: string | null;
} {
  const parts = pagePath.split("/").filter(Boolean);
  return {
    hub: parts[0] || "home",
    skill: parts[1] || null,
  };
}

/**
 * Build context about the current page.
 */
function buildPageContext(currentPage: string): string {
  const { hub, skill } = parsePagePath(currentPage);
  const lines: string[] = [`Current page: ${currentPage}`, `Hub: ${hub}`];
  if (skill) {
    lines.push(`Skill: ${skill}`);
  }
  return lines.join("\n");
}

/**
 * Build the full startup context payload as a prompt string.
 * This gets written to the PTY after spawn to give the CLI context.
 *
 * @deprecated Use buildPromptFromEnvelope() from '@/lib/chat/context-envelope' instead.
 */
export function buildStartupPrompt(currentPage: string): string {
  const identity = readProjectIdentity();
  const pageCtx = buildPageContext(currentPage);

  const lines = [
    "You are the Augur assistant embedded in the dashboard. Here is your context:",
    "",
    "## Project",
    identity,
    "",
    "## Current Context",
    pageCtx,
    "",
    "Greet the user briefly and ask how you can help with this page.",
  ];

  return lines.join("\n");
}

/**
 * Build startup context as a structured object (for API responses).
 *
 * @deprecated Use resolveContext() from '@/lib/chat/context-envelope' instead.
 */
function buildStartupContext(currentPage: string): StartupContext {
  return {
    projectIdentity: readProjectIdentity(),
    pageContext: buildPageContext(currentPage),
    timestamp: Date.now(),
  };
}
