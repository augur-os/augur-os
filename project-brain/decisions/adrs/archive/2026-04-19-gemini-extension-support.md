# Gemini Extension Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Implements:** ADR-553 - Gemini Extension Support for Augur Plugin Pack

**Goal:** Add Gemini CLI as a first-class Augur plugin-pack target so Gemini receives a native Augur extension with MCP access, core `/augur:*` commands, and selected Augur skills.

**Architecture:** Extend the existing plugin-pack target architecture with a Gemini profile and formatter. The formatter owns Gemini-specific extension layout while the assembler keeps one shared discovery and transformation pipeline. Add a sync-agents adapter parallel to the Codex and Cowork plugin adapters so normal sync can assemble and install the Gemini extension.

**Tech Stack:** Python 3.11+, pytest, Gemini CLI extension files, TOML command definitions, JSON manifests, Next.js route metadata.

---

## File Map

- Modify `staging/r3/skills/plugin-pack/scripts/profiles.py`: add `GEMINI_PROFILE`.
- Modify `staging/r3/skills/plugin-pack/scripts/formatters/base.py`: add a default `plugin_dir()` hook.
- Create `staging/r3/skills/plugin-pack/scripts/formatters/gemini.py`: write and install Gemini extension output.
- Modify `staging/r3/skills/plugin-pack/scripts/formatters/__init__.py`: export `GeminiFormatter`.
- Modify `staging/r3/skills/plugin-pack/scripts/plugin_assembler.py`: register `gemini` target and use formatter-owned output directory.
- Modify `staging/r3/skills/plugin-pack/augur/tests/test_profiles.py`: profile coverage.
- Modify `staging/r3/skills/plugin-pack/augur/tests/test_assembler.py`: assembler coverage.
- Create `staging/r3/skills/plugin-pack/augur/tests/test_gemini_formatter.py`: Gemini formatter coverage.
- Create `skills/ai/scripts/sync_agents/adapters/gemini_plugin.py`: sync lifecycle adapter for the Gemini extension.
- Modify `skills/ai/scripts/sync_agents/adapters/__init__.py`: export `GeminiPluginAdapter`.
- Modify `skills/ai/scripts/sync_agents/engine.py`: instantiate adapter and gate it with the Gemini group.
- Modify `skills/ai/scripts/sync_agents/__init__.py`: allow `gemini-plugin` as a sync client filter.
- Modify `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`: adapter lifecycle and registration coverage.
- Modify `staging/r3/skills/plugin-pack/SKILL.md`: document Gemini target.
- Modify `apps/dashboard/app/api/plugin-pack/route.ts`: expose Gemini in read-only plugin-pack API metadata.
- Keep `docs/generated/adr-index.md`: regenerated after ADR-553.

## Task 1: Add Gemini Filter Profile

**Files:**
- Modify: `staging/r3/skills/plugin-pack/augur/tests/test_profiles.py`
- Modify: `staging/r3/skills/plugin-pack/scripts/profiles.py`

- [ ] **Step 1: Write the failing profile tests**

In `staging/r3/skills/plugin-pack/augur/tests/test_profiles.py`, add:

```python
def test_gemini_profile_matches_codex_initial_scope():
    from profiles import CODEX_PROFILE, GEMINI_PROFILE

    assert GEMINI_PROFILE.name == "gemini"
    assert GEMINI_PROFILE.hubs == CODEX_PROFILE.hubs
    assert GEMINI_PROFILE.excluded_prefixes == CODEX_PROFILE.excluded_prefixes
    assert GEMINI_PROFILE.excluded_skills == CODEX_PROFILE.excluded_skills
    assert GEMINI_PROFILE.commands == CODEX_PROFILE.commands
```

Replace `test_both_profiles_exclude_plugin_pack()` with:

```python
def test_packaged_profiles_exclude_plugin_pack():
    from profiles import COWORK_PROFILE, CODEX_PROFILE, GEMINI_PROFILE

    for profile in [COWORK_PROFILE, CODEX_PROFILE, GEMINI_PROFILE]:
        assert "plugin-pack" in profile.excluded_skills
```

Replace `test_both_profiles_have_core_commands()` with:

```python
def test_packaged_profiles_have_core_commands():
    from profiles import COWORK_PROFILE, CODEX_PROFILE, GEMINI_PROFILE

    for profile in [COWORK_PROFILE, CODEX_PROFILE, GEMINI_PROFILE]:
        assert "ask" in profile.commands
        assert "search" in profile.commands
        assert "save" in profile.commands
```

Replace `test_get_profile_by_name()` with:

```python
def test_get_profile_by_name():
    from profiles import get_profile

    assert get_profile("cowork").name == "cowork"
    assert get_profile("codex").name == "codex"
    assert get_profile("gemini").name == "gemini"
```

