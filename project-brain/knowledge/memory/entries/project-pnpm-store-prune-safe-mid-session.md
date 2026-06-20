---
title: project-pnpm-store-prune-safe-mid-session
name: project-pnpm-store-prune-safe-mid-session
description: '`pnpm store prune` is safe to run mid-session because APFS clones survive
  store deletion — block references persist independently of the source file. Reclaim
  can be 1-3 GB on a long-lived dev machine'
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_pnpm_store_prune_safe_mid_session.md
source_hash: f3605d3a5eaf8dcf
---


`pnpm store prune` removes unreferenced package versions from the global pnpm store (`~/Library/pnpm/store/` on macOS). It is **safe to run while a dev server is up, while installed worktrees are in use, and while pnpm is not actively installing** — APFS `clonefile()` clones in `node_modules` have their own inodes and block references that persist when the source store file is deleted. The bytes don't vanish; the block ref-count just decrements by one.

**Why:** measured this during ADR-759 (2026-05-16). Store went from 2967 MB → 0 MB (removed 47080 files / 1174 packages), volume free went from 22286 MB → 24747 MB → **2461 MB reclaimed**, and every existing worktree continued to work normally. The Next.js dev server on port 3000 kept returning HTTP 200; `node -e "require('next/package.json')"` succeeded; all 50 toolchain tests passed. APFS preserved every clone.

**How to apply:**
1. On a long-lived dev machine where the pnpm store has accumulated multiple package versions, **`pnpm store prune` typically reclaims 1-3 GB**. Cheaper than deleting worktrees.
2. Safe alongside running dev servers and active worktrees — does not break clones.
3. Trade-off: the **next** `pnpm install` (in any worktree) will need to re-download missing packages from the registry to rebuild the store. Typical cost: 10-30s for a fresh dashboard install.
4. The Augur `/dev-clean` command does **not** include `pnpm store prune` today — adding it would be a natural Tier 1 (or guarded Tier 2) extension. See follow-up ADR if drafted.
5. Don't conflate with `rm -rf node_modules`: that touches a single worktree's tree and reclaims only its unique bytes (typically ~16 MB on APFS because of clonefile sharing). Store prune is the bigger win.

Related: [[project-pnpm-apfs-clonefile-behavior]] explains *why* APFS clones survive — `clonefile()` creates an independent inode with its own block-reference list, not a hardlink to the source.
