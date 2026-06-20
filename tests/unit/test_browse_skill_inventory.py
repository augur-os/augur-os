from __future__ import annotations

import json
import zipfile
from email.message import EmailMessage
from pathlib import Path

from src.lib.brain_manifest import (
    BrainManifest,
    ensure_brain_skeleton,
    write_brain_manifest,
)
from src.lib.brain_registry_models import BrainType
from src.lib.frontmatter_utils import write_frontmatter


def _write_browse_eml(
    path: Path,
    *,
    subject: str,
    sender: str = "alice@example.com",
    body: str = "Read https://example.com/article",
    with_attachment: bool = False,
) -> None:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = "me@example.com"
    message["Subject"] = subject
    message["Date"] = "Thu, 14 May 2026 12:00:00 +0000"
    message.set_content(body)
    if with_attachment:
        message.add_attachment(
            b"Attachment body",
            maintype="text",
            subtype="plain",
            filename="brief.txt",
        )
    path.write_bytes(message.as_bytes())


def test_browse_index_exposes_skill_source_and_ownership(tmp_path: Path, monkeypatch) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    category_dir = tmp_path / "rag" / "skills"
    source_path = tmp_path / "project-brain" / "capabilities" / "skills" / "knowledge" / "SKILL.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("---\nname: knowledge\n---\n", encoding="utf-8")
    entry_path = category_dir / "brain" / "knowledge.md"
    write_frontmatter(
        entry_path,
        {
            "type": "skill",
            "hub": "workspace",
            "name": "knowledge",
            "source": "augur",
            "ownership": "augur",
            "skill_client": "augur",
            "skill_origin": "canonical",
            "source_path": "project-brain/capabilities/skills/knowledge/SKILL.md",
            "description": "Search and curate memory.",
        },
        "",
    )

    index_reader = Path("src/lib/index/index_reader.py").resolve()
    monkeypatch.setattr(browse_index, "find_skill_file", lambda *args: index_reader)
    monkeypatch.setattr(browse_index, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(browse_index, "_get_skill_enrichment", lambda: {})
    # Isolate to tmp: the real AI-artifact inventory pulls registered project brains
    # (~80 skills) into the skills category outside the monkeypatched RAG dir.
    monkeypatch.setattr(browse_index, "inventory_browse_entries_for_category", lambda category: [])

    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: category_dir)

    result = json.loads(browse_index.browse_index_impl("skills"))

    assert result["count"] == 1
    item = result["items"][0]
    assert item["source"] == "augur"
    assert item["ownership"] == "augur"
    assert item["metadata"]["source"] == "augur"
    assert item["metadata"]["ownership"] == "augur"


