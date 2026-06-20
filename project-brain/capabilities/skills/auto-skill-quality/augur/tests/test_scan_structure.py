"""Tests for scan_structure scanner."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

mod = importlib.import_module("skills.auto-skill-quality.scripts.scan_structure")
scan_skills = mod.scan_skills


def test_scan_structure_importable():
    """Verify that scan_structure can be imported without errors."""
    assert mod is not None


def test_standard_bundle_not_flagged_as_missing_skill_md(tmp_path: Path) -> None:
    """Standard-skill bundles (DESCRIPTION.md + nested sub-skill SKILL.md, no top-level
    SKILL.md) must NOT produce a missing-SKILL.md finding.  A plain leaf dir with neither
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

    violations = scan_skills(skills_dir)
    details = [v.get("detail", "") + " " + v.get("skill", "") for v in violations]

    # The standard bundle must NOT be flagged for missing SKILL.md
    assert not any(
        "local-audio-processing" in d and "SKILL.md" in d for d in details
    ), "Standard bundle must not be flagged as missing SKILL.md"

    # The plain leaf MUST be flagged
    assert any(
        "plain-leaf-skill" in d and "SKILL.md" in d for d in details
    ), "Plain leaf dir without SKILL.md must still be flagged"
