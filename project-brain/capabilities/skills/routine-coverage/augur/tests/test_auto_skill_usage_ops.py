"""Auto-generated importability test for auto_skill_usage_ops."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_auto_skill_usage_ops_importable():
    """Verify that auto_skill_usage_ops can be imported without errors."""
    import importlib
    mod = importlib.import_module("auto_skill_usage_ops")
    assert mod is not None


def test_discover_skills_uses_shared_vault(tmp_path: Path):
    import importlib

    mod = importlib.import_module("auto_skill_usage_ops")
    skill_md = tmp_path / "project-brain" / "capabilities" / "skills" / "knowledge" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("---\nname: knowledge\n---\n", encoding="utf-8")

    assert mod._discover_skills(tmp_path) == ["knowledge"]


def test_skill_usage_maps_command_wrappers_to_source_skills(tmp_path: Path):
    import importlib
    from collections import Counter

    mod = importlib.import_module("auto_skill_usage_ops")
    skill_md = tmp_path / "project-brain" / "capabilities" / "skills" / "augur-core" / "SKILL.md"
    command_md = skill_md.parent / "commands" / "adr.md"
    command_md.parent.mkdir(parents=True)
    skill_md.write_text(
        "---\n"
        "name: augur-core\n"
        "x-augur-commands:\n"
        "  - id: ask\n"
        "    type: workflow\n"
        "---\n",
        encoding="utf-8",
    )
    command_md.write_text("---\nx-augur-export-command: true\n---\n# /adr\n", encoding="utf-8")

    skills = mod._discover_skills(tmp_path)
    aliases = mod._skill_aliases(tmp_path, skills)
    counts = mod._canonicalize_counts(Counter({"adr": 2, "augur:ask": 1}), aliases, skills)

    assert counts == Counter({"augur-core": 3})
