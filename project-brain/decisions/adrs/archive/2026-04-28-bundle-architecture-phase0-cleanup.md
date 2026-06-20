# Bundle Architecture — Phase 0 Cleanup Implementation Plan (v3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **v3 changelog (2026-04-29 evening):** v2's `test_no_vault_skill_refs.py` was attempted; the narrowed src/-only test caught 10 violations across 7 files (apple + lifestyle baked into framework code). Same pattern as the dashboard discovery: vault-private skill names are framework-deep, not just dashboard. **Track 3a's scope expanded** in the migration spec to include removing these src/ hardcodes when augur-core's dynamic discovery comes online. Phase 0 v3 drops `test_no_vault_skill_refs.py` entirely — the architecture rule lands when Track 3a delivers it. Phase 0 still removes the apple dead-code line as a small code cleanup (no test required for a 1-line removal).

**Goal:** Land the prerequisite cleanup PR for the cross-client bundle architecture migration: remove the dead-code reference to a vault-private skill in `src/`, decouple `rag` from `ingest` Python imports, and add a CI architecture-test that prevents cross-skill import regressions during Tracks 1–4.

**Architecture:** Single PR. Changes touch three areas: (a) `src/config/mcp_tools.py` (delete one dead apple reference line), (b) `skills/rag/scripts/mcp/rag_tools.py` and `skills/ingest/scripts/mcp/wiki_tools.py` (move two wiki MCP tools from rag to ingest where their dependencies live), (c) `tests/architecture/` (new test directory with one static-analysis test for cross-skill imports). Documented by an ADR co-located in `Au-docs/adrs/`.

**Tech Stack:** Python 3.11+, pytest, AST-based static analysis. No new dependencies.

**Related specs:**
- `docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md` (Layer 1)
- `docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md` (Layer 4 — see Track 3a/3b for hardcoded-name removals)

## Why this is v3

- v1 included Tasks 8–10 to extract a `layer_routing.py` shared module from two dashboard generators. v1's Task 2 audit revealed 50+ vault-private skill name hardcodes across `apps/dashboard/` (URL routing, skill-import templates, workflow code, production UI). The 5-line generator hardcode was the surface; the structural assumption is dashboard-deep. Fixing it properly is **Track 3b** in the migration spec, not Phase 0. v1 was reverted at commit `6dadfdd9e` and replaced with v2.
- v2 narrowed the architecture-rule test to `src/` only. Execution showed v2's test still caught 10 violations across 7 src/ files — vault-private skill names are baked into MCP framework code (`mcp_management.py`, `domain/plugins.py` default param, `tools/hubs/scrape_and_save_idea.py` whole module, etc.). Same pattern as dashboard. **Track 3a's scope expanded** to cover those framework hardcodes alongside the augur-core/augur-framework split. v3 drops `test_no_vault_skill_refs.py` from Phase 0 entirely — the test belongs with the rewrite that makes it pass.

Phase 0 v3 ships only what is honestly Phase 0:
- One architecture-rule test for cross-skill imports (no exceptions, ships clean).
- The 1-line apple-dead-code removal (no test gating it; just code cleanup).
- The wiki MCP tool relocation rag → ingest.
- The ADR records the narrowed scope and the Track 3a/3b deferrals.

The original v1 file was checked in at commit `16652c909`; v3 supersedes it on the same path.

---

## File Structure

### New files

| File | Purpose |
|---|---|
| `tests/architecture/__init__.py` | Empty package marker (already created in v1 Task 1) |
| `tests/architecture/conftest.py` | Shared fixtures (already created in v1 Task 1) |
| `tests/architecture/test_no_cross_skill_imports.py` | Static AST check — no project skill imports another skill's Python modules |
| `Au-docs/adrs/ADR-NNN-bundle-architecture-phase0-cleanup.md` | Decision record for this phase |

### Files modified

