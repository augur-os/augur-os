// Compiled to scripts/dist/generate-item-actions.mjs by build-scripts.mjs
import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";
import YAML from "yaml";

import { parseActionsYaml, type UnifiedAction } from "../lib/actions/actionsYamlSchema";
import { type ItemActionDef } from "../lib/browse/itemActionSchema";
import { BROWSE_CATEGORIES } from "../lib/browse/types";
import { getClientSkillDirs } from "../lib/plugin-discovery";
import { getDashboardRoot } from "./lib/path-utils";

const scriptFilename = fileURLToPath(import.meta.url);
const scriptDirname = path.dirname(scriptFilename);

/**
 * Fork-1 (ADR-807): generic per-category card buttons are baker DEFAULTS defined
 * once, genericized with {title}/{path} placeholders. Each skill's own runnable
 * card actions live in {skill}/augur/actions.yaml and merge on top of these.
 *
 * Genericized from the retired per-skill `augur/browse-actions.yaml` files: every
 * button set that previously hardcoded a skill name now uses {title}, and the
 * eight duplicate per-skill "Overview" buttons collapse into one `skill-overview`.
 */
export const DEFAULT_CARD_ACTIONS: Record<string, ItemActionDef[]> = {
  skills: [
    {
      id: "skill-overview",
      label: "Overview",
      icon: "Info",
      kind: "ai",
      template: "Tell me about the {title} skill at {path}. What does it do and how is it used?",
    },
    {
      id: "skill-enhance",
      label: "Enhance",
      icon: "Sparkles",
      kind: "ai",
      template:
        "Review the {title} skill ({path}) for user value, structure, tests, and dashboard wiring. Propose focused improvements.",
    },
    {
      id: "skill-audit",
      label: "Audit",
      icon: "Search",
      kind: "ai",
      template:
        "Audit the {title} skill ({path}) through /auto-test-pytest or the scan-skill-structure CLI surface, then report user-visible gaps before changing code.",
    },
    {
      id: "skill-health",
      label: "Health",
      icon: "Gauge",
      kind: "direct",
      tool: "skill-resolvable-report",
      invalidates: ["skill-health", "browse-index"],
    },
  ],
  "agent-profiles": [
    {
      id: "agent-follow-up",
      label: "Follow-up",
      icon: "MessageSquare",
      kind: "ai",
      template: "I'm looking at the {title} agent ({path}). ",
    },
    {
      id: "agent-enhance",
      label: "Enhance",
      icon: "Sparkles",
      kind: "ai",
      template:
        "Review the {title} agent profile at {path} for prompt quality, tool scoping, and safety. Also tidy redundancy, normalize the frontmatter, and align it to the agent template. Propose the improvements, then apply them to the file.",
    },
    {
      id: "agent-update",
      label: "Update",
      icon: "RefreshCw",
      kind: "ai",
      template:
        "Check the {title} agent profile at {path} for drift (model, mode, and tools vs plugins/agents/registry.json and the agent template). Update the file to match, then re-sync agents.",
    },
    {
      id: "agent-sweep",
      label: "Sweep",
      icon: "Archive",
      kind: "ai",
      template:
        "I want to safely retire the {title} agent ({path}). First map everything that depends on it: its plugins/agents/registry.json entry, generated client configs (.claude/agents, .codex, .gemini via sync_agents), any Task/subagent_type references in commands and skills, and config/system/capability_exposure.yaml. Report the impact. Then, only after I confirm, archive the file to .archive/ (do not hard-delete), neutralize the references, and re-sync agents.",
    },
  ],
  "mcp-tools": [
    {
      id: "mcp-tool-invoke",
      label: "Invoke",
      icon: "Play",
      kind: "ai",
      template:
        "Prepare a safe invocation plan for the {title} MCP tool ({path}). Read its signature and examples, ask for missing arguments, then run it through MCP only after confirming the call shape.",
    },
    {
      id: "mcp-tool-coverage",
      label: "Check coverage",
      icon: "Search",
      kind: "direct",
      tool: "skill-resolvable-report",
      invalidates: ["browse-index"],
    },
    {
      id: "mcp-tool-explain",
      label: "Explain",
      icon: "MessageSquare",
      kind: "ai",
      template: "Explain what the {title} MCP tool does, where it is registered, and which skill owns it.",
    },
  ],
  adrs: [
    {
      id: "adr-implement",
      label: "Implement",
      icon: "Play",
      kind: "ai",
      template:
        "Implement {title} ({path}) through /adr implement. Resolve its plan file first and preserve the current worktree.",
    },
    {
      id: "adr-harden",
      label: "Harden",
      icon: "ShieldCheck",
      kind: "ai",
      template:
        "Run a hardening review for {title} ({path}). Compare the ADR requirements to the live implementation and list gaps first.",
    },
    {
      id: "adr-gaps",
      label: "Check gaps",
      icon: "Search",
      kind: "ai",
      template: "Run /adr gaps for {title} ({path}) and report implementation gaps by severity with file evidence.",
    },
  ],
  commands: [
    {
      id: "command-explain",
      label: "Explain",
      icon: "MessageSquare",
      kind: "ai",
      template:
        "Explain the {title} command ({path}), including owning skill, arguments, guardrails, and verification.",
    },
    {
      id: "command-edit",
      label: "Edit",
      icon: "Pencil",
      kind: "ai",
      template:
        "Update the {title} command ({path}) in its owning skill. Preserve --help behavior and generated-client safety.",
    },
    {
      id: "command-run",
      label: "Run",
      icon: "Play",
      kind: "ai",
      template:
        "Prepare to run the {title} command ({path}). Show the exact slash command and expected safety gates before executing.",
    },
  ],
  documents: [
    {
      id: "document-summary",
      label: "Extract Summary",
      icon: "Sparkles",
      kind: "ai",
      template:
        "Summarize {title} ({path}). Use extract-document or knowledge-summarize-file for documents. For audio/video, transcribe before summarizing. Respect offline mode: use local OCR/transcription only when offline; if the configured local engine is missing, report the setup step and leave the file unchanged. Save useful derived summary metadata or a sidecar, then refresh Browse.",
    },
    {
      id: "document-update-catalog-summary",
      label: "Update Summary",
      icon: "Pencil",
      kind: "ai",
      template:
        "Update the git-tracked catalog summary for {title}. Inspect the current Browse metadata first: source_id={metadata.source_id}, source_relative_path={metadata.source_relative_path}, remote_id={metadata.remote_id}, provider={metadata.provider}, attached_brain_ids={metadata.attachedBrainIds}, remote_revision={metadata.remoteRevision}. Draft a two-to-four-line summary, let me revise it, then write the accepted text using the upsert-document-catalog-summary MCP tool with summary_status=human and summary_generated_from_revision={metadata.remoteRevision}. Refresh Browse after the write-back.",
    },
    {
      id: "document-sweep",
      label: "Sweep",
      icon: "Archive",
      kind: "ai",
      template:
        "Sweep {title} ({path}) from source root {metadata.source_root}. Analyze the file, choose a normalized name and Au-docs destination, apply high-confidence moves through the sweep/hygiene MCP flow, ask me only when destination, filename, privacy, or version grouping is ambiguous, and write the move record before refreshing Browse.",
    },
    {
      id: "document-reextract",
      label: "Re-extract",
      icon: "RefreshCw",
      kind: "ai",
      template:
        "Re-extract {title} ({path}) through the document-extractor command/MCP surface. Inspect the real extracted output, honor offline OCR policy, and refresh Browse/index metadata only after the output is useful.",
    },
    {
      id: "document-transcript",
      label: "Transcript",
      icon: "Mic",
      kind: "ai",
      when: {
        mediaKinds: ["audio", "video"],
        fileExtensions: ["aac", "flac", "m4a", "mp3", "mov", "mp4", "ogg", "wav", "webm"],
      },
      template:
        "Transcribe {title} ({path}). Use extract-audio, then audio-classify, then audio-ingest-write when the transcript should become a voice memo or meeting note. In offline mode, use only the configured local transcription backend; if it is unavailable, report the exact missing setup and leave the source file unchanged. Include transcript status, engine/provider, duration, language, sidecar or note path, and summary preview.",
    },
    {
      id: "document-image-describe",
      label: "Describe Image",
      icon: "Image",
      kind: "ai",
      when: { mediaKinds: ["image"] },
      template:
        "Analyze image {title} ({path}). Describe the visible content, identify actionable details, and extract any relevant context. Respect offline mode and use local OCR/vision only when offline; if no local engine is configured, report setup instructions and leave the file unchanged.",
    },
    {
      id: "document-image-ocr",
      label: "Extract Text",
      icon: "FileText",
      kind: "ai",
      when: { mediaKinds: ["image"] },
      template:
        "Extract readable text from image {title} ({path}) using the document-extractor OCR path. Preserve reading order. Respect offline mode; if local OCR is missing while offline, report setup instructions and leave the file unchanged.",
    },
    {
      id: "document-video-moments",
      label: "Key Moments",
      icon: "Film",
      kind: "ai",
      when: { mediaKinds: ["video"] },
      template:
        "Analyze video {title} ({path}). Transcribe or inspect available metadata first, then summarize key moments, decisions, action items, and follow-ups. Respect offline mode and leave the file unchanged when the configured local transcription engine is unavailable.",
    },
    {
      id: "document-summarize",
      label: "Key Points",
      icon: "BookOpen",
      kind: "ai",
      template:
        "Summarize the document {title} ({path}) and extract the decisions, open questions, and reusable facts.",
    },
    {
      id: "document-index",
      label: "Index",
      icon: "RefreshCw",
      kind: "ai",
      template:
        "Index {title} ({path}) through the approved knowledge index command, then verify the real document is searchable and refresh Browse metadata.",
    },
    {
      id: "document-ask",
      label: "Ask",
      icon: "MessageSquare",
      kind: "ai",
      template:
        "Use Augur search to answer questions about {title} ({path}). Start by listing what the index knows about it.",
    },
  ],
  wiki: [
    {
      id: "wiki-follow-up",
      label: "Follow-up",
      icon: "MessageSquare",
      kind: "ai",
      template: "I'm looking at the {title} wiki page ({path}). ",
    },
    {
      id: "wiki-update",
      label: "Update",
      icon: "RefreshCw",
      kind: "ai",
      template:
        "Update the {title} wiki page ({path}). Re-scan its sources, reconcile the compiled-truth section against the timeline (ADR-740), refresh anything stale, and write the result back using the wiki tools (wiki-scan-sources, wiki-read, wiki-update, wiki-write). Summarize what changed.",
    },
    {
      id: "wiki-dead-links",
      label: "Find dead links",
      icon: "Search",
      kind: "ai",
      template:
        "Find dead citations for {title} ({path}) through the dream-dead-citations command surface, then summarize broken links and proposed repairs before applying changes.",
    },
    {
      id: "wiki-enhance",
      label: "Enhance",
      icon: "Sparkles",
      kind: "ai",
      template:
        "Review the {title} wiki page ({path}) for clarity, structure, and citation quality. Use wiki-rewrite-candidates and wiki-rewrite-proposals to surface weak sections, tidy and tighten them, then apply the top proposal (wiki-apply-top-rewrite-proposal) and lint with wiki-lint. Show me the diff.",
    },
  ],
  notes: [
    {
      id: "note-summarize",
      label: "Summarize",
      icon: "BookOpen",
      kind: "ai",
      template: "Summarize the {title} note ({path}) into a tight executive summary and key insights.",
    },
    {
      id: "note-enrich",
      label: "Enrich",
      icon: "Sparkles",
      kind: "ai",
      when: { noteTypes: ["url", "file"] },
      template:
        "Enrich the {title} article note ({path}) through the LLM-assisted enrichment MCP flow. Call enrich-article with note_path={path}; if it returns needs_llm, use the returned instructions to produce the enrichment fields and then call submit-enrich-article-result with the same note_path. Report the updated note path and changed sections.",
    },
    {
      id: "note-clean",
      label: "Clean",
      icon: "Hammer",
      kind: "ai",
      template: "Clean up the {title} note ({path}) while preserving meaning, frontmatter, and source citations.",
    },
  ],
  drafts: [
    {
      id: "draft-clean",
      label: "Clean",
      icon: "Hammer",
      kind: "ai",
      template: "Clean and prepare the {title} draft ({path}) for publication. Preserve intent and call out unresolved gaps.",
    },
    {
      id: "draft-publish",
      label: "Publish",
      icon: "Send",
      kind: "ai",
      template: "Promote the {title} draft ({path}) into the right Augur destination. Show the target path before writing.",
    },
  ],
  archive: [
    {
      id: "archive-restore",
      label: "Restore",
      icon: "RefreshCw",
      kind: "ai",
      template: "Restore or unarchive {title} ({path}) safely. Identify the active destination and preserve history.",
    },
  ],
  profile: [
    {
      id: "profile-refine",
      label: "Refine",
      icon: "Sparkles",
      kind: "ai",
      template: "Review the {title} memory/profile entry ({path}) and propose tighter wording without losing nuance.",
    },
    {
      id: "profile-curate",
      label: "Curate",
      icon: "RefreshCw",
      kind: "direct",
      tool: "memory-curate",
      confirm: true,
      invalidates: ["memory-profile", "browse-index"],
    },
    {
      id: "profile-regenerate",
      label: "Regenerate profile",
      icon: "Brain",
      kind: "direct",
      tool: "memory-profile-regenerate",
      confirm: true,
      invalidates: ["memory-profile", "browse-index"],
    },
  ],
  integrations: [
    {
      id: "integration-configure",
      label: "Configure",
      icon: "Settings",
      kind: "ai",
      template:
        "Configure the {title} integration ({path}) through the approved onboarding/settings surface. Do not mutate credentials directly.",
    },
    {
      id: "integration-test",
      label: "Test connection",
      icon: "Search",
      kind: "ai",
      template:
        "Test the {title} integration ({path}) with the relevant MCP/status tool and report what works, what is missing, and next setup steps.",
    },
  ],
  "mcp-servers": [
    {
      id: "mcp-server-health",
      label: "Health check",
      icon: "Gauge",
      kind: "ai",
      template:
        "Run the infrastructure health check for {title} ({path}) through the platform-admin CLI/command surface and report real unhealthy records before taking action.",
    },
    {
      id: "mcp-server-restart",
      label: "Restart",
      icon: "RefreshCw",
      kind: "ai",
      template:
        "Diagnose and restart the {title} MCP server only through the documented lifecycle gate. Do not kill client processes.",
    },
  ],
  scripts: [
    {
      id: "script-run",
      label: "Run",
      icon: "Play",
      kind: "ai",
      template:
        "Run {title} ({path}) only through its approved Augur command or auto-loop surface. Do not invoke raw scripts if a slash command exists.",
    },
    {
      id: "script-explain",
      label: "Explain",
      icon: "MessageSquare",
      kind: "ai",
      template: "Explain what {title} ({path}) does, its inputs, and the command surface that owns it.",
    },
    {
      id: "script-refactor",
      label: "Refactor",
      icon: "Hammer",
      kind: "ai",
      template: "Refactor {title} ({path}) with tests first. Preserve cross-OS behavior and command-surface contracts.",
    },
  ],
  "api-routes": [
    {
      id: "api-route-test",
      label: "Test",
      icon: "Search",
      kind: "ai",
      template: "Test the {title} API route ({path}) through dashboard/API test tooling. Do not bypass MCP-owned data flow.",
    },
    {
      id: "api-route-explain",
      label: "Explain",
      icon: "MessageSquare",
      kind: "ai",
      template: "Explain the {title} API route ({path}), its caller, response shape, and MCP/tool dependencies.",
    },
  ],
  tests: [
    {
      id: "test-run",
      label: "Run",
      icon: "Play",
      kind: "ai",
      template:
        "Run the {title} test ({path}) through the relevant auto-loop (/auto-test-dashboard, /auto-test-pytest, or /auto-test-build).",
    },
    {
      id: "test-explain-failure",
      label: "Explain failure",
      icon: "Search",
      kind: "ai",
      template: "Inspect failures for {title} ({path}) and identify root cause before changing code.",
    },
    {
      id: "test-fix",
      label: "Fix",
      icon: "Hammer",
      kind: "ai",
      template: "Fix the failing {title} test ({path}) with systematic debugging and a focused regression.",
    },
  ],
  logs: [
    {
      id: "log-analyze",
      label: "Analyze",
      icon: "Search",
      kind: "ai",
      template: "Analyze {title} ({path}) for user-visible failures, repeated stack traces, and next debugging steps.",
    },
    {
      id: "log-find-errors",
      label: "Find errors",
      icon: "AlertCircle",
      kind: "ai",
      template: "Find the relevant errors in {title} ({path}), group duplicates, and trace the first likely root cause.",
    },
  ],
  "system-metadata": [
    {
      id: "metadata-follow-up",
      label: "Follow-up",
      icon: "MessageSquare",
      kind: "ai",
      template: "I'm looking at the {title} system metadata entry ({path}). Explain what owns it and whether it is current.",
    },
  ],
  pages: [
    {
      id: "page-explain",
      label: "Explain",
      icon: "MessageSquare",
      kind: "ai",
      template: "Explain the {title} dashboard page ({path}), its owning skill, data sources, and user workflow.",
    },
    {
      id: "page-edit-config",
      label: "Edit config",
      icon: "Pencil",
      kind: "ai",
      template: "Edit the skill-owned config/source for the {title} page ({path}); do not edit generated app route copies.",
    },
  ],
  "background-routines": [
    {
      id: "routine-run-now",
      label: "Run now",
      icon: "Play",
      kind: "ai",
      template:
        "Run the {title} background routine ({path}) through /routines or the routine MCP surface, then report the job ledger entry.",
    },
    {
      id: "routine-pause-resume",
      label: "Pause/Resume",
      icon: "RefreshCw",
      kind: "ai",
      template: "Change the schedule state for {title} ({path}) only after showing the current cadence, next run, and impact.",
    },
    {
      id: "routine-last-run",
      label: "View last run",
      icon: "Search",
      kind: "ai",
      template: "Open the last run for {title} ({path}) and summarize outcome, duration, and follow-ups.",
    },
  ],
};

