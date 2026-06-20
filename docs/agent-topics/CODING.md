<!--
⚠️  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
Source: docs/agent-topics/CODING.md
Generator: project-brain/capabilities/skills/ai/scripts/sync_agents/__init__.py
-->
# Coding Standards

> **When to load**: Load this doc when writing code, making commits, or reviewing code style conventions.

## Code Style

### Python
- 4-space indent, `snake_case` functions/variables, `PascalCase` classes
- Type hints on public functions
- Docstrings: Google style for public APIs
- When refactoring a module into a package, re-export all public symbols from `__init__.py` to preserve the flat import API (`from package import symbol`) that existing callers and tests rely on
- Use lazy imports (inside function bodies) to break circular dependencies between sibling modules in a package

### TypeScript
- 2-space indent, `camelCase` variables, `PascalCase` components/types
- Prefer named exports over default exports
- Co-locate tests: `Component.tsx` -> `Component.test.tsx`

### Commits
- Conventional Commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- Optional scope: `feat(dashboard):`, `fix(paths):`

## Critical Rules

### No Hardcoded Paths

```python
# FORBIDDEN - will fail pre-commit audit
path = "/Users/username/Projects/augur"

# CORRECT
from src.config.paths import get_config_dir, get_project_root
```

### Test Failures: Fix Root Cause
- Debug and fix the underlying issue
- No skips, stubs, or temporary hacks to force green tests

### No Workarounds - System Solutions Only

**Philosophy**: Always understand and fix the system, never work around it.

#### When Tests Fail
```python
# FORBIDDEN - workarounds
@pytest.mark.skip("Flaky test")
def test_something(): ...

mock.return_value = "stub"  # Hiding real behavior

# CORRECT - root cause analysis
# 1. Reproduce the failure
# 2. Add logging to understand why
# 3. Fix the actual bug or test assumption
# 4. Verify fix addresses root cause
```

#### When Pre-Commit Hooks Fail
```bash
# FORBIDDEN - bypassing the system
git commit --no-verify
git push --force

# CORRECT - understand the system
# 1. Read the hook's error message
# 2. Understand what validation failed and why
# 3. Fix the underlying issue (file structure, format, etc.)
# 4. If hook rule is outdated, propose change to the hook itself
```

#### When Build/Lint Fails
```typescript
// FORBIDDEN - silencing errors
// @ts-ignore
// eslint-disable-next-line

// CORRECT - fix the type/lint issue
// 1. Understand what the error is telling you
// 2. Fix the actual code issue
// 3. If rule is wrong for this codebase, update eslint/tsconfig properly
```

**Golden Rule**: If you're adding a workaround, STOP. Debug deeper until you find the real fix.

### In-Code TODO_ Markers (Track Issues In Place)

**Philosophy**: Mark issues where you find them. CI scans nightly to surface all markers.

When you encounter issues during work, add `TODO_` markers directly in the code:

| Marker | When to Use |
|--------|-------------|
| `# TODO_BUG(category/severity):` | Found a bug with clear code location |
| `# TODO_OUTDATED:` | Docs/comments reference old behavior |
| `# TODO_WORKAROUND:` | Adding a temporary fix (must document why) |
| `# TODO_IMPROVE(category):` | Spotted an enhancement opportunity |
| `# TODO_MISPLACED:` | File/code is in the wrong location |
| `# TODO_CLEANUP:` | Dead code, unused imports, tech debt |
| `# TODO_SECURITY:` | Needs security audit |
| `# TODO_REFACTOR:` | Code structure needs improvement |
| `# TODO_IDEA:` | Future idea for plugin backlog |
| `# TODO_PERFORMANCE:` | Performance optimization needed |

**TODO_BUG Categories**: `security`, `performance`, `ux`, `data`, `integration`
**TODO_BUG Severities**: `critical`, `high`, `medium`, `low`
**TODO_IMPROVE Categories**: `performance`, `ux`, `maintainability`, `security`, `testing`

```python
# Example: Found a security issue while working on something else
# TODO_BUG(security/high): Path traversal not blocked
# FIX: Validate path is within allowed roots
result = read_file(user_input)

# Example: Noticed outdated documentation
# TODO_OUTDATED: This describes v1 API, we're on v3 now

# Example: Had to add a workaround
# TODO_WORKAROUND: Remove after Next.js 15 (fixes hydration bug)

# Example: Had an idea for future improvement
# TODO_IDEA: Add caching layer for frequently accessed data
```

**Workflow**:
1. Encounter issue while working -> Add `TODO_` marker in place
2. Nightly CI -> Scans all markers -> Generates report
3. During cleanup -> Fix issues -> Remove markers

**View markers**: `python3 .github/scripts/scan_code_markers.py`
**Full docs**: this section is the canonical bug-filing reference; broader system-improvement workflows live in the owning skill's `project-brain/capabilities/skills/{skill}/references/` docs when they are project/team workflows.

### Plugin Backlogs

Each plugin can have a `BACKLOG.md` file for tracking future ideas, improvements, and features.

**Location**: `project-brain/capabilities/skills/{skill}/BACKLOG.md`

**When to use**:
- Capture `TODO_IDEA` markers during nightly cleanup
- Record feature requests during user sessions
- Track long-term improvement plans

**Template**: `docs/templates/BACKLOG.md`

## Read Folder README Before Editing

**MANDATORY**: Before creating or editing files in any directory, read its `README.md` first.

Each folder has a README explaining:
- What belongs in that folder
- What does NOT belong there
- Folder-specific rules

**Key folder READMEs**:
- `src/README.md` - Framework code rules
- `project-brain/capabilities/skills/README.md` - Project/team skill rules
- `config/README.md` - Configuration files
- `docs/README.md` - Documentation rules
- `apps/dashboard/README.md` - Dashboard rules (plugin mounting!)

## Git Commit Protocol for Team Agents (MANDATORY)

**When working as a teammate (spawned via Task with team_name), you MUST commit after completing each task.**

Multiple agents share the same working directory. Uncommitted edits to tracked files are destroyed when any agent (or concurrent session) switches branches or merges. New files survive (untracked), but edits to existing files do not.

### Rules
1. **Commit after every task** -- not at the end of all tasks, after EACH one
2. **Stage only your files** -- `git add <specific files>`, never `git add -A` or `git add .`
3. **Conventional commit message** -- `feat|fix|refactor|chore(scope): description`
4. **Never amend** -- always create new commits
5. **Never push** -- only commit locally; the team lead handles push
6. **Never switch branches** -- stay on whatever branch you were started on
7. **If staging fails** (file changed by another agent) -- report conflict to team lead via SendMessage
8. **Verify build before commit** -- if you touched `.ts`/`.tsx`/`.js`/`.jsx` files, run `/dev-build` and confirm it passes before committing. A broken build blocks all customers.

### Template
```bash
git add path/to/file1 path/to/file2
git commit -m "feat(scope): what this task implemented

Co-Authored-By: Augur Agent <noreply@augur.local>"
```

### When This Applies
- You are a teammate spawned with `team_name` parameter
- You are working alongside other agents in the same repo
- You have write access (not in advisory/read-only mode)

### When This Does NOT Apply
- You are the only agent working (solo session)
- You are in advisory mode (read-only, no file edits)
- The team lead explicitly says "do not commit"
- **Nightly daemon auto-sync** — `auto-repo-sync` at difficulty 3+ may commit and push both the main repo and vault repo during nightly runs. This is intentional: the daemon runs solo and vault auto-commits must be pushed to prevent unbounded local divergence.
