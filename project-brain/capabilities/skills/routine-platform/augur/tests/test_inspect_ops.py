"""Auto-generated importability test for inspect_ops."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_inspect_ops_importable():
    """Verify that inspect_ops can be imported without errors."""
    import importlib
    mod = importlib.import_module("inspect_ops")
    assert mod is not None


def test_inspect_counts_shared_vault_skill_files(tmp_path: Path):
    import importlib

    mod = importlib.import_module("inspect_ops")
    skill_md = tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("---\nx-augur-hub: dev\n---\n# Demo\n", encoding="utf-8")

    count, _total_bytes, total_lines = mod._count_skill_md_stats(tmp_path)

    assert count == 1
    assert total_lines == 4


def test_inspect_counts_shared_vault_ops_modules(tmp_path: Path):
    import importlib

    mod = importlib.import_module("inspect_ops")
    ops_file = tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "scripts" / "demo_ops.py"
    ops_file.parent.mkdir(parents=True)
    ops_file.write_text("name = 'demo'\n", encoding="utf-8")

    assert mod._count_ops_modules(tmp_path) == 1


def test_inspect_finds_shared_vault_orphan_skills(tmp_path: Path):
    import importlib

    mod = importlib.import_module("inspect_ops")
    (tmp_path / "project-brain" / "capabilities" / "skills" / "empty").mkdir(parents=True)

    assert mod._find_orphan_skills(tmp_path) == ["empty"]