export interface SkillCardActionSource {
  skillId: string;
  filePath: string;
  actions: UnifiedAction[];
}

export type MergeCardActionSourcesResult =
  | { ok: true; registry: Record<string, ItemActionDef[]> }
  | { ok: false; errors: string[] };

function defaultFollowUpAction(category: string): ItemActionDef {
  return {
    id: `${category}-follow-up`,
    label: "Follow-up",
    icon: "MessageSquare",
    kind: "ai",
    template: "I'm looking at {title} ({path}). ",
  };
}

/**
 * Map a unified card-surfaced action to an ItemActionDef.
 * - kind:"ai"  → ItemActionDef{kind:"ai", template}
 * - kind:"mcp" → ItemActionDef{kind:"direct", tool: mcp_tool, args}
 */
function toItemActionDef(action: UnifiedAction): ItemActionDef | null {
  const base: Partial<ItemActionDef> = {
    id: action.id,
    label: action.label,
    icon: action.icon ?? "MessageSquare",
  };
  if (action.kind === "ai") {
    if (!action.template) return null;
    return { ...base, kind: "ai", template: action.template } as ItemActionDef;
  }
  if (action.kind === "mcp") {
    if (!action.mcp_tool) return null;
    const args = Object.fromEntries(
      Object.entries(action.args).map(([key, value]) => [key, String(value)]),
    );
    return {
      ...base,
      kind: "direct",
      tool: action.mcp_tool,
      ...(Object.keys(args).length > 0 ? { args } : {}),
      ...(action.confirm ? { confirm: true } : {}),
    } as ItemActionDef;
  }
  return null;
}