- [ ] **Step 2: Run profile tests and confirm the failure**

Run:

```bash
pytest staging/r3/skills/plugin-pack/augur/tests/test_profiles.py -q
```

Expected: FAIL with an import error or assertion failure for missing `GEMINI_PROFILE`.

- [ ] **Step 3: Implement `GEMINI_PROFILE`**

In `staging/r3/skills/plugin-pack/scripts/profiles.py`, add this block after `CODEX_PROFILE`:

```python
GEMINI_PROFILE = FilterProfile(
    name="gemini",
    hubs=CODEX_PROFILE.hubs,
    excluded_prefixes=CODEX_PROFILE.excluded_prefixes,
    excluded_skills=CODEX_PROFILE.excluded_skills,
    commands=_CORE_COMMANDS,
)
```

Replace `_PROFILES` with:

```python
_PROFILES = {
    "cowork": COWORK_PROFILE,
    "codex": CODEX_PROFILE,
    "gemini": GEMINI_PROFILE,
}
```

- [ ] **Step 4: Run profile tests and confirm they pass**

Run:

```bash
pytest staging/r3/skills/plugin-pack/augur/tests/test_profiles.py -q
```

Expected: all tests PASS.

- [ ] **Step 5: Commit the profile checkpoint**

Run:

```bash
git add staging/r3/skills/plugin-pack/augur/tests/test_profiles.py staging/r3/skills/plugin-pack/scripts/profiles.py
git commit -m "feat(plugin-pack): add gemini filter profile"
```

## Task 2: Add Gemini Formatter

**Files:**
- Create: `staging/r3/skills/plugin-pack/augur/tests/test_gemini_formatter.py`
- Modify: `staging/r3/skills/plugin-pack/scripts/formatters/base.py`
- Create: `staging/r3/skills/plugin-pack/scripts/formatters/gemini.py`
- Modify: `staging/r3/skills/plugin-pack/scripts/formatters/__init__.py`

- [ ] **Step 1: Write failing formatter tests**

Create `staging/r3/skills/plugin-pack/augur/tests/test_gemini_formatter.py`:

```python
"""Tests for Gemini formatter (Gemini CLI extension output)."""
import json
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = PROJECT_ROOT / "skills" / "plugin-pack" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_plugin_dir_uses_gemini_extensions_layout(tmp_path):
    from formatters.gemini import GeminiFormatter

    assert GeminiFormatter().plugin_dir(tmp_path / "build") == (
        tmp_path / "build" / "extensions" / "augur"
    )


def test_write_manifest_creates_gemini_manifest_and_context(tmp_path):
    from formatters.gemini import GeminiFormatter

    fmt = GeminiFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_manifest(plugin_dir, "1.0.0")

    manifest_path = plugin_dir / "gemini-extension.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["name"] == "augur"
    assert data["version"] == "1.0.0"
    assert data["contextFileName"] == "GEMINI.md"
    assert "mcpServers" not in data

    context = (plugin_dir / "GEMINI.md").read_text()
    assert "/augur:ask" in context
    assert "augur MCP server" in context


def test_write_mcp_config_merges_gemini_client_id_into_manifest(tmp_path):
    from formatters.gemini import GeminiFormatter

    fmt = GeminiFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_manifest(plugin_dir, "1.0.0")
    fmt.write_mcp_config(plugin_dir, Path("/fake/root"), "/fake/python")

    data = json.loads((plugin_dir / "gemini-extension.json").read_text())
    server = data["mcpServers"]["augur"]
    assert server["command"] == "/fake/python"
    assert server["args"] == ["-m", "augur_mcp", "--client-id", "gemini"]
    assert server["cwd"] == "/fake/root"
    assert server["env"]["AUGUR_ROOT"] == "/fake/root"
    assert server["env"]["PYTHONPATH"] == "/fake/root:/fake/root/src/mcp"


def test_write_skills_creates_skill_dirs(tmp_path):
    from formatters.gemini import GeminiFormatter

    fmt = GeminiFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_skills(
        plugin_dir,
        {
            "career": "---\nname: career\n---\n# Career\n",
            "knowledge": "---\nname: knowledge\n---\n# Knowledge\n",
        },
    )

    assert (plugin_dir / "skills" / "career" / "SKILL.md").exists()
    assert (plugin_dir / "skills" / "knowledge" / "SKILL.md").exists()


def test_write_commands_creates_namespaced_toml(tmp_path):
    from formatters.gemini import GeminiFormatter

    fmt = GeminiFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_commands(
        plugin_dir,
        {
            "ask": {"description": "Ask a question", "body": "Ask body."},
            "save": {"description": "Save content", "body": "Save body."},
        },
    )

    ask_path = plugin_dir / "commands" / "augur" / "ask.toml"
    assert ask_path.exists()
    parsed = tomllib.loads(ask_path.read_text())
    assert parsed["description"] == "Ask a question"
    assert "Ask body." in parsed["prompt"]
    assert "{{args}}" in parsed["prompt"]

    assert (plugin_dir / "commands" / "augur" / "save.toml").exists()


def test_write_marketplace_noops(tmp_path):
    from formatters.gemini import GeminiFormatter

    fmt = GeminiFormatter()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    fmt.write_marketplace(output_dir, "1.0.0")

    assert not (output_dir / ".agents").exists()
    assert not (output_dir / ".claude-plugin").exists()


def test_install_replaces_augur_extension(tmp_path):
    from formatters.gemini import GeminiFormatter

    fmt = GeminiFormatter()
    output_dir = tmp_path / "build"
    plugin_dir = output_dir / "extensions" / "augur"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "gemini-extension.json").write_text('{"name": "augur"}\n')

    extensions_dir = tmp_path / "home" / ".gemini" / "extensions"
    existing = extensions_dir / "augur"
    existing.mkdir(parents=True)
    (existing / "old.txt").write_text("old")

    result = fmt.install(output_dir, "1.0.0", extensions_dir=extensions_dir)

    assert result is True
    assert not (existing / "old.txt").exists()
    assert (existing / "gemini-extension.json").exists()
```