| File | Change |
|---|---|
| `src/config/mcp_tools.py` | Delete `"has_voice": False,` from the context dict at line 373; delete the `context["has_voice"] = ...` line at 411 |
| `skills/rag/scripts/mcp/rag_tools.py` | Remove `from skills.ingest.scripts.wiki_status import build_wiki_status` at line 25; delete the `wiki-status`, `wiki-lint`, and `wiki-purge` MCP tool definitions (canonical versions already exist in ingest's `wiki_tools.py` with equal-or-better implementations); remove orphan top-of-file imports (`get_runtime_wiki_dir`, `get_rag_category_dir`) |
| `skills/ingest/scripts/mcp/wiki_tools.py` | No changes — `wiki-status`, `wiki-lint`, and `wiki-purge` are already canonically registered here. Discovered during Task 4 execution; plan amended via commits `e1999e499` (Task 5 expansion) and `bc506befa` (allowlist 7th entry). |
| `skills/rag/augur/tests/test_rag_tools.py` | Remove `test_wiki_status_uses_shared_operational_status_helper` (Task 4) — equivalent canonical test exists in ingest. Replace with pointer comment. |
| `skills/ingest/augur/tests/test_rag_tools.py` | Remove `test_registers_rag_side_wiki_purge_tool` (Task 5) — same pattern as Task 4. |

### Files deleted

None. Phase 0 v3 only adds, modifies, and relocates.

### What's NOT in this PR

- `tests/architecture/test_no_vault_skill_refs.py` — moved to Track 3a (src/ scope) and Track 3b (apps/dashboard/ scope). The test belongs with the refactor that makes it pass cleanly.
- The `layer_routing.py` shared module from v1 — moved to Track 3b.
- Dashboard generator updates (`dashboard_generator.py`, `comprehensive_dashboard_generator.py`) — moved to Track 3b.
- The full `_detect_project_context()` refactor and the 9 other src/ vault-private hardcodes (`mcp_management.py`, `config.py`, `plugins.py`, `capabilities.py`, `scrape_and_save_idea.py`, `browse/dev.py`) — deferred to Track 3a when `augur-core`'s dynamic discovery replaces them.
- Daemon's subprocess invocations of platform-admin scripts — these are runtime orchestration, not Python-import smells. No change needed.
- Ingest's filesystem-discovery references to `obsidian/SKILL.md` — discovery checks are not import smells. No change needed.

---

## Status of work-in-progress (resuming from worktree state)

This v3 plan resumes Phase 0 execution from the worktree branch `phase0-bundle-cleanup`. As of 2026-04-29 evening:

- **v1 Task 1** (test scaffolding) — already committed at `a76fb11b4`. **Skip.**
- **v1 Task 2** (over-broad test with dashboard scope) — committed and reverted at `6dadfdd9e`.
- **v2 Task 2** (narrowed src/-only test) — written in the worktree but never committed; deleted before this v3 plan landed.
- **All later tasks** — not started.

Task numbering below restarts at Task 2 (apple fix — the first task that v3 still includes).

---

## Task Sequencing

| # | Task | Commits |
|---|---|---|
| (done) | Test infrastructure scaffolding (`a76fb11b4`) | (skipped) |
| 2 | Fix the apple dead-code violation | 1 |
| 3 | Write `test_no_cross_skill_imports.py` (TDD: failing on rag→ingest) | 1 |
| 4 | Relocate `wiki-status` MCP tool rag → ingest | 1 |
| 5 | Relocate `wiki-lint` MCP tool rag → ingest | 1 |
| 6 | Verify `test_no_cross_skill_imports.py` passes | 0 (verification gate) |
| 7 | Write the ADR | 1 |
| 8 | Run full test suite; final verification | 0 (no commit unless something fails) |

Total v3 commits: **5** (plus 2 from before the v3 cut = 7 commits on the branch when merged).

---

## Task 2: Fix the apple dead-code violation

**Files:**
- Modify: `src/config/mcp_tools.py`

This is a small code cleanup. The `has_voice` flag is set from a hardcoded apple-skill check but read nowhere — verified dead code. No test gates this fix in Phase 0 v3; the architecture-rule test for vault-private skill names lands with Track 3a's broader rewrite.

- [ ] **Step 2.1: Verify `has_voice` is dead code**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && grep -rn 'has_voice' src/ apps/ skills/ 2>/dev/null | grep -v __pycache__
```

Expected: only the two lines in `src/config/mcp_tools.py` (set in dict at line 373, assigned at line 411). Read nowhere. If the grep returns reads, STOP and report — `has_voice` is not actually dead.

- [ ] **Step 2.2: Read the surrounding context**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && sed -n '365,413p' src/config/mcp_tools.py
```

Confirm:
- Line 373: `"has_voice": False,` inside the `context: dict[str, Any] = { ... }` literal
- Lines 410–411: comment + assignment that references `apple/SKILL.md`

- [ ] **Step 2.3: Delete both occurrences**

Edit `src/config/mcp_tools.py`:

1. In the dict initialization around line 373, remove this line:
```python
        "has_voice": False,
```

2. Remove these two lines around 410–411:
```python
    # Check for voice-oriented personal workflows
    context["has_voice"] = (skills_dir / "apple" / "SKILL.md").exists()
```

- [ ] **Step 2.4: Run existing src/config tests to confirm no regression**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && uv run pytest tests/config/ -v 2>&1 | tail -10
```

Expected: all pass. No test should depend on `has_voice` (verified in Step 2.1).

- [ ] **Step 2.5: Commit**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && git add src/config/mcp_tools.py && git commit -m "fix(config): remove dead apple SKILL.md reference in _detect_project_context

has_voice was set from a hardcoded apple-skill check but read nowhere.
Removed both the dict-init entry and the assignment line. apple is a
vault-private skill and must not be hardcoded in src/ code.

The wider hardcoded-skill-name smell in this function (career, recipes,
lifestyle, finance, frontend, validator, advisor, mcp-app-factory) and
across src/ MCP framework code (~10 known references in mcp_management.py,
config.py, domain/plugins.py default param, tools/hubs/scrape_and_save_idea.py,
etc.) is deferred to Track 3a, which replaces these with augur-core's
dynamic skill discovery."
```

---

## Task 3: Write `test_no_cross_skill_imports.py` — TDD failing test

**Files:**
- Create: `tests/architecture/test_no_cross_skill_imports.py`

This is the TDD red step for the cross-skill import rule. The test will fail because `rag_tools.py` imports from `skills.ingest`. Tasks 4 and 5 fix the violations. Commit the failing test as the TDD red marker.

- [ ] **Step 3.1: Write the test file**

Save to `tests/architecture/test_no_cross_skill_imports.py`:

```python
# tests/architecture/test_no_cross_skill_imports.py
"""Architecture rule: a skill must not import another skill's Python modules.

Skills may share runtime data, MCP tools, or filesystem-located resources, but they
must not couple at the Python-import level. Shared library code belongs in src/lib/
(a future location populated by Track 1 of the migration).

This rule applies to:
- skills/<skill_a>/**/*.py importing skills.<skill_b>.scripts.X
- src/ or apps/ importing skills.<vault_private>.scripts.X (those skills may be absent)

Allowed exceptions (initially empty; entries added with PR review when justified):
- None at Phase 0. Future exceptions go in ALLOWED_CROSS_SKILL_IMPORTS below.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

# Format: ("importer_skill", "imported_skill") tuples.
# These pairs are pre-existing debt. Each pair is retired by Track 1 of the bundle
# architecture migration: when an imported skill is extracted to src/lib/<x>/, all
# ("*", "<imported>") entries become library imports and the entries are removed.
# Track 1's verification: this set is empty after the migration completes.
ALLOWED_CROSS_SKILL_IMPORTS: frozenset[tuple[str, str]] = frozenset({
    # ingest → rag: ingest's inbox/wiki workflows consume rag's indexer.
    # Retired by Track 1 when rag becomes src/lib/index/.
    ("ingest", "rag"),
    # ingest → ai: ingest's command-contract tests reference ai modules.
    # Retired by Track 1 when ai becomes src/lib/ai/.
    ("ingest", "ai"),
    # knowledge → rag: knowledge's rag_search_cli imports rag's MCP tool.
    # Retired by Track 1 when rag's library code moves to src/lib/index/.
    ("knowledge", "rag"),
    # document-extractor → ai: ollama_client.py imports skills.ai.augur.lib.get_llm_client.
    # Retired by Track 1 when ai becomes src/lib/ai/.
    ("document-extractor", "ai"),
    # onboard → ai: cloud_status.py imports skills.ai.augur.lib.cloud_execution.
    # Retired by Track 1 when ai becomes src/lib/ai/.
    ("onboard", "ai"),
    # platform-admin → ai: run_prompt.py imports skills.ai.augur.lib.prompt_registry.
    # Retired by Track 1 when ai becomes src/lib/ai/.
    ("platform-admin", "ai"),
    # file-manager → ai: autoloop.py:42 imports skills.ai.augur.lib.get_llm_client.
    # Retired by Track 1 when ai becomes src/lib/ai/.
    ("file-manager", "ai"),
})


# Match any `from skills.<name>.<rest>` or `import skills.<name>.<rest>`.
# Covers both `scripts/`-rooted modules (e.g., skills.X.scripts.Y) and
# `augur/lib/`-rooted modules (e.g., skills.X.augur.lib.Y). Skill name
# pattern uses [a-zA-Z0-9_] because Python module paths cannot contain
# hyphens — hyphenated skills (e.g., document-extractor) are imported
# under their underscore form via importlib aliases. Self-imports are
# filtered out separately by the test.
SKILL_IMPORT_RE = re.compile(r"\bskills\.([a-zA-Z0-9_]+)\.")


def _imports_in_file(path: Path) -> list[tuple[int, str]]:
    """Return (line_number, imported_skill_name) for every `from skills.<X>.scripts.` import."""
    out: list[tuple[int, str]] = []
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return out
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        for n, line in enumerate(text.splitlines(), start=1):
            for m in SKILL_IMPORT_RE.finditer(line):
                if line.lstrip().startswith(("from ", "import ")):
                    out.append((n, m.group(1)))
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            m = SKILL_IMPORT_RE.match(node.module + ".")
            if m:
                out.append((node.lineno, m.group(1)))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                m = SKILL_IMPORT_RE.match(alias.name + ".")
                if m:
                    out.append((node.lineno, m.group(1)))
    return out


def _owning_skill(path: Path, skills_dir: Path) -> str | None:
    """If `path` is inside skills/<X>/, return X; otherwise None."""
    try:
        rel = path.relative_to(skills_dir)
    except ValueError:
        return None
    return rel.parts[0] if rel.parts else None


def _iter_py_files(roots: list[Path]) -> list[Path]:
    excludes = {".venv", "__pycache__", "node_modules", ".next"}
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            if any(part in excludes for part in p.parts):
                continue
            out.append(p)
    return out


def test_no_skill_imports_another_skill(project_root, skills_dir, project_skill_names):
    """A skill's Python code must not `from skills.<other>.X` import another project skill."""
    # Validate the allowlist references real skill names — catches typos at PR time
    # rather than silently disabling the rule.
    bad_allowlist = [
        (a, b) for (a, b) in ALLOWED_CROSS_SKILL_IMPORTS
        if a not in project_skill_names or b not in project_skill_names
    ]
    assert not bad_allowlist, (
        f"ALLOWED_CROSS_SKILL_IMPORTS contains pairs referencing non-existent skills: {bad_allowlist}. "
        f"Known project skills: {sorted(project_skill_names)}"
    )

    # Map underscore-form import names back to filesystem skill names
    # (e.g., `document_extractor` import → `document-extractor` skill).
    underscore_to_skill = {name.replace("-", "_"): name for name in project_skill_names}

    violations: list[tuple[Path, int, str, str]] = []
    for py in _iter_py_files([skills_dir]):
        owner = _owning_skill(py, skills_dir)
        if owner is None:
            continue
        for lineno, imported_raw in _imports_in_file(py):
            # Resolve back to the actual skill directory name (handles hyphenated skills
            # imported via their underscore Python alias).
            imported = underscore_to_skill.get(imported_raw, imported_raw)
            # Skip imports of names that aren't actually project skills (dangling imports
            # like `skills.channels.*` referencing a non-existent skill belong to a
            # different class of bug — out of scope for this rule).
            if imported not in project_skill_names:
                continue
            if imported == owner:
                continue  # self-import is fine
            if (owner, imported) in ALLOWED_CROSS_SKILL_IMPORTS:
                continue
            violations.append((py.relative_to(project_root), lineno, owner, imported))
    assert not violations, (
        "A skill is importing another skill's Python modules. Move shared code to "
        "src/lib/ (Track 1) or relocate the consuming code to where its dependencies live.\n"
        + "\n".join(
            f"  {p}:{n}  skills/{o} imports skills/{i}"
            for p, n, o, i in violations
        )
    )


def test_no_project_code_imports_vault_skill(project_root, vault_private_names):
    """Project code (src/, apps/) must not import from vault-private skills."""
    violations: list[tuple[Path, int, str]] = []
    roots = [project_root / "src", project_root / "apps"]
    for py in _iter_py_files(roots):
        for lineno, imported in _imports_in_file(py):
            if imported in vault_private_names:
                violations.append((py.relative_to(project_root), lineno, imported))
    assert not violations, (
        "Project code imports from a vault-private skill. Vault skills are per-user "
        "and may be absent. Use a dynamic skill registry instead.\n"
        + "\n".join(f"  {p}:{n}  imports skills/{i}" for p, n, i in violations)
    )
```

- [ ] **Step 3.2: Run the test to confirm it fails on the rag→ingest violation**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && uv run pytest tests/architecture/test_no_cross_skill_imports.py -v 2>&1 | tail -15
```

Expected: FAILS on `test_no_skill_imports_another_skill` listing **exactly two violations** (the rag→ingest pair):
- `skills/rag/scripts/mcp/rag_tools.py:25  skills/rag imports skills/ingest`
- `skills/rag/scripts/mcp/rag_tools.py:356  skills/rag imports skills/ingest`

All other cross-skill imports identified during planning are excluded by the seeded `ALLOWED_CROSS_SKILL_IMPORTS` allowlist (7 pair entries — see the file). The allowlist absorbs:

- `("ingest", "rag")` — 5 sites (ingest's `inbox_consume.py`, `wiki_reset.py`, plus 2 test files)
- `("ingest", "ai")` — 3 test sites
- `("knowledge", "rag")` — 1 CLI site
- `("document-extractor", "ai")` — 1 site (`ollama_client.py` via `skills.ai.augur.lib`)
- `("onboard", "ai")` — 1 site (`cloud_status.py` via `skills.ai.augur.lib`)
- `("platform-admin", "ai")` — 1 site (`run_prompt.py` via `skills.ai.augur.lib`)
- `("file-manager", "ai")` — 1 site (`autoloop.py:42` via `skills.ai.augur.lib`)

Plus one dangling reference (`skills.channels` from `file-manager/scripts/autoloop.py:197`) is filtered out by the `imported not in project_skill_names` check — `channels` is not a project skill, so it's a different class of bug (dangling import) and out of this rule's scope.

The rag→ingest pair is NOT in the allowlist because Tasks 4 and 5 remove those imports entirely by relocating the wiki MCP tools.

`test_no_project_code_imports_vault_skill` should pass — `src/` and `apps/` do not currently import any vault skill at the Python level.

If violations beyond the rag→ingest pair appear (i.e., the allowlist is missing entries), STOP and report — that means the codebase has new couplings since the plan was written.

- [ ] **Step 3.3: Commit**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && git add tests/architecture/test_no_cross_skill_imports.py && git commit -m "test(architecture): add no-cross-skill-imports check (currently failing on rag->ingest)"
```

---

## Task 4: Relocate `wiki-status` MCP tool from rag to ingest

**Files:**
- Modify: `skills/rag/scripts/mcp/rag_tools.py` (remove the import and the `wiki-status` MCP tool)
- Modify: `skills/ingest/scripts/mcp/wiki_tools.py` (add the `wiki-status` MCP tool)

- [ ] **Step 4.1: Read the current `wiki-status` definition in rag**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && sed -n '20,30p;360,365p' skills/rag/scripts/mcp/rag_tools.py
```

Expected: `from skills.ingest.scripts.wiki_status import build_wiki_status` near line 25, and `@mcp.tool(name="wiki-status")` definition near line 360.

- [ ] **Step 4.2: Inspect `wiki_tools.py` imports**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && grep -n "^import json\|^from json\|build_wiki_status\|register_wiki_tools" skills/ingest/scripts/mcp/wiki_tools.py
```

Note which imports are at module level so you don't duplicate them in the relocated tool.

- [ ] **Step 4.3: Add the relocated `wiki-status` tool to `wiki_tools.py`**

Open `skills/ingest/scripts/mcp/wiki_tools.py`. Find the `register_wiki_tools(mcp, mcp_tool_interceptor, metrics)` function (begins around line 412). Inside that function, after the existing tool definitions, append:

```python
    @mcp.tool(name="wiki-status")
    @mcp_tool_interceptor
    async def wiki_status() -> str:
        """Return wiki structure, compiler backlog, batch, coverage, and index status."""
        from skills.ingest.scripts.wiki_status import build_wiki_status
        import json
        return json.dumps(build_wiki_status(), indent=2, default=str)
```

If `json` and `build_wiki_status` are already imported at module level (per Step 4.2), drop the local imports.

- [ ] **Step 4.4: Remove the `wiki-status` MCP tool from `rag_tools.py`**

In `skills/rag/scripts/mcp/rag_tools.py`, delete:

```python
    @mcp.tool(name="wiki-status")
    @mcp_tool_interceptor
    async def wiki_status() -> str:
        """Return wiki structure, compiler backlog, batch, coverage, and index status."""
        return json.dumps(build_wiki_status(), indent=2, default=str)
```

Also delete the corresponding top-of-file import:
```python
from skills.ingest.scripts.wiki_status import build_wiki_status
```

- [ ] **Step 4.5: Run the wiki tests to confirm functional parity**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && uv run pytest skills/ingest/augur/tests/ skills/rag/augur/tests/ -k wiki -v 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 4.6: Commit**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && git add skills/rag/scripts/mcp/rag_tools.py skills/ingest/scripts/mcp/wiki_tools.py && git commit -m "refactor(wiki): relocate wiki-status MCP tool from rag to ingest

wiki-status reads compiler backlog and source inventory data that lives in
ingest's scripts. Hosting the MCP tool in rag forced rag to import ingest
internals. Moving the tool to ingest's wiki_tools.py keeps the dependency
graph DAG-shaped and removes the cross-skill import."
```

---

## Task 5: Remove `wiki-lint` and `wiki-purge` MCP tools from rag (canonical versions already in ingest)

**Files:**
- Modify: `skills/rag/scripts/mcp/rag_tools.py` — remove the `wiki-lint` and `wiki-purge` MCP tool definitions and any orphan imports

**Plan amendment (2026-04-29):** During Task 4's execution, it was discovered that `wiki-status` was already canonically registered in `skills/ingest/scripts/mcp/wiki_tools.py` with a richer implementation than the rag-side duplicate. Code review on Task 4 then verified the same is true for both `wiki-lint` (rag:351 + ingest:509) and `wiki-purge` (rag:359 + ingest:537). For each tool, ingest's implementation is strictly equal-or-better:
- `wiki-lint` — both call `lint_wiki(wiki_dir=...)` from ingest; ingest's version uses tool annotations + metrics. rag's adds nothing the ingest version lacks.
- `wiki-purge` — both rmtree the wiki dirs; ingest's version additionally calls `_reset_cached_wiki_handles()` to invalidate cached handles, preventing stale-handle bugs after the purge. rag's version misses this.

Task 5 therefore does NOT add anything to ingest. It only removes the rag-side duplicates and any now-orphan imports. After Task 5, the architecture test passes (no rag→ingest cross-skill imports remain) and there are no duplicate MCP tool registrations between the two bundles.

- [ ] **Step 5.1: Remove the `wiki-lint` MCP tool from `rag_tools.py`**

In `skills/rag/scripts/mcp/rag_tools.py`, delete the `@mcp.tool(name="wiki-lint")` block (5 lines around line 351):

```python
    @mcp.tool(name="wiki-lint")
    @mcp_tool_interceptor
    async def wiki_lint() -> str:
        """Validate the compiled wiki for missing pages, broken links, and orphans."""
        from skills.ingest.scripts.wiki_maintenance import lint_wiki

        return json.dumps(lint_wiki(wiki_dir=get_compiled_wiki_dir()))
```

The `from skills.ingest.scripts.wiki_maintenance import lint_wiki` is a local function-body import; deleting the function deletes that import too. No top-of-file import needs touching.

- [ ] **Step 5.2: Remove the `wiki-purge` MCP tool from `rag_tools.py`**

In `skills/rag/scripts/mcp/rag_tools.py`, delete the `@mcp.tool(name="wiki-purge")` block (around line 359, ~28 lines):

```python
    @mcp.tool(name="wiki-purge")
    @mcp_tool_interceptor
    async def wiki_purge() -> str:
        """Delete the compiled wiki plus runtime and wiki-index artifacts for a clean rebuild."""
        metrics.track_tool("wiki_purge", skill="rag")
        runtime_wiki_dir = get_runtime_wiki_dir()
        wiki_dir = get_compiled_wiki_dir()
        rag_wiki_dir = get_rag_category_dir("wiki")

        removed_wiki = wiki_dir.exists()
        removed_runtime_wiki = runtime_wiki_dir.exists()
        removed_rag_wiki = rag_wiki_dir.exists()

        if removed_wiki:
            shutil.rmtree(wiki_dir)
        if removed_runtime_wiki:
            shutil.rmtree(runtime_wiki_dir)
        if removed_rag_wiki:
            shutil.rmtree(rag_wiki_dir)

        return json.dumps(
            {
                "status": "success",
                "wiki_dir": str(wiki_dir),
                "runtime_wiki_dir": str(runtime_wiki_dir),
                "rag_wiki_dir": str(rag_wiki_dir),
                "removed_wiki": removed_wiki,
                "removed_runtime_wiki": removed_runtime_wiki,
                "removed_rag_wiki": removed_rag_wiki,
            }
        )
```

- [ ] **Step 5.3: Check for orphan imports / helpers**

After deleting the two tool blocks, run:

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && grep -n "get_runtime_wiki_dir\|get_rag_category_dir\|^import shutil\|^from shutil\|get_compiled_wiki_dir\|lint_wiki" skills/rag/scripts/mcp/rag_tools.py
```

For each match, decide: is the symbol still used by remaining code in the file? If `shutil` or any of the path helpers are no longer used after the deletions, remove the corresponding top-of-file import. If they're used by other tools (`wiki-reindex`, `rag-cleanup`, etc.), leave them.

- [ ] **Step 5.4: Run the wiki tests**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && uv run pytest skills/ingest/augur/tests/ skills/rag/augur/tests/ -k wiki -v 2>&1 | tail -15
```

Expected: all pass. Both `wiki-lint` and `wiki-purge` tests live on the ingest side already (per Task 4's discovery pattern); deleting rag's duplicates doesn't break them.

- [ ] **Step 5.5: Verify the architecture test now passes**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && uv run pytest tests/architecture/test_no_cross_skill_imports.py -v 2>&1 | tail -10
```

Expected: PASS — no more cross-skill imports. The test goes green for the first time.

- [ ] **Step 5.6: Commit**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && git add skills/rag/scripts/mcp/rag_tools.py && git commit -m "$(cat <<'EOF'
refactor(wiki): remove duplicate wiki-lint and wiki-purge MCP tools from rag

Both wiki-lint and wiki-purge were registered in BOTH rag and ingest
bundles. Whichever bundle registered second silently overrode the first.
Code review on Task 4 (wiki-status relocation) verified that ingest's
implementations are strictly equal-or-better than rag's:

- wiki-lint: equivalent. Both call lint_wiki() from ingest; ingest's
  version adds tool annotations + metrics tracking.
- wiki-purge: ingest is RICHER. Both rmtree the wiki dirs; ingest's
  version additionally calls _reset_cached_wiki_handles() to invalidate
  cached handles after the purge, preventing stale-handle bugs.

Removed rag's duplicate registrations. The architecture test
(tests/architecture/test_no_cross_skill_imports.py) now passes — the
last cross-skill import (the wiki-lint helper from
skills.ingest.scripts.wiki_maintenance) is gone with the function it
was scoped to.

Behavior change is monotonic improvement: post-commit there is exactly
one canonical registration per tool name, and that registration is the
one with metrics + extra cleanup.
EOF
)"
```

---

## Task 6: Verify `test_no_cross_skill_imports.py` passes

- [ ] **Step 6.1: Run the architecture test**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && uv run pytest tests/architecture/test_no_cross_skill_imports.py -v 2>&1 | tail -10
```

