# MCP-First Client Export and Command Stub Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace broad copied skill exports with an MCP-first model that exports only explicitly marked command entrypoints and removes the Codex-native special path.

**Architecture:** Keep `skills/` as the authored source of truth, but stop using it as a broad client distribution channel. Normal client exports become command-only, filtered by `x-augur-export-command: true`, while `_sync_skill_stubs()` becomes a cleanup/migration path for previously generated copies. Codex-specific prompt/native skill exceptions are removed so normal client behavior follows one shared policy.

**Tech Stack:** Python 3, pytest, pathlib, YAML frontmatter parsing

---

## File Structure

**Modify:**
- `skills/ai/scripts/sync_agents/skill_sync.py`
  Central export policy changes: command filtering, skill-export shutdown, Codex-path removal, managed cleanup.
- `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`
  Regression coverage for command opt-in, skill cleanup migration, user-file preservation, and Codex export removal.
- `skills/ai/scripts/sync_agents/engine.py`
  Only if needed to simplify or remove stale re-export/comment references around prompt/native skill sync behavior.

**Possibly modify:**
- `skills/ai/commands/*.md`
  Only if existing daily-driver commands need the new `x-augur-export-command: true` frontmatter during implementation.

**Reference only:**
- `docs/superpowers/specs/2026-04-16-mcp-first-command-export-design.md`
- `skills/ai/scripts/sync_agents/__init__.py`

---

### Task 1: Filter Command Export To Explicit Opt-In

**Files:**
- Modify: `skills/ai/scripts/sync_agents/skill_sync.py`
- Test: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`

- [ ] **Step 1: Write the failing command export tests**

```python
def test_command_sync_exports_only_commands_marked_for_client_export(tmp_path):
    from sync_agents.skill_sync import _sync_command_stubs

    exported_root = tmp_path / "skills" / "augur-core"
    (exported_root / "commands").mkdir(parents=True)
    (exported_root / "commands" / "ask.md").write_text(
        "---\n"
        "id: ask\n"
        "description: Ask your second brain\n"
        "x-augur-export-command: true\n"
        "---\n"
        "# /ask\n",
        encoding="utf-8",
    )

    hidden_root = tmp_path / "skills" / "devops"
    (hidden_root / "commands").mkdir(parents=True)
    (hidden_root / "commands" / "internal-ops.md").write_text(
        "---\n"
        "id: internal-ops\n"
        "description: Internal maintenance\n"
        "---\n"
        "# /internal-ops\n",
        encoding="utf-8",
    )

    with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
         patch("sync_agents.generators.PROJECT_ROOT", tmp_path), \
         patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
        written = _sync_command_stubs([SimpleNamespace(adapter_name="claude_code")])

    assert written == 1
    assert (tmp_path / ".claude" / "commands" / "ask.md").exists()
    assert not (tmp_path / ".claude" / "commands" / "internal-ops.md").exists()


def test_command_sync_cleans_stale_generated_command_when_flag_removed(tmp_path):
    from sync_agents.skill_sync import _sync_command_stubs

    skill_root = tmp_path / "skills" / "augur-core"
    (skill_root / "commands").mkdir(parents=True)
    (skill_root / "commands" / "ask.md").write_text(
        "---\n"
        "id: ask\n"
        "description: Ask your second brain\n"
        "---\n"
        "# /ask\n",
        encoding="utf-8",
    )

    commands_dir = tmp_path / ".claude" / "commands"
    commands_dir.mkdir(parents=True)
    (commands_dir / "ask.md").write_text("generated\n", encoding="utf-8")
    (commands_dir / ".augur-generated-commands.json").write_text(
        json.dumps({"files": ["ask.md"]}),
        encoding="utf-8",
    )

    with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
         patch("sync_agents.generators.PROJECT_ROOT", tmp_path), \
         patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
        written = _sync_command_stubs([SimpleNamespace(adapter_name="claude_code")])

    assert written == 0
    assert not (commands_dir / "ask.md").exists()
