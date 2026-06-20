from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def test_save_thought_note_rejects_blank_body(tmp_path: Path) -> None:
    from skills.ingest.scripts import note_capture as mod

    result = mod.save_thought_note(vault_dir=tmp_path, body=" \n\t ")

    assert result == {"success": False, "error": "body is required"}


def test_save_thought_note_writes_card_and_refreshes_browse(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts import note_capture as mod
    from src.lib.ingest.note_index_refresh import NoteBrowseIndexRefresh

    calls: list[Path] = []

    def fake_refresh(*, vault_dir: Path) -> NoteBrowseIndexRefresh:
        calls.append(vault_dir)
        return NoteBrowseIndexRefresh(success=True, count=9)

    monkeypatch.setattr(mod, "refresh_notes_browse_index", fake_refresh)

    result = mod.save_thought_note(
        vault_dir=tmp_path,
        title="Notes Zone Verification",
        body="One canonical capture zone keeps browsing and commands aligned.",
        captured_at=datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
    )

    assert result["success"] is True
    assert result["deduplicated"] is False
    assert result["browse_index"] == {"success": True, "count": 9}
    assert calls == [tmp_path]
    path = Path(str(result["path"]))
    assert path.parent == tmp_path / "knowledge" / "notes"
    # naming spec 2026-06-12 Wave 3: date-free slug from title (max 6 words)
    assert path.name == "notes-zone-verification.md"


def test_save_thought_note_routes_to_project_brain_when_cwd_attached(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts import note_capture as mod
    from src.lib.ingest.note_index_refresh import NoteBrowseIndexRefresh
    from src.lib.brain_manifest import BrainManifest, ensure_brain_skeleton, write_brain_manifest
    from src.lib.brain_registry_io import save_registry
    from src.lib.brain_registry_models import Brain, BrainRegistry, BrainType, GitArrangement, GitConfig

    personal = tmp_path / "personal"
    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id="project-repo",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(project),
        ),
    )
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "personal": Brain(
                    id="personal",
                    type=BrainType.PERSONAL,
                    data_root=personal,
                    git=GitConfig(arrangement=GitArrangement.UNTRACKED),
                )
            },
        ),
        registry_path,
    )

    monkeypatch.setattr(
        mod,
        "refresh_notes_browse_index",
        lambda *, vault_dir: NoteBrowseIndexRefresh(success=True, count=1),
    )

    result = mod.save_thought_note(
        vault_dir=personal,
        body="Project-local capture should stay with the project brain.",
        captured_at=datetime(2026, 5, 21, 9, 30, tzinfo=UTC),
        cwd=project / "src",
        registry_path=registry_path,
    )

    assert result["success"] is True
    assert result["brain"] == {
        "id": "project-repo",
        "type": "project",
        "reason": "active-project",
        "mode": "direct",
    }
    path = Path(str(result["path"]))
    assert path.parent == brain_root / "knowledge" / "notes"
    assert not (personal / "knowledge" / "notes").exists()

    repeated = mod.save_thought_note(
        vault_dir=personal,
        body="Project-local capture should stay with the project brain.",
        captured_at=datetime(2026, 5, 21, 9, 30, tzinfo=UTC),
        cwd=project / "src",
        registry_path=registry_path,
    )

    assert repeated["deduplicated"] is True
    assert repeated["path"] == result["path"]
    assert repeated["brain"] == result["brain"]


def test_save_thought_note_surfaces_refresh_failure_after_save(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts import note_capture as mod
    from src.lib.ingest.note_index_refresh import NoteBrowseIndexRefresh

    calls: list[Path] = []

    def fake_refresh(*, vault_dir: Path) -> NoteBrowseIndexRefresh:
        calls.append(vault_dir)
        return NoteBrowseIndexRefresh(success=False, error="index unavailable")

    monkeypatch.setattr(mod, "refresh_notes_browse_index", fake_refresh)

    result = mod.save_thought_note(
        vault_dir=tmp_path,
        body="Save this even if Browse cannot refresh.",
        captured_at=datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
    )

    assert result["success"] is True
    assert result["deduplicated"] is False
    assert result["browse_index"] == {
        "success": False,
        "count": 0,
        "error": "index unavailable",
    }
    assert calls == [tmp_path]
    assert Path(str(result["path"])).is_file()


def test_save_thought_note_dedupes_without_claiming_new_browse_refresh(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts import note_capture as mod
    from src.lib.ingest.note_index_refresh import NoteBrowseIndexRefresh

    calls: list[Path] = []

    def fake_refresh(*, vault_dir: Path) -> NoteBrowseIndexRefresh:
        calls.append(vault_dir)
        return NoteBrowseIndexRefresh(success=True, count=9)

    monkeypatch.setattr(mod, "refresh_notes_browse_index", fake_refresh)
    kwargs = {
        "vault_dir": tmp_path,
        "title": "Repeat",
        "body": "repeat this thought",
        "captured_at": datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
    }

    first = mod.save_thought_note(**kwargs)
    second = mod.save_thought_note(**kwargs)

    assert first["deduplicated"] is False
    assert first["browse_index"] == {"success": True, "count": 9}
    assert second["deduplicated"] is True
    assert second["path"] == first["path"]
    assert second["sha256"] == first["sha256"]
    assert "browse_index" not in second
    assert calls == [tmp_path]