Expected: PASS — both `test_no_skill_imports_another_skill` and `test_no_project_code_imports_vault_skill` pass.

The pass is achieved via:
- The rag→ingest imports are removed entirely by Tasks 4 and 5 (no allowlist entry needed).
- The 9 other cross-skill imports remain in the codebase but are absorbed by the seeded `ALLOWED_CROSS_SKILL_IMPORTS` allowlist (3 pair entries: `("ingest", "rag")`, `("ingest", "ai")`, `("knowledge", "rag")`).

The allowlist is documented Track 1 debt: each entry retires when the imported skill (rag, ai) extracts to `src/lib/`. Track 1's verification will be "ALLOWED_CROSS_SKILL_IMPORTS is empty after extraction."

- [ ] **Step 6.2: Run the full architecture test suite**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && uv run pytest tests/architecture/ -v 2>&1 | tail -10
```

Expected: 2 tests pass (the two functions in `test_no_cross_skill_imports.py`). The conftest contributes 0 tests.

No commit at this step — verification gate.

---

## Task 7: Write the ADR

**Files:**
- Create: `Au-docs/adrs/ADR-NNN-bundle-architecture-phase0-cleanup.md`

- [ ] **Step 7.1: Determine the next ADR number**

```bash
ls ~/Projects/Au-docs/adrs | grep '^ADR-' | sort -V | tail -1
```

The next number is one more than the most recent.

- [ ] **Step 7.2: Create the ADR**

Save to `~/Projects/Au-docs/adrs/ADR-<NNN>-bundle-architecture-phase0-cleanup.md`:

```markdown
---
status: Implemented
date: 2026-04-29
deciders:
  - gsannikov
