---
title: only ask deep design questions, no technical detail questions; long-term refactor,
  no shortcuts
name: only-ask-deep-design-questions-no-technical-detail-questions-long-term-refactor-no-shortcuts
description: User wants Claude to handle technical/implementation decisions autonomously
  and only escalate deep architectural questions. User is committed to long-term/proper
  refactors and explicitly does not want shortcuts or minimal-scope cop-outs.
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_design_only_no_shortcuts.md
source_hash: 36f2972b32d852b2
---

User explicitly wants:

1. **Only deep architectural questions, no technical detail questions.** Don't ask about CLI namespaces, file paths, manifest locations, or other implementation details. Make those decisions autonomously as a senior engineer would. Save questions for genuine architectural forks (e.g., "should we use rename-via-overlap or atomic moves?", "should bundles get per-bundle servers or shared servers?").

2. **Long-term refactors, no shortcuts.** When designing or scoping work, build the right thing, not the cheap thing. Don't propose "narrow scope" or "MVP-first" alternatives unless the broader scope would genuinely span multiple cycles. Don't take expedient shortcuts that create future debt.

**Why:** User said this directly after approving the Track 2 design spec on 2026-04-29: "approved dont ask me technical questions only deep design also assumption I want to do now long term refactor so dont look for shortcuts".

**How to apply:**
- During brainstorming: ask only architectural questions; decide implementation details myself
- During planning: don't propose scope-reduction alternatives; design for the full refactor
- During execution: pick the canonical solution, not the workaround
- When in doubt about a technical detail: pick a sensible default and proceed; surface only if I genuinely can't decide between two architecturally-distinct paths