```

- [ ] **Step 2: Run the command export slice and verify it fails**

Run:
```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "command_sync_exports_only_commands_marked_for_client_export or command_sync_cleans_stale_generated_command_when_flag_removed" -v
```

Expected: FAIL because `_load_command_sources()` currently exports every explicit command doc.

- [ ] **Step 3: Implement command opt-in filtering**

```python
def _load_command_sources(skills_dir: Path) -> list[tuple[str, Path, str]]:
    """Load only explicit command docs marked for client export."""
    sources: list[tuple[str, Path, str]] = []
    for command_file in sorted(skills_dir.glob("*/commands/*.md")):
        raw = command_file.read_text(encoding="utf-8")
        frontmatter = _load_yaml_frontmatter(raw)
        if "skill" in frontmatter:
            continue
        if not _is_truthy_frontmatter(frontmatter.get("x-augur-export-command")):
            continue
        sources.append((command_file.stem, command_file, raw))
    return sources
```

- [ ] **Step 4: Run the command export slice and verify it passes**

Run:
```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "command_sync_exports_only_commands_marked_for_client_export or command_sync_cleans_stale_generated_command_when_flag_removed" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ai/scripts/sync_agents/skill_sync.py skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py
git commit -m "feat(sync): require opt-in for exported command stubs"
```

---

### Task 2: Stop Bulk Skill Export To Normal Clients

**Files:**
- Modify: `skills/ai/scripts/sync_agents/skill_sync.py`
- Test: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`

- [ ] **Step 1: Write the failing bulk-export shutdown tests**

```python
def test_skill_stub_sync_cleans_managed_client_skill_exports_without_rewriting_them(tmp_path):
    from sync_agents.skill_sync import _sync_skill_stubs

    skill_root = tmp_path / "skills" / "knowledge"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: knowledge\ndescription: Knowledge search\n---\n# Knowledge\n",
        encoding="utf-8",
    )

    claude_dir = tmp_path / ".claude" / "skills"
    managed_dir = claude_dir / "knowledge"
    managed_dir.mkdir(parents=True)
    (managed_dir / "SKILL.md").write_text("generated\n", encoding="utf-8")
    (claude_dir / ".augur-generated-prompts.json").write_text(
        json.dumps({"files": ["knowledge/SKILL.md"]}),
        encoding="utf-8",
    )

    with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
         patch("sync_agents.skill_sync._resolve_client_skill_dirs", return_value=[("claude-local", claude_dir, True)]), \
         patch("sync_agents.skill_sync._load_skill_scopes", return_value={"claude-code": "project"}):
        written = _sync_skill_stubs([SimpleNamespace(adapter_name="claude_code")])

    assert written == 0
    assert not managed_dir.exists()


def test_skill_stub_sync_preserves_user_skill_dirs_while_cleaning_managed_exports(tmp_path):
    from sync_agents.skill_sync import _sync_skill_stubs

    claude_dir = tmp_path / ".claude" / "skills"
    managed_dir = claude_dir / "knowledge"
    managed_dir.mkdir(parents=True)
    (managed_dir / "SKILL.md").write_text("generated\n", encoding="utf-8")
    user_dir = claude_dir / "personal-skill"
    user_dir.mkdir(parents=True)
    (user_dir / "SKILL.md").write_text("user\n", encoding="utf-8")
    (claude_dir / ".augur-generated-prompts.json").write_text(
        json.dumps({"files": ["knowledge/SKILL.md"]}),
        encoding="utf-8",
    )

    with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
         patch("sync_agents.skill_sync._resolve_client_skill_dirs", return_value=[("claude-local", claude_dir, True)]), \
         patch("sync_agents.skill_sync._load_skill_scopes", return_value={"claude-code": "project"}):
        written = _sync_skill_stubs([SimpleNamespace(adapter_name="claude_code")])

    assert written == 0
    assert not managed_dir.exists()
    assert (user_dir / "SKILL.md").exists()
```