related:
  - docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md
  - docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md
hub: null
tags:
  - architecture
  - bundle-migration
  - phase-0
superseded_by: null
---

# ADR-NNN: Bundle Architecture — Phase 0 Cleanup

## Context

Two specs (Layer 1 architecture + Layer 4 migration) describe moving Augur from a
single-MCP-server monolith with a hand-edited visibility allowlist to a per-bundle
MCP-server architecture with no proprietary visibility filter. The migration
proceeds as four tracks (libraries, vault server split, framework split + dashboard
hub-routing redesign, visibility filter removal).

Before any track starts, an audit identified two real, Phase-0-scoped layering
smells:

1. `src/config/mcp_tools.py` referenced the vault-private skill `apple` by string
   literal in `_detect_project_context()`. The flag (`has_voice`) was set but
   never read — dead code.
2. `skills/rag/scripts/mcp/rag_tools.py` imported `build_wiki_status` and
   `lint_wiki` from `skills/ingest/scripts/`. The `wiki-status` and `wiki-lint`
   MCP tools were registered in rag's tool surface but their dependencies lived
   in ingest.

**During Phase 0 execution, two further architectural findings emerged:**

3. The dashboard hardcodes vault-private skill names (`apple`, `lifestyle`) in
   50+ locations across URL routing, skill-import templates, workflow code, and
   production UI. The `lifestyle` hub structure is a load-bearing dashboard
   architectural assumption — not a trivial cleanup. Migration spec Track 3
   was split into Track 3a (MCP framework split) and Track 3b (dashboard
   hub-routing redesign) to give 3b its own brainstorming and implementation
   cycle.
