---
title: gitignore-blind-spot-pollution
name: gitignore-blind-spot-pollution
description: Augur repo .gitignore blanket-hides binaries (*.png/*.pdf/*.wav) so junk
  accumulates invisibly; auto-repo-pollution loop scans the working tree directly;
  screenshots belong in get_logs_dir()/browser-verification
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: gitignore-blind-spot-pollution.md
source_hash: 0bf310c6bc8474bb
---


The Augur repo .gitignore carries blanket binary patterns (`*.png`, `*.pdf`, `*.wav`), so any session artifact dropped in the tree never shows in git status — git-based hygiene is structurally blind to it. Root pollution reached 70 entries (proof screenshots in 6 ad-hoc locations, tmp media, deck outputs) before the 2026-06-10 deep clean.

**Why:** "git status clean" ≠ "tree clean" in this repo; verification screenshots saved into the repo are the main pollution source.

**How to apply:**
- Save browser-proof/verification screenshots to `get_logs_dir()/browser-verification/` (`~/Library/Logs/Augur/browser-verification/`), NEVER in the repo tree (documented in DEBUGGING.md).
- The `auto-repo-pollution` loop (routine-platform, nightly self-heal) scans the working tree for OS junk, orphan pycache, gitignored binaries, session artifacts, empty dirs — it deletes session artifacts it finds, so don't park anything binary in the tree.
- Work products go to the Documents store (Au-docs): resumes → `career/tailored/`, deck outputs → `venture-augur/deck/`.
- Vault `drafts/staging/` is contract-protected release inventory (its README forbids generic scanners) — not pollution; see [[feedback-never-ignore-bugs]] for the fix-at-root standard.
