"""Regression tests for skill importer ZIP extraction hardening."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest


def _load_skill_importer_module():
    # Canonical location after the mcp-app-factory + frontend + page-builder merge.
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "apps" / "dashboard" / "scripts" / "skill-scripts" / "skill_importer.py"
    spec = importlib.util.spec_from_file_location("dashboard_skill_importer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_zip_rejects_path_traversal(tmp_path: Path) -> None:
    module = _load_skill_importer_module()
    zip_path = tmp_path / "malicious.zip"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../escape.txt", "owned")

    with pytest.raises(ValueError, match="Unsafe ZIP member path"):
        module.extract_zip(zip_path, tmp_path / "extract")


def test_extract_zip_allows_valid_entries(tmp_path: Path) -> None:
    module = _load_skill_importer_module()
    zip_path = tmp_path / "plugin.zip"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("my-plugin/SKILL.md", "# Test skill")

    extracted_path = module.extract_zip(zip_path, tmp_path / "extract")

    assert extracted_path.name == "my-plugin"
    assert (extracted_path / "SKILL.md").read_text(encoding="utf-8") == "# Test skill"