4. The MCP framework code in `src/` itself hardcodes vault-private skill names
   in 10 places across 7 files: `mcp_management.py:289`, `config.py:736`,
   `domain/plugins.py:218` (default parameter value!), `tools/hubs/capabilities.py:24`,
   `tools/hubs/scrape_and_save_idea.py:17/22/53` (entire module),
   `infrastructure/browse/dev.py:98`, plus the `_detect_project_context()` set
   literal at `mcp_tools.py:387`. Same pattern as dashboard. Track 3a's scope
   expanded to include removing these src/ framework hardcodes alongside the
   server split.

(Two further "smells" identified by the original regex audit — daemon's subprocess
invocations of platform-admin scripts, and ingest's filesystem checks for
obsidian's SKILL.md — were re-evaluated and confirmed to be path/discovery
references, not Python-import smells. No fix needed.)

## Decision

Land a single Phase 0 PR that does three small things:

1. Remove the `has_voice` dead-code reference to `apple` from `mcp_tools.py`. No
   architecture-rule test in Phase 0 enforces this — the broader rule lands with
   Track 3a, which rewrites the surrounding hardcoded-skill-name code under
   `augur-core`'s dynamic discovery.
2. Relocate the `wiki-status` and `wiki-lint` MCP tools from rag to ingest, so
   the function definitions co-locate with the underlying ingest helpers.
