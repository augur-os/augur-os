from __future__ import annotations

from pathlib import Path

import pytest

from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter


class FakeMcp:
    def __init__(self) -> None:
        self.tools = {}
        self.annotations = {}

    def tool(self, name, annotations=None):
        def decorator(func):
            self.tools[name] = func
            self.annotations[name] = annotations
            return func

        return decorator


class RefreshResult:
    def to_dict(self) -> dict[str, object]:
        return {"success": True, "indexed": 1}


def test_normalize_accepts_project_github_watching_high() -> None:
    from skills.ingest.scripts.mcp.note_classification_tools import (
        normalize_note_classification_update,
    )

    assert normalize_note_classification_update(
        domain="projects",
        source="github",
        status="watching",
        classification_confidence="high",
    ) == {
        "x-augur-domain": "projects",
        "x-augur-source": "github",
        "x-augur-status": "watching",
        "x-augur-classification-confidence": "high",
    }


def test_normalize_rejects_status_for_people() -> None:
    from skills.ingest.scripts.mcp.note_classification_tools import (
        normalize_note_classification_update,
    )

    with pytest.raises(
        ValueError,
        match="status applied is not valid for domain people",
    ):
        normalize_note_classification_update(
            domain="people",
            source="linkedin",
            status="applied",
            classification_confidence="medium",
        )


def test_update_catches_invalid_input_and_returns_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from skills.ingest.scripts.mcp import note_classification_tools

    vault = tmp_path / "vault"
    note = vault / "knowledge" / "notes" / "lead.md"
    note.parent.mkdir(parents=True)
    note.write_text("---\ntitle: Lead\n---\nBody.\n", encoding="utf-8")
    monkeypatch.setattr(note_classification_tools, "get_vault_dir", lambda: vault)

    result = note_classification_tools.update_note_classification_impl(
        note_path=str(note),
        domain="people",
        source="linkedin",
        status="applied",
        classification_confidence="medium",
    )

    assert result == {
        "success": False,
        "error": "status applied is not valid for domain people",
    }


def test_update_preserves_body_and_clears_irrelevant_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from skills.ingest.scripts.mcp import note_classification_tools

    vault = tmp_path / "vault"
    note = vault / "knowledge" / "notes" / "lead.md"
    note.parent.mkdir(parents=True)
    body = "## Body\n\nKeep this exactly.\n\n- [[Existing Link]]\n"
    note.write_text(
        """---
title: Lead
x-augur-domain: jobs
x-augur-source: website
x-augur-status: applied
---
"""
        + body,
        encoding="utf-8",
    )
    monkeypatch.setattr(
        note_classification_tools,
        "refresh_notes_browse_index",
        lambda: RefreshResult(),
    )
    monkeypatch.setattr(note_classification_tools, "get_vault_dir", lambda: vault)

    result = note_classification_tools.update_note_classification_impl(
        note_path=str(note),
        domain="people",
        source="linkedin",
        status="",
        classification_confidence="low",
    )

    metadata, updated_body = parse_frontmatter(
        note,
        include_sidecar_config=False,
    )
    assert result["success"] is True
    assert result["note_path"] == str(note)
    assert result["metadata"] == {
        "x-augur-domain": "people",
        "x-augur-source": "linkedin",
        "x-augur-classification-confidence": "low",
    }
    assert result["refresh"] == {"success": True, "indexed": 1}
    assert updated_body == body
    assert metadata["title"] == "Lead"
    assert metadata["x-augur-domain"] == "people"
    assert metadata["x-augur-source"] == "linkedin"
    assert metadata["x-augur-classification-confidence"] == "low"
    assert "x-augur-status" not in metadata


def test_update_does_not_persist_system_field_read_aliases(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from skills.ingest.scripts.mcp import note_classification_tools

    vault = tmp_path / "vault"
    note = vault / "knowledge" / "notes" / "system.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        """---
title: System Metadata
_source_type: url
---
Body.
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        note_classification_tools,
        "refresh_notes_browse_index",
        lambda: RefreshResult(),
    )
    monkeypatch.setattr(note_classification_tools, "get_vault_dir", lambda: vault)

    result = note_classification_tools.update_note_classification_impl(
        note_path=str(note),
        domain="projects",
        source="github",
        status="saved",
        classification_confidence="high",
    )

    assert result["success"] is True
    raw = note.read_text(encoding="utf-8")
    assert "_source_type: url" in raw
    assert "\nsource_type: url\n" not in raw


