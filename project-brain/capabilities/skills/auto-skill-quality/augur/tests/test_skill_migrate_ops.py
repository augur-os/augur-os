"""Tests for skill_migrate_ops scanner."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from src.lib.ops_protocol import OpsContext

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

mod = importlib.import_module("skills.auto-skill-quality.scripts.skill_migrate_ops")


def test_skill_migrate_ops_importable():
    """Verify that skill_migrate_ops can be imported without errors."""
    assert mod is not None


def test_standard_bundle_not_flagged_as_missing_skill_md(tmp_path: Path, monkeypatch) -> None:
    """Standard-skill bundles (DESCRIPTION.md + nested sub-skill SKILL.md, no top-level
    SKILL.md) must NOT produce a missing-skill-md finding.  A plain leaf dir with neither
    file MUST still produce one."""
    skills_dir = tmp_path / "project-brain" / "capabilities" / "skills"

    # Standard bundle: DESCRIPTION.md + sub/SKILL.md, no top-level SKILL.md
    bundle_dir = skills_dir / "local-audio-processing"
    (bundle_dir / "speech-to-text").mkdir(parents=True)
    (bundle_dir / "DESCRIPTION.md").write_text(
        "# Local Audio Processing\n\nStandard audio bundle.\n", encoding="utf-8"
    )
    (bundle_dir / "speech-to-text" / "SKILL.md").write_text(
        "# Speech to Text\n\nUse local Whisper.\n", encoding="utf-8"
    )

    # Plain leaf dir: neither DESCRIPTION.md nor SKILL.md — should still be flagged
    leaf_dir = skills_dir / "plain-leaf-skill"
    leaf_dir.mkdir(parents=True)

    monkeypatch.setattr(mod, "_get_skills_dir", lambda: skills_dir)

    result = mod.scan(OpsContext(project_root=tmp_path, difficulty=0, config={}))

    violations = [i["violation"] for i in result.issues]
    details = [i["detail"] for i in result.issues]

    # The standard bundle must NOT be flagged
    assert not any(
        "local-audio-processing" in d for d in details if "missing SKILL.md" in d
    ), "Standard bundle must not be flagged as missing SKILL.md"

    # The plain leaf MUST be flagged
    assert any(
        "plain-leaf-skill" in d and "missing SKILL.md" in d for d in details
    ), "Plain leaf dir without SKILL.md must still be flagged"