- [ ] **Step 2: Run formatter tests and confirm the failure**

Run:

```bash
pytest staging/r3/skills/plugin-pack/augur/tests/test_gemini_formatter.py -q
```

Expected: FAIL because `formatters.gemini` does not exist.

- [ ] **Step 3: Add the formatter directory hook**

In `staging/r3/skills/plugin-pack/scripts/formatters/base.py`, add this method before `write_manifest()`:

```python
    def plugin_dir(self, output_dir: Path) -> Path:
        """Return the plugin root directory for this formatter's assembled output."""
        return output_dir / "plugins" / "augur"
```

- [ ] **Step 4: Implement `GeminiFormatter`**

Create `staging/r3/skills/plugin-pack/scripts/formatters/gemini.py`:

```python
"""Gemini formatter - produces Gemini CLI extension structure."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from .base import BaseFormatter

logger = logging.getLogger(__name__)


class GeminiFormatter(BaseFormatter):
    """Format assembled plugin output as a Gemini CLI extension."""

    def plugin_dir(self, output_dir: Path) -> Path:
        return output_dir / "extensions" / "augur"

    def write_manifest(self, plugin_dir: Path, version: str) -> None:
        manifest = {
            "name": "augur",
            "version": version,
            "description": (
                "Your second brain -- personal knowledge, career, finance, "
                "health, and productivity powered by Augur"
            ),
            "contextFileName": "GEMINI.md",
        }
        (plugin_dir / "gemini-extension.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

        context = """# Augur Extension

Augur is a local-first second brain exposed through the augur MCP server.

Use `/augur:ask` for reflective second-brain questions.
Use `/augur:search` for knowledge retrieval.
Use `/augur:save` for saving knowledge or assets.

Operational project commands such as `/dev-loops` may also be available from project-local Gemini skill wrappers.
"""
        (plugin_dir / "GEMINI.md").write_text(context, encoding="utf-8")

    def write_mcp_config(self, plugin_dir: Path, project_root: Path, python_path: str) -> None:
        manifest_path = plugin_dir / "gemini-extension.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = {"name": "augur", "contextFileName": "GEMINI.md"}

        manifest["mcpServers"] = {
            "augur": {
                "command": python_path,
                "args": ["-m", "augur_mcp", "--client-id", "gemini"],
                "cwd": str(project_root),
                "env": {
                    "AUGUR_ROOT": str(project_root),
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONPATH": f"{project_root}:{project_root}/src/mcp",
                },
            }
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def write_marketplace(self, output_dir: Path, version: str) -> None:
        return None

    def write_skills(self, plugin_dir: Path, skills: dict[str, str]) -> None:
        for name, content in skills.items():
            skill_dir = plugin_dir / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def write_commands(self, plugin_dir: Path, commands: dict[str, dict]) -> None:
        commands_dir = plugin_dir / "commands" / "augur"
        commands_dir.mkdir(parents=True, exist_ok=True)
        for name, cmd in commands.items():
            prompt = f"{cmd['body']}\n\nUser arguments:\n{{{{args}}}}\n"
            content = (
                f"description = {json.dumps(cmd['description'])}\n"
                f"prompt = {json.dumps(prompt)}\n"
            )
            (commands_dir / f"{name}.toml").write_text(content, encoding="utf-8")

    def install(
        self,
        output_dir: Path,
        version: str,
        *,
        extensions_dir: Path | None = None,
    ) -> bool:
        plugin_source = output_dir / "extensions" / "augur"
        if not plugin_source.exists():
            logger.warning("Gemini extension source not found at %s", plugin_source)
            return False

        if extensions_dir is None:
            extensions_dir = Path.home() / ".gemini" / "extensions"

        target = extensions_dir / "augur"
        if target.exists() or target.is_symlink():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(plugin_source, target)
        logger.info("  Installed augur Gemini extension: %s", target)
        return True
```

