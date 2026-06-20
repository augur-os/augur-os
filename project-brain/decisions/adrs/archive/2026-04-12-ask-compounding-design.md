# `/ask` Compounding Design

**Date:** 2026-04-12  
**Status:** Proposed  
**Scope:** `/ask` command behavior, retention pipeline, session-end compounding, memory/synthesis/wiki layering

## Goal

Improve `/ask` so it does not just answer questions well in the moment, but also makes the second brain measurably stronger over time.

`/ask` should remain the public conversational surface because it matches the product framing: **ask your second brain**. The change is not the command name. The change is the compounding model behind it.

## Problem

Today `/ask` is reflective and context-aware, but weakly compounding.

Current behavior:

1. Read personal context via `reflect-context`
2. Respond in a reflective voice
3. Optionally offer:
   - `memory-log-decision`
   - `memory-log-preference`
   - `save-synthesis`

This has three limitations:

1. Retention depends too much on discretionary agent behavior
2. Durable insights from `/ask` are not consistently routed into the right long-term layer
3. The wiki does not benefit systematically from repeated reflective conversations

The result is a good conversation surface, but not yet a strongly compounding second-brain surface.

## Design Principles

1. Keep `/ask` as the public command name
2. Make compounding automatic by default, but conservative
3. Separate atomic memory, retained synthesis, and compiled wiki pages
4. Preserve a conversational UX rather than turning `/ask` into a logging UI
5. Treat contradictions as evidence to track, not something to overwrite immediately
6. Keep wiki pages rewritten and compiled in the LLM-wiki style, never chat-shaped

## Recommended Model

`/ask` becomes a four-stage pipeline:

1. **Conversation**
   - Answer the user using `reflect-context`
2. **Classification**
   - Decide whether the answer produced durable knowledge
3. **Retention**
   - Store high-signal outcomes into memory and/or synthesis
4. **Session-end compounding**
   - Review retained outcomes from the session and update the wiki when warranted

This keeps `/ask` lightweight at the point of use, while making durable understanding accumulate in structured layers.

## Storage Layers

The long-term model is intentionally layered:

### 1. Memory

Use memory for atomic facts that should remain easy to query, revise, and compare.

Examples:

- stable preferences
- explicit decisions
- short durable principles
- confirmed constraints

This layer should remain relatively granular.

### 2. Synthesis

Use synthesis for durable, richer interpretations that exceed atomic memory.

Examples:

- cross-domain patterns
- explanations of how the user tends to think
- multi-paragraph summaries of recurring tradeoffs
- inferred but meaningful self-understanding

This is the buffer between conversation and wiki.

### 3. Wiki

Use wiki pages as the compiled layer.

Wiki pages should only be updated after a later compounding pass decides that retained memory/synthesis is strong enough to change the canonical understanding. `/ask` should not write wiki pages directly during the primary answer path.

This preserves the LLM-wiki pattern:

- raw or retained material first
- compiled markdown wiki second

## Retention Behavior

Retention should be automatic by default, but with a high threshold.

### Default behavior

`/ask <question>`

- answer normally
- classify whether the turn produced durable knowledge
- retain high-signal outcomes automatically
- append a minimal retention footer when something was kept

### Optional flags

- `/ask --retain <question>`
  - stronger bias toward keeping high-signal outcomes
- `/ask --no-retain <question>`
  - answer only, do not persist
- `/ask --private <question>`
  - answer only, never persist and never feed session-end compounding

These flags are optional UX improvements; the design does not depend on them existing in the first implementation.

## Outcome Classification

After answering, `/ask` should classify the result into one or more durable outcome types:

- `decision`
- `preference`
- `insight`
- `inferred-pattern`
- `contradiction`
- `open-question`
- `ephemeral`

### Routing rules

- `decision` -> `memory-log-decision`
- `preference` -> `memory-log-preference`
- `insight` -> `save-synthesis`
- `inferred-pattern` -> `save-synthesis` with confidence metadata
- `contradiction` -> structured contradiction/tension record
- `open-question` -> unresolved insight bucket or deferred synthesis candidate
- `ephemeral` -> no persistence

## Explicit vs Inferred Knowledge

The system should retain both:

- **explicit knowledge** — directly stated by the user
- **inferred knowledge** — patterns inferred from repeated context or cross-domain signals

These should not be treated identically.

### Explicit knowledge

- higher default trust
- may update memory more directly
- still subject to contradiction tracking if it conflicts with prior retained material

