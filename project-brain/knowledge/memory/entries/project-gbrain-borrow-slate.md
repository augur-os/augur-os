---
title: project-gbrain-borrow-slate
name: project-gbrain-borrow-slate
description: 9-ADR slate (ADR-738..746) borrows knowledge-graph, RRF, timeline, eval,
  ledger, and dream-cycle patterns from gbrain (github.com/garrytan/gbrain) while
  explicitly rejecting its embedded-DB substrate
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_gbrain_borrow_slate.md
source_hash: 6d37466ebea905f5
---


In May 2026 the user asked for a deep comparison between Augur and gbrain (github.com/garrytan/gbrain, MIT, Y Combinator production deployment) and then a borrow plan. Outcome was a 9-ADR slate, all `Proposed`, all dated 2026-05-13.

**Why:** gbrain validates several patterns Augur was already trending toward (typed graph, RRF fusion, compiled-truth/timeline, eval harness, durable job ledger, dream cycle). Borrowing the *patterns* (not the code or runtime) shortcuts design exploration significantly.

**How to apply:** When picking up any of these ADRs for implementation, treat the gbrain reference as a *design anchor*, not a code source. Augur is Python + Next.js; gbrain is TypeScript + Bun. Algorithms (RRF formula, graph edge patterns, state-machine schema) are public/portable; runtime is not. See [[feedback-vendor-neutral-design]] — any phase that gbrain solves with a direct LLM call must be dispatched through the active AI-client session via `oneshot` instead.

**Slate (in dependency order):**
- ADR-738: typed knowledge graph + entity tiering (foundation)
- ADR-743: file-based job ledger — JSONL append-only, **no SQLite, no PGLite** (foundation)
- ADR-739: hybrid search with RRF + search-mode tiering
- ADR-740: compiled-truth + timeline wiki pattern
- ADR-741: skill resolvability + MECE audit (extends auto-skill-quality)
- ADR-742: retrieval eval harness + contributor capture (validates 738/739/740)
- ADR-744: dream cycle as a **cross-client routine** (not an Augur auto-loop) — trigger lives in the client's routine system (Claude `/schedule`, Codex scheduled agents, Gemini routines); `sync_agents` projects the routine per-client. Depends on 738 + 740 + 743 + 670
- ADR-745: skillify bug-to-skill workflow command
- ADR-746: root `llms.txt` + `llms-full.txt`

**Explicitly NOT borrowed from gbrain** (vision conflicts):
- PGLite / Postgres / pgvector as the storage substrate — clashes with file-first transparency and human-readability principle the user explicitly named
- Direct Anthropic/OpenAI calls from the runtime — violates Rule #11/#19 and [[feedback-vendor-neutral-design]]
- Bun + TypeScript core — Augur is Python + Next.js
- Centralized `gbrain.yml` config — ADR-163 mandates config decentralization via SKILL.md frontmatter
- OAuth 2.1 HTTP MCP server — enterprise-tier concern, not personal
- Forked CLI surface — Augur already has `aug discover` / `aug <tool>`

**File-first constraint** is the load-bearing differentiator and shows up in ADR-738 (frontmatter + JSONL cache), ADR-739 (rebuildable file cache only), ADR-742 (JSONL queries + markdown judgments), ADR-743 (JSONL ledger, never a DB). When implementing any of these, the `cat <file>` test must pass — a user must be able to inspect any state with `cat` / `less` / `grep`.