3. Add one architecture-rule test under `tests/architecture/`:
   - `test_no_cross_skill_imports.py` — fails if any skill imports another skill's
     Python modules at the AST level (or if project code imports a vault skill).
     Ships with a seeded `ALLOWED_CROSS_SKILL_IMPORTS` allowlist of 3 pair entries
     (`("ingest", "rag")`, `("ingest", "ai")`, `("knowledge", "rag")`) covering
     the 9 known pre-existing import sites that Track 1 will retire.

Phase 0 deliberately does NOT add `test_no_vault_skill_refs.py`. That rule has
a different shape — its violations are per-line strings rather than per-pair
couplings, so a per-line allowlist would be unwieldy bookkeeping. The src/ scope
of that rule is delivered by Track 3a alongside the framework rewrite that makes
it pass cleanly. The dashboard scope is delivered by Track 3b.

`test_no_cross_skill_imports.py` IS added because its allowlist mechanism is a
clean fit: each entry maps to a Track 1 deliverable (extract `rag` → empty all
`("*", "rag")` entries; extract `ai` → empty all `("*", "ai")` entries). The
allowlist is small (3 entries), each entry has a documented retirement plan,
and the test still gates against NEW cross-skill imports during the long
Tracks 1+2 execution period.

## Consequences

### Positive