export function mergeCardActionSources(
  sources: SkillCardActionSource[],
  categoryIds: Iterable<string> = BROWSE_CATEGORIES.map((category) => category.id),
): MergeCardActionSourcesResult {
  const registry: Record<string, ItemActionDef[]> = {};
  const seenIdsByCategory = new Map<string, Map<string, string>>();
  const errors: string[] = [];

  // 1) Seed each category bucket with the Fork-1 generic defaults.
  for (const [category, actions] of Object.entries(DEFAULT_CARD_ACTIONS)) {
    const categoryIdsSeen = new Map<string, string>();
    const bucket: ItemActionDef[] = [];
    for (const action of actions) {
      categoryIdsSeen.set(action.id, "DEFAULT_CARD_ACTIONS");
      bucket.push(action);
    }
    seenIdsByCategory.set(category, categoryIdsSeen);
    registry[category] = bucket;
  }

  // 2) Merge skill-declared card actions from augur/actions.yaml on top.
  for (const source of [...sources].sort((a, b) => a.filePath.localeCompare(b.filePath))) {
    for (const action of source.actions) {
      const def = toItemActionDef(action);
      if (!def) continue;
      for (const category of action.categories) {
        const categoryIdsSeen = seenIdsByCategory.get(category) ?? new Map<string, string>();
        seenIdsByCategory.set(category, categoryIdsSeen);
        const bucket = registry[category] ?? [];
        const previous = categoryIdsSeen.get(def.id);
        if (previous) {
          errors.push(
            `${source.filePath}: duplicate action id "${def.id}" in category "${category}" (already declared in ${previous})`,
          );
          continue;
        }
        categoryIdsSeen.set(def.id, source.filePath);
        bucket.push(def);
        registry[category] = bucket;
      }
    }
  }

  // 3) Categories with no default and no skill action keep the generic follow-up.
  for (const category of categoryIds) {
    if (!registry[category] || registry[category].length === 0) {
      registry[category] = [defaultFollowUpAction(category)];
    }
  }

  if (errors.length > 0) return { ok: false, errors };
  return { ok: true, registry };
}

