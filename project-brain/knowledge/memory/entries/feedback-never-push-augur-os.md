---
title: feedback-never-push-augur-os
name: feedback-never-push-augur-os
description: Push target rule — ALWAYS push to the private `origin` (github.com/gsannikov/augur)
  by default after committing; NEVER push to `augur-os` (the public docs-only mirror,
  release-only via /dev release)
brain_scope: personal
type: feedback
status: active
source_client: claude-code
source_file: feedback_never_push_augur_os.md
source_hash: d10759caf44b2be9
_mentions:
- '[[feedback-cross-agent-enforcement]]'
- '[[feedback-no-mechanical-question-escalation]]'
- '[[project-main-checkout-branch-breaks-dashboard]]'
---



There are TWO remotes in this checkout:
- `origin` → `https://github.com/gsannikov/augur.git` — the user's **PRIVATE dev repo**, the **default push target**. `main` tracks `origin/main`. **The user ALWAYS wants dev work pushed here** after committing (commit + push are one motion for them — don't stop at commit, don't ask "want me to push?").
- `augur-os` → `https://github.com/augur-os/augur-os.git` — the **public, docs-only release mirror**, NOT a dev push target. Its `main` is `README/LICENSE/CHANGELOG/docs/…` only and shares **no common ancestor** with the dev line (unrelated histories). Publishing there is release-only.

**Why:** Two separate corrections from the user. (1) During the browse multi-select merge I let `/dev-merge` attempt `git push augur-os main` and reasoned about rebasing dev code onto it — the user was emphatic nothing reaches augur-os except a deliberate release. (2) After the cc-switch/Onyx notes I committed and then *declined to push* ("not pushed, you didn't ask"), and the user corrected: "I always want to push, but to my private repo not the augur-os one." My earlier read that the private remote wasn't configured was simply WRONG — `origin` is and always was the private repo.

**How to apply:**
- After committing dev work, **push to `origin` by default** (`git push origin main`) without being asked — that's the settled default, not a question to escalate. Don't end closeouts with "not pushed, you didn't ask."
- Never `git push augur-os …`, never rebase/merge dev work onto `augur-os/main`, never treat it as the merge target.
- Publishing to augur-os is exclusively `/dev release`, which builds an isolated public tree in a temp repo and pushes that; it does not push from the working checkout.
- A committed pre-push hook (`.githooks/pre-push`, `core.hooksPath=.githooks`) hard-blocks any push to augur-os unless `AUGUR_RELEASE_PUSH=1` — cross-agent enforcement per [[feedback-cross-agent-enforcement]]. So a default `git push origin main` is always safe; the hook is the backstop against the wrong target.
- Augur commits to `main` directly (no feature branch) per [[project-main-checkout-branch-breaks-dashboard]]; this checkout may be shared by multiple live AI sessions (codex/claude/cowork) — avoid disruptive branch switches, but a fast-forward push of `main` to `origin` is the normal flow.
- Don't re-surface the augur-os prohibition as a caveat unless about to do something that genuinely risks it — see [[feedback-no-mechanical-question-escalation]]. The thing to actually DO is push to origin, quietly.
