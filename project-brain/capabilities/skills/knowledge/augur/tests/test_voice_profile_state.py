from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from profile_state import (  # noqa: E402
    InterviewState,
    about_me_path,
    append_answer,
    archive_dir,
    archive_state,
    get_about_me_age_days,
    load_state,
    save_state,
    state_path,
    write_about_me,
)
from src.lib.frontmatter_utils import parse_frontmatter  # noqa: E402


def test_language_paths_are_scoped_under_profile_language(tmp_path: Path) -> None:
    assert state_path(tmp_path, "en") == tmp_path / "profile" / "en" / "interview-in-progress.yaml"
    assert about_me_path(tmp_path, "he") == tmp_path / "profile" / "he" / "about-me.md"
    assert archive_dir(tmp_path, "he") == tmp_path / "profile" / "he" / "archive"


def test_interview_state_roundtrip_preserves_language(tmp_path: Path) -> None:
    path = tmp_path / "state.yaml"
    state = append_answer(
        InterviewState.fresh(language="he"),
        category="voice",
        question="Q1",
        answer="A1",
    )

    save_state(path, state)
    loaded = load_state(path)

    assert loaded is not None
    assert loaded.language == "he"
    assert loaded.answered == 1
    assert loaded.percentage == 1
    assert loaded.qa_pairs[0].q == "Q1"


def test_archive_state_suffixes_same_day_collisions(tmp_path: Path) -> None:
    state_file = tmp_path / "interview-in-progress.yaml"
    target_archive = tmp_path / "archive"
    target_archive.mkdir()
    (target_archive / "interview-2026-05-13.yaml").write_text("first\n", encoding="utf-8")
    state_file.write_text("second\n", encoding="utf-8")

    archived = archive_state(state_file, target_archive, run_date_iso="2026-05-13")

    assert archived == target_archive / "interview-2026-05-13-2.yaml"
    assert archived.read_text(encoding="utf-8") == "second\n"
    assert not state_file.exists()


def test_get_about_me_age_days_uses_mtime(tmp_path: Path) -> None:
    profile = tmp_path / "about-me.md"
    profile.write_text("# Profile\n", encoding="utf-8")
    old = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
    os.utime(profile, (old, old))

    assert get_about_me_age_days(profile) == 10


def test_write_about_me_adds_voice_profile_frontmatter(tmp_path: Path) -> None:
    profile = tmp_path / "about-me.md"

    write_about_me(profile, "# About me\n\nDirect and concise.\n", language="en")

    frontmatter, body = parse_frontmatter(profile, include_sidecar_config=False)
    assert frontmatter["title"] == "Voice Profile (EN)"
    assert frontmatter["language"] == "en"
    assert frontmatter["_hub"] == "brain"
    assert frontmatter["_content_kind"] == "voice-profile"
    assert body.lstrip().startswith("# About me")
