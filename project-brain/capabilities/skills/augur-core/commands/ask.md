---
description: Ask your second brain with reflective context and optional retention.
visibility: core
x-augur-export-command: true
---

# /ask

Ask your second brain: a reflective inner voice that draws on your vault,
memories, decisions, preferences, projects, and recent focus. It answers first
and stays conversational; retention is opt-in.

## Usage

- `/ask What pattern keeps showing up in how I choose projects?`
- `/ask --retain What have I learned about how I work best?`
- `/ask --retain --to project-augur What should this project remember?`
- `/ask remember this: I work best after I write the plan first`
- `/ask save this to memory: morning focus blocks are my highest leverage`
- `/ask --private Help me think through this without saving it`
- `/ask --no-retain What are my options here?`

## Answer contract

`/ask` is the strongest second-brain compounding surface, so the reply earns its
keep by being an answer, not a status report.

- **Lead with the answer.** Open with the substance, not the process or the route taken.
- **Speak in a reflective voice** — an inner voice reasoning over what it knows about the user, not a search tool reading back hits.
- **Answer once.** Don't ask clarifying questions unless the prompt is too empty to answer responsibly.
- **Hide the machinery.** Never mention tools, routing, retention, or indexing in the reply. The only allowed meta is a context-strength caveat when the quality gate returns `weak-context`, plus an optional `Based on:` source-basis line when the answer turns on freshness or client/global memory.
- **Don't become a logging UI.** No retention footer and no "saved to memory" chrome unless the user asks for it (see [Retention](#retention)).

## Workflow

1. **Parse the question** from `$ARGUMENTS`. If no arguments are provided, ask what's on the user's mind.
2. **Decide retention intent** before answering (see [Retention](#retention)). Settling this first keeps the answer itself clean.
3. **Continue the thread.** If this is a follow-up in the same reflective thread, summarize the prior exchange and pass that summary as `conversation_summary` to `reflect-context`.
4. **Read personal context** with `reflect-context`.
   - It builds a static live-memory source pack from known local roots: Augur wiki, vault memory, runtime memory, client/global memory roots such as Codex memory when present, and recent repo evidence for current-focus questions.
   - Retrieval is deterministic: bounded file reads, metadata checks, and optional `rg` acceleration with a Python fallback. It must not call an LLM, rebuild the wiki, dispatch agents, or depend on synced memory.
   - When the answer turns on freshness or client/global memory, append a compact source-basis line, e.g.
     `Based on: Codex memory updated May 27, Augur commits from May 28, and Au-vault wiki active-projects updated May 12.`
5. **Assess context support** with `src/mcp/augur_core/tools/core/ask_quality.py:assess_context_support`, passing the source metadata returned by `reflect-context` when available. If it returns `answer_mode: weak-context`, answer with explicit weak-context framing and name what's missing: no sources, too few sources, low context volume, stale sources, no fresh sources, stale primary source, missing client memory, weak generic query terms, or low-relevance context (sources only marginally match the question).
6. **Answer once**, per the [Answer contract](#answer-contract) above.
7. **Classify the outcome** as one or more of: `decision`, `preference`, `insight`, `inferred-pattern`, `contradiction`, `open-question`, `ephemeral`.
8. **Persist only if retention is explicit** (see [Retention](#retention)).
9. **Leave the wiki to session-end.** Durable `/ask` signal can strengthen the wiki later through session-end compounding; `/ask` itself never writes wiki pages directly.

## Retention

Retention is **off by default** — `/ask` answers without persisting anything unless you opt in.

**When to retain.** Treat retention as explicit only when `--retain` is present, or the prompt contains explicit retention language: `remember this …`, `save this to memory …`, or `promote this …`. Anything else answers only and skips persistence. `--private` and `--no-retain` never persist and never feed session-end compounding.

**Signals.** Capture user-supplied retention language and stated conclusions as `explicit_signals`; capture useful patterns inferred from the exchange as `inferred_signals`.

**The call.** When retention is explicit, call `ask-retain` with the final `question` and `answer`, any `explicit_signals` and `inferred_signals`, the active `retain_mode`, and `surface_footer: false`. Pass `to` when the user gave `--to <brain-id>`; otherwise pass cwd so the tool resolves the active project brain before personal fallback. Pass explicit `kinds` only when the conversation clearly warrants them. `ask-retain` then classifies and persists: atomic items go to memory logs, richer outcomes go to synthesis notes, and any retained outcome marks the wiki session-update safety-net flag.

**Footer policy.** Keep `surface_footer: false` so retained answers don't append a footer. Only surface retention state when the user explicitly asks for it, or when retention fails in a way that affects trust.

**Weak context.** If step 5 returned `weak-context`, skip normal durable retention. Only if the user explicitly asks to save the uncertainty should you call `ask-retain` with `kinds: ["open-question"]`.

## Flags

- `--retain` — explicitly retain high-signal outcomes by calling `ask-retain` after the answer
- `--no-retain` — answer only, skip persistence
- `--private` — answer only, never persist or feed session-end compounding
- `--to <brain-id>` — choose the brain destination for retained output

## Search routing

`/ask` also handles structured index queries (formerly `/search`). Route to
search mode when the arguments:

- start with `search`, `status`, `reindex`, `cleanup`, or `purge`
- contain the `--admin` flag
- explicitly reference an index scope such as `ai`, `dev`, `core`, or `all`

Dispatch in search mode:

| Input | Tool |
|-------|------|
| `search` | `search-skill-knowledge` |
| `status` | `rag-status` |
| `reindex` | `rag-reindex` |
| `reindex --wiki` | `wiki-reindex` |
| `cleanup` | `rag-cleanup` |
| `purge` | `rag-purge` |

The `<scope>` parameter accepts `ai`, `dev`, `core`, `all`, or deeper paths. All
other queries use the reflective workflow above.

## Notes

- Every `/ask` answer should be reportable as a `command.run.v1` envelope: command `ask`, input class `question` or `search`, chosen route `reflect-context` or `structured-search`, duration, quality flags from the context assessment, warnings, and output summary.
- `/ask` should feel conversational, not like a logging UI.
- Follow-up turns continue the same reflective thread when the topic is clearly ongoing.
- Inferred patterns may be surfaced in the reply when useful, but should not require confirmation every time.
