from __future__ import annotations

import re
from pathlib import Path

import yaml

SKILL_ROOT = Path(__file__).resolve().parents[1]
SUBSKILL = "retrieval-eval-harness"


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}
    return yaml.safe_load(match.group(1)) or {}


def test_standard_bundle_shape() -> None:
    assert (SKILL_ROOT / "DESCRIPTION.md").is_file()
    assert (SKILL_ROOT / SUBSKILL / "SKILL.md").is_file()
    assert not (SKILL_ROOT / "SKILL.md").exists()
    assert not (SKILL_ROOT / "augur").exists()
    assert not (SKILL_ROOT / "scripts" / "mcp").exists()


def test_standard_subskill_has_no_augur_metadata() -> None:
    data = _frontmatter(SKILL_ROOT / SUBSKILL / "SKILL.md")
    assert data["description"].startswith("Use when")
    assert not any(key.startswith("x-augur") for key in data)
