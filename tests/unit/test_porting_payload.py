from pathlib import Path

from src.lib.porting_payload import (
    build_release_payload,
    parse_release_manifest,
    STAGED_RELEASES,
    validate_payload_tree,
)


def test_staged_releases_match_future_release_model() -> None:
    assert STAGED_RELEASES == ("r1", "r2", "r3", "r4", "later")


def test_parse_release_manifest_reads_required_fields(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.md"
    manifest_path.write_text(
        """---
release: r2
motive: creation and ingestion expansion
skills:
  - content
  - import
pages:
  - apps/dashboard/app/life/content/page.tsx
prerequisites:
  - dashboard mount registry already supports staged page import
---

# R2 Payload
""",
        encoding="utf-8",
    )

    manifest = parse_release_manifest(manifest_path)

    assert manifest.release == "r2"
    assert manifest.skills == ["content", "import"]
    assert manifest.pages == ["apps/dashboard/app/life/content/page.tsx"]


def test_validate_payload_tree_rejects_non_payload_files(tmp_path: Path) -> None:
    release_root = tmp_path / "vault" / "drafts" / "staging" / "r2"
    (release_root / "skills").mkdir(parents=True)
    (release_root / "pages").mkdir()
    (release_root / "manifest.md").write_text(
        "---\nrelease: r2\nmotive: test\nskills: []\npages: []\nprerequisites: []\n---\n",
        encoding="utf-8",
    )
    (release_root / "notes.txt").write_text("not allowed\n", encoding="utf-8")

    try:
        validate_payload_tree(release_root)
    except ValueError as exc:
        assert "unexpected files" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_build_release_payload_collects_skills_pages_and_manifest(tmp_path: Path) -> None:
    release_root = tmp_path / "vault" / "drafts" / "staging" / "r3"
    (release_root / "skills" / "validator").mkdir(parents=True)
    (release_root / "pages" / "command").mkdir(parents=True)
    (release_root / "skills" / "validator" / "SKILL.md").write_text(
        "---\nname: validator\n---\n",
        encoding="utf-8",
    )
    (release_root / "pages" / "command" / "validator.tsx").write_text(
        "export default null\n",
        encoding="utf-8",
    )
    (release_root / "manifest.md").write_text(
        "---\nrelease: r3\nmotive: admin builder\nskills:\n  - validator\npages:\n  - command/validator.tsx\nprerequisites: []\n---\n",
        encoding="utf-8",
    )

    payload = build_release_payload(release_root)

    assert payload.release == "r3"
    assert payload.skill_paths == [release_root / "skills" / "validator"]
    assert payload.page_paths == [release_root / "pages" / "command" / "validator.tsx"]