- [ ] **Step 5: Export the formatter**

In `staging/r3/skills/plugin-pack/scripts/formatters/__init__.py`, add:

```python
from .gemini import GeminiFormatter
```

Replace `__all__` with:

```python
__all__ = ["BaseFormatter", "CodexFormatter", "CoworkFormatter", "GeminiFormatter"]
```

- [ ] **Step 6: Run formatter tests and confirm they pass**

Run:

```bash
pytest staging/r3/skills/plugin-pack/augur/tests/test_gemini_formatter.py -q
```

Expected: all tests PASS.

- [ ] **Step 7: Run existing formatter tests for regressions**

Run:

```bash
pytest staging/r3/skills/plugin-pack/augur/tests/test_codex_formatter.py staging/r3/skills/plugin-pack/augur/tests/test_cowork_formatter.py -q
```

Expected: all tests PASS.

- [ ] **Step 8: Commit the formatter checkpoint**

Run:

```bash
git add staging/r3/skills/plugin-pack/augur/tests/test_gemini_formatter.py staging/r3/skills/plugin-pack/scripts/formatters/base.py staging/r3/skills/plugin-pack/scripts/formatters/gemini.py staging/r3/skills/plugin-pack/scripts/formatters/__init__.py
git commit -m "feat(plugin-pack): add gemini formatter"
```

## Task 3: Register Gemini in Plugin Assembler

**Files:**
- Modify: `staging/r3/skills/plugin-pack/augur/tests/test_assembler.py`
- Modify: `staging/r3/skills/plugin-pack/scripts/plugin_assembler.py`

- [ ] **Step 1: Write failing assembler tests**

In `staging/r3/skills/plugin-pack/augur/tests/test_assembler.py`, add:

```python
def test_should_include_skill_gemini():
    from plugin_assembler import should_include_skill
    from profiles import GEMINI_PROFILE

    assert should_include_skill("career", {"x-augur-hub": "career"}, GEMINI_PROFILE) is True
    assert should_include_skill("dev-test", {"x-augur-hub": "command"}, GEMINI_PROFILE) is True
    assert should_include_skill("dev-merge", {"x-augur-hub": "command"}, GEMINI_PROFILE) is True
    assert should_include_skill("auto-lint", {"x-augur-hub": "adaptive"}, GEMINI_PROFILE) is False
    assert should_include_skill("ai", {"x-augur-hub": "brain"}, GEMINI_PROFILE) is False
```

Add:

```python
def test_assemble_gemini(tmp_path):
    from plugin_assembler import assemble

    output, version = assemble("gemini", tmp_path / "gemini-out")
    assert isinstance(version, str)
    assert (output / "extensions" / "augur" / "gemini-extension.json").exists()
    assert (output / "extensions" / "augur" / "GEMINI.md").exists()
    assert (output / "extensions" / "augur" / "commands" / "augur" / "ask.toml").exists()

    manifest = json.loads(
        (output / "extensions" / "augur" / "gemini-extension.json").read_text()
    )
    server = manifest["mcpServers"]["augur"]
    assert server["args"] == ["-m", "augur_mcp", "--client-id", "gemini"]
```

- [ ] **Step 2: Run assembler tests and confirm the failure**

Run:

```bash
pytest staging/r3/skills/plugin-pack/augur/tests/test_assembler.py -q
```

Expected: FAIL with `Unknown target: 'gemini'`.

- [ ] **Step 3: Register the formatter and output directory hook**

In `staging/r3/skills/plugin-pack/scripts/plugin_assembler.py`, replace:

```python
from formatters import CoworkFormatter, CodexFormatter
```

with:

```python
from formatters import CoworkFormatter, CodexFormatter, GeminiFormatter
```

Replace `_FORMATTERS` with:

```python
_FORMATTERS: dict[str, type[BaseFormatter]] = {
    "cowork": CoworkFormatter,
    "codex": CodexFormatter,
    "gemini": GeminiFormatter,
}
```

Replace:

```python
    plugin_dir = output_dir / "plugins" / "augur"
```

with:

```python
    plugin_dir = formatter.plugin_dir(output_dir)
```

Update the module docstring usage block to include:

```python
    python skills/plugin-pack/scripts/plugin_assembler.py --target gemini [--install]
```

