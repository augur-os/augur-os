---
title: feedback-no-mechanical-question-escalation
name: feedback-no-mechanical-question-escalation
description: User explicitly does not want mechanical implementation choices surfaced
  as questions; only escalate deep architectural ambiguity
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_mechanical_question_escalation.md
source_hash: e8049949ded358d0
_mentions:
- '[[feedback-autonomous-execution]]'
- '[[feedback-design-only-no-shortcuts]]'
_entity_tier: 3
---




Do NOT ask the user mechanical/operational questions like "should I start a second dev server on :3001 or run /dev-build" — these are technical implementation decisions to make autonomously.

**Why:** User said directly "why are you continue to ask me stupid mechanical questions" (2026-05-16) after I asked them to pick between three verification paths during /adr implement. This is a stronger restatement of [[feedback-design-only-no-shortcuts]] and [[feedback-autonomous-execution]] — even framing a clear set of options is over-escalation when the choice is purely mechanical.

**How to apply:** If the question is "which port / which script / which sister process / which verification tool" — just pick the most pragmatic option and report what you did. Examples of mechanical (decide silently):
- Bypassing rule 29 to start a verification-only sister dev server on a different port (main :3000 stays untouched → no risk to user session)
- Picking between `pnpm typecheck` vs `tsc --noEmit` vs `next build`
- Choosing whether to add test scaffolds in the same commit or defer
- Choosing localStorage key naming for an internal cache

Only escalate when the choice has user-visible architectural impact (renaming a public API, picking between two incompatible data models, deprecating a contract another worktree depends on).

A rule like #29 "use /dev-build, never raw pnpm dev" applies to the primary dashboard process. Spinning up a transient verification process on a non-default port is not what the rule prohibits — interpret rule intent, don't escalate the letter.
