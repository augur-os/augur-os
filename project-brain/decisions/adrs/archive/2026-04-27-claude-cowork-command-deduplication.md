# Claude/Cowork Command Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Claude/Cowork expose each Augur slash command through one owner by keeping Claude Code project commands in `.claude/commands` and removing overlapping command files from the Cowork plugin bundle.

**Architecture:** Cowork plugin-pack becomes a commandless plugin surface: it still ships `.mcp.json`, `.claude-plugin/plugin.json`, and plugin skills, but it no longer writes packaged slash commands. A sync-agent diagnostic inventories Claude Code and Cowork command surfaces and reports duplicate command names with exact source paths. Cowork cleanup remains Augur-scoped and preserves unrelated Cowork plugins.

**Tech Stack:** Python 3.11+, pytest, Augur `skills/plugin-pack` assembler/formatter modules, `skills.ai.scripts.sync_agents` CLI and adapter lifecycle tests.

**Spec:** `docs/superpowers/specs/2026-04-27-claude-cowork-command-dedup-design.md`

---

## Implementation Setup

This plan should be executed from a clean feature worktree. The main checkout may contain unrelated user-owned dirty files, so do not stage or revert them.

```bash
cd ~/Projects/Augur
git fetch origin main --prune
git worktree add ../augur-wt-claude-cowork-dedup -b fix/claude-cowork-command-dedup HEAD
cd ../augur-wt-claude-cowork-dedup
```

Expected:

```text
Preparing worktree (new branch 'fix/claude-cowork-command-dedup')
HEAD is now at <current-head> ...
```

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `skills/plugin-pack/scripts/profiles.py` | Modify | Make Cowork profile omit packaged commands while other plugin profiles keep core commands |
| `skills/plugin-pack/scripts/formatters/cowork.py` | Modify | Do not create an empty `commands/` directory when no Cowork commands are configured |
| `skills/plugin-pack/augur/tests/test_profiles.py` | Modify | Prove Cowork has no command exports and Codex/Gemini/Copilot still do |
| `skills/plugin-pack/augur/tests/test_cowork_formatter.py` | Modify | Prove empty command sets do not create `commands/` |
| `skills/plugin-pack/augur/tests/test_assembler.py` | Modify | Prove assembled Cowork plugin still has MCP/skills but no command files |
| `skills/ai/scripts/sync_agents/command_surface.py` | Create | Inventory command exposure across `.claude/commands`, Cowork uploads/cache, and `build/cowork` |
| `skills/ai/scripts/sync_agents/modes.py` | Modify | Add a command-surface report mode |
| `skills/ai/scripts/sync_agents/__init__.py` | Modify | Add `command-surfaces` CLI subcommand |
| `skills/ai/scripts/sync_agents/tests/test_command_surface.py` | Create | Unit tests for inventory, duplicate grouping, and report formatting |
| `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py` | Modify | Add Cowork cleanup regression preserving unrelated plugins |

---

## Task 1: Stop Cowork Plugin Command Export

**Files:**
- Modify: `skills/plugin-pack/scripts/profiles.py`
- Modify: `skills/plugin-pack/scripts/formatters/cowork.py`
- Modify: `skills/plugin-pack/augur/tests/test_profiles.py`
- Modify: `skills/plugin-pack/augur/tests/test_cowork_formatter.py`
- Modify: `skills/plugin-pack/augur/tests/test_assembler.py`

- [ ] **Step 1: Write failing profile tests**

Edit `skills/plugin-pack/augur/tests/test_profiles.py`.

Replace `test_packaged_profiles_have_core_commands` with:

```python
def test_cowork_profile_exports_no_packaged_commands():
    from profiles import COWORK_PROFILE

    assert COWORK_PROFILE.commands == {}


def test_non_cowork_packaged_profiles_keep_core_commands():
    from profiles import CODEX_PROFILE, COPILOT_PROFILE, GEMINI_PROFILE

    packaged_profiles = (CODEX_PROFILE, GEMINI_PROFILE, COPILOT_PROFILE)
    for profile in packaged_profiles:
        assert "ask" in profile.commands
        assert "search" in profile.commands
        assert "save" in profile.commands
        assert "wiki" in profile.commands
```

- [ ] **Step 2: Write failing formatter test**

Append to `skills/plugin-pack/augur/tests/test_cowork_formatter.py`:

```python
def test_write_commands_with_empty_command_set_does_not_create_commands_dir(tmp_path):
    from formatters.cowork import CoworkFormatter

    fmt = CoworkFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_commands(plugin_dir, {})

    assert not (plugin_dir / "commands").exists()
```

