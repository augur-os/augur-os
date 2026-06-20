# Track 4 — Visibility Filter Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Worktree required:** Before starting, use `superpowers:using-git-worktrees` to create a worktree off `main` with branch name `track4-visibility-filter-removal`.

> **Prerequisites:** Track 3a must be merged before this plan runs. The visibility filter lives in `client_surface.py` which Track 3a relocates from `src/mcp/augur_mcp/` to `src/mcp/augur_shared/`. Running before Track 3a creates merge conflicts.

**Goal:** Delete `CURATED_VISIBLE_TOOLS`, `COWORK_VISIBLE_TOOLS`, `filter_tools_for_client`, and `x-augur-visibility` field reads. The filter was a 200-tool monolith bandage that's no longer needed after Tracks 1-3a bounded per-server tool counts to ~114.

**Architecture:** Single PR. Delete dead code. No manifest changes, no client config updates, no cross-repo coordination.

**Tech Stack:** Python 3.11+, pytest, uv. No new dependencies.

**Related specs:**
- Layer 1: `docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md`
- Layer 4 migration: `docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md`
- Track 4 design: `docs/superpowers/specs/2026-04-29-track4-visibility-filter-removal-design.md`
- Track 3a (prerequisite): `docs/superpowers/plans/2026-04-29-track3a-framework-split.md`

## Critical execution rules

- **Never** use `--no-verify` on `git commit`.
- **Worktree pollution check** before commit.
- **No client-config writes** — `~/.claude/`, `~/.codex/`, `~/.gemini/` are not touched in any track.
- **Track 2 invariant**: vault servers continue working; this PR doesn't touch the bundle launcher.
- **Verification across all 3 clients** required (per Track 4 design spec). After deletion, fresh sessions in Claude Code / Codex / Gemini must show full per-server tool surfaces.

---

## Task 1: PR 1 — Delete the visibility filter