export function generateItemActionsSource(registry: Record<string, ItemActionDef[]>): string {
  const sortedRegistry: Record<string, ItemActionDef[]> = {};
  for (const category of Object.keys(registry).sort()) {
    sortedRegistry[category] = registry[category];
  }

  return [
    "// AUTO-GENERATED — do not edit. Run: pnpm run generate-item-actions",
    'import type { ItemActionDef } from "./itemActionSchema";',
    "",
    "export const GENERATED_ITEM_ACTIONS: Record<string, ItemActionDef[]> = ",
    `${JSON.stringify(sortedRegistry, null, 2)};`,
    "",
  ].join("\n");
}

async function readSkillCardActionSource(
  skillId: string,
  filePath: string,
): Promise<SkillCardActionSource | { errors: string[] }> {
  const raw = await fs.readFile(filePath, "utf8");
  let parsed: unknown;
  try {
    parsed = YAML.parse(raw) as unknown;
  } catch (error) {
    return { errors: [`${filePath}: ${error instanceof Error ? error.message : String(error)}`] };
  }

  let actions: UnifiedAction[];
  try {
    actions = parseActionsYaml(parsed);
  } catch (error) {
    return { errors: [`${filePath}: ${error instanceof Error ? error.message : String(error)}`] };
  }

  // Keep only actions surfaced on a Browse card.
  const cardActions = actions.filter((action) => action.surfaces.includes("card"));
  return { skillId, filePath, actions: cardActions };
}

