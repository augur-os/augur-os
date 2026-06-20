import subprocess
import sys
from pathlib import Path

from scripts.check_notes_depth import (
    DEFAULT_ALLOWED_DEEP_DIRS,
    NotesDepthIssue,
    check_notes_depth,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_notes_depth.py"


def _write(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("sample\n", encoding="utf-8")


def test_reports_skinny_deep_folder_chain(tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    _write(notes_root / "augur" / "advisor" / "design" / "docs" / "architecture" / "llm.md")

    issues = check_notes_depth(notes_root)

    assert (
        NotesDepthIssue(
            kind="skinny_deep_dir",
            path=Path("augur/advisor/design"),
            message="Directory has exactly one file descendant at depth 3.",
        )
        in issues
    )


def test_reports_repeated_notes_layer(tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    _write(notes_root / "career" / "notes" / "learning" / "scoring-formulas.md")

    issues = check_notes_depth(notes_root)

    assert (
        NotesDepthIssue(
            kind="repeated_notes_layer",
            path=Path("career/notes/learning/scoring-formulas.md"),
            message="Path contains a nested 'notes' folder under the notes root.",
        )
        in issues
    )


def test_reports_config_and_template_dirs_under_notes(tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    _write(notes_root / "lifestyle" / "ideas" / "_config" / "config.yaml")
    _write(notes_root / "lifestyle" / "notes" / "_templates" / "idea.md")

    issues = check_notes_depth(notes_root)

    assert (
        NotesDepthIssue(
            kind="config_under_notes",
            path=Path("lifestyle/ideas/_config/config.yaml"),
            message="Config or template path lives under notes.",
        )
        in issues
    )
    assert (
        NotesDepthIssue(
            kind="config_under_notes",
            path=Path("lifestyle/notes/_templates/idea.md"),
            message="Config or template path lives under notes.",
        )
        in issues
    )


def test_allows_dense_collection_dirs(tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    _write(notes_root / "lifestyle" / "recipe-manager" / "recipes" / "to-try" / "one.md")
    _write(notes_root / "lifestyle" / "recipe-manager" / "recipes" / "to-try" / "two.md")

    issues = check_notes_depth(notes_root, allowed_deep_dirs=DEFAULT_ALLOWED_DEEP_DIRS)

    assert not [issue for issue in issues if issue.kind == "skinny_deep_dir"]


def test_allows_apple_reminders_sync_list_dirs(tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    _write(notes_root / "lifestyle" / "apple" / "reminders" / "shopping-list" / "unsectioned.md")

    issues = check_notes_depth(notes_root, allowed_deep_dirs=DEFAULT_ALLOWED_DEEP_DIRS)

    assert (
        NotesDepthIssue(
            kind="skinny_deep_dir",
            path=Path("lifestyle/apple/reminders/shopping-list"),
            message="Directory has exactly one file descendant at depth 4.",
        )
        not in issues
    )


def test_allows_apple_voice_memo_queue_dir(tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    _write(notes_root / "lifestyle" / "apple" / "voice-memos" / "inbox.yaml")

    issues = check_notes_depth(notes_root, allowed_deep_dirs=DEFAULT_ALLOWED_DEEP_DIRS)

    assert (
        NotesDepthIssue(
            kind="skinny_deep_dir",
            path=Path("lifestyle/apple/voice-memos"),
            message="Directory has exactly one file descendant at depth 3.",
        )
        not in issues
    )


def test_missing_notes_root_reports_missing_issue(tmp_path: Path) -> None:
    notes_root = tmp_path / "missing-notes"

    issues = check_notes_depth(notes_root)

    assert issues == [
        NotesDepthIssue(
            kind="missing_notes_root",
            path=Path("."),
            message="Notes root does not exist.",
        )
    ]


def test_invalid_notes_root_reports_invalid_issue(tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    notes_root.write_text("not a directory\n", encoding="utf-8")

    issues = check_notes_depth(notes_root)

    assert issues == [
        NotesDepthIssue(
            kind="invalid_notes_root",
            path=Path("."),
            message="Notes root is not a directory.",
        )
    ]


def test_cli_reports_missing_notes_root(tmp_path: Path) -> None:
    notes_root = tmp_path / "missing-notes"

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--notes-root", str(notes_root)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Strict notes-depth issues:" in result.stdout
    assert "missing_notes_root: . - Notes root does not exist." in result.stdout


def test_cli_reports_invalid_notes_root(tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    notes_root.write_text("not a directory\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--notes-root", str(notes_root)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Strict notes-depth issues:" in result.stdout
    assert "invalid_notes_root: . - Notes root is not a directory." in result.stdout
