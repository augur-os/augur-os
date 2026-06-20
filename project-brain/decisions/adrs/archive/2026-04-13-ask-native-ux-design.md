# `/ask` Native Conversational UX Design

**Date:** 2026-04-13  
**Status:** Proposed  
**Scope:** `/ask` visible UX, silent retention defaults, follow-up continuity, and MCP contract adjustments

## Goal

Make `/ask` feel like talking to a second brain in one conversational pass, instead of using a reflective workflow with visible post-processing.

The system should still retain durable knowledge and compound over time, but the default user experience should feel like a natural conversation rather than a logging surface.

## Problem

The current `/ask` architecture is directionally correct, but its contract still exposes too much workflow language.

Today the system already has the right building blocks:

1. `reflect-context` assembles personal context for reflective answers
2. `ask-retain` classifies and persists durable outcomes after the answer
3. session-end compounding later promotes retained outcomes into the wiki

The problem is the visible UX contract:

1. `/ask` guidance still tells the agent to append a `retained:` footer after successful persistence
2. continuity across turns is supported in `reflect-context`, but not strongly required by the `/ask` contract
3. visible retention signals make the interaction feel like an instrumented workflow rather than an inner-voice conversation

The result is a command that is structurally reflective, but not yet fully native-feeling.

## Desired User Experience

The default `/ask` experience should behave like this:

1. The user asks a reflective question once
2. `/ask` answers immediately in reflective voice
3. Retention happens silently in the background unless the user explicitly disables it
4. Follow-up turns feel like continuation of the same thought, not a fresh query each time
5. The user never sees tool names, routing language, or save mechanics unless something fails or they explicitly ask

Example:

```text
/ask Why do I keep choosing infrastructure-heavy projects?
```

Expected experience:

- one reflective answer
- no visible footer by default
- no “should I save this?”
- no “do you want to retain this?”
- follow-up `/ask` turns continue naturally from prior context

## Design Principles

1. Keep `/ask` as the public command name
2. Preserve automatic compounding behind the scenes
3. Make the default experience conversational, not inspectable
4. Require follow-up continuity as part of the contract, not as optional agent behavior
5. Keep explicit visibility available when needed, but not on by default

## Recommended Model

`/ask` should use a two-layer contract:

### Layer 1: Visible conversational behavior

This is what the user experiences.

- Answer first
- Answer once
- Answer reflectively
- Avoid clarifying questions unless the prompt is too empty to answer
- Do not append retention metadata by default

### Layer 2: Invisible compounding behavior

This happens after the answer and should remain mostly invisible.

- classify durable outcomes
- retain them through `ask-retain`
- mark wiki compounding as needed
- allow session-end `/ask sync` and wiki updates later

This preserves the current architecture while removing workflow leakage from the user-facing surface.

## Changes Required

### 1. Redefine the `/ask` command contract

The `/ask` command spec should be updated so that:

- retention remains default behavior
- visible retention footers are no longer default behavior
- follow-up turns should pass `conversation_summary` into `reflect-context`
- the response should be framed as one reflective answer, not “answer + bookkeeping”

New default rule:

- if retention succeeds, do not mention it unless explicitly requested

Exceptions:

- if the user uses a future explicit debug or verbose mode
- if retention fails and that failure materially changes trust in the system

### 2. Extend `ask-retain` with a visibility control

`ask-retain` should support this UX flag:

- `surface_footer: bool = False`

Behavior:

- when `False`, retention footer is omitted even if retention succeeds
- when `True`, the existing footer behavior remains available

This avoids forcing UI policy into the command prompt alone and makes silent retention an explicit part of the MCP contract.

### 3. Make continuity part of the `/ask` contract

`reflect-context` already supports `conversation_summary`.

The `/ask` contract should now explicitly require:

- pass prior-turn summary when a reflective conversation is continuing
- bias toward continuity in interpretation and tone
- avoid resetting to a contextless answer unless the user clearly changes topic

This is the key change that makes `/ask` feel like “talking with your brain” rather than repeatedly querying a tool.

### 4. Keep the same compounding model

No changes are needed to the long-term layering model:

- atomic durable items can still go into memory
- richer reflective outputs can still go into synthesis
- wiki updates still happen later through compounding

This work is a UX-contract upgrade, not a storage-architecture rewrite.

## Non-Goals

This design does not introduce:

1. a new dedicated `/ask` memory layer
2. same-turn wiki writes
3. a separate public command for “native ask”
4. mandatory user confirmation before retaining reflective outcomes
5. a multi-message reflective interview flow

## Files To Change

### Primary

- `skills/augur-core/commands/ask.md`
  - redefine default UX as answer-first, silent-retain, continuity-aware
- `src/mcp/augur_mcp/core/ask_retention.py`
  - add footer visibility control and keep silent retention as the default path
- `src/mcp/augur_mcp/core/__init__.py`
  - register the MCP parameter for the `ask-retain` tool

### Tests

- `skills/augur-core/augur/tests/test_ask_retention.py`
  - remove assumption that visible `retained:` output is the default
  - add coverage for silent retention and optional footer surfacing

### Optional documentation alignment

- generated agent instruction surfaces if they directly mirror `/ask` contract text

## Behavioral Rules

### Default `/ask`

- answer reflectively
- retain automatically when appropriate
- do not show footer

### `/ask --retain`

- stronger bias toward keeping non-ephemeral outcomes
- still do not show footer by default

### `/ask --no-retain`

- answer only
- skip persistence entirely

### `/ask --private`

- answer only
- skip persistence
- do not feed session-end compounding

## Failure Handling

If reflective answering succeeds but retention fails:

- keep the main answer
- do not dump internal tool details into the reply
- only surface a minimal trust-preserving note if needed

Example acceptable fallback:

- “I answered from your current context, but I didn’t retain this turn.”

This should be rare and should not become the common visible path.

## Test Strategy

### Unit tests

1. `build_retention_footer()` still works when explicitly requested
2. `retain_ask_outcome_impl(..., surface_footer=False)` returns no footer
3. `retain_ask_outcome_impl(..., surface_footer=True)` returns the current footer string
4. `--private` and `--no-retain` still skip persistence

### Contract tests

1. `/ask` command text describes silent retention as the default
2. `/ask` command text explicitly requires continuity for follow-up turns
3. `/ask` command text no longer frames visible `retained:` footers as default behavior

## Risks

### Risk: lost trust because retention becomes invisible

Mitigation:

- keep optional footer support in the MCP contract
- keep `--private` and `--no-retain`
- surface failures when they materially affect trust

### Risk: continuity becomes too sticky across topic changes

Mitigation:

- require continuity only when the follow-up is clearly part of the same reflective thread
- allow topic resets to omit prior summary

### Risk: prompt-only drift

Mitigation:

- encode silent-footer behavior in the MCP tool contract, not only in docs
- add tests that defend the new default

## Recommendation

Adopt silent retention as the default `/ask` behavior and treat visible retention as an optional diagnostic surface, not the public UX.

This is the smallest change that makes `/ask` feel like a native second-brain conversation while preserving the compounding architecture already built behind it.
