"""Tests for auto-markdowns scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "markdown_ops.py"
_SPEC = importlib.util.spec_from_file_location("markdown_ops_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-markdowns"


def test_scan_no_tsx_files(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert isinstance(result, ScanResult)
    assert result.issues == []


def test_scan_d0_detects_missing_template(tmp_path: Path) -> None:
    """d0 flags runAction calls with no prompt template file."""
    _write(
        tmp_path / "skills" / "browse" / "augur" / "dashboard" / "page.tsx",
        """
        function handler() {
            runAction({ id: 'test-action', label: 'Test' });
        }
        """,
    )
    with patch.object(mod, "get_all_client_skill_dirs", return_value=[tmp_path / "skills" / "browse"]):
        result = mod.scan(_ctx(tmp_path, difficulty=0))
    missing = [i for i in result.issues if i["type"] == "missing_template"]
    assert len(missing) == 1
    assert missing[0]["action_id"] == "test-action"


def test_scan_d0_no_issue_when_template_exists(tmp_path: Path) -> None:
    """d0 passes when prompt template exists for action."""
    _write(
        tmp_path / "skills" / "browse" / "augur" / "dashboard" / "page.tsx",
        """runAction({ id: 'do-thing', label: 'Do' });""",
    )
    _write(
        tmp_path / "skills" / "browse" / "assets" / "seeds" / "prompts" / "do-thing.md",
        "---\naction: do-thing\n---\n<instructions>Do stuff</instructions>\n<task>The task</task>\n",
    )
    with patch.object(mod, "get_all_client_skill_dirs", return_value=[tmp_path / "skills" / "browse"]):
        result = mod.scan(_ctx(tmp_path, difficulty=0))
    missing = [i for i in result.issues if i["type"] == "missing_template"]
    assert missing == []


def test_check_template_structure_missing_sections(tmp_path: Path) -> None:
    """_check_template_structure flags missing instructions/task sections."""
    md = tmp_path / "template.md"
    md.write_text("---\naction: test\n---\nJust some text.\n")
    missing = mod._check_template_structure(md)
    assert "instructions" in missing
    assert "task" in missing


def test_check_template_structure_complete(tmp_path: Path) -> None:
    md = tmp_path / "template.md"
    md.write_text("---\naction: test\n---\n<instructions>Do X</instructions>\n<task>Y</task>\n")
    missing = mod._check_template_structure(md)
    assert missing == []