- [ ] **Step 3: Update assembler expectation**

Edit `skills/plugin-pack/augur/tests/test_assembler.py`.

In `test_assemble_cowork`, replace:

```python
    assert (output / "plugins" / "augur" / "commands" / "ask.md").exists()
```

with:

```python
    assert not (output / "plugins" / "augur" / "commands").exists()
    assert (output / "plugins" / "augur" / "skills").exists()
```

- [ ] **Step 4: Run the focused tests and verify failure**

```bash
python3 -m pytest \
  skills/plugin-pack/augur/tests/test_profiles.py \
  skills/plugin-pack/augur/tests/test_cowork_formatter.py \
  skills/plugin-pack/augur/tests/test_assembler.py \
  -q
```

Expected before implementation:

```text
FAILED ... test_cowork_profile_exports_no_packaged_commands
FAILED ... test_write_commands_with_empty_command_set_does_not_create_commands_dir
FAILED ... test_assemble_cowork
```

- [ ] **Step 5: Implement Cowork commandless profile**

Edit `skills/plugin-pack/scripts/profiles.py`.

Change the `COWORK_PROFILE` block from:

```python
COWORK_PROFILE = FilterProfile(
    name="cowork",
    hubs=frozenset({"brain", "career", "life", "studio"}),
    excluded_prefixes=("auto-", "dev-", "client-"),
    excluded_skills=_COMMON_EXCLUDED_SKILLS | {"developer", "onboard"},
    commands=_CORE_COMMANDS,
)
```

to:

```python
COWORK_PROFILE = FilterProfile(
    name="cowork",
    hubs=frozenset({"brain", "career", "life", "studio"}),
    excluded_prefixes=("auto-", "dev-", "client-"),
    excluded_skills=_COMMON_EXCLUDED_SKILLS | {"developer", "onboard"},
    commands={},
)
```

- [ ] **Step 6: Implement empty-command formatter behavior**

Edit `skills/plugin-pack/scripts/formatters/cowork.py`.

Change `write_commands` from:

```python
    def write_commands(self, plugin_dir: Path, commands: dict[str, dict]) -> None:
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        for name, cmd in commands.items():
            content = f"---\nname: {name}\ndescription: {cmd['description']}\n---\n\n{cmd['body']}\n"
            (commands_dir / f"{name}.md").write_text(content, encoding="utf-8")
```

to:

```python
    def write_commands(self, plugin_dir: Path, commands: dict[str, dict]) -> None:
        if not commands:
            return

        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        for name, cmd in commands.items():
            content = f"---\nname: {name}\ndescription: {cmd['description']}\n---\n\n{cmd['body']}\n"
            (commands_dir / f"{name}.md").write_text(content, encoding="utf-8")
```

- [ ] **Step 7: Run focused tests and verify pass**

```bash
python3 -m pytest \
  skills/plugin-pack/augur/tests/test_profiles.py \
  skills/plugin-pack/augur/tests/test_cowork_formatter.py \
  skills/plugin-pack/augur/tests/test_assembler.py \
  -q
```

Expected:

```text
... passed
```

- [ ] **Step 8: Commit Task 1**

```bash
git add \
  skills/plugin-pack/scripts/profiles.py \
  skills/plugin-pack/scripts/formatters/cowork.py \
  skills/plugin-pack/augur/tests/test_profiles.py \
  skills/plugin-pack/augur/tests/test_cowork_formatter.py \
  skills/plugin-pack/augur/tests/test_assembler.py
git commit -m "fix(plugin-pack): stop cowork command duplication"
```

---

## Task 2: Add Command Surface Inventory Diagnostic

**Files:**
- Create: `skills/ai/scripts/sync_agents/command_surface.py`
- Create: `skills/ai/scripts/sync_agents/tests/test_command_surface.py`

- [ ] **Step 1: Write failing diagnostic tests**

Create `skills/ai/scripts/sync_agents/tests/test_command_surface.py`:

