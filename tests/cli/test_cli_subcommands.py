"""Tests verifying CLI subcommand integration (ADR-260)."""

import argparse
import sys
from types import SimpleNamespace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestCLISubcommands:
    def test_cli_uses_discover_subcommands(self):
        """src/cli.py must import and call discover_subcommands."""
        cli_source = (PROJECT_ROOT / "src" / "cli.py").read_text()
        assert "discover_subcommands" in cli_source
        assert "from src.cli_plugins import discover_subcommands" in cli_source

    def test_cli_has_subcommand_routing(self):
        """src/cli.py must route via args.func for subcommands."""
        cli_source = (PROJECT_ROOT / "src" / "cli.py").read_text()
        assert "args.func" in cli_source

    def test_cli_has_discover_handler(self):
        """src/cli.py has a discover handler (hardcoded or plugin-contributed)."""
        cli_source = (PROJECT_ROOT / "src" / "cli.py").read_text()
        assert "discover" in cli_source

    def test_cli_registers_builtin_init_before_plugin_discovery(self):
        """src/cli.py must register built-in aug init before plugin discovery."""
        cli_source = (PROJECT_ROOT / "src" / "cli.py").read_text()
        assert "_register_builtin_subcommands" in cli_source
        assert "init_project_brain" in cli_source
        assert 'subparsers.add_parser("init"' in cli_source
        assert "format_project_init_launch_journey" in cli_source
        assert "_register_builtin_subcommands(subparsers)" in cli_source
        assert cli_source.index("_register_builtin_subcommands(subparsers)") < cli_source.index(
            "discover_subcommands(subparsers)"
        )

    def test_discover_plugin_exists(self):
        """At least one canonical skill must expose register_subcommands()."""
        candidates = [
            path
            for path in sorted(PROJECT_ROOT.glob("project-brain/capabilities/skills/*/scripts/mcp/__init__.py"))
            if "register_subcommands" in path.read_text()
        ]
        assert candidates
        source = candidates[0].read_text()
        assert "register_subcommands" in source

    def test_plugin_init_collision_skips_only_colliding_subcommand(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Plugin init collision must not drop later non-conflicting subcommands."""
        from src.cli import _register_builtin_subcommands
        from src.cli_plugins import discover_subcommands

        plugin = tmp_path / "project-brain" / "capabilities" / "skills" / "collision" / "scripts" / "mcp"
        plugin.mkdir(parents=True)
        (plugin / "__init__.py").write_text(
            "def register_subcommands(subparsers):\n"
            "    subparsers.add_parser('init')\n"
            "    subparsers.add_parser('after-init')\n",
            encoding="utf-8",
        )

        import src.config.paths as paths

        monkeypatch.setattr(paths, "get_project_root", lambda: tmp_path)

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="tool")
        _register_builtin_subcommands(subparsers)
        builtin_init = subparsers._name_parser_map["init"]

        assert discover_subcommands(subparsers) == 1
        assert subparsers._name_parser_map["init"] is builtin_init
        assert "after-init" in subparsers._name_parser_map

    def test_handle_init_prints_created_inventory_only_result_by_default(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        """_handle_init defaults to inventory-only init without projection sync."""
        from src.cli import _handle_init, _register_builtin_subcommands
        import src.lib.brain_init as brain_init

        calls = []
        project_root = tmp_path / "firmware"
        brain_root = project_root / "project-brain"

        def fake_init_project_brain(project, run_sync=True):
            calls.append((project, run_sync))
            return SimpleNamespace(
                brain_id="project-firmware",
                brain_root=brain_root,
                project_root=project_root,
                created=True,
                sync_returncode=None,
                inventory_path=brain_root / "config" / "inventory" / "ai-artifacts.json",
                inventory_count=3,
                inventory_warning_count=1,
            )

        monkeypatch.setattr(brain_init, "init_project_brain", fake_init_project_brain)

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="tool")
        _register_builtin_subcommands(subparsers)
        args = parser.parse_args(["init", "--project", str(project_root)])

        code = _handle_init(args)

        assert code == 0
        assert calls == [(project_root, False)]
        output = capsys.readouterr().out.splitlines()
        assert output == [
            "First value: AI artifact inventory",
            "Project brain: project-firmware",
            f"Metadata folder: {brain_root}",
            f"Attached folder: {project_root}",
            "AI artifact inventory: 3 records, 1 warnings",
            f"Inventory path: {(brain_root / 'config' / 'inventory' / 'ai-artifacts.json').as_posix()}",
            "Chosen-folder writes: project-brain metadata and inventory only",
            (
                "Existing vendor files: read-only inventory; not adopted, rewritten, "
                "merged, deleted, or projected over"
            ),
            "Browse: http://localhost:3000/browse",
            "Next action: Ask Augur about this project",
            (
                "Prompt: What should I know about this project based on the AI setup "
                "and inventory Augur just found? Answer only; do not save or retain "
                "anything unless I ask."
            ),
        ]

    def test_handle_init_accepts_no_sync_as_compatible_noop(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Existing --no-sync wording remains accepted and leaves sync disabled."""
        from src.cli import _handle_init, _register_builtin_subcommands
        import src.lib.brain_init as brain_init

        calls = []
        project_root = tmp_path / "firmware"
        brain_root = project_root / "project-brain"

        def fake_init_project_brain(project, run_sync=True):
            calls.append((project, run_sync))
            return SimpleNamespace(
                brain_id="project-firmware",
                brain_root=brain_root,
                project_root=project_root,
                created=True,
                sync_returncode=None,
                inventory_path=None,
                inventory_count=0,
                inventory_warning_count=0,
            )

        monkeypatch.setattr(brain_init, "init_project_brain", fake_init_project_brain)

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="tool")
        _register_builtin_subcommands(subparsers)
        args = parser.parse_args(["init", "--project", str(project_root), "--no-sync"])

        code = _handle_init(args)

        assert code == 0
        assert calls == [(project_root, False)]

    def test_handle_init_returns_nonzero_sync_code(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        """_handle_init reports and returns non-zero projection sync exits with --sync."""
        from src.cli import _handle_init, _register_builtin_subcommands
        import src.lib.brain_init as brain_init

        calls = []
        project_root = tmp_path / "firmware"
        brain_root = project_root / "project-brain"

        def fake_init_project_brain(project, run_sync=True):
            calls.append((project, run_sync))
            return SimpleNamespace(
                brain_id="project-firmware",
                brain_root=brain_root,
                project_root=project_root,
                created=False,
                sync_returncode=17,
                inventory_path=brain_root / "config" / "inventory" / "ai-artifacts.json",
                inventory_count=0,
                inventory_warning_count=0,
            )

        monkeypatch.setattr(brain_init, "init_project_brain", fake_init_project_brain)

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="tool")
        _register_builtin_subcommands(subparsers)
        args = parser.parse_args(["init", "--project", str(project_root), "--sync"])

        code = _handle_init(args)

        assert code == 17
        assert calls == [(project_root, True)]
        output = capsys.readouterr().out.splitlines()
        assert output == [
            "First value: AI artifact inventory",
            "Project brain: project-firmware",
            f"Metadata folder: {brain_root}",
            f"Attached folder: {project_root}",
            "AI artifact inventory: 0 records, 0 warnings",
            f"Inventory path: {(brain_root / 'config' / 'inventory' / 'ai-artifacts.json').as_posix()}",
            (
                "Chosen-folder writes: project-brain metadata, inventory, and "
                "requested generated AI-client projections"
            ),
            (
                "Existing vendor files: read-only inventory; not adopted, rewritten, "
                "merged, deleted, or projected over"
            ),
            "Browse: http://localhost:3000/browse",
            "Next action: Ask Augur about this project",
            (
                "Prompt: What should I know about this project based on the AI setup "
                "and inventory Augur just found? Answer only; do not save or retain "
                "anything unless I ask."
            ),
            "Projection sync exit code: 17",
        ]

    def test_new_subcommands_discovered(self):
        """note-url + wiki (ingest) and sync (ai) must be discoverable.

        Guards the bare-load regression: cli_plugins loads each skill's
        scripts/mcp/__init__.py WITHOUT package context, so a top-level relative
        import (which ingest used to have) silently drops the subcommand. This
        test fails if any of these vault-tier-bundle CLI surfaces stop loading.
        """
        from src.cli_plugins import discover_subcommands

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="tool")
        discover_subcommands(subparsers)
        names = set(subparsers._name_parser_map.keys())
        for expected in ("note-url", "wiki", "sync"):
            assert expected in names, f"{expected} subcommand not discovered (bare-load regression?)"