def test_browse_index_attaches_project_brain_id_for_project_brain_skills(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    category_dir = tmp_path / "rag" / "skills"
    brain_root = tmp_path / "project-brain"
    ensure_brain_skeleton(brain_root)
    write_brain_manifest(
        brain_root,
        BrainManifest(
            schema_version=1,
            id="project-demo",
            type=BrainType.PROJECT,
            root=str(brain_root),
            attached_project=str(tmp_path),
        ),
    )
    source_path = brain_root / "capabilities" / "skills" / "knowledge" / "SKILL.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("---\nname: knowledge\n---\n", encoding="utf-8")
    write_frontmatter(
        category_dir / "brain" / "knowledge.md",
        {
            "type": "skill",
            "hub": "workspace",
            "name": "knowledge",
            "source": "project-brain",
            "ownership": "augur",
            "source_path": "project-brain/capabilities/skills/knowledge/SKILL.md",
            "description": "Search and curate memory.",
        },
        "",
    )

    index_reader = Path("src/lib/index/index_reader.py").resolve()
    from src.mcp.augur_framework.tools.infrastructure.browse import index_resolve

    monkeypatch.setattr(browse_index, "find_skill_file", lambda *args: index_reader)
    monkeypatch.setattr(browse_index, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(index_resolve, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(browse_index, "_get_skill_enrichment", lambda: {})
    # Isolate to tmp: the real AI-artifact inventory pulls registered project brains
    # (~80 skills) into the skills category outside the monkeypatched RAG dir.
    monkeypatch.setattr(browse_index, "inventory_browse_entries_for_category", lambda category: [])

    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: category_dir)

    result = json.loads(browse_index.browse_index_impl("skills"))

    assert result["count"] == 1
    assert result["items"][0]["metadata"]["brain_id"] == "project-demo"


def test_browse_index_search_filters_before_limit(tmp_path: Path, monkeypatch) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    category_dir = tmp_path / "rag" / "skills"
    for idx in range(12):
        name = f"skill-{idx:02d}"
        source_path = tmp_path / "project-brain" / "capabilities" / "skills" / name / "SKILL.md"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
        write_frontmatter(
            category_dir / "brain" / f"{name}.md",
            {
                "type": "skill",
                "hub": "workspace",
                "name": name,
                "source_path": f"project-brain/capabilities/skills/{name}/SKILL.md",
                "description": "Ordinary skill",
            },
            "",
        )
    source_path = tmp_path / "project-brain" / "capabilities" / "skills" / "zz-target-skill" / "SKILL.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("---\nname: zz-target-skill\n---\n", encoding="utf-8")
    write_frontmatter(
        category_dir / "brain" / "zz-target-skill.md",
        {
            "type": "skill",
            "hub": "workspace",
            "name": "zz-target-skill",
            "source_path": "project-brain/capabilities/skills/zz-target-skill/SKILL.md",
            "description": "Late matching skill",
        },
        "",
    )

    index_reader = Path("src/lib/index/index_reader.py").resolve()
    from src.mcp.augur_framework.tools.infrastructure.browse import index_resolve

    monkeypatch.setattr(browse_index, "find_skill_file", lambda *args: index_reader)
    monkeypatch.setattr(browse_index, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(index_resolve, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(browse_index, "_get_skill_enrichment", lambda: {})

    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: category_dir)

    result = json.loads(browse_index.browse_index_impl("skills", limit=1, search="target"))

    assert [item["title"] for item in result["items"]] == ["zz-target-skill"]


def test_browse_index_exposes_and_searches_skill_client_sources(tmp_path: Path, monkeypatch) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    category_dir = tmp_path / "rag" / "skills"
    source_path = tmp_path / "project" / ".codex" / "skills" / "dev-loops" / "SKILL.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("---\nname: dev-loops\n---\n", encoding="utf-8")
    write_frontmatter(
        category_dir / "external" / "dev-loops.md",
        {
            "type": "skill",
            "hub": "external",
            "name": "dev-loops",
            "source": "codex-local",
            "ownership": "external",
            "skill_client": "codex",
            "skill_origin": "client-local",
            "client_sources": ["codex-local", "gemini-local"],
            "skill_clients": ["codex", "gemini"],
            "source_path": str(source_path),
            "description": "Manage loops",
        },
        "",
    )

    index_reader = Path("src/lib/index/index_reader.py").resolve()
    monkeypatch.setattr(browse_index, "find_skill_file", lambda *args: index_reader)
    monkeypatch.setattr(browse_index, "_get_skill_enrichment", lambda: {})

    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: category_dir)

    result = json.loads(browse_index.browse_index_impl("skills", search="gemini"))

    assert result["count"] == 1
    item = result["items"][0]
    assert item["title"] == "dev-loops"
    assert item["client_sources"] == ["codex-local", "gemini-local"]
    assert item["skill_clients"] == ["codex", "gemini"]
    assert item["metadata"]["clientSources"] == "codex-local,gemini-local"
    assert item["metadata"]["skillClients"] == "codex,gemini"


def test_browse_index_filters_vault_journey_before_limit(tmp_path: Path, monkeypatch) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    category_dir = tmp_path / "rag" / "vault"
    for idx in range(1005):
        write_frontmatter(
            category_dir / "notes" / f"note-{idx:04d}.md",
            {
                "type": "vault",
                "hub": "workspace",
                "name": f"note-{idx:04d}",
                "title": f"Note {idx:04d}",
                "source_path": f"~/Projects/Au-vault/notes/note-{idx:04d}.md",
                "description": "Ordinary note",
            },
            "",
        )
    write_frontmatter(
        category_dir / "sources" / "target.md",
        {
            "type": "vault",
            "hub": "workspace",
            "name": "target-source",
            "title": "Target Source",
            "source_path": "~/Projects/Au-vault/sources/web/target.md",
            "description": "Late source item",
        },
        "",
    )

    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: category_dir)

    result = json.loads(browse_index.browse_index_impl("vault", journey_category="sources"))

    assert result["count"] == 1
    assert result.get("total_count") is None
    assert [item["title"] for item in result["items"]] == ["Target Source"]


def test_browse_index_filters_drafts_journey_to_drafts_root(tmp_path: Path, monkeypatch) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    category_dir = tmp_path / "rag" / "vault"
    write_frontmatter(
        category_dir / "drafts" / "staging" / "draft.md",
        {
            "type": "vault",
            "hub": "workspace",
            "name": "draft",
            "title": "Active Draft Root",
            "source_path": "~/Projects/Au-vault/drafts/staging/draft.md",
            "description": "Draft root item",
        },
        "",
    )
    write_frontmatter(
        category_dir / "_drafts" / "staging" / "legacy.md",
        {
            "type": "vault",
            "hub": "workspace",
            "name": "legacy-draft",
            "title": "Legacy Draft Root",
            "source_path": "~/Projects/Au-vault/_drafts/staging/legacy.md",
            "description": "Legacy draft root item",
        },
        "",
    )

    import src.config.paths as paths

    from src.mcp.augur_framework.tools.infrastructure.browse import index_sweep

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: category_dir)
    monkeypatch.setattr(index_sweep, "get_runtime_dir", lambda: tmp_path / "runtime")

    result = json.loads(browse_index.browse_index_impl("vault", journey_category="drafts"))

    assert result["count"] == 1
    assert [item["title"] for item in result["items"]] == ["Active Draft Root"]