def test_update_rejects_repo_markdown_outside_vault(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from skills.ingest.scripts.mcp import note_classification_tools

    vault = tmp_path / "vault"
    repo_doc = tmp_path / "repo" / "docs" / "adr.md"
    repo_doc.parent.mkdir(parents=True)
    repo_doc.write_text("---\ntitle: ADR\n---\nBody.\n", encoding="utf-8")
    monkeypatch.setattr(note_classification_tools, "get_vault_dir", lambda: vault)

    result = note_classification_tools.update_note_classification_impl(
        note_path=str(repo_doc),
        domain="projects",
        source="github",
        status="saved",
        classification_confidence="high",
    )

    assert result == {
        "success": False,
        "error": f"note must be inside an Augur note root: {repo_doc}",
    }
    assert "x-augur-domain" not in repo_doc.read_text(encoding="utf-8")


def test_update_rejects_profile_memory_inside_vault(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from skills.ingest.scripts.mcp import note_classification_tools

    vault = tmp_path / "vault"
    profile_memory = vault / "memory" / "profile.md"
    profile_memory.parent.mkdir(parents=True)
    profile_memory.write_text("---\ntitle: Profile\n---\nBody.\n", encoding="utf-8")
    monkeypatch.setattr(note_classification_tools, "get_vault_dir", lambda: vault)

    result = note_classification_tools.update_note_classification_impl(
        note_path=str(profile_memory),
        domain="people",
        source="linkedin",
        classification_confidence="high",
    )

    assert result == {
        "success": False,
        "error": f"note must be inside an Augur note root: {profile_memory}",
    }
    assert "x-augur-domain" not in profile_memory.read_text(encoding="utf-8")


def test_update_allows_source_note_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from skills.ingest.scripts.mcp import note_classification_tools

    vault = tmp_path / "vault"
    source_note = vault / "knowledge" / "sources" / "urls" / "github.md"
    source_note.parent.mkdir(parents=True)
    source_note.write_text("---\ntitle: Source\n---\nBody.\n", encoding="utf-8")
    monkeypatch.setattr(note_classification_tools, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(
        note_classification_tools,
        "refresh_notes_browse_index",
        lambda: RefreshResult(),
    )

    result = note_classification_tools.update_note_classification_impl(
        note_path=str(source_note),
        domain="projects",
        source="github",
        status="saved",
        classification_confidence="high",
    )

    metadata, _body = parse_frontmatter(source_note, include_sidecar_config=False)
    assert result["success"] is True
    assert metadata["x-augur-domain"] == "projects"
    assert metadata["x-augur-source"] == "github"


def test_update_reports_missing_file_exactly(tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp.note_classification_tools import (
        update_note_classification_impl,
    )

    missing = tmp_path / "missing.md"

    assert update_note_classification_impl(
        note_path=str(missing),
        domain="projects",
        source="github",
    ) == {"success": False, "error": f"note not found: {missing}"}


def test_register_tool_exposes_update_annotations() -> None:
    from skills.ingest.scripts.mcp.note_classification_tools import (
        register_note_classification_tools,
    )

    fake = FakeMcp()
    register_note_classification_tools(fake, lambda func: func, None)

    assert "note-classification-update" in fake.tools
    assert fake.annotations["note-classification-update"]["title"] == (
        "Update Note Classification"
    )
    assert fake.annotations["note-classification-update"]["readOnlyHint"] is False


def test_standard_write_frontmatter_changes_parsed_body_for_nonempty_body(
    tmp_path: Path,
) -> None:
    note = tmp_path / "standard.md"
    body = "## Body\n\nKeep this exactly.\n"

    write_frontmatter(note, {"title": "Standard"}, body)

    _metadata, parsed_body = parse_frontmatter(
        note,
        include_sidecar_config=False,
    )
    assert parsed_body != body
    assert parsed_body == f"\n{body}"


def test_package_register_tools_exposes_note_classification_update() -> None:
    from skills.ingest.scripts.mcp import register_tools

    fake = FakeMcp()
    register_tools(fake, lambda func: func, None)

    assert "note-classification-update" in fake.tools
    assert fake.annotations["note-classification-update"]["readOnlyHint"] is False