```python
from pathlib import Path


def test_inventory_collects_claude_cowork_and_build_command_sources(tmp_path):
    from sync_agents.command_surface import inventory_augur_command_surfaces

    project_root = tmp_path / "repo"
    repo_commands = project_root / ".claude" / "commands"
    repo_commands.mkdir(parents=True)
    (repo_commands / "wiki.md").write_text("---\nname: wiki\n---\n", encoding="utf-8")

    cowork_dir = tmp_path / "cowork_plugins"
    upload_commands = cowork_dir / "marketplaces" / "local-desktop-app-uploads" / "augur" / "commands"
    upload_commands.mkdir(parents=True)
    (upload_commands / "wiki.md").write_text("---\nname: wiki\n---\n", encoding="utf-8")

    build_commands = project_root / "build" / "cowork" / "plugins" / "augur" / "commands"
    build_commands.mkdir(parents=True)
    (build_commands / "ask.md").write_text("---\nname: ask\n---\n", encoding="utf-8")

    entries = inventory_augur_command_surfaces(project_root, cowork_plugin_dirs=[cowork_dir])

    assert [(entry.command, entry.source_class) for entry in entries] == [
        ("wiki", "claude-code-project"),
        ("ask", "cowork-build"),
        ("wiki", "cowork-upload"),
    ]


def test_find_duplicate_commands_reports_all_source_paths(tmp_path):
    from sync_agents.command_surface import (
        CommandSurfaceEntry,
        find_duplicate_commands,
    )

    entries = [
        CommandSurfaceEntry("wiki", "claude-code-project", tmp_path / ".claude" / "commands" / "wiki.md"),
        CommandSurfaceEntry("wiki", "cowork-upload", tmp_path / "cowork" / "commands" / "wiki.md"),
        CommandSurfaceEntry("ask", "cowork-upload", tmp_path / "cowork" / "commands" / "ask.md"),
    ]

    duplicates = find_duplicate_commands(entries)

    assert len(duplicates) == 1
    assert duplicates[0].command == "wiki"
    assert duplicates[0].suggested_owner == "claude-code-project"
    assert [source.source_class for source in duplicates[0].sources] == [
        "claude-code-project",
        "cowork-upload",
    ]


def test_format_duplicate_report_is_actionable(tmp_path):
    from sync_agents.command_surface import (
        CommandDuplicate,
        CommandSurfaceEntry,
        format_duplicate_report,
    )

    duplicate = CommandDuplicate(
        command="wiki",
        suggested_owner="claude-code-project",
        sources=[
            CommandSurfaceEntry("wiki", "claude-code-project", tmp_path / ".claude" / "commands" / "wiki.md"),
            CommandSurfaceEntry("wiki", "cowork-upload", tmp_path / "cowork" / "commands" / "wiki.md"),
        ],
    )

    report = format_duplicate_report([duplicate])

    assert "DUPLICATE /wiki" in report
    assert "owner: claude-code-project" in report
    assert "cowork-upload" in report
    assert str(tmp_path / "cowork" / "commands" / "wiki.md") in report
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python3 -m pytest skills/ai/scripts/sync_agents/tests/test_command_surface.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'sync_agents.command_surface'
```

- [ ] **Step 3: Implement diagnostic module**

Create `skills/ai/scripts/sync_agents/command_surface.py`:

```python
"""Inventory Augur command exposure across Claude Code and Cowork surfaces."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandSurfaceEntry:
    command: str
    source_class: str
    path: Path


@dataclass(frozen=True)
class CommandDuplicate:
    command: str
    suggested_owner: str
    sources: list[CommandSurfaceEntry]


def _command_files(commands_dir: Path) -> list[Path]:
    if not commands_dir.exists() or not commands_dir.is_dir():
        return []
    return sorted(
        path
        for path in commands_dir.glob("*.md")
        if path.name != ".augur-generated-commands.json"
    )


def _entries_from_dir(commands_dir: Path, source_class: str) -> list[CommandSurfaceEntry]:
    return [
        CommandSurfaceEntry(command=path.stem, source_class=source_class, path=path)
        for path in _command_files(commands_dir)
    ]


def inventory_augur_command_surfaces(
    project_root: Path,
    *,
    cowork_plugin_dirs: list[Path] | None = None,
) -> list[CommandSurfaceEntry]:
    """Return Augur command sources from project-local and Cowork plugin surfaces."""
    project_root = Path(project_root)
    entries: list[CommandSurfaceEntry] = []

    entries.extend(
        _entries_from_dir(project_root / ".claude" / "commands", "claude-code-project")
    )
    entries.extend(
        _entries_from_dir(
            project_root / "build" / "cowork" / "plugins" / "augur" / "commands",
            "cowork-build",
        )
    )

    for cowork_dir in sorted(cowork_plugin_dirs or []):
        entries.extend(
            _entries_from_dir(
                cowork_dir / "marketplaces" / "local-desktop-app-uploads" / "augur" / "commands",
                "cowork-upload",
            )
        )
        entries.extend(
            _entries_from_dir(
                cowork_dir / "cache" / "augur-cowork" / "commands",
                "cowork-cache",
            )
        )

    return sorted(entries, key=lambda entry: (entry.command, entry.source_class, str(entry.path)))


def find_duplicate_commands(entries: list[CommandSurfaceEntry]) -> list[CommandDuplicate]:
    grouped: dict[str, list[CommandSurfaceEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.command, []).append(entry)

    duplicates: list[CommandDuplicate] = []
    for command, sources in sorted(grouped.items()):
        source_classes = {source.source_class for source in sources}
        if len(sources) < 2 or len(source_classes) < 2:
            continue
        owner = (
            "claude-code-project"
            if any(source.source_class == "claude-code-project" for source in sources)
            else sources[0].source_class
        )
        duplicates.append(
            CommandDuplicate(
                command=command,
                suggested_owner=owner,
                sources=sorted(sources, key=lambda source: (source.source_class, str(source.path))),
            )
        )
    return duplicates


def format_duplicate_report(duplicates: list[CommandDuplicate]) -> str:
    if not duplicates:
        return "No duplicate Augur command surfaces found."

    lines: list[str] = []
    for duplicate in duplicates:
        lines.append(f"DUPLICATE /{duplicate.command} owner: {duplicate.suggested_owner}")
        for source in duplicate.sources:
            lines.append(f"  - {source.source_class}: {source.path}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run diagnostic tests and verify pass**

```bash
python3 -m pytest skills/ai/scripts/sync_agents/tests/test_command_surface.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit Task 2**

