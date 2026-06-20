"""Tests for ops/project_index.py — project index rebuild detection.

Validates the reindex-project ops command: detecting when the project index
is stale relative to source metadata (SKILL.md, config sidecars, ADRs), and
triggering a rebuild via unified_indexer.py.
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.lib.ops_protocol import OpsContext

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "project_index.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location("ai_project_index", SCRIPT_PATH)
project_index = importlib.util.module_from_spec(_spec)
sys.modules["ai_project_index"] = project_index
assert _spec.loader is not None
_spec.loader.exec_module(project_index)


def _make_ctx(tmp_path: Path, **overrides) -> OpsContext:
    defaults = {"project_root": tmp_path, "difficulty": 0, "dry_run": False}
    defaults.update(overrides)
    return OpsContext(**defaults)


# ---------------------------------------------------------------------------
# Module-level sanity
# ---------------------------------------------------------------------------


class TestModuleInterface:
    def test_name_attribute(self):
        assert project_index.name == "reindex-project"

    def test_scan_is_callable(self):
        assert callable(project_index.scan)

    def test_fix_is_callable(self):
        assert callable(project_index.fix)


# ---------------------------------------------------------------------------
# _latest_input_mtime
# ---------------------------------------------------------------------------


class TestLatestInputMtime:
    def test_no_files_returns_zero(self, tmp_path: Path):
        with patch.object(project_index, "get_all_client_skill_dirs", return_value=[]), \
             patch.object(project_index, "get_adr_dir", return_value=tmp_path / "missing-adrs"):
            assert project_index._latest_input_mtime(tmp_path) == 0.0

    def test_picks_up_skill_md(self, tmp_path: Path):
        skills_dir = tmp_path / ".claude" / "skills"
        skill = skills_dir / "test" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# Test Skill", encoding="utf-8")
        with patch.object(project_index, "get_all_client_skill_dirs", return_value=[skills_dir]), \
             patch.object(project_index, "get_adr_dir", return_value=tmp_path / "missing-adrs"):
            mtime = project_index._latest_input_mtime(tmp_path)
        assert mtime > 0

    def test_picks_up_skill_config_sidecar(self, tmp_path: Path):
        skills_dir = tmp_path / ".claude" / "skills"
        skill_dir = skills_dir / "test"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test\nx-augur-config-file: config.yaml\n---\n",
            encoding="utf-8",
        )
        sidecar = skill_dir / "config.yaml"
        sidecar.write_text("contributions:\n  pages: []\n", encoding="utf-8")

        with patch.object(project_index, "get_all_client_skill_dirs", return_value=[skills_dir]), \
             patch.object(project_index, "get_adr_dir", return_value=tmp_path / "missing-adrs"):
            mtime = project_index._latest_input_mtime(tmp_path)
        assert mtime == sidecar.stat().st_mtime

    def test_picks_up_adr(self, tmp_path: Path):
        adr = tmp_path / "docs" / "decisions" / "ADR-100.md"
        adr.parent.mkdir(parents=True)
        adr.write_text("# ADR-100", encoding="utf-8")
        with patch.object(project_index, "get_all_client_skill_dirs", return_value=[]), \
             patch.object(project_index, "get_adr_dir", return_value=adr.parent):
            mtime = project_index._latest_input_mtime(tmp_path)
        assert mtime > 0


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


class TestScan:
    def test_manifest_newer_than_inputs_returns_current(self, tmp_path: Path):
        rag_dir = tmp_path / "rag"
        meta = rag_dir / "_meta"
        meta.mkdir(parents=True)
        manifest = meta / "manifest.yaml"
        manifest.write_text("version: 1", encoding="utf-8")

        with patch.object(project_index, "get_rag_dir", return_value=rag_dir), \
             patch.object(project_index, "get_all_client_skill_dirs", return_value=[]):
            ctx = _make_ctx(tmp_path)
            result = project_index.scan(ctx)
            assert result.issues == []
            assert "current" in result.summary.lower()

    def test_no_manifest_returns_rebuild_needed(self, tmp_path: Path):
        rag_dir = tmp_path / "rag"

        skills_dir = tmp_path / ".claude" / "skills"
        skill = skills_dir / "test" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# Test", encoding="utf-8")

        with patch.object(project_index, "get_rag_dir", return_value=rag_dir), \
             patch.object(project_index, "get_all_client_skill_dirs", return_value=[skills_dir]):
            ctx = _make_ctx(tmp_path)
            result = project_index.scan(ctx)
            assert len(result.issues) == 1
            assert result.issues[0]["action"] == "rebuild-project-index"

    def test_stale_manifest_returns_rebuild_needed(self, tmp_path: Path):
        rag_dir = tmp_path / "rag"
        meta = rag_dir / "_meta"
        meta.mkdir(parents=True)
        manifest = meta / "manifest.yaml"
        manifest.write_text("version: 1", encoding="utf-8")
        # Make manifest old
        import os
        old_time = time.time() - 86400
        os.utime(manifest, (old_time, old_time))

        # Create a newer input
        time.sleep(0.05)
        skills_dir = tmp_path / ".claude" / "skills"
        skill = skills_dir / "test" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# Test", encoding="utf-8")

        with patch.object(project_index, "get_rag_dir", return_value=rag_dir), \
             patch.object(project_index, "get_all_client_skill_dirs", return_value=[skills_dir]):
            ctx = _make_ctx(tmp_path)
            result = project_index.scan(ctx)
            assert len(result.issues) == 1


# ---------------------------------------------------------------------------
# Fix
# ---------------------------------------------------------------------------


class TestFix:
    def test_dry_run(self, tmp_path: Path):
        ctx = _make_ctx(tmp_path, dry_run=True)
        result = project_index.fix(ctx, [{"action": "rebuild-project-index"}])
        assert result.success is True
        assert "Dry run" in result.summary

    def test_missing_indexer_script(self, tmp_path: Path):
        ctx = _make_ctx(tmp_path)
        result = project_index.fix(ctx, [{"action": "rebuild-project-index"}])
        assert result.success is False
        assert "src/lib/index/unified_indexer.py" in result.summary

    @patch("subprocess.run")
    def test_successful_reindex(self, mock_run, tmp_path: Path):
        indexer = tmp_path / "src" / "lib" / "index" / "unified_indexer.py"
        indexer.parent.mkdir(parents=True)
        indexer.write_text("# placeholder", encoding="utf-8")

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ctx = _make_ctx(tmp_path)
        result = project_index.fix(ctx, [{"action": "rebuild-project-index"}])
        assert result.success is True
        assert "rebuilt" in result.summary.lower()
        first_call = mock_run.call_args_list[0]
        assert first_call.args[0][1] == str(indexer)
        assert "--skip-contextualization" not in first_call.args[0]
        assert first_call.kwargs["timeout"] == 900

    @patch("subprocess.run")
    def test_reindex_honors_configured_timeout(self, mock_run, tmp_path: Path):
        indexer = tmp_path / "src" / "lib" / "index" / "unified_indexer.py"
        indexer.parent.mkdir(parents=True, exist_ok=True)
        indexer.write_text("# placeholder", encoding="utf-8")

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ctx = _make_ctx(tmp_path, config={"index_timeout": 30})
        result = project_index.fix(ctx, [{"action": "rebuild-project-index"}])

        assert result.success is True
        _args, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 30
