"""Tests for auto-flow-optimizer scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import yaml

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "flow_optimizer.py"
_SPEC = importlib.util.spec_from_file_location("flow_optimizer_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_scan_no_mismatches(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []


def test_scan_detects_fire_with_llm_description(tmp_path: Path) -> None:
    """fire dispatch with LLM-suggesting description gets flagged."""
    skill_root = tmp_path / "skills"
    action_dir = skill_root / "browse" / "augur" / "actions"
    _write(
        action_dir / "summarize.yaml",
        yaml.dump({
            "id": "summarize-page",
            "dispatch": "fire",
            "description": "Generate an AI summary of the page content",
        }),
    )
    with patch.object(mod, "get_all_client_skill_dirs", return_value=[skill_root]):
        result = mod.scan(_ctx(tmp_path))
    mismatch = [i for i in result.issues if i["action"] == "dispatch-mismatch"]
    assert len(mismatch) == 1
    assert mismatch[0]["current_dispatch"] == "fire"


def test_scan_detects_ide_with_simple_description(tmp_path: Path) -> None:
    """ide dispatch with simple CRUD description gets flagged."""
    skill_root = tmp_path / "skills"
    action_dir = skill_root / "browse" / "augur" / "actions"
    _write(
        action_dir / "refresh.yaml",
        yaml.dump({
            "id": "refresh-data",
            "dispatch": "ide",
            "description": "Refresh the list of items",
        }),
    )
    with patch.object(mod, "get_all_client_skill_dirs", return_value=[skill_root]):
        result = mod.scan(_ctx(tmp_path))
    mismatch = [i for i in result.issues if i["action"] == "dispatch-mismatch"]
    assert len(mismatch) == 1
    assert mismatch[0]["suggestion"] == "fire"


def test_scan_skips_overview_action_with_llm_description(tmp_path: Path) -> None:
    """Descriptive *-overview cards are NOT flagged even with an LLM-ish description.

    Overview actions are Browse cards that summarize a skill: they navigate to a page
    and never dispatch an LLM/backend call, so dispatch: fire is correct. Their
    description necessarily mentions the AI skill being described, which used to trip
    the heuristic (23 false positives in the real repo). Regression guard.
    """
    skill_root = tmp_path / "skills"
    action_dir = skill_root / "audio-ingest" / "augur" / "actions"
    _write(
        action_dir / "audio-ingest-overview.yaml",
        yaml.dump({
            "id": "audio-ingest-overview",
            "dispatch": "fire",
            "page": "/workspace/audio-ingest",
            "description": (
                "View Audio modality that classifies recordings with an LLM agent "
                "step and writes structured note cards."
            ),
        }),
    )
    with patch.object(mod, "get_all_client_skill_dirs", return_value=[skill_root]):
        result = mod.scan(_ctx(tmp_path))
    mismatch = [i for i in result.issues if i["action"] == "dispatch-mismatch"]
    assert mismatch == []


def test_scan_skips_page_only_card_without_executable(tmp_path: Path) -> None:
    """Structural signal: a page-navigating card with no executable key is descriptive.

    Even without the -overview suffix, a fire action that only carries a `page` and no
    command/mcp_tool/callable is descriptive navigation and must not be flagged.
    """
    skill_root = tmp_path / "skills"
    action_dir = skill_root / "browse" / "augur" / "actions"
    _write(
        action_dir / "intro-card.yaml",
        yaml.dump({
            "id": "intro-card",
            "dispatch": "fire",
            "page": "/browse",
            "description": "View a card that uses Claude to analyze your vault.",
        }),
    )
    with patch.object(mod, "get_all_client_skill_dirs", return_value=[skill_root]):
        result = mod.scan(_ctx(tmp_path))
    mismatch = [i for i in result.issues if i["action"] == "dispatch-mismatch"]
    assert mismatch == []


def test_scan_still_flags_executable_fire_with_llm_description(tmp_path: Path) -> None:
    """A genuine executable action (has a command) with fire + LLM description IS flagged.

    The descriptive-action exclusion must not blind the heuristic to real mismatches:
    an action that dispatches real work (carries `command`) is still subject to the
    dispatch-mode check even if it also declares a `page`.
    """
    skill_root = tmp_path / "skills"
    action_dir = skill_root / "browse" / "augur" / "actions"
    _write(
        action_dir / "summarize.yaml",
        yaml.dump({
            "id": "summarize-page",
            "dispatch": "fire",
            "command": "/summarize",
            "page": "/browse",
            "description": "Generate an AI summary of the page content",
        }),
    )
    with patch.object(mod, "get_all_client_skill_dirs", return_value=[skill_root]):
        result = mod.scan(_ctx(tmp_path))
    mismatch = [i for i in result.issues if i["action"] == "dispatch-mismatch"]
    assert len(mismatch) == 1
    assert mismatch[0]["action_id"] == "summarize-page"
    assert mismatch[0]["current_dispatch"] == "fire"


def test_fix_dry_run(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path, dry_run=True), [{"action": "dispatch-mismatch"}])
    assert isinstance(result, FixResult)
    assert result.success is True
    assert "Dry run" in result.summary