```bash
git add \
  skills/ai/scripts/sync_agents/command_surface.py \
  skills/ai/scripts/sync_agents/tests/test_command_surface.py
git commit -m "feat(sync-agents): inventory claude cowork command surfaces"
```

---

## Task 3: Expose Command Surface Diagnostic In sync_agents CLI

**Files:**
- Modify: `skills/ai/scripts/sync_agents/modes.py`
- Modify: `skills/ai/scripts/sync_agents/__init__.py`
- Modify: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`

- [ ] **Step 1: Write failing CLI dispatch test**

Append to `class TestCleanHygieneMode` in `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`, near the existing `test_main_clean_hygiene_command_calls_clean_hygiene_mode` and `test_main_sync_commands_client_dispatches_selected_client` tests:

```python
    def test_main_command_surfaces_dispatches_report_mode(self):
        from sync_agents import main

        with patch("sync_agents.command_surface.inventory_augur_command_surfaces", return_value=[]), \
             patch("sync_agents.command_surface.find_duplicate_commands", return_value=[]), \
             patch("sync_agents.command_surface.format_duplicate_report", return_value="No duplicate Augur command surfaces found."), \
             patch.object(sys, "argv", ["sync_agents", "command-surfaces"]):
            assert main() == 0
```

- [ ] **Step 2: Run the test and verify failure**

```bash
python3 -m pytest \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestCleanHygieneMode::test_main_command_surfaces_dispatches_report_mode \
  -q
```

Expected:

```text
error: argument mode: invalid choice: 'command-surfaces'
```

- [ ] **Step 3: Add report mode**

Edit `skills/ai/scripts/sync_agents/modes.py`.

Add this function after `clean_hygiene_mode`:

```python
def command_surfaces_mode() -> int:
    """Print duplicate Augur command exposure across Claude/Cowork surfaces."""
    from .adapters.cowork import _find_cowork_plugin_dirs
    from .command_surface import (
        find_duplicate_commands,
        format_duplicate_report,
        inventory_augur_command_surfaces,
    )

    entries = inventory_augur_command_surfaces(
        PROJECT_ROOT,
        cowork_plugin_dirs=_find_cowork_plugin_dirs(),
    )
    duplicates = find_duplicate_commands(entries)
    print(format_duplicate_report(duplicates))
    return 1 if duplicates else 0
```

- [ ] **Step 4: Wire parser and dispatch**

Edit `skills/ai/scripts/sync_agents/__init__.py`.

In the import list from `.engine`, keep existing imports unchanged. Add this separate import near the existing `_purge_state_mode` import:

```python
from .modes import command_surfaces_mode as _command_surfaces_mode
```

In `_build_parser`, after `clean-hygiene`, add:

```python
    subparsers.add_parser("command-surfaces", help="Report duplicate Claude/Cowork command surfaces")