- [ ] **Step 2: Run the skill-stub slice and verify it fails**

Run:
```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "skill_stub_sync_cleans_managed_client_skill_exports_without_rewriting_them or skill_stub_sync_preserves_user_skill_dirs_while_cleaning_managed_exports" -v
```

Expected: FAIL because `_sync_skill_stubs()` still writes client skill copies.

- [ ] **Step 3: Implement cleanup-first normal client skill behavior**

```python
def _sync_skill_stubs(adapters: list) -> int:
    """Stop normal client skill export and clean up previously managed copies."""
    skills_dir = PROJECT_ROOT / "skills"
    if not skills_dir.is_dir():
        return 0

    client_dirs = _resolve_client_skill_dirs(PROJECT_ROOT)
    enabled_ids = {a.adapter_name for a in adapters}
    skill_scopes = _load_skill_scopes()

    for cid, cdir, has_subdirs in client_dirs:
        adapter_name = _source_tag_to_adapter_name(cid)
        if adapter_name == "codex":
            continue
        if adapter_name not in enabled_ids:
            _cleanup_managed_skill_dir(cdir, has_subdirs)
            continue
        _cleanup_managed_skill_dir(cdir, has_subdirs)

    return 0
```

Note: keep any existing disabled-adapter cleanup behavior that still applies, but normal client skill export should now converge on zero written files.

- [ ] **Step 4: Run the skill-stub slice and verify it passes**

Run:
```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "skill_stub_sync_cleans_managed_client_skill_exports_without_rewriting_them or skill_stub_sync_preserves_user_skill_dirs_while_cleaning_managed_exports" -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ai/scripts/sync_agents/skill_sync.py skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py
git commit -m "refactor(sync): stop bulk client skill exports"
```

---

### Task 3: Remove Codex-Native Skill And Prompt Special Paths

**Files:**
- Modify: `skills/ai/scripts/sync_agents/skill_sync.py`
- Modify: `skills/ai/scripts/sync_agents/engine.py`
- Test: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`

- [ ] **Step 1: Write the failing Codex-removal tests**

```python
def test_codex_sync_does_not_export_native_skills_or_prompts(tmp_path):
    from sync_agents.skill_sync import _sync_skill_stubs, _sync_prompt_stubs

    skill_root = tmp_path / "skills" / "augur-core"
    (skill_root / "commands").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\n"
        "name: augur-core\n"
        "description: Core workflows\n"
        "x-augur-codex-native: true\n"
        "---\n"
        "# Augur Core\n",
        encoding="utf-8",
    )
    (skill_root / "commands" / "ask.md").write_text(
        "---\n"
        "id: ask\n"
        "description: Ask your second brain\n"
        "x-augur-export-command: true\n"
        "---\n"
        "# /ask\n",
        encoding="utf-8",
    )

    project_prompts = tmp_path / ".codex" / "prompts"
    global_prompts = tmp_path / "home" / ".codex" / "prompts"
    project_native = tmp_path / ".codex" / "skills"
    global_native = tmp_path / "home" / ".agents" / "skills" / "augur"
    for path in (project_prompts, global_prompts, project_native, global_native):
        path.mkdir(parents=True, exist_ok=True)

    fake_adapter = SimpleNamespace(adapter_name="codex")

    with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
         patch("sync_agents.skill_sync.get_codex_prompt_dir", side_effect=[project_prompts, global_prompts]), \
         patch("sync_agents.skill_sync.get_codex_native_skills_dir", side_effect=[project_native, project_native, global_native]), \
         patch("sync_agents.skill_sync._resolve_client_skill_dirs", return_value=[]):
        written_skills = _sync_skill_stubs([fake_adapter])
        written_prompts = _sync_prompt_stubs([fake_adapter])

    assert written_skills == 0
    assert written_prompts == 0
    assert not any(global_native.iterdir())
    assert not any(global_prompts.iterdir())