**Files (Modify):**
- `src/mcp/augur_shared/client_surface.py` (assuming Track 3a's PR 1 moved it; if not yet moved, edit `src/mcp/augur_mcp/client_surface.py`)
- Any caller of `filter_tools_for_client`, `CURATED_VISIBLE_TOOLS`, `COWORK_VISIBLE_TOOLS`
- Any test that asserted filter behavior

### Step 1.1: Verify branch + Track 3a prerequisite

```bash
cd ~/Projects/Augur/.worktrees/track4-visibility-filter-removal && \
  git branch --show-current && \
  git log --oneline | head -5
```
Expected: `track4-visibility-filter-removal`. Recent commits should include Track 3a's PR 7 (`augur_mcp/` namespace dismantled). STOP if Track 3a doesn't appear merged.

```bash
cd ~/Projects/Augur/.worktrees/track4-visibility-filter-removal && \
  ls src/mcp/augur_shared/client_surface.py
```
Expected: file exists at this path (Track 3a moved it here).

### Step 1.2: Read current state

```bash
cd ~/Projects/Augur/.worktrees/track4-visibility-filter-removal && \
  cat src/mcp/augur_shared/client_surface.py | head -100
```

Identify:
- `CURATED_VISIBLE_TOOLS` frozenset literal
- `COWORK_VISIBLE_TOOLS` frozenset literal
- `filter_tools_for_client(client_id, tools)` function — note its full signature, body, and any non-visibility logic

### Step 1.3: Audit grep for callers (BEFORE deleting)

```bash
cd ~/Projects/Augur/.worktrees/track4-visibility-filter-removal && \
  grep -rn "CURATED_VISIBLE_TOOLS\|COWORK_VISIBLE_TOOLS\|filter_tools_for_client" \
    --include="*.py" --include="*.ts" --include="*.tsx" \
    src/ apps/ tests/ scripts/ 2>&1 | grep -v "__pycache__\|node_modules\|/.worktrees/" | head -30
```

Document each caller. They fall into 3 categories:
- **Tool-list dispatchers** — call `filter_tools_for_client(client_id, tools)` to scope what's exposed. Update to return tools unchanged after the filter is gone.
- **Tests** — assert filter behavior. Delete the assertions or the entire test if it's purely about filter behavior.
- **Type-import-only** — import the symbols but don't call them. Remove the import line.

### Step 1.4: Inspect `filter_tools_for_client` for non-visibility branches

If the function has logic beyond `tools - CURATED_VISIBLE_TOOLS`, that other logic might survive. Read carefully:

```python
def filter_tools_for_client(client_id: str, tools: list) -> list:
    # Visibility branch:
    if client_id == "claude":
        return tools - CURATED_VISIBLE_TOOLS
    elif client_id == "cowork":
        return tools - COWORK_VISIBLE_TOOLS
    
    # OTHER LOGIC HERE? — keep this if it exists.
    
    return tools
```

If non-visibility logic exists, the function survives in reduced form (visibility branch removed). If purely visibility, delete the function entirely.

### Step 1.5: Delete the filter

Edit `src/mcp/augur_shared/client_surface.py`:

1. Delete `CURATED_VISIBLE_TOOLS = frozenset({...})`
2. Delete `COWORK_VISIBLE_TOOLS = frozenset({...})`
3. Either:
   - **Delete `filter_tools_for_client` entirely** (if purely visibility), OR
   - **Simplify to non-visibility logic** (if other branches exist)

Remove related comments / docstrings that reference the filter.

### Step 1.6: Update callers

For each caller from Step 1.3:

- **Tool-list dispatchers**: Replace `filter_tools_for_client(client_id, tools)` calls with `tools` directly. If `client_id` was passed only to this function, audit whether the calling function still needs the parameter.
- **Tests**: Delete tests that asserted filter behavior. Keep tests that exercised non-visibility branches if those branches survived in Step 1.5.
- **Type-import-only**: Remove the import statement.

### Step 1.7: Audit `x-augur-visibility` field reads

```bash
cd ~/Projects/Augur/.worktrees/track4-visibility-filter-removal && \
  grep -rn "x-augur-visibility\|x_augur_visibility" \
    --include="*.py" --include="*.ts" --include="*.tsx" \
    src/ apps/ tests/ scripts/ 2>&1 | grep -v "__pycache__\|node_modules\|/.worktrees/" | head -30
```

For each match in `.py` / `.ts` / `.tsx`:
- If it's a code path that READS the field — delete the read (the field is irrelevant after the filter is gone).
- If it's a docstring or comment — leave it (historical).

For `.md` and `.yaml` docs that describe the legacy behavior — leave alone (history).

### Step 1.8: Run test cascade

```bash
cd ~/Projects/Augur/.worktrees/track4-visibility-filter-removal && \
  uv run pytest tests/ skills/ 2>&1 | tail -10
```
Expected: pass (modulo any Track 3a-introduced pre-existing failures).

If tests that asserted filter behavior fail, delete them per Step 1.6's "Tests" instruction.

### Step 1.9: Build the dashboard

```bash
cd ~/Projects/Augur/.worktrees/track4-visibility-filter-removal && \
  pnpm --filter dashboard build 2>&1 | tail -10
```
Expected: build succeeds.

If dashboard regenerated artifacts, restore with `git checkout HEAD --`.

### Step 1.10: Manual verification across 3 clients

This step is OPTIONAL during agent execution and documented in the commit body for the user to do post-merge:

1. Reload Claude Code session: `tools/list` against `augur-core` returns 29 tools; `tools/list` against `augur-framework` returns ~114 tools.
2. Reload Codex session: same.
3. Reload Gemini session: same.
4. Verify previously-hidden tools are now visible (e.g., from `augur-apple`, `augur-obsidian`, `augur-framework`).
5. Verify the 91%-hidden problem cannot recur — there's no filter mechanism left.

The agent doesn't run this step. Document it in the commit body.

### Step 1.11: Worktree pollution check + commit

```bash
cd ~/Projects/Augur/.worktrees/track4-visibility-filter-removal && \
  git status --short | head -20
```

Expected:
- `M src/mcp/augur_shared/client_surface.py` (filter deletion)
- Possibly `M` or `D` on caller files (per Step 1.6)
- Possibly `M` or `D` on test files (per Step 1.6)
- Possibly `M` on files that read `x-augur-visibility` (per Step 1.7)

```bash
cd ~/Projects/Augur/.worktrees/track4-visibility-filter-removal && \
  git add -A && \
  git commit -m "$(cat <<'EOF'
refactor(track4): delete visibility filter — migration complete

Track 4 (final track of the cross-client bundle architecture migration).
Deletes CURATED_VISIBLE_TOOLS, COWORK_VISIBLE_TOOLS, filter_tools_for_client,
and x-augur-visibility field reads.

The filter existed because the augur monolith registered ~200 tools
and exposing all to every client overwhelmed AI tool selectors — the
filter restricted to ~9% per client. After Tracks 1-3a:

- Track 1: 5 framework libraries extracted to src/lib/
- Track 2: 5 vault bundles split into per-bundle MCP servers (7-42 tools each)
- Track 3a: project monolith split into augur-core (29) + augur-framework (~114),
  23 dormant tools retired

No server registers more than ~114 tools. The filter is dead code.

Per Track 4 design spec at
docs/superpowers/specs/2026-04-29-track4-visibility-filter-removal-design.md:
- Verify across 3 clients: fresh sessions show full per-server tool
  surfaces (no hidden tools).
- The 91%-hidden problem cannot recur because the mechanism is gone.

POST-MERGE STEPS REQUIRED BY USER:
  1. cd ~/Projects/Augur && git pull
  2. Reload Claude Code, Codex, Gemini sessions
  3. Verify tools/list shows full per-server tool surfaces (e.g.,
     apple-* from augur-apple, ingest-* from augur-ingest)

Migration complete. Standard MCP + standard SKILL.md, no proprietary
fields, per-bundle server topology, no monolith, no hidden-by-default
tools.

ADR track4-visibility-filter-removal.md to be written separately.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Step 1.12: Push branch

```bash
cd ~/Projects/Augur/.worktrees/track4-visibility-filter-removal && \
  git push origin track4-visibility-filter-removal 2>&1 | tail -3
```

---

## Done criteria

1. ✅ `CURATED_VISIBLE_TOOLS` and `COWORK_VISIBLE_TOOLS` deleted from `client_surface.py`
2. ✅ `filter_tools_for_client` deleted (or simplified to non-visibility logic)
3. ✅ `x-augur-visibility` field is no longer read in any `.py` / `.ts` / `.tsx` code
4. ✅ All tests pass; dashboard builds clean
5. ✅ Branch pushed to `origin/track4-visibility-filter-removal`
6. ⏳ POST-USER: fresh sessions in Claude Code / Codex / Gemini show full per-server tool surfaces (manual verification)
7. ⏳ POST-USER: ADR `track4-visibility-filter-removal.md` written to `~/Documents/Augur/adrs/`

## Migration complete

After Track 4 ships and the user verifies across 3 clients, the cross-client bundle architecture migration is complete:

- ✅ Phase 0: layering cleanup
- ✅ Track 1: 5 framework libraries to `src/lib/`
- ✅ Track 2: 5 vault bundles to per-bundle MCP servers
- ✅ Track 3a: project monolith split + 23-tool cleanup + 11 hardcode fixes + allowlist empty
- ✅ Track 3b: dashboard hub-routing redesigned
- ✅ Track 4: visibility filter deleted

The architecture matches Layer 1's target: standard MCP + standard SKILL.md + no proprietary fields + per-bundle server topology + no monolith + no hidden-by-default tools.