```

In `main`, after the `clean-hygiene` branch, add:

```python
    if mode == "command-surfaces":
        return _command_surfaces_mode()
```

- [ ] **Step 5: Run CLI dispatch test and diagnostic module tests**

```bash
python3 -m pytest \
  skills/ai/scripts/sync_agents/tests/test_command_surface.py \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestCleanHygieneMode::test_main_command_surfaces_dispatches_report_mode \
  -q
```

Expected:

```text
4 passed
```

- [ ] **Step 6: Run the diagnostic locally**

```bash
python3 -m skills.ai.scripts.sync_agents command-surfaces
```

Expected after Task 1 but before reinstalling Cowork:

```text
DUPLICATE /wiki owner: claude-code-project
  - claude-code-project: ~/Projects/Augur/.claude/commands/wiki.md
  - cowork-upload: ~/Library/Application Support/Claude/.../cowork_plugins/.../augur/commands/wiki.md
```

If the installed Cowork plugin has already been regenerated, the expected output is:

```text
No duplicate Augur command surfaces found.
```

- [ ] **Step 7: Commit Task 3**

```bash
git add \
  skills/ai/scripts/sync_agents/modes.py \
  skills/ai/scripts/sync_agents/__init__.py \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py
git commit -m "feat(sync-agents): report claude cowork command duplicates"
```

---

## Task 4: Guard Cowork Cleanup Scope

**Files:**
- Modify: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`
- Modify if needed: `skills/ai/scripts/sync_agents/adapters/cowork.py`

- [ ] **Step 1: Write cleanup preservation test**

Append to `class TestCoworkAdapter` in `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`:

```python
    def test_cleanup_removes_augur_plugin_surfaces_and_preserves_unrelated_plugins(self, tmp_path):
        cowork_dir = tmp_path / "cowork_plugins"
        augur_upload = cowork_dir / "marketplaces" / "local-desktop-app-uploads" / "augur"
        augur_upload.mkdir(parents=True)
        (augur_upload / "commands").mkdir()
        (augur_upload / "commands" / "wiki.md").write_text("wiki\n", encoding="utf-8")

        legacy_cache = cowork_dir / "cache" / "augur-cowork"
        legacy_cache.mkdir(parents=True)
        (legacy_cache / "commands").mkdir()
        (legacy_cache / "commands" / "ask.md").write_text("ask\n", encoding="utf-8")

        unrelated_plugin = cowork_dir / "cache" / "knowledge-work-plugins"
        unrelated_plugin.mkdir(parents=True)
        (unrelated_plugin / "plugin.json").write_text("{}", encoding="utf-8")

        installed_path = cowork_dir / "installed_plugins.json"
        installed_path.write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        "augur@local-desktop-app-uploads": [{"scope": "user"}],
                        "cowork-plugin-management@knowledge-work-plugins": [{"scope": "user"}],
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()
        (runtime_dir / "claude_desktop_config.json").write_text(
            json.dumps({"mcpServers": {"augur": {}, "other": {}}}) + "\n",
            encoding="utf-8",
        )

        adapter = CoworkAdapter()
        adapter._output_dir = tmp_path / "build" / "cowork"

        with patch("sync_agents.adapters.cowork._find_cowork_plugin_dirs", return_value=[cowork_dir]), \
             patch("sync_agents.adapters.cowork.get_client_runtime_dir", return_value=runtime_dir):
            deleted = adapter.cleanup()

        assert str(augur_upload) + "/" in deleted
        assert str(legacy_cache) + "/" in deleted
        assert str(installed_path) in deleted
        assert not augur_upload.exists()
        assert not legacy_cache.exists()
        assert unrelated_plugin.exists()

        installed = json.loads(installed_path.read_text(encoding="utf-8"))
        assert "augur@local-desktop-app-uploads" not in installed["plugins"]
        assert "cowork-plugin-management@knowledge-work-plugins" in installed["plugins"]

        config = json.loads((runtime_dir / "claude_desktop_config.json").read_text(encoding="utf-8"))
        assert "augur" not in config["mcpServers"]
        assert "other" in config["mcpServers"]
```

- [ ] **Step 2: Run the test**

```bash
python3 -m pytest \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestCoworkAdapter::test_cleanup_removes_augur_plugin_surfaces_and_preserves_unrelated_plugins \
  -q
```

Expected:

```text
1 passed
```

If it fails, adjust only `skills/ai/scripts/sync_agents/adapters/cowork.py` to preserve unrelated plugin keys and dirs while removing Augur-owned uploads/cache/manifests/MCP entries.