```

- [ ] **Step 2: Run the Codex-removal slice and verify it fails**

Run:
```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "codex_sync_does_not_export_native_skills_or_prompts or codex_native" -v
```

Expected: FAIL because current code still has native skill/prompt behavior and related tests expecting it.

- [ ] **Step 3: Remove Codex-native export behavior**

```python
def _load_codex_native_skill_names(skills_dir: Path) -> set[str]:
    """Codex-native export is retired under the MCP-first export policy."""
    return set()


def _sync_prompt_stubs(adapters: list, *, cleanup_disabled: bool = True) -> int:
    """Codex prompt mirroring is retired; only clean up managed leftovers."""
    if cleanup_disabled:
        for scope in ("project", "global"):
            prompt_dir = get_codex_prompt_dir(scope)
            _cleanup_managed_skill_dir(prompt_dir, has_subdirs=False)
    return 0
```

Also remove or simplify any branches in `_sync_skill_exports()` that continue to call `_sync_codex_native_skills()`.

- [ ] **Step 4: Update stale Codex-native tests to the new MCP-first expectation**

Replace expectations that assert:

- global native skills are written
- global Codex prompts are written

with expectations that:

- managed Codex native exports are cleaned up
- user files in those directories survive
- no new Codex native/prompt exports are created

- [ ] **Step 5: Run the Codex-removal slice and verify it passes**

Run:
```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "codex_sync_does_not_export_native_skills_or_prompts or codex_native or codex_prompt" -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add skills/ai/scripts/sync_agents/skill_sync.py skills/ai/scripts/sync_agents/engine.py skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py
git commit -m "refactor(sync): remove codex native export paths"
```

---

### Task 4: Prove Migration Cleanup And End-To-End Sync Behavior

**Files:**
- Modify: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`
- Possibly modify: `skills/ai/scripts/sync_agents/skill_sync.py`

- [ ] **Step 1: Write the end-to-end migration tests**

```python
def test_sync_skill_stubs_removes_previously_generated_exports_across_normal_clients(tmp_path):
    from sync_agents.skill_sync import _sync_skill_stubs

    claude_dir = tmp_path / ".claude" / "skills"
    gemini_dir = tmp_path / ".gemini" / "skills"
    cursor_dir = tmp_path / ".cursor" / "rules"

    for client_dir, managed_entry, manifest_entry in (
        (claude_dir, claude_dir / "knowledge" / "SKILL.md", "knowledge/SKILL.md"),
        (gemini_dir, gemini_dir / "knowledge" / "SKILL.md", "knowledge/SKILL.md"),
        (cursor_dir, cursor_dir / "knowledge.md", "knowledge.md"),
    ):
        managed_entry.parent.mkdir(parents=True, exist_ok=True)
        managed_entry.write_text("generated\n", encoding="utf-8")
        (client_dir / ".augur-generated-prompts.json").write_text(
            json.dumps({"files": [manifest_entry]}),
            encoding="utf-8",
        )

    client_dirs = [
        ("claude-local", claude_dir, True),
        ("gemini-local", gemini_dir, True),
        ("cursor-local", cursor_dir, False),
    ]

    adapters = [
        SimpleNamespace(adapter_name="claude_code"),
        SimpleNamespace(adapter_name="gemini"),
        SimpleNamespace(adapter_name="cursor"),
    ]

    with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
         patch("sync_agents.skill_sync._resolve_client_skill_dirs", return_value=client_dirs), \
         patch("sync_agents.skill_sync._load_skill_scopes", return_value={}):
        written = _sync_skill_stubs(adapters)

    assert written == 0
    assert not (claude_dir / "knowledge").exists()
    assert not (gemini_dir / "knowledge").exists()
    assert not (cursor_dir / "knowledge.md").exists()
```