Update the `assemble()` docstring target sentence to:

```python
        target: Target platform name ("cowork", "codex", or "gemini").
```

- [ ] **Step 4: Run assembler tests and confirm they pass**

Run:

```bash
pytest staging/r3/skills/plugin-pack/augur/tests/test_assembler.py -q
```

Expected: all tests PASS.

- [ ] **Step 5: Run profile and formatter tests together**

Run:

```bash
pytest staging/r3/skills/plugin-pack/augur/tests/test_profiles.py staging/r3/skills/plugin-pack/augur/tests/test_gemini_formatter.py staging/r3/skills/plugin-pack/augur/tests/test_assembler.py -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit the assembler checkpoint**

Run:

```bash
git add staging/r3/skills/plugin-pack/augur/tests/test_assembler.py staging/r3/skills/plugin-pack/scripts/plugin_assembler.py
git commit -m "feat(plugin-pack): register gemini target"
```

## Task 4: Add Gemini Plugin Sync Adapter

**Files:**
- Create: `skills/ai/scripts/sync_agents/adapters/gemini_plugin.py`
- Modify: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`

- [ ] **Step 1: Write failing adapter lifecycle tests**

In `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`, add this import near the existing plugin adapter imports:

```python
from sync_agents.adapters.gemini_plugin import GeminiPluginAdapter
```

Add `GeminiPluginAdapter` to `ALL_ADAPTERS` after `CodexPluginAdapter`.

Add this test class after `TestCodexPluginAdapter`:

```python
class TestGeminiPluginAdapter:
    def test_plugin_pack_scripts_dir_raises_when_missing(self, tmp_path):
        from sync_agents.adapters.gemini_plugin import _plugin_pack_scripts_dir

        with pytest.raises(FileNotFoundError, match="plugin-pack skill payload not found"):
            _plugin_pack_scripts_dir(tmp_path)

    def test_adapter_name(self):
        assert GeminiPluginAdapter().adapter_name == "gemini_plugin"

    def test_managed_files_include_build_and_extension(self, tmp_path):
        with patch("sync_agents.adapters.gemini_plugin.Path.home", return_value=tmp_path / "home"):
            files = GeminiPluginAdapter().get_managed_files()

        assert str(Path.home() / ".gemini" / "extensions" / "augur") not in files
        assert str(tmp_path / "home" / ".gemini" / "extensions" / "augur") + "/" in files
        assert any(path.endswith("/build/gemini/") for path in files)

    def test_cleanup_noop_when_nothing_present(self, tmp_path):
        adapter = GeminiPluginAdapter()
        adapter._output_dir = tmp_path / "build" / "gemini"
        with patch("sync_agents.adapters.gemini_plugin.Path.home", return_value=tmp_path / "home"):
            assert adapter.cleanup(dry_run=True) == []

    def test_cleanup_removes_build_and_extension(self, tmp_path):
        adapter = GeminiPluginAdapter()
        adapter._output_dir = tmp_path / "build" / "gemini"
        adapter._output_dir.mkdir(parents=True)
        (adapter._output_dir / "marker.txt").write_text("build")

        home = tmp_path / "home"
        extension = home / ".gemini" / "extensions" / "augur"
        extension.mkdir(parents=True)
        (extension / "marker.txt").write_text("extension")

        with patch("sync_agents.adapters.gemini_plugin.Path.home", return_value=home):
            deleted = adapter.cleanup()

        assert str(adapter._output_dir) + "/" in deleted
        assert str(extension) + "/" in deleted
        assert not adapter._output_dir.exists()
        assert not extension.exists()

    def test_generate_mcp_config_calls_assembler(self, tmp_path, monkeypatch):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "plugin_assembler.py").write_text(
            "calls = []\n"
            "def assemble(target, output_dir):\n"
            "    calls.append(('assemble', target, str(output_dir)))\n"
            "    return output_dir, '1.0.0'\n"
            "def install(target, output_dir, version):\n"
            "    calls.append(('install', target, str(output_dir), version))\n"
            "    return True\n",
            encoding="utf-8",
        )

        adapter = GeminiPluginAdapter()
        adapter._output_dir = tmp_path / "build" / "gemini"
        monkeypatch.setattr(
            "sync_agents.adapters.gemini_plugin._plugin_pack_scripts_dir",
            lambda project_root: scripts_dir,
        )
        monkeypatch.setattr("sync_agents.adapters.gemini_plugin.PROJECT_ROOT", tmp_path)

        sys.modules.pop("plugin_assembler", None)
        try:
            adapter.generate_mcp_config()
            import plugin_assembler

            assert plugin_assembler.calls == [
                ("assemble", "gemini", str(adapter._output_dir)),
                ("install", "gemini", str(adapter._output_dir), "1.0.0"),
            ]
        finally:
            sys.modules.pop("plugin_assembler", None)
```

