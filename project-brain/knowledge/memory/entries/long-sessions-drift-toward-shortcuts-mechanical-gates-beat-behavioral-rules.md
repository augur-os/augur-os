---
title: long sessions drift toward shortcuts; mechanical gates beat behavioral rules
name: long-sessions-drift-toward-shortcuts-mechanical-gates-beat-behavioral-rules
description: Quality degrades over long context windows because attention spreads
  thin; behavioral rules in CLAUDE.md compete for attention while mechanical hooks
  don't
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_long_session_drift.md
source_hash: 6d0454ee2ad4ff13
---

Direct user observation late in a long session: "why is there such degradation in performance lately?" and the related "I had agent instructions to use relevant slash command for dashboard ops and not doing it manually."

**Why:** Three causes the user reasonably named:
1. Shortcuts that violate explicit rules — using SSR/curl smoke instead of Chrome despite CLAUDE.md saying otherwise.
2. Long-session drift — as conversation context fills with tool output, scanner reports, agent transcripts, attention spreads thin and "good enough" reports pass quality gates that would have caught them earlier.
3. Instruction-layer growth — every miss adds a rule (28, 29, …); 29+ rules competing for attention favors whichever was reinforced most recently.

**How to apply:**
- For any rule the user wants enforced, prefer mechanical hooks (`.githooks/`, `.pre-commit-config.yaml`, `.claude/settings.json` PreToolUse) over adding another behavioral rule.
- When responding to a quality-degradation complaint, do not be defensive — name the specific shortcuts taken in the conversation and which rule each violated.
- For long sessions, treat the drift cost as real: dispatch sub-agents for heavy work to keep the parent session's context bounded; consume system reminders as signals to check task list, not as noise to ignore.
