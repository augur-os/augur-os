from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


REQUIRED_READMES = [
    "README.md",
    "knowledge/memory/entries/README.md",
    "knowledge/notes/README.md",
    "knowledge/notes/roles/README.md",
    "knowledge/sources/README.md",
    "knowledge/wiki/README.md",
    "capabilities/skills/README.md",
    "config/README.md",
]


def _frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n"), f"{path} must start with YAML frontmatter"
    _, frontmatter, _body = content.split("---", 2)
    parsed = yaml.safe_load(frontmatter)
    assert isinstance(parsed, dict), f"{path} frontmatter must parse as a mapping"
    return parsed


def test_project_brain_required_readmes_exist() -> None:
    root = PROJECT_ROOT / "project-brain"

    for rel_path in REQUIRED_READMES:
        path = root / rel_path
        assert path.is_file(), f"missing project-brain contract file: {path}"


def test_project_brain_readmes_have_frontmatter_and_scope() -> None:
    root = PROJECT_ROOT / "project-brain"

    for rel_path in REQUIRED_READMES:
        metadata = _frontmatter(root / rel_path)
        assert metadata["brain_scope"] == "project"
        assert metadata["status"] in {"active", "inactive"}


def test_project_brain_contract_names_canonical_skill_root() -> None:
    root_readme = (PROJECT_ROOT / "project-brain" / "README.md").read_text(encoding="utf-8")

    assert "project-brain/capabilities/skills/" in root_readme
