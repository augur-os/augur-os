from pathlib import Path
from subprocess import run

from scripts import manage_porting_payload


def test_init_release_creates_expected_payload_layout(tmp_path: Path) -> None:
    drafts_root = tmp_path / "vault" / "drafts" / "staging"
    result = run(
        [
            "python3",
            "scripts/manage_porting_payload.py",
            "init-release",
            "--drafts-root",
            str(drafts_root),
            "--release",
            "later",
            "--motive",
            "unscheduled backlog",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert (drafts_root / "later" / "skills").is_dir()
    assert (drafts_root / "later" / "pages").is_dir()
    assert (drafts_root / "later" / "manifest.md").exists()


def test_init_release_defaults_to_vault_staging_root(tmp_path: Path, monkeypatch) -> None:
    drafts_root = tmp_path / "vault" / "drafts" / "staging"
    monkeypatch.setattr(manage_porting_payload, "get_vault_staging_dir", lambda: drafts_root)

    rc = manage_porting_payload.main(
        [
            "init-release",
            "--release",
            "later",
            "--motive",
            "unscheduled backlog",
        ]
    )

    assert rc == 0
    assert (drafts_root / "later" / "skills").is_dir()
    assert (drafts_root / "later" / "pages").is_dir()
    assert (drafts_root / "later" / "manifest.md").exists()


def test_validate_release_rejects_unexpected_payload_files(tmp_path: Path) -> None:
    release_root = tmp_path / "vault" / "drafts" / "staging" / "r3"
    (release_root / "skills").mkdir(parents=True)
    (release_root / "pages").mkdir()
    (release_root / "manifest.md").write_text(
        "---\nrelease: r3\nmotive: admin\nskills: []\npages: []\nprerequisites: []\n---\n",
        encoding="utf-8",
    )
    (release_root / "junk.md").write_text("bad\n", encoding="utf-8")

    result = run(
        [
            "python3",
            "scripts/manage_porting_payload.py",
            "validate-release",
            "--release-root",
            str(release_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "unexpected files" in result.stderr


def test_end_to_end_stage_then_port(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    drafts_root = tmp_path / "vault" / "drafts" / "staging"

    init = run(
        [
            "python3",
            "scripts/manage_porting_payload.py",
            "init-release",
            "--drafts-root",
            str(drafts_root),
            "--release",
            "r2",
            "--motive",
            "creation and ingestion expansion",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert init.returncode == 0

    release_root = drafts_root / "r2"
    (release_root / "skills" / "content").mkdir(parents=True)
    (release_root / "skills" / "content" / "SKILL.md").write_text(
        "---\nname: content\n---\n",
        encoding="utf-8",
    )

    validate = run(
        [
            "python3",
            "scripts/manage_porting_payload.py",
            "validate-release",
            "--release-root",
            str(release_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert validate.returncode == 0

    port = run(
        [
            "python3",
            "scripts/port_release_into_main.py",
            "--repo-root",
            str(repo_root),
            "--release",
            "r2",
            "--release-root",
            str(release_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert port.returncode == 0
    assert (repo_root / "project-brain" / "capabilities" / "skills" / "content" / "SKILL.md").exists()