def test_browse_inbox_indexes_default_email_drop_folder_as_email_cards(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    documents_dir = tmp_path / "documents"
    mail_dir = documents_dir / "inbox" / "email"
    mail_dir.mkdir(parents=True)
    _write_browse_eml(
        mail_dir / "first.eml",
        subject="First invoice",
        sender="billing@example.com",
        with_attachment=True,
    )
    _write_browse_eml(
        mail_dir / "second.eml",
        subject="Second article",
        sender="editor@example.com",
    )

    import src.config.paths as paths

    from src.mcp.augur_framework.tools.infrastructure.browse import index_email

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: tmp_path / "rag" / category)
    monkeypatch.setattr(index_email, "get_documents_dir", lambda: documents_dir)
    monkeypatch.setattr(index_email, "get_runtime_dir", lambda: tmp_path / "runtime")

    result = json.loads(browse_index.browse_index_impl("vault", journey_category="inbox"))

    assert result["count"] == 2
    titles = {item["title"] for item in result["items"]}
    assert titles == {"First invoice", "Second article"}
    invoice = next(item for item in result["items"] if item["title"] == "First invoice")
    assert invoice["type"] == "email-drop"
    assert invoice["hub"] == "workspace"
    assert invoice["source_path"] == str(mail_dir / "first.eml")
    assert invoice["metadata"]["journey_category"] == "inbox"
    assert invoice["metadata"]["source_root"] == "documents-inbox-email"
    assert invoice["metadata"]["email_from"] == "billing@example.com"
    assert invoice["metadata"]["attachment_count"] == "1"
    assert invoice["metadata"]["link_count"] == "1"


def test_browse_inbox_returns_email_cards_before_existing_vault_inbox_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    documents_dir = tmp_path / "documents"
    mail_dir = documents_dir / "inbox" / "email"
    mail_dir.mkdir(parents=True)
    _write_browse_eml(mail_dir / "first.eml", subject="Visible mail")
    category_dir = tmp_path / "rag" / "vault"
    write_frontmatter(
        category_dir / "inbox" / "shared" / "README.md",
        {
            "type": "vault",
            "hub": "workspace",
            "name": "README",
            "title": "Shared Inbox README",
            "source_path": "/tmp/project-brain/inbox/promotions/README.md",
            "journey_category": "inbox",
        },
        "",
    )

    import src.config.paths as paths

    from src.mcp.augur_framework.tools.infrastructure.browse import index_email

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: category_dir)
    monkeypatch.setattr(index_email, "get_documents_dir", lambda: documents_dir)
    monkeypatch.setattr(index_email, "get_runtime_dir", lambda: tmp_path / "runtime")

    result = json.loads(browse_index.browse_index_impl("vault", journey_category="inbox", limit=1))

    assert result["count"] == 1
    assert result["total_count"] == 2
    assert result["items"][0]["title"] == "Visible mail"
    assert result["items"][0]["type"] == "email-drop"


def test_browse_inbox_archive_email_card_points_to_archive_source(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    documents_dir = tmp_path / "documents"
    mail_dir = documents_dir / "inbox" / "email"
    mail_dir.mkdir(parents=True)
    nested_eml = tmp_path / "nested.eml"
    _write_browse_eml(nested_eml, subject="Archived mail")
    archive_path = mail_dir / "messages.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(nested_eml, arcname="nested/message.eml")

    import src.config.paths as paths

    from src.mcp.augur_framework.tools.infrastructure.browse import index_email

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: tmp_path / "rag" / category)
    monkeypatch.setattr(index_email, "get_documents_dir", lambda: documents_dir)
    monkeypatch.setattr(index_email, "get_runtime_dir", lambda: tmp_path / "runtime")

    result = json.loads(browse_index.browse_index_impl("vault", journey_category="inbox"))

    assert result["count"] == 1
    item = result["items"][0]
    assert item["title"] == "Archived mail"
    assert item["source_path"] == str(archive_path)
    assert item["metadata"]["contained_path"] == "nested/message.eml"


def test_browse_inbox_skips_unreadable_email_artifact_without_hiding_valid_cards(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    documents_dir = tmp_path / "documents"
    mail_dir = documents_dir / "inbox" / "email"
    mail_dir.mkdir(parents=True)
    _write_browse_eml(mail_dir / "valid.eml", subject="Still visible")
    (mail_dir / "broken.zip").write_bytes(b"not a zip")

    import src.config.paths as paths

    from src.mcp.augur_framework.tools.infrastructure.browse import index_email

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: tmp_path / "rag" / category)
    monkeypatch.setattr(index_email, "get_documents_dir", lambda: documents_dir)
    monkeypatch.setattr(index_email, "get_runtime_dir", lambda: tmp_path / "runtime")

    result = json.loads(browse_index.browse_index_impl("vault", journey_category="inbox"))

    assert result["count"] == 1
    assert result["items"][0]["title"] == "Still visible"
