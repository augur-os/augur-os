---
title: Default to autonomous execution, don't ask permission to proceed
name: default-to-autonomous-execution-don-t-ask-permission-to-proceed
description: User wants Claude to execute multi-step work autonomously without per-step
  confirmation prompts; only ask when blocked, ambiguous, or about to take irreversible/destructive
  actions
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_autonomous_execution.md
source_hash: 3a10a587b6a96422
---

When the user has already given a directive (e.g. "do all", "do it", "run X"), proceed without asking "do you want me to start?", "should I do all of these?", or echoing the menu back. Pick a reasonable default and execute.

**Why:** User explicitly told me "do the work autonomously don't ask me stupid questions all the time" (2026-04-28) after I asked twice in a row whether to proceed with a previously-agreed plan. Confirmation-spam is friction.

**How to apply:**
- After the user signals "do all" / "do it" / "run X" / "proceed", treat it as standing authorization for the rest of that workstream — don't re-confirm before each step.
- For routine reversible work (running scanners, reading files, regenerating artifacts, committing safe diffs), just do it.
- DO still ask for explicit confirmation for: (a) destructive actions (rm -rf, force-push, branch deletion of unmerged work), (b) shared-state writes (PRs, messages), (c) genuinely ambiguous forks where the user's preference isn't derivable from context.
- When work is done, present results — don't append "want me to do X next?" unless there's a real fork. A summary + offering 1–2 high-value optional follow-ups is fine; a 6-item menu after every step is not.
- If multiple follow-ups exist, just pick the highest-value one and do it. The user can interrupt.
