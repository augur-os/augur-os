from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = next(
    (
        p
        for p in Path(__file__).resolve().parents
        if (p / "pyproject.toml").exists() and (p / ".git").exists()
    ),
    Path(__file__).resolve().parents[-1],
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

mod = importlib.import_module("skills.auto-skill-quality.scripts.skill_migrate_ops")
classify_skill_directory = mod.classify_skill_directory


def test_standard_skill_bundle_does_not_require_augur_frontmatter(
    tmp_path: Path,
) -> None:
    root = tmp_path / "apple"
    (root / "apple-notes").mkdir(parents=True)
    (root / "DESCRIPTION.md").write_text(
        "# Apple\n\nStandard bundle.\n",
        encoding="utf-8",
    )
    (root / "apple-notes" / "SKILL.md").write_text(
        "# Apple Notes\n\nUse local CLI.\n",
        encoding="utf-8",
    )

    result = classify_skill_directory(root)

    assert result.mode == "standard"
    assert "x-augur-hub" not in result.required_metadata