### Inferred knowledge

- must include confidence
- must be easier to revise
- may be surfaced in the answer when materially useful
- should not require forced user confirmation on every turn

This keeps the second brain intelligent without creating too much interaction friction.

## Contradiction Handling

`/ask` should not use last-write-wins semantics for self-knowledge.

When a new retained claim conflicts with an older one:

1. do not immediately overwrite the old belief
2. create a contradiction/tension record
3. keep both interpretations available for future reasoning
4. increase the newer claim's priority only if it recurs or gains stronger evidence
5. allow future `/ask` answers to surface the tension explicitly when relevant

This makes the second brain adaptive instead of brittle.

## User Experience

The user should still feel like they are in a reflective conversation, not a logging workflow.

### Main reply

The reply remains the primary output:

- personal
- grounded
- concise when context is thin
- synthetic when context is rich

### Retention footer

If something durable was retained, append a small explicit footer, for example:

- `retained: preference`
- `retained: synthesis + inferred pattern`
- `retained: contradiction`

This should remain intentionally small. The goal is trust, not UI noise.

### Surfacing inferences

When an inferred pattern materially helps the user, it may be stated in the main answer. But the system should not stop every time to ask for confirmation. That would overfit the UX around bookkeeping and reduce compounding.

## Session-End Compounding

Automatic session-end compounding is the key mechanism that turns repeated `/ask` usage into a better second brain.

### Session-end flow

At the end of a session involving meaningful `/ask` activity:

1. review retained `/ask` outcomes from the session
2. merge atomic items into memory when they are strong enough
3. cluster richer syntheses by topic and stability
4. compare clustered syntheses against current wiki tags/pages
5. update wiki pages only where new evidence justifies a rewrite
6. record the session summary in the wiki log

### Wiki update behavior

When the compounding pass decides the wiki should change:

1. call `wiki-tags`
2. find matching existing pages
3. `wiki-read` where needed
4. rewrite via `wiki-write`
5. `wiki-log` the changes

This ensures the wiki remains compiled and editorial rather than reactive and chat-shaped.

## Why `/ask` Should Not Write Wiki Pages Directly

Direct same-turn wiki updates would be simpler, but wrong long term.

Failure modes:

- wiki becomes too reactive to transient thoughts
- pages drift toward conversation summaries
- contradictions overwrite each other too fast
- repeated small turns create noisy page churn

Deferring wiki updates to a compounding stage is what preserves the LLM-wiki concept.

## Command Family

Public identity should stay centered on `/ask`.

Recommended command family:

- `/ask` — ask your second brain
- `/ask --retain` — stronger bias toward retention
- `/ask --private` — reflective but non-persistent
- `/ask sync` — manually trigger compounding of recent retained `/ask` insights

Even if `sync` is not shipped immediately, the model should support it.

## Example Flow

User:

`/ask What pattern keeps showing up in how I choose projects?`

System:

1. gathers reflective context
2. answers normally
3. detects:
   - one inferred pattern
   - one durable insight
4. stores:
   - inferred pattern as synthesis with confidence
   - insight as synthesis
5. returns footer:
   - `retained: synthesis + inferred pattern`
6. session-end compounding later decides whether related wiki pages should be rewritten

## Implementation Outline

### Phase 1: `/ask` retention classification

- add post-answer classification step to `/ask`
- classify into decision/preference/insight/inferred-pattern/contradiction/open-question/ephemeral
- add retention footer

### Phase 2: structured retention routing

- route decisions/preferences to memory
- route insights/inferred patterns to synthesis
- store inferred confidence and contradiction metadata

### Phase 3: session-end ask compounding

- collect retained `/ask` outcomes for the session
- cluster by topic and stability
- push high-confidence changes into wiki maintenance flow

### Phase 4: manual compounding surface

- add `/ask sync`
- expose summary of what changed during compounding

## Open Questions

These do not block the design, but affect implementation detail:

1. Should contradiction records live in memory, synthesis metadata, or a dedicated store?
2. Should inferred confidence be numeric, categorical, or both?
3. Should `/ask --retain` force retention of any non-ephemeral result, or only lower the threshold?

## Decision

Adopt `/ask` as the stable public command name and upgrade it from a reflective Q&A surface into a structured compounding surface:

- automatic retention by default
- layered memory -> synthesis -> wiki flow
- explicit and inferred knowledge both supported
- contradiction-aware updates
- automatic session-end compounding
- minimal but visible retention UX
