---
title: project-worktree-claude-plugin-registration
name: project-worktree-claude-plugin-registration
description: Fresh Augur worktrees show "plugin enabled in project settings but isn't
  installed here" for Claude plugins; worktree_preflight now auto-registers them.
  Only Claude is path-scoped.
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_worktree_claude_plugin_registration.md
source_hash: 3f78a1cdb21eb640
---


Fresh git worktrees throw Claude Code `/plugin` errors like *"superpowers enabled in project settings but isn't installed here"* because the committed `.claude/settings.json` `enabledPlugins` propagates to every worktree, but Claude's install registry (`~/.claude/plugins/installed_plugins.json`, honoring `CLAUDE_CONFIG_DIR`) keys project-scoped installs by exact `projectPath` — a new worktree path has no record. The plugin cache is shared, so the "install" is just a per-path registration.

**Fix (added 2026-05-23):** `scripts/worktree_preflight.py::_ensure_client_plugin_registrations` clones an existing install record under the new worktree's `projectPath` (atomic `os.replace`, append-only). It runs inside `build_contract`'s `is_non_main_instance` branch and fires on every worktree create because both launch paths call preflight with `--profile worktree --repair`:
- canonical cross-OS engine `src/scripts/agent_launch.py::bootstrap_worktree` (behind `ca`/`ga`/`xa` launchers, all clients, Win+POSIX)
- legacy `scripts/worktree-launch.sh::bootstrap_worktree`

**Only Claude is path-scoped.** Gemini keys activation by GLOB overrides in `~/.gemini/extensions/extension-enablement.json` (a `.../Projects/*` pattern spans all worktrees); Codex enables plugins globally via `[plugins."<id>"]` in `~/.codex/config.toml`. Both are intentional no-ops in the repair, documented in the function docstring. If either ever adds path-scoped installs, add its registrar there.

Tests: `tests/scripts/test_worktree_preflight_client_plugins.py`. A running Claude session reads the registry at startup, so registering mid-session won't clear the current session's error — it clears on next launch (or via `/plugin` → Errors → Enter to resolve). Related: [[project-worktree-dashboard-port-verification]], [[main-checkout-branch breaks dashboard startup]].

**2026-05-25 — root-cause for the recurring "superpowers keeps disappearing":** the preflight auto-registration only fires for worktrees it *creates*; the **main checkout `~/Projects/Augur` is never auto-registered**, so any project-scoped plugin vanishes whenever you work from main. The real fix is scope, not registration: every plugin the user relies on (`augur`, `codex`, `claude-md-management`, …) is installed at **`--scope user`** (path-independent) — `superpowers` was the lone outlier at `--scope project`, keyed to a handful of throwaway worktree paths. Fix that recurs-proof: `claude plugin install superpowers@claude-plugins-official --scope user` (this also auto-flips the user `enabledPlugins` flag true; the user's was a stale `false` from the `claude-settings-incident-fix` worktree). Then prune dead-path project records from `installed_plugins.json` (back it up first). Do NOT edit the committed `.claude/settings.json` `enabledPlugins` to "fix" this — that file ships as shared/public defaults; per-machine disables belong in the untracked `settings.local.json` (which is why `episodic-memory` is correctly off locally despite the committed `true`, and its startup warning is cosmetic).
