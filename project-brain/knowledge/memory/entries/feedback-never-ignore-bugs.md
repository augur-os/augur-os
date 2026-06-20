---
title: feedback-never-ignore-bugs
name: feedback-never-ignore-bugs
description: Gur's standing directive — never leave discovered bugs unfixed or merely
  flagged; fix them at the root in the same session
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback-never-ignore-bugs.md
source_hash: d21ceb85d155f498
_mentions:
- '[[sdlc-autonomy-aug-dev-build]]'
---



When work surfaces a bug — even adjacent debt found during verification — fix it, don't just report it. Gur explicitly corrected a session that flagged a broken script as "future debt" with "fix never ignore bugs", then followed with "fix all issues" for loop findings.

**Why:** Augur's rules 8/9/21/34 already lean this way (honest loops, fix blockers, autonomous bug fixing); Gur's bar is stricter: a mentioned-but-unfixed bug is an unfinished task.

**How to apply:** When a scan/verification surfaces findings, root-cause each one (scanner bug vs. real debt — e.g. loops flagging dirs that [[sdlc-autonomy-aug-dev-build]]-era brain-init itself scaffolds were scanner staleness). Fix code-level causes in code, register legitimate exceptions via designed mechanisms (.augur-reserved), apply the loop's own fix() for real debt, and re-scan to prove zero/honest-residual. Only age-based observations (e.g. "30 files >90 days") may remain, stated explicitly.
