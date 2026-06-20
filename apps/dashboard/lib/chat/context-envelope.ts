/**
 * ADR-161: Chat Context Injection Optimization
 *
 * Structured context envelope that replaces flat-string context builders.
 * All dispatch paths (chat, oneshot, IDE, escalation) use this envelope
 * for typed, budget-aware context injection.
 */

import { mcpCall } from "@/lib/mcp/client";

// ─── Token Budget Tiers ──────────────────────────────────────────────────────

/** Minimal: Agent bubbles / oneshot — page + hub + action prompt only */
export const BUDGET_MINIMAL = 200;

/** Standard: Chat sessions — page + hub + skill summary + tool list */
export const BUDGET_STANDARD = 800;

/** Rich: IDE dispatch — full skill context + action chain + data paths */
export const BUDGET_RICH = 2000;

export type ContextPriority = "minimal" | "standard" | "rich";

// ─── Context Envelope ────────────────────────────────────────────────────────

export interface ContextAction {
  id: string;
  label: string;
  description: string;
  prompt: string;
}

export interface ContextEnvelope {
  /** Session identity */
  sessionId: string;
  timestamp: number;

  /** Navigation context */
  page: string;
  hub: string;
  skill: string | null;

  /** Skill context (pre-resolved by resolve-context API) */
  skillSummary: string | null;
  skillDataDir: string | null;
  skillTools: string[];
  skillActions: string[];

  /** Action context (when triggered by action button) */
  action: ContextAction | null;

  /** Project identity (populated server-side by resolve-context API) */
  projectIdentity: string | null;

  /** Token budget */
  maxContextTokens: number;
  priority: ContextPriority;
}

// ─── Token Estimation ────────────────────────────────────────────────────────

/** Approximate token count — chars/4 is the standard heuristic for English text. */
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

// ─── Priority-Based Prompt Assembly ──────────────────────────────────────────

interface PromptSection {
  content: string;
  /** Higher priority = more likely to survive budget cuts. 5 = always kept, 1 = cut first. */
  priority: number;
  tokens: number;
}

/**
 * Assemble sections within a token budget.
 * Sorts by priority descending, drops lowest-priority sections first.
 */
function assembleWithinBudget(
  sections: PromptSection[],
  maxTokens: number,
): string {
  // Sort by priority descending (highest first = survives cuts)
  const sorted = sections.toSorted((a, b) => b.priority - a.priority);

  let totalTokens = 0;
  const included: PromptSection[] = [];

  for (const section of sorted) {
    if (totalTokens + section.tokens <= maxTokens) {
      included.push(section);
      totalTokens += section.tokens;
    }
    // Skip sections that would exceed budget
  }

  // Reassemble in priority order (highest first for readability)
  included.sort((a, b) => b.priority - a.priority);
  return included.map((s) => s.content).join("\n\n");
}

/**
 * Build a prompt string from a ContextEnvelope with priority-based budget truncation.
 *
 * Priority order (5 = always preserved, 1 = cut first):
 *   5: Core routing (page, hub)
 *   4: Action prompt (the user's task)
 *   3: Skill summary (highest signal-to-token ratio)
 *   2: Available tools/actions for quick grounding
 *   1: Project identity (generic, lowest signal)
 */
export function buildPromptFromEnvelope(envelope: ContextEnvelope): string {
  const sections: PromptSection[] = [];

  // Priority 5 (always): Core routing
  const routingLines = [`Page: ${envelope.page}`, `Hub: ${envelope.hub}`];
  if (envelope.skill) {
    routingLines.push(`Skill: ${envelope.skill}`);
  }
  if (envelope.skillDataDir) {
    routingLines.push(`Data dir: ${envelope.skillDataDir}`);
  }
  const routingContent = routingLines.join("\n");
  sections.push({
    content: routingContent,
    priority: 5,
    tokens: estimateTokens(routingContent),
  });

  // Priority 4 (always): Action prompt
  if (envelope.action) {
    const actionContent = `## Task\n${envelope.action.prompt}`;
    sections.push({
      content: actionContent,
      priority: 4,
      tokens: estimateTokens(actionContent),
    });
  }

  // Priority 3: Skill summary
  if (envelope.skillSummary) {
    const skillContent = `## Skill: ${envelope.skill}\n${envelope.skillSummary}`;
    sections.push({
      content: skillContent,
      priority: 3,
      tokens: estimateTokens(skillContent),
    });
  }

  // Priority 2: Tools and actions (useful grounding, but cut before summary/task/routing)
  if (envelope.skillTools && envelope.skillTools.length > 0) {
    const toolsContent = `## Tools\n${envelope.skillTools.join(", ")}`;
    sections.push({
      content: toolsContent,
      priority: 2,
      tokens: estimateTokens(toolsContent),
    });
  }

  if (envelope.skillActions && envelope.skillActions.length > 0) {
    const actionsContent = `## Actions\n${envelope.skillActions.join(", ")}`;
    sections.push({
      content: actionsContent,
      priority: 2,
      tokens: estimateTokens(actionsContent),
    });
  }

  // Priority 1 (cut first): Project identity
  if (envelope.projectIdentity) {
    sections.push({
      content: `## Project\n${envelope.projectIdentity}`,
      priority: 1,
      tokens: estimateTokens(envelope.projectIdentity) + 5,
    });
  }

  return assembleWithinBudget(sections, envelope.maxContextTokens);
}

// ─── Budget Helper ───────────────────────────────────────────────────────────

/** Map a priority level to its token budget. */
export function getBudgetForPriority(priority: ContextPriority): number {
  switch (priority) {
    case "minimal":
      return BUDGET_MINIMAL;
    case "standard":
      return BUDGET_STANDARD;
    case "rich":
      return BUDGET_RICH;
  }
}

// ─── Client-Side Fetch Helper ────────────────────────────────────────────────

/**
 * Fetch a ContextEnvelope from the resolve-context API.
 * Intended for use in client-side dispatch paths (useActionRunner, FloatingChat).
 */
export async function resolveContext(
  page: string,
  priority: ContextPriority = "standard",
  action?: { id: string; label: string; description: string; prompt: string },
): Promise<ContextEnvelope> {
  const hub = page.split("/").filter(Boolean)[0] || "home";
  const skill = page.split("/").filter(Boolean)[1] || null;

  let projectIdentity: string | null = null;
  try {
    const raw = await mcpCall<Record<string, unknown>>("get-context", { page, priority, action });
    // get-context returns { result: "markdown string" } — extract the context text
    if (raw && typeof raw === "object") {
      if ("result" in raw && typeof raw.result === "string") {
        projectIdentity = raw.result;
      } else if ("page" in raw && "hub" in raw) {
        // Already a proper ContextEnvelope — use directly
        return raw as unknown as ContextEnvelope;
      }
    }
  } catch {
    // MCP tool unavailable — proceed with null projectIdentity
  }

  return {
    sessionId: crypto.randomUUID(),
    timestamp: Date.now(),
    page,
    hub,
    skill,
    skillSummary: null,
    skillDataDir: null,
    skillTools: [],
    skillActions: [],
    action: action ?? null,
    projectIdentity,
    maxContextTokens: getBudgetForPriority(priority),
    priority,
  };
}