- [ ] **Step 3: Commit Task 4**

```bash
git add skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py skills/ai/scripts/sync_agents/adapters/cowork.py
git commit -m "test(sync-agents): guard cowork cleanup scope"
```

If `cowork.py` did not change, omit it from `git add`.

---

## Task 5: Regenerate, Verify, And Commit Installed-Surface Fix

**Files:**
- Runtime/install side effects only: `build/cowork/` and Claude Desktop Cowork plugin install
- No user-owned Claude/Cowork plugins should be deleted

- [ ] **Step 1: Run full focused test suite**

```bash
python3 -m pytest \
  skills/plugin-pack/augur/tests/test_profiles.py \
  skills/plugin-pack/augur/tests/test_cowork_formatter.py \
  skills/plugin-pack/augur/tests/test_assembler.py \
  skills/ai/scripts/sync_agents/tests/test_command_surface.py \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestCoworkAdapter \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestCleanHygieneMode::test_main_command_surfaces_dispatches_report_mode \
  -q
```

Expected:

```text
... passed
```

- [ ] **Step 2: Assemble Cowork plugin and prove no commands are built**

```bash
python3 skills/plugin-pack/scripts/plugin_assembler.py --target cowork --output /tmp/augur-cowork-dedup-check
test ! -e /tmp/augur-cowork-dedup-check/plugins/augur/commands
test -e /tmp/augur-cowork-dedup-check/plugins/augur/.mcp.json
test -d /tmp/augur-cowork-dedup-check/plugins/augur/skills
```

Expected:

```text
Assembled cowork plugin ...
```

All `test` commands exit `0`.

- [ ] **Step 3: Regenerate and install the real Cowork plugin**

```bash
python3 -m skills.ai.scripts.sync_agents sync all cowork
```

Expected:

```text
Generated plugin ... for cowork ...
Installed augur to Cowork desktop
```

If Cowork is not detected, run:

```bash
python3 skills/plugin-pack/scripts/plugin_assembler.py --target cowork --install
```

- [ ] **Step 4: Run duplicate diagnostic**

```bash
python3 -m skills.ai.scripts.sync_agents command-surfaces
```

Expected:

```text
No duplicate Augur command surfaces found.
```

- [ ] **Step 5: Confirm repository diff is scoped**

```bash
git status --short
git diff --stat
```

Expected changed source files only from this plan. Do not stage local runtime state, external Claude Desktop files, unrelated user edits, or `build/cowork/` unless it is already a tracked repo file.

- [ ] **Step 6: Commit any remaining source changes**

If Task 5 produced source changes not already committed:

```bash
git add <specific-source-files>
git commit -m "chore(sync-agents): verify cowork command surface ownership"
```

If there are no remaining source changes, skip this commit.

---

## Final Verification

- [ ] **Step 1: Run all relevant tests**

```bash
python3 -m pytest \
  skills/plugin-pack/augur/tests/test_profiles.py \
  skills/plugin-pack/augur/tests/test_cowork_formatter.py \
  skills/plugin-pack/augur/tests/test_assembler.py \
  skills/ai/scripts/sync_agents/tests/test_command_surface.py \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestCoworkAdapter \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::TestCleanHygieneMode::test_main_command_surfaces_dispatches_report_mode \
  -q
```

Expected:

```text
... passed
```

- [ ] **Step 2: Run syntax/import checks**

```bash
python3 -m py_compile \
  skills/plugin-pack/scripts/profiles.py \
  skills/plugin-pack/scripts/formatters/cowork.py \
  skills/ai/scripts/sync_agents/command_surface.py \
  skills/ai/scripts/sync_agents/modes.py \
  skills/ai/scripts/sync_agents/__init__.py
```

Expected: no output and exit `0`.

- [ ] **Step 3: Run whitespace/conflict checks**

```bash
git diff --check
rg -n "^(<<<<<<<|=======|>>>>>>>)" \
  skills/plugin-pack/scripts \
  skills/plugin-pack/augur/tests \
  skills/ai/scripts/sync_agents
```

Expected: `git diff --check` exits `0`; `rg` exits `1` with no matches.

- [ ] **Step 4: Verify duplicate report**

```bash
python3 -m skills.ai.scripts.sync_agents command-surfaces
```

Expected:

```text
No duplicate Augur command surfaces found.
```

- [ ] **Step 5: Show final commits**

```bash
git log --oneline --max-count=6
git status --short --branch
```

Expected: implementation commits are present, branch has no unexpected dirty files.