- [ ] **Step 2: Run the migration slice and verify it fails if cleanup is incomplete**

Run:
```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "removes_previously_generated_exports_across_normal_clients" -v
```

Expected: FAIL until all normal-client cleanup paths behave consistently.

- [ ] **Step 3: Adjust cleanup details if any surface still rewrites exports**

Expected implementation shape:

```python
for cid, cdir, has_subdirs in client_dirs:
    adapter_name = _source_tag_to_adapter_name(cid)
    if adapter_name == "codex":
        continue
    _cleanup_managed_skill_dir(cdir, has_subdirs)
```

Do not add new export branches for normal client skill dirs.

- [ ] **Step 4: Run the migration slice and verify it passes**

Run:
```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "removes_previously_generated_exports_across_normal_clients" -v
```

Expected: PASS

- [ ] **Step 5: Run the full sync-adapter lifecycle suite**

Run:
```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py skills/ai/scripts/sync_agents/skill_sync.py
git commit -m "test(sync): cover mcp-first export migration"
```

---

### Task 5: Mark Real Exported Commands And Verify User-Facing Behavior

**Files:**
- Modify: `skills/*/commands/*.md` for commands that should remain exported
- Test: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`

- [ ] **Step 1: Add export flags to the intended daily-driver commands**

Examples:

```yaml
---
id: ask
description: Ask your second brain
x-augur-export-command: true
---
```

```yaml
---
id: dev-merge
description: Merge daily loop/worktree output safely
x-augur-export-command: true
---
```

```yaml
---
id: dev-loops
description: Run hardening and maintenance loops
x-augur-export-command: true
---
```

Apply the flag only to the commands the user has approved for export.

- [ ] **Step 2: Write the user-facing export test**

```python
def test_command_sync_exports_approved_daily_driver_commands(tmp_path):
    from sync_agents.skill_sync import _sync_command_stubs

    ask_root = tmp_path / "skills" / "augur-core"
    (ask_root / "commands").mkdir(parents=True)
    (ask_root / "commands" / "ask.md").write_text(
        "---\n"
        "id: ask\n"
        "description: Ask your second brain\n"
        "x-augur-export-command: true\n"
        "---\n"
        "# /ask\n",
        encoding="utf-8",
    )

    with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path), \
         patch("sync_agents.generators.PROJECT_ROOT", tmp_path), \
         patch("sync_agents.constants.PROJECT_ROOT", tmp_path):
        written = _sync_command_stubs([SimpleNamespace(adapter_name="claude_code")])

    assert written == 1
    assert (tmp_path / ".claude" / "commands" / "ask.md").exists()
```

- [ ] **Step 3: Run the targeted command behavior test**

Run:
```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "approved_daily_driver_commands or command_sync_exports_only_commands_marked_for_client_export" -v
```

Expected: PASS

- [ ] **Step 4: Run a real sync command locally**

Run:
```bash
python -m skills.ai.scripts.sync_agents sync commands claude-code
```

Expected:
- exported daily-driver commands are written to `.claude/commands/`
- unmarked commands are not written

- [ ] **Step 5: Commit**

```bash
git add skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py skills/*/commands/*.md
git commit -m "feat(sync): export only approved slash commands"
```

---

## Self-Review

- Spec coverage:
  - bulk skill export shutdown is covered in Task 2 and Task 4
  - `x-augur-export-command: true` filtering is covered in Task 1 and Task 5
  - Codex-native removal is covered in Task 3
  - migration cleanup and user-file preservation are covered in Task 2, Task 3, and Task 4
- Placeholder scan:
  - every task names exact files, test targets, and expected commands
  - no `TODO`/`TBD` placeholders remain
- Type consistency:
  - plan consistently refers to `_sync_skill_stubs`, `_sync_command_stubs`, `_sync_prompt_stubs`, `_load_command_sources`, `_cleanup_managed_skill_dir`, and `x-augur-export-command: true`