export async function discoverSkillCardActionSources(startDir = scriptDirname): Promise<SkillCardActionSource[]> {
  const clientSkillDirs = getClientSkillDirs(startDir);
  const sources: SkillCardActionSource[] = [];
  const errors: string[] = [];

  for (const skillsDir of Object.values(clientSkillDirs).sort()) {
    let entries: Array<{ name: string; isDirectory: () => boolean }>;
    try {
      entries = await fs.readdir(skillsDir, { withFileTypes: true });
    } catch {
      continue;
    }

    for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
      if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
      const filePath = path.join(skillsDir, entry.name, "augur", "actions.yaml");
      try {
        await fs.access(filePath);
      } catch {
        continue;
      }

      const source = await readSkillCardActionSource(entry.name, filePath);
      if ("errors" in source) {
        errors.push(...source.errors);
      } else {
        sources.push(source);
      }
    }
  }

  if (errors.length > 0) {
    throw new Error(errors.join("\n"));
  }

  return sources;
}

export async function generateItemActions(startDir = scriptDirname): Promise<string> {
  const dashboardRoot = getDashboardRoot(startDir);
  const sources = await discoverSkillCardActionSources(startDir);
  const merged = mergeCardActionSources(sources);
  if (!merged.ok) {
    throw new Error(merged.errors.join("\n"));
  }

  const target = path.join(dashboardRoot, "lib", "browse", "generated-item-actions.ts");
  await fs.writeFile(target, generateItemActionsSource(merged.registry), "utf8");
  return target;
}

if (process.argv[1] && path.resolve(process.argv[1]) === scriptFilename) {
  generateItemActions()
    .then((target) => {
      console.log(`Generated ${path.relative(process.cwd(), target)}`);
    })
    .catch((error: unknown) => {
      console.error(error instanceof Error ? error.message : String(error));
      process.exit(1);
    });
}