- One architecture rule (cross-skill imports) is encoded as an automated test that
  fails fast on regression. Future contributors cannot introduce new cross-skill
  Python imports without explicit ALLOWLIST changes that are visible in PR review.
- The rag↔ingest cyclical-import risk is reduced; the wiki MCP tools live where
  their dependencies live. Track 1's library extraction for `rag` (→ `src/lib/index/`)
  no longer has to detangle this coupling along the way.
- The migration's Track 3 acquires an honest scope split (3a + 3b), reflecting
  what the framework and dashboard refactors actually require.
- Track 3a's scope is now precise: the 10 known src/ hardcodes are an explicit
  deliverable, alongside the augur-core/augur-framework split.

### Negative

- The `src/` and `apps/dashboard/` parallel architecture-rule tests are not added
  in Phase 0. Until Tracks 3a and 3b land, those areas are not protected from
  new vault-private hardcodes by automated CI. Mitigation: code review and the
  eventual track-specific tests catch regressions.
- Phase 0 is smaller than originally planned; the broader cleanup is deferred
  to separate cycles.

### Neutral

- The original regex audit overcounted: 5 smells became 2 confirmed Phase-0-scoped
  (apple dead code, rag→ingest) plus 2 architectural findings deferred to later
  tracks (dashboard hardcodes → Track 3b, src/ framework hardcodes → Track 3a)
  plus 2 false positives (daemon→platform-admin subprocess, ingest→obsidian
  filesystem discovery). The audit methodology is improved for future use.