- [ ] **Step 2: Run adapter tests and confirm the failure**

Run:

```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "GeminiPluginAdapter or adapter_names_are_unique" -q
```

Expected: FAIL because `sync_agents.adapters.gemini_plugin` does not exist.

- [ ] **Step 3: Implement the adapter**

Create `skills/ai/scripts/sync_agents/adapters/gemini_plugin.py`:

```python
"""sync_agents/adapters/gemini_plugin.py - Gemini CLI extension bundle adapter."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .base import BaseAdapter
from ..constants import PROJECT_ROOT


def _plugin_pack_scripts_dir(project_root: Path) -> Path:
    from src.lib.staged_skill_catalog import find_skill_dir

    skill_dir = find_skill_dir(project_root, "plugin-pack")
    if skill_dir is None:
        raise FileNotFoundError(
            "plugin-pack skill payload not found in live skills or staged releases"
        )
    return skill_dir / "scripts"


class GeminiPluginAdapter(BaseAdapter):
    """Assembles and installs the Augur extension bundle for Gemini CLI."""

    adapter_name = "gemini_plugin"

    def __init__(self) -> None:
        super().__init__()
        self._output_dir = PROJECT_ROOT / "build" / "gemini"

    @staticmethod
    def _extension_dir() -> Path:
        return Path.home() / ".gemini" / "extensions" / "augur"

    def get_managed_files(self) -> list[str]:
        return [
            str(self._output_dir) + "/",
            str(self._extension_dir()) + "/",
        ]

    def detect_installed(self) -> bool:
        return shutil.which("gemini") is not None or (Path.home() / ".gemini").is_dir()

    def sync_rules(self, content: str) -> None:
        pass

    def sync_memory(self) -> None:
        pass

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        deleted: list[str] = []

        if self._output_dir.exists():
            deleted.append(str(self._output_dir) + "/")
            if not dry_run:
                shutil.rmtree(self._output_dir)

        extension_dir = self._extension_dir()
        if extension_dir.exists() or extension_dir.is_symlink():
            deleted.append(str(extension_dir) + "/")
            if not dry_run:
                if extension_dir.is_dir() and not extension_dir.is_symlink():
                    shutil.rmtree(extension_dir)
                else:
                    extension_dir.unlink()

        return deleted

    def generate_mcp_config(self) -> None:
        """Assemble and install the Gemini CLI extension bundle."""
        scripts_path = str(_plugin_pack_scripts_dir(PROJECT_ROOT))
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)

        from plugin_assembler import assemble, install

        output, version = assemble("gemini", self._output_dir)
        install("gemini", output, version)
```

- [ ] **Step 4: Run adapter tests and confirm the new adapter passes**

Run:

```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "GeminiPluginAdapter or adapter_names_are_unique" -q
```

Expected: selected tests PASS.

- [ ] **Step 5: Commit the adapter checkpoint**

Run:

```bash
git add skills/ai/scripts/sync_agents/adapters/gemini_plugin.py skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py
git commit -m "feat(sync-agents): add gemini plugin adapter"
```

## Task 5: Register Gemini Plugin Adapter

**Files:**
- Modify: `skills/ai/scripts/sync_agents/adapters/__init__.py`
- Modify: `skills/ai/scripts/sync_agents/engine.py`
- Modify: `skills/ai/scripts/sync_agents/__init__.py`
- Modify: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`

- [ ] **Step 1: Write failing registration tests**

In `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`, add:

```python
def test_engine_lists_gemini_plugin_adapter():
    from sync_agents.engine import _get_all_adapters

    names = [adapter.adapter_name for adapter in _get_all_adapters()]
    assert "gemini_plugin" in names


def test_gemini_plugin_adapter_is_gated_with_gemini_group():
    from sync_agents.engine import _ADAPTER_TO_GROUP

    assert _ADAPTER_TO_GROUP["gemini_plugin"] == "gemini"
```

- [ ] **Step 2: Run registration tests and confirm the failure**

Run:

```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "engine_lists_gemini_plugin_adapter or gemini_plugin_adapter_is_gated" -q
```

Expected: FAIL because the engine does not instantiate or gate the adapter yet.

- [ ] **Step 3: Export the adapter**

In `skills/ai/scripts/sync_agents/adapters/__init__.py`, add:

```python
from .gemini_plugin import GeminiPluginAdapter
```

Add `"GeminiPluginAdapter"` to `__all__`.

- [ ] **Step 4: Register the adapter in the engine**

In `skills/ai/scripts/sync_agents/engine.py`, add this to `_ADAPTER_TO_GROUP`:

```python
    "gemini_plugin": "gemini",
