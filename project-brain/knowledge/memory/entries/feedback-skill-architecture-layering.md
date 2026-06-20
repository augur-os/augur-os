---
title: feedback-skill-architecture-layering
name: feedback-skill-architecture-layering
description: Augur's four-layer harness model — trigger → policy (commands/*.md) →
  agent orchestration → atomic ops. MCP shows up in TWO places (discovery wrapper
  on top + atomic tools at bottom) and conflating them causes architecture drift.
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_skill_architecture_layering.md
source_hash: fa9c4d473541239d
_mentions:
- '[[feedback-vendor-neutral-design]]'
_entity_tier: 3
---




Augur is a **harness layer around native AI clients**, not the executor. The architecture is four layers, in fixed direction:

```
TRIGGER          CLI / Dashboard / Daemon / slash command
                      ↓
POLICY           commands/*.md  ←── canonical user-facing surface
                      ↓
                 [Two ways the policy reaches the agent:]
                  (a) Native client reads commands/*.md directly
                      (Claude Code, Codex, Gemini)
                  (b) MCP discovery wrapper exposes the same command
                      as an MCP tool for clients that can't read
                      commands/*.md natively (OpenCode, etc.)
                      ↓
ORCHESTRATION    Native AI-client agent (vendor-neutral)
                 Reads policy, uses ITS OWN fetch/browser tools,
                 judges, classifies, sequences
                      ↓
ATOMIC OPS       Atomic MCP tools + `aug` CLI commands
                 Bounded, stateless, never orchestrate
```

**The MCP layer appears twice and they are different.** This is the conceptual trap that causes AI clients to drift:

- **MCP as discovery wrapper (top)** — a thin tool that says "I am `/ingest`; here's the policy body". Same body, same agent flow, just routed for non-generic clients.
- **MCP as atomic op (bottom)** — `save-url-source`, `wiki-write`, etc. The agent's hands.

`x-augur-mcp-tools` in SKILL.md frontmatter doesn't distinguish the two roles. That's why a tool listed there can look "canonical" when it's actually a workflow-shaped violation (e.g. `ingest-url` doing fetch+extract+save in one call is the "Bad" shape from `docs/references/agent-vs-mcp-examples.md` Example 2).

**How to apply:**
- When writing a slash command body (`commands/<name>.md`), the body's primary instructions tell the agent to use ITS OWN browser/fetch tools (claude-in-chrome MCP, WebFetch, playwright MCP, Codex web, Gemini grounding) for fetch-and-parse, THEN call atomic MCP/CLI tools for the save step. Never make an MCP tool the primary "do the whole thing" surface.
- When designing a new MCP tool, ask which layer it sits in. Discovery wrappers and atomic ops both exist on the wire as MCP tools, but they have different jobs. A tool that "fetches + extracts + writes" is neither — it's a violation.
- When the architecture is unclear from frontmatter alone, the canonical sources are `docs/references/ai-client-execution-model.md`, `docs/references/agent-vs-mcp-checklist.md`, and `docs/references/agent-vs-mcp-examples.md` (especially Example 2: PDF ingestion).
- Related: [[feedback-vendor-neutral-design]] (don't bind to a specific AI client/vendor); ADR-734 (Capability Surface Phase 3, accepted 2026-05-12) is moving away from auto-generated command wrappers when `AGENTS.md` and Browse suffice — wrappers survive only for clients that can't read agent-instruction Markdown natively.
- See also: `docs/references/agent-fetch-primitives.md` (to be written) for the vendor-neutral menu of fetch options per content type.