## Alternatives Considered

### Alternative 1: Skip Phase 0; fix smells opportunistically during tracks

Each track would discover and fix its own smells in passing. Rejected because
the smells span multiple tracks. Bundling the small Phase-0-scoped fixes here
leaves later tracks focused on their architectural goals.

### Alternative 2: Stretch Phase 0 to fix the dashboard hub-routing layer (v1)

Initially attempted (Phase 0 v1 plan). When the architecture-test was written, it
revealed 50+ violations across the dashboard. Fixing them properly requires
rewriting skill-import templates, redesigning hub URL routing, regenerating tab
registries, and updating production data/UI code — far outside Phase 0 scope.
Rejected; deferred to Track 3b. The v1 plan was reverted at commit `6dadfdd9e`
and replaced with v2.

### Alternative 3: Keep `test_no_vault_skill_refs.py` with an ALLOWED-debt list (v2)

v2 narrowed the test to `src/` only and would have committed the test with an
allowlist of 10 known violations to be emptied by Track 3a. Rejected as v3:
adding a test that requires immediate maintenance burden (allowlist) is busywork.
The honest place for the rule is Track 3a, where the rule lands clean.

### Alternative 4: Stretch Phase 0 to fix the broader `_detect_project_context()` smell

Replacing `_detect_project_context()` with a dynamic skill-registry lookup
requires the `augur-core` server that lands in Track 3a. Rejected for Phase 0
scope.

## References

- Layer 1 spec: `docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md`
- Layer 4 spec (with Track 3a/3b split): `docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md`
- Phase 0 v3 plan: `docs/superpowers/plans/2026-04-28-bundle-architecture-phase0-cleanup.md`
- Phase 0 v1 reverted at commit `6dadfdd9e` on branch `phase0-bundle-cleanup`

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - name: "MCP tool 'wiki-status'"
      from: skills/rag/scripts/mcp/rag_tools.py
      to: skills/ingest/scripts/mcp/wiki_tools.py
      breaking: false
    - name: "MCP tool 'wiki-lint'"
      from: skills/rag/scripts/mcp/rag_tools.py
      to: skills/ingest/scripts/mcp/wiki_tools.py
      breaking: false
  patterns_deprecated:
    - "Cross-skill Python imports (`from skills.<X>.scripts.<Y>`)"
  files_affected:
    - src/config/mcp_tools.py
    - skills/rag/scripts/mcp/rag_tools.py
    - skills/ingest/scripts/mcp/wiki_tools.py
    - tests/architecture/  (new directory)
```
```

- [ ] **Step 7.3: Commit the ADR**

```bash
git -C ~/Projects/Au-docs add adrs/ADR-<NNN>-bundle-architecture-phase0-cleanup.md
git -C ~/Projects/Au-docs commit -m "ADR-<NNN>: bundle architecture phase 0 cleanup"
```

---

## Task 8: Final verification

- [ ] **Step 8.1: Run the architecture test suite**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && uv run pytest tests/architecture/ -v 2>&1 | tail -10
```

Expected: 2 tests pass (the two functions in `test_no_cross_skill_imports.py`).

- [ ] **Step 8.2: Run the full project test suite**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && uv run pytest -x --ignore=tests/architecture 2>&1 | tail -30
```

Expected: all pass. Common failure modes if something is wrong:
- `ImportError: cannot import name 'build_wiki_status' from ...rag_tools` — somewhere imports from rag what is now in ingest. Search and fix.
- `KeyError: 'has_voice'` — somewhere reads the deleted dict key. Should be impossible given Step 2.1 verified it was unused.

- [ ] **Step 8.3: Build the dashboard to confirm no runtime regressions**

```bash
cd ~/Projects/Augur/.worktrees/phase0-bundle-cleanup && pnpm --filter dashboard build 2>&1 | tail -15
```

Expected: build succeeds.

- [ ] **Step 8.4: Verify the ADR is committed in the docs repo**

```bash
git -C ~/Projects/Au-docs log --oneline -1 adrs/
```

Expected: most recent commit is the ADR commit from Task 7.

- [ ] **Step 8.5: No commit at this step — Phase 0 v3 is complete.**

If all verifications pass, the Phase 0 PR is ready to merge from `phase0-bundle-cleanup` into `main`.

---

## Done criteria

Phase 0 v3 is complete when:

1. ✅ Two architecture tests pass (`tests/architecture/test_no_cross_skill_imports.py`).
2. ✅ The full pytest suite passes.
3. ✅ The dashboard builds successfully.
4. ✅ ADR-NNN is committed to `Au-docs/adrs/`.
5. ✅ All v3 commits in this plan are merged to `main`.

After Phase 0 v3 lands, the next session brainstorms one of:
- **Track 1** (library extraction) — independently shippable, can run in parallel with Track 2.
- **Track 2** (vault server split) — independently shippable.
- **Track 3a** (framework MCP split + remove src/ vault-private hardcodes + add `test_no_vault_skill_refs.py` for src/).
- **Track 3b** (dashboard hub-routing redesign + remove dashboard vault-private hardcodes + add `test_no_vault_skill_refs.py` for apps/dashboard/).

The recommended order remains: Tracks 1 + 2 in parallel, then 3a, then 3b, then 4.