```

Inside `_get_all_adapters()`, add:

```python
    from .adapters.gemini_plugin import GeminiPluginAdapter
```

Add `GeminiPluginAdapter()` immediately after `GeminiAdapter()` in the returned list.

- [ ] **Step 5: Add CLI client filter support**

In `skills/ai/scripts/sync_agents/__init__.py`, add `"gemini-plugin"` to `_SYNC_CLIENTS` after `"gemini"`.

- [ ] **Step 6: Run registration tests and confirm they pass**

Run:

```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k "engine_lists_gemini_plugin_adapter or gemini_plugin_adapter_is_gated or GeminiPluginAdapter or adapter_names_are_unique" -q
```

Expected: selected tests PASS.

- [ ] **Step 7: Run the full adapter lifecycle test file**

Run:

```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -q
```

Expected: all tests PASS.

- [ ] **Step 8: Commit the registration checkpoint**

Run:

```bash
git add skills/ai/scripts/sync_agents/adapters/__init__.py skills/ai/scripts/sync_agents/engine.py skills/ai/scripts/sync_agents/__init__.py skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py
git commit -m "feat(sync-agents): register gemini plugin adapter"
```

## Task 6: Update Plugin-Pack Documentation and Dashboard Metadata

**Files:**
- Modify: `staging/r3/skills/plugin-pack/SKILL.md`
- Modify: `apps/dashboard/app/api/plugin-pack/route.ts`

- [ ] **Step 1: Update plugin-pack skill documentation**

In `staging/r3/skills/plugin-pack/SKILL.md`, update the frontmatter description to:

```yaml
description: 'Assemble and install Augur as a plugin for Claude Desktop (Cowork),
  OpenAI Codex, and Gemini CLI. Covers: plugin pack, targets'
```

Add `gemini` to `x-augur-tags`.

Replace the target table with:

```markdown
| Target | Platform | Output Format |
|--------|----------|---------------|
| `cowork` | Claude Desktop | `.claude-plugin/plugin.json` + marketplace |
| `codex` | OpenAI Codex | `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json` |
| `gemini` | Gemini CLI | `gemini-extension.json` + `~/.gemini/extensions/augur` |
```

Replace the usage block with:

````markdown
```
/plugin-pack --target cowork           # Assemble for Claude Desktop
/plugin-pack --target codex            # Assemble for Codex
/plugin-pack --target gemini           # Assemble for Gemini CLI
/plugin-pack --target gemini --install # Assemble and install
```
````

Replace workflow step 3 with:

```markdown
3. Let the formatter write the platform-specific plugin bundle for Cowork, Codex, or Gemini.
```

Replace the validation checklist first item with:

```markdown
- Confirm the target is correct before packaging (`cowork`, `codex`, or `gemini`).
```

In the directory structure block, replace the formatter list with:

```markdown
│   ├── formatters/
│   │   ├── base.py              # BaseFormatter ABC
│   │   ├── cowork.py            # Claude Desktop formatter
│   │   ├── codex.py             # Codex plugin formatter
│   │   └── gemini.py            # Gemini CLI extension formatter
```

- [ ] **Step 2: Update read-only dashboard API metadata**

In `apps/dashboard/app/api/plugin-pack/route.ts`, add this object to `TARGETS`:

```ts
  {
    id: "gemini",
    platform: "Gemini CLI",
    output: "gemini-extension.json + ~/.gemini/extensions/augur",
  },
```

Replace this pipeline string:

```ts
  "formatters/* write the final Cowork or Codex manifest bundle.",
```

with:

```ts
  "formatters/* write the final Cowork, Codex, or Gemini manifest bundle.",
```

- [ ] **Step 3: Run documentation and TypeScript syntax checks**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path("staging/r3/skills/plugin-pack/SKILL.md").read_text(encoding="utf-8")
assert "`gemini` | Gemini CLI" in text
assert "gemini.py" in text
route = Path("apps/dashboard/app/api/plugin-pack/route.ts").read_text(encoding="utf-8")
assert 'id: "gemini"' in route
assert "Cowork, Codex, or Gemini" in route
PY
```

Expected: command exits 0.

Run:

```bash
pnpm --filter dashboard exec tsc --noEmit --pretty false
```

Expected: TypeScript exits 0. If the dashboard package does not expose TypeScript dependencies in this checkout, record the exact package-manager error and run the aggregate pytest and assembler checks in Task 7.

- [ ] **Step 4: Commit the documentation checkpoint**

Run:

```bash
git add staging/r3/skills/plugin-pack/SKILL.md apps/dashboard/app/api/plugin-pack/route.ts
git commit -m "docs(plugin-pack): document gemini target"
```

## Task 7: End-to-End Verification

**Files:**
- Verify: all files changed by Tasks 1-6

- [ ] **Step 1: Run plugin-pack tests**

