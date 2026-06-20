from pathlib import Path
from subprocess import run

from scripts import port_release_into_main
from scripts.port_release_into_main import port_release_payload


def test_port_release_payload_copies_skills_and_pages(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    release_root = tmp_path / "vault" / "drafts" / "staging" / "r2"

    (release_root / "skills" / "content").mkdir(parents=True)
    (release_root / "skills" / "content" / "SKILL.md").write_text(
        "---\nname: content\n---\n",
        encoding="utf-8",
    )
    (release_root / "pages" / "apps" / "dashboard" / "app" / "life" / "content").mkdir(parents=True)
    (release_root / "pages" / "apps" / "dashboard" / "app" / "life" / "content" / "page.tsx").write_text(
        "export default null\n",
        encoding="utf-8",
    )
    (release_root / "manifest.md").write_text(
        "---\nrelease: r2\nmotive: creation and ingestion expansion\nskills:\n  - content\npages:\n  - apps/dashboard/app/life/content/page.tsx\nprerequisites: []\n---\n",
        encoding="utf-8",
    )

    port_release_payload(repo_root=repo_root, release="r2", release_root=release_root, consume=False)

    assert (repo_root / "project-brain" / "capabilities" / "skills" / "content" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == ("---\nname: content\n---\n")
    assert (repo_root / "apps" / "dashboard" / "app" / "life" / "content" / "page.tsx").read_text(
        encoding="utf-8"
    ) == "export default null\n"
    assert (release_root / "skills" / "content").exists()


def test_port_release_payload_consume_removes_release_folder(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    release_root = tmp_path / "vault" / "drafts" / "staging" / "r3"
    (release_root / "skills").mkdir(parents=True)
    (release_root / "pages").mkdir()
    (release_root / "manifest.md").write_text(
        "---\nrelease: r3\nmotive: admin builder\nskills: []\npages: []\nprerequisites: []\n---\n",
        encoding="utf-8",
    )

    port_release_payload(repo_root=repo_root, release="r3", release_root=release_root, consume=True)

    assert not release_root.exists()


def test_port_release_payload_defaults_to_vault_staging_root(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    release_root = tmp_path / "vault" / "drafts" / "staging" / "r2"
    (release_root / "skills" / "content").mkdir(parents=True)
    (release_root / "skills" / "content" / "SKILL.md").write_text(
        "---\nname: content\n---\n",
        encoding="utf-8",
    )
    (release_root / "pages").mkdir(parents=True, exist_ok=True)
    (release_root / "manifest.md").write_text(
        "---\nrelease: r2\nmotive: creation and ingestion expansion\nskills:\n  - content\npages: []\nprerequisites: []\n---\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(port_release_into_main, "get_vault_staging_dir", lambda: release_root.parent)

    payload = port_release_into_main.port_release_payload(repo_root=repo_root, release="r2")

    assert payload.release_root == release_root
    assert (repo_root / "project-brain" / "capabilities" / "skills" / "content" / "SKILL.md").exists()


def test_port_release_cli_ports_staged_payload(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    release_root = tmp_path / "vault" / "drafts" / "staging" / "r2"
    (release_root / "skills" / "content").mkdir(parents=True)
    (release_root / "skills" / "content" / "SKILL.md").write_text(
        "---\nname: content\n---\n",
        encoding="utf-8",
    )
    (release_root / "pages").mkdir(parents=True, exist_ok=True)
    (release_root / "manifest.md").write_text(
        "---\nrelease: r2\nmotive: creation and ingestion expansion\nskills:\n  - content\npages: []\nprerequisites: []\n---\n",
        encoding="utf-8",
    )

    result = run(
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

    assert result.returncode == 0
    assert str(release_root) in result.stdout
    assert (repo_root / "project-brain" / "capabilities" / "skills" / "content" / "SKILL.md").exists()
