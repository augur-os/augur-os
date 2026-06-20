# apps/dashboard/

**Purpose**: Next.js 14 web application for the Augur dashboard.

## CRITICAL: Skill Mounting

Files in `app/{hub}/` (like `app/control/`, `app/workspace/`) are **AUTO-GENERATED**.

```
app/control/tabs/LogsTab.tsx     ← WRONG to edit (will be overwritten)
project-brain/capabilities/skills/<skill>/augur/dashboard/tabs/LogsTab.tsx  ← CORRECT shared/team source file
```

**To edit hub UI**: Edit the shared/team source in `project-brain/capabilities/skills/{skill}/augur/dashboard/`, NOT here.

## Getting Started

```bash
cd apps/dashboard
npm ci
npm run dev
```

Open `http://localhost:3000`.

## Worktree Toolchain Sharing

`apps/dashboard/node_modules` is per-worktree (the preflight orchestrator keeps every
worktree fully isolated), but the *bytes* are shared at the filesystem layer via pnpm
hardlinks. The dashboard-local `.npmrc` sets `package-import-method=hardlink`, so
`pnpm install` commands run from this directory hardlink files from the
platform-default store rather than copying them. The preflight fallback path also
passes `--package-import-method hardlink` explicitly.

**Requirement:** the pnpm store and the projects directory must live on the same
filesystem volume. Hardlinks cannot cross volumes. Preflight checks this on every run;
if misaligned, it surfaces a high-severity `worktree/toolchain/pnpm-store-misaligned`
incident telling you to either move the projects directory or run
`pnpm config set store-dir <path-on-projects-volume>`.

**New worktree creation:** preflight chooses the cheapest path to ready `node_modules`:

- **CoW clone from main** on APFS / btrfs / ReFS — sub-second, ~0 new bytes (file blocks
  are shared with main at the filesystem layer until modified).
- **`pnpm install --frozen-lockfile --package-import-method hardlink`** on filesystems
  without CoW — still fast because hardlinks replace network downloads.

Either way the existing invariant holds: each worktree owns its own real `node_modules`
directory (no symlinks). Verify any time with `uv run python scripts/verify_worktree_toolchain.py`.

See `docs/superpowers/specs/2026-05-16-dashboard-worktree-toolchain-sharing-design.md`
and ADR-759 for the full design.

## Structure

- `app/` - Next.js App Router (some routes are auto-generated from skills)
- `components/` - Shared React components (safe to edit)
- `lib/` - Utilities, stores, helpers (safe to edit)
- `scripts/` - Build scripts including mount-plugins.ts
- `public/` - Static assets

## Rules

- Use design tokens (CSS variables), not hardcoded colors
- Follow GlassCard pattern for cards
- Run `npm run build` before commits to verify

## Dashboard Validation

**⚠️ REQUIRED: Run validation after any dashboard changes**

After creating or modifying dashboard components (API routes, service layers, or components), **always run validation**:

```bash
cd ~/Projects/augur
python3 .github/scripts/validate_dashboard.py <skill-name>
```

This validates:

- ✅ All API route imports match service file exports
- ✅ TypeScript types and interfaces are properly exported
- ✅ No missing function exports

**Fix any validation errors before committing changes.** This prevents build errors and ensures the dashboard works correctly.

### When to Validate

- After creating new API routes
- After modifying service layer functions
- After adding new dashboard components
- After refactoring dashboard code
- Before committing dashboard changes