Run:

```bash
pytest staging/r3/skills/plugin-pack/augur/tests/test_profiles.py staging/r3/skills/plugin-pack/augur/tests/test_assembler.py staging/r3/skills/plugin-pack/augur/tests/test_codex_formatter.py staging/r3/skills/plugin-pack/augur/tests/test_cowork_formatter.py staging/r3/skills/plugin-pack/augur/tests/test_gemini_formatter.py -q
```

Expected: all tests PASS.

- [ ] **Step 2: Run sync adapter tests**

Run:

```bash
pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -q
```

Expected: all tests PASS.

- [ ] **Step 3: Assemble Gemini extension from the CLI**

Run:

```bash
rm -rf /tmp/augur-gemini-extension-test
python staging/r3/skills/plugin-pack/scripts/plugin_assembler.py --target gemini --output /tmp/augur-gemini-extension-test
```

Expected output includes:

```text
Assembled gemini plugin
```

- [ ] **Step 4: Verify generated Gemini extension files**

Run:

```bash
test -f /tmp/augur-gemini-extension-test/extensions/augur/gemini-extension.json
test -f /tmp/augur-gemini-extension-test/extensions/augur/GEMINI.md
test -f /tmp/augur-gemini-extension-test/extensions/augur/commands/augur/ask.toml
test -d /tmp/augur-gemini-extension-test/extensions/augur/skills
```

Expected: all commands exit 0.

- [ ] **Step 5: Verify manifest and TOML content**

Run:

```bash
python3 - <<'PY'
import json
import tomllib
from pathlib import Path

root = Path("/tmp/augur-gemini-extension-test/extensions/augur")
manifest = json.loads((root / "gemini-extension.json").read_text(encoding="utf-8"))
assert manifest["name"] == "augur"
assert manifest["contextFileName"] == "GEMINI.md"
assert manifest["mcpServers"]["augur"]["args"] == ["-m", "augur_mcp", "--client-id", "gemini"]

ask = tomllib.loads((root / "commands" / "augur" / "ask.toml").read_text(encoding="utf-8"))
assert ask["description"] == "Ask your second brain any question"
assert "{{args}}" in ask["prompt"]
PY
```

Expected: command exits 0.

- [ ] **Step 6: Run targeted sync client command**

Run:

```bash
python3 -m skills.ai.scripts.sync_agents sync all gemini-plugin
```

Expected: command exits 0 and logs Gemini plugin assembly or install activity. If Gemini CLI is not installed, the adapter still assembles because installation targets `~/.gemini/extensions/augur`; verify cleanup scope before committing.

- [ ] **Step 7: Inspect git state**

Run:

```bash
git status --short
```

Expected: only intentional source, test, generated ADR index, and documentation files are modified.

- [ ] **Step 8: Final implementation commit**

If previous task commits were skipped during inline execution, make one focused implementation commit:

```bash
git add staging/r3/skills/plugin-pack/scripts/profiles.py \
  staging/r3/skills/plugin-pack/scripts/plugin_assembler.py \
  staging/r3/skills/plugin-pack/scripts/formatters/base.py \
  staging/r3/skills/plugin-pack/scripts/formatters/__init__.py \
  staging/r3/skills/plugin-pack/scripts/formatters/gemini.py \
  staging/r3/skills/plugin-pack/augur/tests/test_profiles.py \
  staging/r3/skills/plugin-pack/augur/tests/test_assembler.py \
  staging/r3/skills/plugin-pack/augur/tests/test_gemini_formatter.py \
  skills/ai/scripts/sync_agents/adapters/gemini_plugin.py \
  skills/ai/scripts/sync_agents/adapters/__init__.py \
  skills/ai/scripts/sync_agents/engine.py \
  skills/ai/scripts/sync_agents/__init__.py \
  skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py \
  staging/r3/skills/plugin-pack/SKILL.md \
  apps/dashboard/app/api/plugin-pack/route.ts \
  docs/generated/adr-index.md
git commit -m "feat(plugin-pack): add gemini extension target"
```

- [ ] **Step 9: Mark ADR-553 implemented after verification**

After the implementation commit is created and verification passes, run:

```bash
python3 - <<'PY'
import subprocess
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter

adr = Path("~/Projects/Au-docs/adrs/ADR-553-gemini-extension-support-for-augur-plugin-pack.md")
metadata, body = parse_frontmatter(adr)
metadata["status"] = "Implemented"
metadata["implemented_date"] = "2026-04-19"
metadata["implementation_commits"] = [
    subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
]
write_frontmatter(adr, metadata, body)
PY
```

Then run:

```bash
python3 .github/scripts/generate_adr_index.py
```

Expected: `docs/generated/adr-index.md` includes ADR-553 as Implemented.
