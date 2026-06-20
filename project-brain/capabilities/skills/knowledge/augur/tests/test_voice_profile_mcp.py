from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
MCP_DIR = SCRIPTS_DIR / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from profile_state import InterviewState, append_answer, save_state  # noqa: E402
from tools_voice_profile import (  # noqa: E402
    _profile_get_age_sync,
    _profile_read_sync,
    _profile_status_all_sync,
    _profile_status_sync,
    _profile_write_sync,
)


def test_profile_status_returns_both_languages_when_omitted(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    en_state = vault / "profile" / "en" / "interview-in-progress.yaml"
    en_state.parent.mkdir(parents=True)
    state = InterviewState.fresh(language="en")
    for idx in range(12):
        state = append_answer(state, category="voice", question=f"Q{idx}", answer=f"A{idx}")
    save_state(en_state, state)

    he_about = vault / "profile" / "he" / "about-me.md"
    he_about.parent.mkdir(parents=True)
    he_about.write_text("# Hebrew profile\n", encoding="utf-8")

    result = _profile_status_all_sync(vault_dir=vault)

    assert result["en"]["in_progress"] is True
    assert result["en"]["answered"] == 12
    assert result["he"]["about_me"]["exists"] is True
    assert result["he"]["complete"] is True


def test_profile_status_single_language_empty(tmp_path: Path) -> None:
    result = _profile_status_sync(
        language="en",
        state_file=tmp_path / "missing.yaml",
        about_me_file=tmp_path / "missing.md",
    )

    assert result["success"] is True
    assert result["language"] == "en"
    assert result["in_progress"] is False
    assert result["about_me"]["exists"] is False
    assert result["answered"] == 0


def test_profile_read_strips_frontmatter_and_returns_metadata(tmp_path: Path) -> None:
    about_me = tmp_path / "about-me.md"
    about_me.write_text("---\ntitle: Voice Profile\n---\n# Body\n", encoding="utf-8")

    result = _profile_read_sync(language="en", about_me_file=about_me)

    assert result["success"] is True
    assert result["language"] == "en"
    assert result["content"] == "# Body\n"
    assert result["frontmatter"]["title"] == "Voice Profile"
    assert result["metadata"]["age_days"] == 0


def test_profile_read_missing_includes_language() -> None:
    result = _profile_read_sync(language="he", about_me_file=Path("/no/such/about-me.md"))

    assert result["success"] is False
    assert result["error"] == "profile_not_found"
    assert result["language"] == "he"


def test_profile_write_archives_same_language_state_only(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    en_state = vault / "profile" / "en" / "interview-in-progress.yaml"
    he_state = vault / "profile" / "he" / "interview-in-progress.yaml"
    en_state.parent.mkdir(parents=True)
    he_state.parent.mkdir(parents=True)
    save_state(en_state, InterviewState.fresh(language="en"))
    save_state(he_state, InterviewState.fresh(language="he"))

    result = _profile_write_sync(
        content="# English\n",
        mode="full",
        language="en",
        about_me_file=vault / "profile" / "en" / "about-me.md",
        state_file=en_state,
        target_archive_dir=vault / "profile" / "en" / "archive",
    )

    assert result["success"] is True
    assert result["language"] == "en"
    assert not en_state.exists()
    assert he_state.exists()
    assert list((vault / "profile" / "en" / "archive").glob("interview-*.yaml"))


def test_profile_get_age_missing_returns_exists_false(tmp_path: Path) -> None:
    result = _profile_get_age_sync(language="he", about_me_file=tmp_path / "missing.md")

    assert result == {"success": True, "language": "he", "exists": False}
