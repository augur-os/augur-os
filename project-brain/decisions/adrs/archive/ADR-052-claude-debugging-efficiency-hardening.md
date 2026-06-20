---
status: Implemented
date: '2026-02-07'
deciders:
- Augur Core Team
related:
- ADR-051 (Crew Skill Sharpening)
- ADR-014 (MCP Instance Management)
- ADR-021 (Platform Enhancements)
hub: null
tags:
- claude
- debugging
- efficiency
- hardening
- full
superseded_by: null
---

# ADR-052: Claude Debugging Efficiency Hardening — Full-Stack Vision & Autonomous Verification

**Source**: Distilled from [Wasp: Claude Code Fullstack Development Essentials](https://wasp.sh/blog/2026/01/29/claude-code-fullstack-development-essentials), filtered for Augur-applicable patterns.

## Context

Augur's existing `/debug-protocol` (4-phase: Assessment → Reproduction → Hypothesis → Fix) is solid for root-cause analysis but operates in a **human-in-the-loop** mode: the developer must report errors, paste logs, describe UI state. This creates bottlenecks:

1. **Blind coding** — Claude Code writes code but can't see build output in real time. Developer must copy-paste terminal errors back.
2. **No browser visibility** — Runtime errors, UI regressions, and design issues are invisible to the agent. Developer acts as the "eyes".
3. **Context window waste** — MCP servers loaded purely for doc-fetching consume 2-5% of context per server before any work begins. With 5+ servers, that's 10-25% burned on tool definitions.
4. **Stale documentation** — Claude's training cutoff means it hallucinates API patterns for fast-moving dependencies (MCP SDK, FastMCP, etc.).

The debugging protocol tells Claude *how to think* about bugs. What's missing is giving Claude *the ability to see* bugs autonomously.

### What the Source Article Gets Right

| Insight | Augur Applicability |
|---------|--------------------|
| Background dev server gives Claude live build feedback | **High** — Augur's MCP server, dashboard, and plugin services all have dev servers |
| Chrome DevTools MCP closes the browser feedback loop | **High** — Dashboard UI debugging, Liquid Glass verification |
| llms.txt is 10-100x more context-efficient than MCP for docs | **High** — We already have multiple doc-fetching MCPs that could be replaced |
| Autonomous verification loops reduce human bottleneck | **High** — Directly extends our debug-protocol |

### What the Source Article Gets Wrong (for us)

| Claim | Reality for Augur |
|-------|------------------|
| "Pick an opinionated framework and AI needs less guidance" | Augur IS the framework. We're building infrastructure, not consuming it. Our CLAUDE.md + ADRs + crew skills ARE the opinionated conventions. |
| "You don't need subagents" | We have 8 crew skills (post ADR-051). For a multi-layer system like Augur, specialized subagents are justified. |
| "Just use basic Claude Code features" | Works for greenfield apps. Augur has 50+ ADRs, plugin architecture, MCP servers — we need the advanced features. |

## Decision

### 1. Add Chrome DevTools MCP for Browser Debugging

**What**: Install Chrome DevTools MCP as a project-scoped server for dashboard UI verification.

**Installation**:
```bash
claude mcp add chrome-devtools --scope project npx chrome-devtools-mcp@latest
```

**When to use**:
- Dashboard feature development (Liquid Glass components, hub navigation)
- Frontend crew skill work requiring visual verification
- Performance auditing (Lighthouse scores via DevTools)
- Verifying that MCP tool results render correctly in the dashboard

**When NOT to use**:
- Backend-only changes (MCP server code, skill scripts, chain execution)
- CI/CD pipelines (no browser available)
- Data migrations or config changes

**CLAUDE.md rule to add**:
```markdown
### Browser Verification (Dashboard Development)
- After any dashboard UI change, verify in browser via Chrome DevTools MCP
- Check: component renders, no console errors, responsive layout intact
- If DevTools MCP unavailable, note "NOT VERIFIED IN BROWSER" in commit message
```

### 2. Background Dev Server as Standard Practice

**What**: When working on Augur components that have dev servers, always run them as Claude Code background tasks.

**Components with dev servers**:
| Component | Command | Purpose |
|-----------|---------|----------|
| Dashboard | `npm run dev` (from `plugins/ai/dashboard/`) | UI development |
| MCP Server | `python -m augur.mcp.server` | Tool development |
| Watcher | `augur watch` | File change reactions |

**CLAUDE.md rule to add**:
```markdown
### Background Dev Servers
- When modifying dashboard code: run `npm run dev` as background task
- When modifying MCP tools: run MCP server as background task
- Read background task output BEFORE reporting success to user
- If build errors appear in background task, fix them before proceeding
```

**Integration with debug-protocol**: Background task output becomes the "instrumentation" in Phase 2 (Reproduction). Instead of the developer creating a repro script, Claude can observe failures directly from the running server.

### 3. Prefer llms.txt Over MCP Servers for Documentation Access

**What**: For dependencies where we currently use MCP servers primarily for doc-fetching, switch to llms.txt URLs fetched on-demand.

**Context window math**:
- 1 MCP server loaded = ~2,000-5,000 tokens (tool definitions, always in context)
- 1 llms.txt fetch = ~100 tokens (index), then ~500-2,000 tokens per doc page (on-demand, only when needed)
- With 5 doc-fetching MCPs replaced: **~10,000-25,000 tokens saved per session**

**Migration table**:
| Dependency | Current Approach | New Approach | llms.txt URL |
|------------|-----------------|--------------|-------------|
| Claude Code itself | Built-in docs map | Keep as-is | N/A (internal) |
| FastMCP | Generic MCP | Fetch llms.txt | Check availability |
| Prisma (if used) | None | Add llms.txt | prisma.io/llms.txt |
| Tailwind | None | Add llms.txt | Check availability |
| React | None | Add llms.txt | Check availability |

**CLAUDE.md rule to add**:
```markdown
### Documentation Fetching Priority
1. Check if dependency has llms.txt → fetch and navigate to relevant docs
2. If no llms.txt → check if MCP server exists with doc tools
3. If neither → use web search as last resort
4. NEVER guess at API patterns for dependencies updated after training cutoff
```

**What to keep as MCP**: Servers that provide *actions* (not just docs) stay as MCP — Supabase, Playwright, GitHub, etc. The rule is: if the MCP server's primary value is executing operations, keep it. If it's primarily doc-fetching, replace with llms.txt.

### 4. Extend debug-protocol with Autonomous Verification Phase

**What**: Add a "Phase 0" and "Phase 5" to the existing 4-phase debug protocol.

**Updated protocol**:

```
Phase 0: Establish Visibility (NEW)
  - Start relevant dev server(s) as background tasks
  - If UI-related: connect Chrome DevTools MCP
  - Confirm you can see build output and/or browser state

Phase 1: Assessment & Complexity (existing)
Phase 2: Reproduction & Instrumentation (existing, enhanced)
  - ENHANCED: Use background task logs as primary instrumentation
  - ENHANCED: Use DevTools console for browser-side errors
Phase 3: System Review & Hypothesis (existing)
Phase 4: Fix & Verification (existing, enhanced)
  - ENHANCED: Verify fix via background task (build passes)
  - ENHANCED: Verify fix via DevTools (no console errors, UI correct)

Phase 5: Autonomous Regression Check (NEW)
  - After fix, navigate to 2-3 related pages/features in browser
  - Confirm no regressions introduced
  - Run relevant test suite if available
  - Only report success after Phase 5 passes
```

**Update location**: `data/ai-bridge/agent-workflows/debug-protocol.md` (source of truth), which syncs to `.claude/commands/debug-protocol.md`.

### 5. CLAUDE.md Debugging Section Consolidation

**What**: Add a unified "Debugging Efficiency" section to CLAUDE.md that ties together background tasks, DevTools, llms.txt, and the enhanced debug-protocol.

**Section to add after the existing "No Workarounds" section**:
```markdown
## 🔍 Debugging Efficiency — Full-Stack Vision

### Principle: See Before You Fix
Claude must OBSERVE failures before attempting fixes. Never fix blind.

### Visibility Stack
1. **Build errors** → Background dev server output (always running during development)
2. **Runtime errors** → Chrome DevTools MCP console logs
3. **UI issues** → Chrome DevTools MCP screenshots and DOM inspection
4. **API errors** → Background MCP server logs
5. **Test failures** → pytest/vitest output with full tracebacks

### Autonomous Verification Checklist
Before reporting a task as complete:
- [ ] Background task shows clean build (no errors/warnings)
- [ ] If UI change: verified in browser via DevTools (no console errors)
- [ ] If API change: tested endpoint returns expected response
- [ ] If config change: restart relevant services and confirm they start cleanly

### Context Window Hygiene
- Prefer llms.txt over MCP servers for documentation
- Run `/compact` when context exceeds 60% (not 75% — we have heavy tool definitions)
- Start new session for unrelated tasks rather than accumulating context
```

## Alternatives Considered

### A: Add Browser Automation via Playwright MCP Instead of Chrome DevTools

**Considered because**: ADR-021 already mentions Playwright MCP for browser automation.

**Rejected because**: Chrome DevTools MCP specializes in debugging (console access, performance profiling, DOM inspection). Playwright MCP specializes in testing (scripted flows, assertions). For debugging efficiency, DevTools is the better fit. Playwright remains for automated testing (validator crew skill).

### B: Build Custom Doc-Fetching MCP Server for All Dependencies

**Considered because**: Could provide unified, pre-processed documentation with version awareness.

**Rejected because**: Engineering overhead for marginal benefit. llms.txt is a standard, maintained by each dependency's authors, and costs effectively zero context tokens when not in use. Building our own doc server would be a maintenance burden.

### C: Skip Browser Automation Entirely, Keep Human-in-the-Loop

**Considered because**: Augur's dashboard is not the primary product surface — most users interact via Claude Code / chat.

**Rejected because**: Dashboard development still consumes significant cycles. Even if it's not the primary surface, every hour saved on UI debugging compounds. The DevTools MCP is lightweight (~2% context) and high-value.

## Implementation

### Priority Order

1. **[Quick Win]** Add Chrome DevTools MCP to project config
2. **[Quick Win]** Add CLAUDE.md rules for background tasks and browser verification
3. **[Medium]** Update debug-protocol with Phase 0 and Phase 5
4. **[Medium]** Audit current MCP servers — identify doc-only servers to replace with llms.txt
5. **[Low]** Create llms.txt index for Augur's own documentation (for users running Claude Code with Augur)

### Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| Debug cycles requiring human error reporting | ~70% | <30% |
| Context window usage at session start | ~15-20% | <10% |
| UI bugs caught by agent autonomously | ~0% | >50% |
| Average fix-verify iterations per bug | 3-4 | 1-2 |

### Risks

- **Chrome DevTools MCP stability**: It's relatively new. May have rough edges. Mitigation: keep Playwright MCP as fallback for scripted testing.
- **llms.txt availability**: Not all dependencies publish llms.txt. Mitigation: fall back to MCP or web search per the priority rules.
- **Context overhead**: Adding DevTools MCP while keeping existing MCPs could net-increase context usage if we don't also remove doc-only servers. Mitigation: implement items 1-4 together, not piecemeal.
