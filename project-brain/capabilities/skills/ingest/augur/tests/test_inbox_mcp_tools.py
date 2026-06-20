from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

import yaml

from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter


def _assert_ranked_demo_artifact(result: dict[str, object], *, min_score: int = 90) -> Path:
    from skills.demo.scripts.demo_collateral_rank import score_demo_collateral_path

    artifact_path = Path(str(result["artifact_path"]))
    assert artifact_path.exists()
    rank = score_demo_collateral_path(artifact_path)
    assert rank["score"] >= min_score, rank
    assert rank["status"] == "pass", rank
    _meta, body = parse_frontmatter(artifact_path)
    assert "/Users/" not in body
    assert "Candidate wiki file:" not in body
    assert "Source synthesis:" not in body
    assert "Retained cluster:" not in body
    return artifact_path


def test_inbox_folders_add_and_list(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp import inbox_tools

    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")
    folder_path = tmp_path / "Desktop"
    folder_path.mkdir()

    added = json.loads(
        asyncio.run(
            inbox_tools.inbox_folders_impl(
                action="add",
                name="Desktop",
                path=str(folder_path),
            )
        )
    )
    listed = json.loads(asyncio.run(inbox_tools.inbox_folders_impl(action="list")))

    assert added["success"] is True
    assert listed["folders"][0]["id"] == "desktop"
    assert listed["latest_runs"] == []


def test_inbox_folders_list_includes_bounded_latest_run_details(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest.inbox_models import InboxFileResult, InboxRunRecord
    from skills.ingest.scripts.mcp import inbox_tools

    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")
    store = inbox_tools._store()
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    for run_index in range(4):
        store.save_run(
            InboxRunRecord(
                id=f"run_{run_index}",
                folder_id=folder.id,
                started_at=f"2026-05-07T12:0{run_index}:00+00:00",
                completed_at=f"2026-05-07T12:0{run_index}:30+00:00",
                status="success",
                airplane_mode=True,
                files_seen=12,
                files_moved=12,
                files_indexed=12,
                files_needing_review=1,
                cloud_calls=0,
                local_agent_calls=2,
                file_results=[
                    InboxFileResult(
                        source_path=f"C:/Desktop/report-{run_index}-{file_index}.pdf",
                        final_path=f"C:/Vault/finance/report-{run_index}-{file_index}.pdf",
                        source_card_path=f"sources/files/report-{run_index}-{file_index}.md",
                        content_type="application/pdf",
                        extraction_method="local-ocr",
                        hardware_backend="npu",
                        confidence="medium",
                        route="finance",
                        renamed_to=f"report-{run_index}-{file_index}.pdf",
                        rag_indexed=True,
                        status="success",
                        local_agent_used=True,
                        cloud_used=False,
                    )
                    for file_index in range(12)
                ],
            )
        )

    listed = json.loads(asyncio.run(inbox_tools.inbox_folders_impl(action="list")))

    assert [run["id"] for run in listed["latest_runs"]] == [
        "run_3",
        "run_2",
        "run_1",
    ]
    assert listed["latest_runs"][0]["airplane_mode"] is True
    assert listed["latest_runs"][0]["cloud_calls"] == 0
    assert listed["latest_runs"][0]["local_agent_calls"] == 2
    assert len(listed["latest_runs"][0]["file_results"]) == 10
    assert listed["latest_runs"][0]["file_results"][0]["hardware_backend"] == "npu"
    assert listed["latest_runs"][0]["file_results"][0]["cloud_used"] is False


def test_inbox_folders_list_hides_consumed_and_stale_staged_packets(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.inbox_unified_models import (
        InboxPacket,
        InboxSourceLane,
        InboxVaultTarget,
        UnifiedInboxRegistry,
        to_dict,
    )
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.ingest.scripts.mcp import _inbox_packet_helpers

    drop_root = tmp_path / "docs" / "inbox" / "claude"
    docs_root = tmp_path / "docs"
    target_folder = docs_root / "matched"
    target_folder.mkdir(parents=True)
    (target_folder / "active-packet-reference.md").write_text(
        "reference", encoding="utf-8"
    )

    def write_packet(packet: InboxPacket, payload: bytes | None = None) -> None:
        packet_dir = Path(packet.packet_dir)
        packet_dir.mkdir(parents=True)
        if payload is not None and packet.payload_paths:
            (packet_dir / packet.payload_paths[0]).write_bytes(payload)
        (packet_dir / "manifest.yaml").write_text(
            yaml.safe_dump(to_dict(packet), sort_keys=False),
            encoding="utf-8",
        )

    write_packet(
        InboxPacket(
            packet_id="active",
            source_id="claude-chat",
            source_type="chat_mcp",
            capture_mode="mcp_content",
            packet_dir=str(drop_root / "active"),
            title="Active Packet Reference",
            status="staged",
            target_vault="personal",
            original_filename="active-packet-reference-v2.md",
            payload_paths=["active-packet-reference-v2.md"],
            created_at="2026-05-18T10:00:00Z",
        ),
        payload=b"active",
    )
    write_packet(
        InboxPacket(
            packet_id="consumed",
            source_id="claude-chat",
            source_type="chat_mcp",
            capture_mode="mcp_content",
            packet_dir=str(drop_root / "consumed"),
            title="Consumed Packet",
            status="consumed",
            target_vault="personal",
            original_filename="consumed.md",
            payload_paths=["consumed.md"],
            created_at="2026-05-18T11:00:00Z",
        )
    )
    write_packet(
        InboxPacket(
            packet_id="stale-staged",
            source_id="claude-chat",
            source_type="chat_mcp",
            capture_mode="mcp_content",
            packet_dir=str(drop_root / "stale-staged"),
            title="Stale Staged Packet",
            status="staged",
            target_vault="personal",
            original_filename="stale-staged.md",
            payload_paths=["stale-staged.md"],
            created_at="2026-05-18T12:00:00Z",
        )
    )

    registry = UnifiedInboxRegistry(
        config_root=tmp_path / "state",
        sources=[
            InboxSourceLane(
                id="claude-chat",
                type="chat_mcp",
                name="Claude Chat",
                domain="docs",
                drop_root=str(drop_root),
            )
        ],
        vaults=[
            InboxVaultTarget(
                id="personal",
                kind="private",
                name="Personal",
                vault_root=str(tmp_path / "vault"),
                docs_root=str(docs_root),
                default=True,
                writable=True,
            )
        ],
    )
    monkeypatch.setattr(_inbox_packet_helpers, "load_inbox_registry", lambda: registry)
    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")

    listed = json.loads(asyncio.run(inbox_tools.inbox_folders_impl(action="list")))

    assert [packet["packet_id"] for packet in listed["routing_queue"]] == ["active"]
    assert listed["routing_queue"][0]["status"] == "ready"


def test_register_tools_exposes_required_names() -> None:
    from skills.ingest.scripts.mcp import register_tools

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

    fake = FakeMcp()
    register_tools(fake, lambda func: func, None)

    assert "inbox-folders" in fake.tools
    assert "email-drop-sources" in fake.tools
    assert "email-drop-scan-source" in fake.tools
    assert "email-drop-consume-source" in fake.tools
    assert "inbox-scan-folder" in fake.tools
    assert "inbox-consume-folder" in fake.tools
    assert "inbox-purge-folder" in fake.tools
    assert "inbox-run-history" in fake.tools
    assert "inbox-run-detail" in fake.tools
    assert "brain-insights" in fake.tools
    assert "wiki-report-data" in fake.tools
    assert "wiki-rewrite-candidates" in fake.tools
    assert "demo-readiness" in fake.tools
    assert "demo-reset" in fake.tools
    assert "demo-smoke" in fake.tools
    assert "demo-run-note" in fake.tools
    assert "demo-run-reset" in fake.tools
    assert "demo-run-record-evidence" in fake.tools
    assert "demo-runbook-output" in fake.tools
    assert "demo-run-wiki-ask" in fake.tools
    assert "demo-run-discover-capture" in fake.tools
    assert "demo-run-transcription-offload" in fake.tools
    assert "demo-run-compound-preview" in fake.tools
    assert "demo-run-airplane-safety" in fake.tools
    assert "demo-run-brain-manifest" in fake.tools
    assert "demo-run-prompt" in fake.tools
    assert "demo-run-transcript" in fake.tools
    assert "demo-run-meeting-memory" in fake.tools
    assert "demo-run-ask-transcript" in fake.tools
    assert "url-extract" in fake.tools
    assert "save-url-source" in fake.tools


def test_demo_desktop_local_alias_resolves_to_default() -> None:
    from skills.demo.scripts.mcp import demo_tools

    expected = Path.home() / "Desktop" / "Augur Workflow Example Inbox"

    assert demo_tools._demo_desktop("") == expected
    assert demo_tools._demo_desktop("local") == expected
    assert demo_tools._demo_desktop("default") == expected
    assert demo_tools._demo_desktop("demo") == expected


def test_register_tools_exposes_unified_inbox_names() -> None:
    from skills.ingest.scripts.mcp import register_tools

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

    fake = FakeMcp()
    register_tools(fake, lambda func: func, None)

    assert "inbox-source-lanes" in fake.tools
    assert "inbox-discover-vaults" in fake.tools
    assert "inbox-register-vault" in fake.tools
    assert "inbox-stage-packet" in fake.tools
    assert "inbox-pending-packet" in fake.tools
    assert "inbox-route-packets" in fake.tools
    assert "inbox-consume-packets" in fake.tools
    assert "inbox-runs" in fake.tools
    assert fake.annotations["inbox-source-lanes"]["readOnlyHint"] is True
    assert fake.annotations["inbox-consume-packets"]["destructiveHint"] is True


def test_register_tools_uses_standard_annotations() -> None:
    from skills.ingest.scripts.mcp import register_tools

    class FakeMcp:
        def __init__(self) -> None:
            self.annotations = {}

        def tool(self, name, annotations=None):
            def decorator(func):
                self.annotations[name] = annotations
                return func

            return decorator

    fake = FakeMcp()
    register_tools(fake, lambda func: func, None)

    assert fake.annotations["inbox-folders"]["title"] == "Inbox Folders"
    assert fake.annotations["url-extract"]["title"] == "Extract URL"
    assert fake.annotations["url-extract"]["idempotentHint"] is True
    assert fake.annotations["save-url-source"]["title"] == "Save URL Source Card"
    assert fake.annotations["save-url-source"]["idempotentHint"] is True
    assert fake.annotations["inbox-folders"]["idempotentHint"] is False
    assert "hints" not in fake.annotations["inbox-folders"]
    assert "annotations" not in fake.annotations["inbox-folders"]
    assert fake.annotations["inbox-scan-folder"]["readOnlyHint"] is False
    assert fake.annotations["email-drop-scan-source"]["readOnlyHint"] is False
    assert fake.annotations["email-drop-consume-source"]["readOnlyHint"] is False
    assert fake.annotations["demo-readiness"]["readOnlyHint"] is True
    assert fake.annotations["demo-reset"]["readOnlyHint"] is False
    assert fake.annotations["demo-smoke"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-note"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-note"]["destructiveHint"] is False
    assert fake.annotations["demo-run-reset"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-reset"]["destructiveHint"] is False
    assert fake.annotations["demo-run-record-evidence"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-record-evidence"]["destructiveHint"] is False
    assert fake.annotations["demo-runbook-output"]["readOnlyHint"] is True
    assert fake.annotations["demo-runbook-output"]["destructiveHint"] is False
    assert fake.annotations["demo-run-wiki-ask"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-wiki-ask"]["destructiveHint"] is False
    assert fake.annotations["demo-run-wiki-ask"]["idempotentHint"] is True
    assert fake.annotations["demo-run-discover-capture"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-discover-capture"]["destructiveHint"] is False
    assert fake.annotations["demo-run-discover-capture"]["idempotentHint"] is True
    assert fake.annotations["demo-run-transcription-offload"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-transcription-offload"]["destructiveHint"] is False
    assert fake.annotations["demo-run-transcription-offload"]["idempotentHint"] is False
    assert fake.annotations["demo-run-compound-preview"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-compound-preview"]["destructiveHint"] is False
    assert fake.annotations["demo-run-compound-preview"]["idempotentHint"] is True
    assert fake.annotations["demo-run-airplane-safety"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-airplane-safety"]["destructiveHint"] is False
    assert fake.annotations["demo-run-airplane-safety"]["idempotentHint"] is False
    assert fake.annotations["demo-run-brain-manifest"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-brain-manifest"]["destructiveHint"] is False
    assert fake.annotations["demo-run-brain-manifest"]["idempotentHint"] is True
    assert fake.annotations["demo-run-prompt"]["readOnlyHint"] is True
    assert fake.annotations["demo-run-prompt"]["destructiveHint"] is False
    assert fake.annotations["demo-run-transcript"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-transcript"]["destructiveHint"] is False
    assert fake.annotations["demo-run-transcript"]["idempotentHint"] is False
    assert fake.annotations["demo-run-meeting-memory"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-meeting-memory"]["destructiveHint"] is False
    assert fake.annotations["demo-run-meeting-memory"]["idempotentHint"] is False
    assert fake.annotations["demo-run-ask-transcript"]["readOnlyHint"] is False
    assert fake.annotations["demo-run-ask-transcript"]["destructiveHint"] is False
    assert fake.annotations["demo-run-ask-transcript"]["idempotentHint"] is False


def test_demo_runbook_output_impl_returns_expected_visible_output(tmp_path: Path) -> None:
    from skills.demo.scripts.mcp import demo_tools

    runbook = tmp_path / "demo_99_test.md"
    runbook.write_text(
        """---
title: Workflow Example 99 - Test
type: demo-runbook
demo_id: demo_99_test
---

# Workflow Example 99 - Test

## Expected Visible Output

```text
Workflow Example 99 is running: test harness proof.
Answer: visible bottom line.
Example status: pass.
```
""",
        encoding="utf-8",
    )

    result = json.loads(
        asyncio.run(
            demo_tools.demo_runbook_output_impl(
                source_path=str(runbook),
                title="Workflow Example 99 - Test",
                demo_id="demo_99_test",
            )
        )
    )

    assert result["success"] is True
    assert result["message"] == "Workflow example runbook output is ready."
    assert result["action_label"] == "Workflow Example 99 - Test"
    assert result["demo_id"] == "demo_99_test"
    assert result["source_path"] == str(runbook)
    assert result["chat_output"] == (
        "Workflow Example 99 is running: test harness proof.\n"
        "Answer: visible bottom line.\n"
        "Example status: pass."
    )
    assert "Read the runbook first" in result["prompt"]
    assert "Before any live workflow example work, run demo-run-reset" in result["prompt"]
    assert "before-demo_99_test" in result["prompt"]
    assert "Follow the runbook's Automatic Reset / Idempotency section" in result["prompt"]
    assert "If the runbook provides a Bounded Live Command" in result["prompt"]
    assert "Do not repeat the Expected Visible Output preview" in result["prompt"]


def test_demo_runbook_output_impl_resolves_runbook_from_demo_id(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    project_root = tmp_path / "repo"
    demos_dir = project_root / "project-brain" / "capabilities" / "skills" / "ingest" / "demos"
    demos_dir.mkdir(parents=True)
    runbook = demos_dir / "demo_99_test.md"
    runbook.write_text(
        """---
title: Workflow Example 99 - Test
type: demo-runbook
demo_id: demo_99_test
---

# Workflow Example 99 - Test

## Expected Visible Output

```text
Workflow Example 99 is running.
Example status: pass.
```
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(demo_tools, "get_project_root", lambda: project_root)

    result = json.loads(
        asyncio.run(
            demo_tools.demo_runbook_output_impl(
                source_path="",
                demo_id="demo_99_test",
            )
        )
    )

    assert result["success"] is True
    assert result["demo_id"] == "demo_99_test"
    assert result["source_path"] == str(runbook)
    assert result["chat_output"] == "Workflow Example 99 is running.\nExample status: pass."


def test_demo_runbook_output_impl_inlines_bounded_command(tmp_path: Path) -> None:
    from skills.demo.scripts.mcp import demo_tools

    runbook = tmp_path / "demo_99_test.md"
    runbook.write_text(
        """---
title: Workflow Example 99 - Test
type: demo-runbook
demo_id: demo_99_test
---

# Workflow Example 99 - Test

## Expected Visible Output

```text
Workflow Example 99 is running.
Example status: pass.
```

## Bounded Live Command

```text
uv run aug demo-run-wiki-ask --days-back 90 --limit 5
```
""",
        encoding="utf-8",
    )

    result = json.loads(
        asyncio.run(
            demo_tools.demo_runbook_output_impl(
                source_path=str(runbook),
            )
        )
    )

    assert result["success"] is True
    assert "Run this bounded command exactly:" in result["prompt"]
    assert "uv run aug demo-run-wiki-ask --days-back 90 --limit 5" in result["prompt"]
    assert "Do not search, inspect source, import Python modules" in result["prompt"]


def test_demo_run_wiki_ask_impl_returns_clear_final_block(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    monkeypatch.setattr(demo_tools, "get_vault_dir", lambda: tmp_path)
    monkeypatch.setattr(
        demo_tools,
        "reset_demo_run_state",
        lambda reason, vault_dir=None: tmp_path / "notes" / "examples" / "workflow-example-run.md",
    )

    def fake_clusters(days_back: int, limit: int):
        assert days_back == 90
        assert limit == 5
        synthesis_path = tmp_path / "knowledge" / "syntheses" / "wiki-compounding.md"
        synthesis_path.parent.mkdir(parents=True)
        synthesis_path.write_text(
            "The wiki is a governed compiler for lived work.",
            encoding="utf-8",
        )
        return [
            {
                "label": (
                    "What pattern is emerging in how i want augur's wiki to "
                    "compound and learn from me over time"
                ),
                "item_count": 4,
                "priority_score": 0.843,
                "shared_tags": ["ask", "insight"],
                "items": [{"path": str(synthesis_path)}],
                "page_targets": [
                    {"page": "concepts/wiki-ingest-and-compilation-commands"}
                ],
            }
        ]

    monkeypatch.setattr(demo_tools, "_demo_wiki_ask_clusters", fake_clusters)

    result = json.loads(
        asyncio.run(demo_tools.demo_run_wiki_ask_impl(days_back=90, limit=5))
    )

    assert result["success"] is True
    assert result["status"] == "pass"
    assert result["cluster"]["item_count"] == 4
    assert "Workflow Example 01 is running" in result["chat_output"]
    assert "Answer: Augur turns repeated /ask answers into source-backed wiki concepts" in result["chat_output"]
    assert "Evidence: ask-sync-clusters returned 4 retained items" in result["chat_output"]
    assert "Human artifact: Workflow Example 01 proof card." in result["chat_output"]
    assert 'Open in Browse: search "Workflow Example 01 Cross-Agent Wiki Compounding".' in result["chat_output"]
    assert "What to show: Wiki Ingest And Compilation Commands" in result["chat_output"]
    assert "Judge takeaway: Codex and Claude can compound into the same governed brain" in result["chat_output"]
    assert "Open synthesis:" not in result["chat_output"]
    assert "Preview to read:" not in result["chat_output"]
    artifact_path = _assert_ranked_demo_artifact(result)
    artifact_text = artifact_path.read_text(encoding="utf-8")
    _artifact_meta, artifact_body = parse_frontmatter(artifact_path)
    assert "# Workflow Example 01: Cross-Agent Wiki Compounding" in artifact_body
    assert "## Bottom Line" in artifact_body
    assert "## Live Proof" in artifact_body
    assert "## Investor Takeaway" in artifact_body
    assert "The wiki is a governed compiler for lived work." in artifact_body
    assert "`" not in artifact_body
    assert "/Users/" not in artifact_body
    assert "Candidate wiki file:" not in artifact_body
    assert "Source synthesis:" not in artifact_body
    assert "Example status: pass." in result["chat_output"]


def test_demo_run_discover_capture_impl_returns_showable_proof(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    monkeypatch.setattr(demo_tools, "get_vault_dir", lambda: tmp_path)
    monkeypatch.setattr(
        demo_tools,
        "reset_demo_run_state",
        lambda reason, vault_dir=None: tmp_path / "notes" / "examples" / "workflow-example-run.md",
    )
    monkeypatch.setattr(
        demo_tools,
        "_demo_list_commands_payload",
        lambda: {"groups": [{"name": "Core"}, {"name": "Dev"}, {"name": "Ops"}]},
        raising=False,
    )
    monkeypatch.setattr(
        demo_tools,
        "_demo_note_url_capture",
        lambda: {
            "success": True,
            "path": str(tmp_path / "notes" / "sources" / "iana.md"),
            "title": "IANA-managed Reserved Domains",
            "canonical_url": "https://www.iana.org/domains/reserved",
            "deduplicated": True,
            "word_count": 320,
        },
        raising=False,
    )
    monkeypatch.setattr(
        demo_tools,
        "_demo_browse_index",
        lambda **kwargs: {
            "items": [
                {
                    "title": "IANA-managed Reserved Domains",
                    "source_path": str(tmp_path / "notes" / "sources" / "iana.md"),
                    "tags": ["example", "web-capture"],
                }
            ],
            "count": 1,
        },
        raising=False,
    )

    result = json.loads(asyncio.run(demo_tools.demo_run_discover_capture_impl()))

    assert result["success"] is True
    assert result["status"] == "pass"
    assert "Workflow Example 02 is running" in result["chat_output"]
    assert "Command surface: 3 command groups" in result["chat_output"]
    assert "Saved webpage: IANA-managed Reserved Domains" in result["chat_output"]
    assert "Human artifact: Workflow Example 02 proof card." in result["chat_output"]
    assert 'Open in Browse: search "Workflow Example 02 Command Surface Web Capture".' in result["chat_output"]
    assert 'What to show: Discover command list, then the saved page from Browse search "IANA-managed Reserved Domains".' in result["chat_output"]
    assert "Example status: pass." in result["chat_output"]
    artifact_path = _assert_ranked_demo_artifact(result)
    _meta, artifact_body = parse_frontmatter(artifact_path)
    assert "# Workflow Example 02: Command Surface And Web Capture" in artifact_body
    assert "IANA-managed Reserved Domains" in artifact_body


def test_demo_url_capture_normalizer_updates_deduped_source_card(tmp_path: Path) -> None:
    from skills.demo.scripts.mcp import demo_tools

    card = tmp_path / "notes" / "iana.md"
    write_vault_frontmatter(
        card,
        {
            "title": "IANA-managed Reserved Domains",
            "x-augur-note-type": "url",
            "tags": ["demo", "discover", "web-capture"],
            "note": "Demo 02 web capture proof",
            "_relates_to": ["[[demo]]", "[[discover]]", "[[web-capture]]"],
        },
        "# IANA-managed Reserved Domains\n\nBody stays intact.\n",
    )
    payload: dict[str, object] = {"path": str(card)}

    demo_tools._normalize_demo_url_capture_card(payload)

    metadata, body = parse_frontmatter(card)
    assert "demo" not in metadata["tags"]
    assert "example" in metadata["tags"]
    assert "workflow-example" in metadata["tags"]
    assert metadata["note"] == "Workflow Example 02 repeatable web capture proof."
    assert "[[demo]]" not in metadata["_relates_to"]
    assert "[[workflow-example]]" in metadata["_relates_to"]
    assert payload["tags"] == metadata["tags"]
    assert "Body stays intact." in body


def _demo_compound_cluster_fixture(tmp_path: Path) -> list[dict[str, object]]:
    synthesis_path = tmp_path / "knowledge" / "syntheses" / "compound-preview.md"
    synthesis_path.parent.mkdir(parents=True)
    synthesis_path.write_text(
        "Compounding is governed promotion from retained outcomes.",
        encoding="utf-8",
    )
    return [
        {
            "label": "What pattern is emerging in how I want Augur's wiki to compound",
            "summary": "Compounding is governed promotion from retained outcomes.",
            "item_count": 4,
            "priority_score": 0.843,
            "items": [{"path": str(synthesis_path)}],
            "page_targets": [
                {"page": "concepts/wiki-ingest-and-compilation-commands"}
            ],
        }
    ]


def test_demo_run_compound_preview_impl_formats_cluster_without_wiki_apply(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    monkeypatch.setattr(demo_tools, "get_vault_dir", lambda: tmp_path)
    monkeypatch.setattr(
        demo_tools,
        "reset_demo_run_state",
        lambda reason, vault_dir=None: tmp_path / "notes" / "examples" / "workflow-example-run.md",
    )
    monkeypatch.setattr(
        demo_tools,
        "_demo_wiki_ask_clusters",
        lambda days_back, limit: _demo_compound_cluster_fixture(tmp_path),
    )

    result = json.loads(
        asyncio.run(demo_tools.demo_run_compound_preview_impl(days_back=90, limit=5))
    )

    assert result["success"] is True
    assert result["status"] == "pass"
    assert "Workflow Example 04 is running" in result["chat_output"]
    assert "Safety proof: no wiki apply command was run" in result["chat_output"]
    assert "priority_score 0.843" in result["chat_output"]
    assert "Human artifact: Workflow Example 04 proof card." in result["chat_output"]
    assert 'Open in Browse: search "Workflow Example 04 Governed Compounding Preview".' in result["chat_output"]
    assert "What to show: 4 retained outcomes would strengthen Wiki Ingest And Compilation Commands." in result["chat_output"]
    assert "Example status: pass." in result["chat_output"]
    artifact_path = _assert_ranked_demo_artifact(result)
    _meta, artifact_body = parse_frontmatter(artifact_path)
    assert "# Workflow Example 04: Governed Compounding Preview" in artifact_body
    assert "no wiki page was mutated" in artifact_body


def test_demo_run_transcription_offload_marks_regular_fallback_partial(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    source_file = tmp_path / "offload-demo-short.m4a"
    source_file.write_bytes(b"audio")
    monkeypatch.setenv("GEMINI_SESSION", "session-123")
    monkeypatch.setattr(demo_tools, "get_vault_dir", lambda: tmp_path)
    monkeypatch.setattr(
        demo_tools,
        "reset_demo_run_state",
        lambda reason, vault_dir=None: tmp_path / "notes" / "examples" / "workflow-example-run.md",
    )
    monkeypatch.setattr(
        demo_tools,
        "_demo_airplane_action",
        lambda action: {"airplane_mode": {"enabled": False}},
    )

    async def fake_transcript(source_path: str, title: str = "") -> str:
        route_mode = "offline" if "Offline" in title else "regular"
        transcript_file = tmp_path / f"offload-demo-short-{route_mode}.md"
        transcript_file.write_text(
            "\n".join(
                [
                    "---",
                    "type: workflow-example-transcript",
                    f"route_mode: {route_mode}",
                    "---",
                    "",
                    "# Transcript",
                    "",
                    "## Routing",
                    "",
                    f"- Mode: `{route_mode}`",
                    "",
                    "## Transcript",
                    "",
                    f"Actual {route_mode} words from the recording.",
                ]
            ),
            encoding="utf-8",
        )
        payload = {
            "success": True,
            "route_mode": route_mode,
            "route_engine_id": "gemini-transcribe" if route_mode == "regular" else "faster-whisper",
            "fallback_engine_id": "faster-whisper" if route_mode == "regular" else None,
            "cloud_used": False,
            "needs_review": route_mode == "regular",
            "source_path": str(source_file),
            "transcript_path": str(transcript_file),
            "evidence_path": str(tmp_path / f"{route_mode}-evidence.md"),
        }
        return json.dumps(payload)

    monkeypatch.setattr(demo_tools, "demo_run_transcript_impl", fake_transcript)

    result = json.loads(
        asyncio.run(
            demo_tools.demo_run_transcription_offload_impl(
                source_path=str(source_file),
                title="Offload Workflow Example",
            )
        )
    )

    assert result["success"] is True
    assert result["status"] == "partial-pass"
    assert "Regular fallback: fallback_engine faster-whisper" in result["chat_output"]
    assert "Human artifact: Workflow Example 03 proof card plus offline and online transcript files." in result["chat_output"]
    assert 'Open in Browse: search "Workflow Example 03 Offline Online Transcription Offload".' in result["chat_output"]
    assert 'Offline transcript card: search Browse for "Offload Workflow Example Offline".' in result["chat_output"]
    assert 'Open offline transcript file: search Browse for "offload-demo-short" or open "offload-demo-short-offline.md".' in result["chat_output"]
    assert "Offline transcript preview: Actual offline words from the recording." in result["chat_output"]
    assert 'Online transcript card: search Browse for "Offload Workflow Example Regular".' in result["chat_output"]
    assert 'Open online transcript file: search Browse for "offload-demo-short" or open "offload-demo-short-regular.md".' in result["chat_output"]
    assert "Online transcript preview: Actual regular words from the recording." in result["chat_output"]
    assert str(tmp_path) not in result["chat_output"]
    assert "Example status: partial-pass." in result["chat_output"]
    artifact_path = _assert_ranked_demo_artifact(result)
    _meta, artifact_body = parse_frontmatter(artifact_path)
    assert "# Workflow Example 03: Offline And Online Transcription Offload" in artifact_body
    assert "Actual offline words from the recording." in artifact_body
    assert "Actual regular words from the recording." in artifact_body


def test_demo_transcript_preview_uses_workflow_example_language(tmp_path: Path) -> None:
    from skills.demo.scripts.mcp import demo_tools

    transcript_file = tmp_path / "transcript.md"
    transcript_file.write_text(
        "\n".join(
            [
                "# Transcript",
                "",
                "## Transcript",
                "",
                "Okay, I am recording a demo from the transcript.",
            ]
        ),
        encoding="utf-8",
    )

    assert demo_tools._demo_transcript_preview({"transcript_path": str(transcript_file)}) == (
        "Okay, I am recording a workflow example from the transcript."
    )


def test_demo_run_transcription_offload_skips_online_outside_gemini(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    source_file = tmp_path / "offload-demo-short.m4a"
    source_file.write_bytes(b"audio")
    calls: list[str] = []
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-123")
    monkeypatch.delenv("GEMINI_SESSION", raising=False)
    monkeypatch.setattr(demo_tools, "get_vault_dir", lambda: tmp_path)
    monkeypatch.setattr(
        demo_tools,
        "reset_demo_run_state",
        lambda reason, vault_dir=None: tmp_path / "notes" / "examples" / "workflow-example-run.md",
    )
    monkeypatch.setattr(
        demo_tools,
        "_demo_airplane_action",
        lambda action: {"airplane_mode": {"enabled": False}},
    )

    async def fake_transcript(source_path: str, title: str = "") -> str:
        calls.append(title)
        transcript_file = tmp_path / "offload-demo-short-offline.md"
        transcript_file.write_text(
            "\n".join(
                [
                    "---",
                    "type: workflow-example-transcript",
                    "route_mode: offline",
                    "---",
                    "",
                    "# Transcript",
                    "",
                    "## Routing",
                    "",
                    "- Mode: `offline`",
                    "",
                    "## Transcript",
                    "",
                    "Actual offline words from the recording.",
                ]
            ),
            encoding="utf-8",
        )
        return json.dumps(
            {
                "success": True,
                "route_mode": "offline",
                "route_engine_id": "faster-whisper",
                "cloud_used": False,
                "needs_review": False,
                "source_path": str(source_file),
                "transcript_path": str(transcript_file),
                "evidence_path": str(tmp_path / "offline-evidence.md"),
            }
        )

    monkeypatch.setattr(demo_tools, "demo_run_transcript_impl", fake_transcript)

    result = json.loads(
        asyncio.run(
            demo_tools.demo_run_transcription_offload_impl(
                source_path=str(source_file),
                title="Offload Workflow Example",
            )
        )
    )

    assert result["success"] is True
    assert result["status"] == "partial-pass"
    assert calls == ["Offload Workflow Example Offline"]
    assert result["active_client"] == "codex"
    assert "Online route: skipped because active client is codex" in result["chat_output"]
    assert "Run this workflow example from Gemini" in result["chat_output"]
    assert "Human artifact: Workflow Example 03 proof card and transcript file." in result["chat_output"]
    assert 'Open in Browse: search "Workflow Example 03 Offline Online Transcription Offload".' in result["chat_output"]
    assert 'Transcript card: search Browse for "Offload Workflow Example Offline".' in result["chat_output"]
    assert 'Open transcript file: search Browse for "offload-demo-short" or open "offload-demo-short-offline.md".' in result["chat_output"]
    assert "Transcript preview: Actual offline words from the recording." in result["chat_output"]
    assert "Evidence card: written." in result["chat_output"]
    assert str(tmp_path) not in result["chat_output"]
    assert "Example status: partial-pass." in result["chat_output"]
    artifact_path = _assert_ranked_demo_artifact(result)
    _meta, artifact_body = parse_frontmatter(artifact_path)
    assert "# Workflow Example 03: Offline And Online Transcription Offload" in artifact_body
    assert "Actual offline words from the recording." in artifact_body
    assert "Gemini" in artifact_body


def test_demo_run_airplane_safety_impl_formats_smoke_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    evidence_path = tmp_path / "evidence.md"
    write_vault_frontmatter(
        evidence_path,
        {
            "title": "demo-meeting",
            "tags": ["inbox", "meetings"],
            "_relates_to": ["[[inbox]]", "[[meetings]]"],
        },
        "\n".join(
            [
                "# demo-meeting",
                "",
                "> Augur Investor Demo Meeting Reviewed Investor Demo Readiness.",
                "",
                "## Meeting Memory",
                "",
                "Augur Investor Demo Meeting Reviewed Investor Demo Readiness.",
                "",
            ]
        ),
    )
    monkeypatch.setattr(demo_tools, "get_vault_dir", lambda: tmp_path)
    monkeypatch.setattr(
        demo_tools,
        "reset_demo_run_state",
        lambda reason, vault_dir=None: tmp_path / "notes" / "examples" / "workflow-example-run.md",
    )
    monkeypatch.setattr(
        demo_tools,
        "_demo_airplane_status",
        lambda: {"airplane_mode": {"enabled": False}},
        raising=False,
    )
    monkeypatch.setattr(
        demo_tools,
        "_demo_airplane_smoke",
        lambda: {
            "success": True,
            "cloud_calls": 0,
            "files_indexed": 3,
            "evidence_pin": {"added": True, "path": str(evidence_path), "title": "demo-meeting"},
            "readiness": {
                "capabilities": {
                    "policy": {"cloud_escalation_allowed": False},
                    "local_engines": ["OpenVINO", "faster-whisper", "Ollama"],
                }
            },
        },
        raising=False,
    )

    result = json.loads(asyncio.run(demo_tools.demo_run_airplane_safety_impl()))

    assert result["success"] is True
    assert result["status"] == "pass"
    assert "Workflow Example 05 is running" in result["chat_output"]
    assert "Cloud calls: 0." in result["chat_output"]
    assert "files_indexed 3" in result["chat_output"]
    assert "Human artifact: Workflow Example 05 proof card." in result["chat_output"]
    assert 'Open in Browse: search "Workflow Example 05 Local Only Safety Evidence".' in result["chat_output"]
    assert "What to show: Cloud calls: 0; files indexed: 3; local engines visible before launch." in result["chat_output"]
    assert "Evidence: saved workflow example evidence card Workflow Example Meeting Evidence." in result["chat_output"]
    assert str(tmp_path) not in result["chat_output"]
    assert "Example status: pass." in result["chat_output"]
    artifact_path = _assert_ranked_demo_artifact(result)
    _meta, artifact_body = parse_frontmatter(artifact_path)
    assert "# Workflow Example 05: Local-Only Safety Evidence" in artifact_body
    assert "Cloud calls: 0" in artifact_body
    assert "Evidence card: Workflow Example Meeting Evidence" in artifact_body
    assert "demo-meeting" not in artifact_body
    evidence_meta, evidence_body = parse_frontmatter(evidence_path)
    assert evidence_meta["title"] == "Workflow Example Meeting Evidence"
    assert "workflow-example" in evidence_meta["tags"]
    assert "# Workflow Example Meeting Evidence" in evidence_body
    assert "Workflow Example Readiness" in evidence_body


def test_demo_run_brain_manifest_impl_reads_real_folder_contract(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    project = tmp_path / "project"
    brain = project / "project-brain"
    for relative in [
        "capabilities/skills",
        "knowledge",
        "instructions",
        "decisions/adrs",
        "workflows",
    ]:
        (brain / relative).mkdir(parents=True)
    (brain / "BRAIN.yaml").write_text(
        "schema_version: 1\nid: project-augur\ntype: project\nroot: .\nattached_project: ..\n",
        encoding="utf-8",
    )
    (brain / "README.md").write_text("# Project brain\n", encoding="utf-8")

    monkeypatch.setattr(demo_tools, "get_project_root", lambda: project)
    monkeypatch.setattr(demo_tools, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        demo_tools,
        "reset_demo_run_state",
        lambda reason, vault_dir=None: tmp_path / "vault" / "notes" / "examples" / "workflow-example-run.md",
    )

    result = json.loads(asyncio.run(demo_tools.demo_run_brain_manifest_impl()))

    assert result["success"] is True
    assert result["status"] == "pass"
    assert result["manifest"]["id"] == "project-augur"
    assert "Workflow Example 06 is running" in result["chat_output"]
    assert "Brain manifest: project-augur, type project" in result["chat_output"]
    assert "Folder contract: capabilities/skills" in result["chat_output"]
    assert "Human artifact: Workflow Example 06 proof card." in result["chat_output"]
    assert 'Open in Browse: search "Workflow Example 06 Brain Manifest Architecture".' in result["chat_output"]
    assert "What to show: BRAIN.yaml, capabilities/skills, knowledge, instructions, decisions/adrs, and the personal brain separation." in result["chat_output"]
    assert str(tmp_path) not in result["chat_output"]
    assert "Example status: pass." in result["chat_output"]
    artifact_path = _assert_ranked_demo_artifact(result)
    _meta, artifact_body = parse_frontmatter(artifact_path)
    assert "# Workflow Example 06: Brain Manifest Architecture" in artifact_body
    assert "BRAIN.yaml" in artifact_body


def test_demo_run_transcript_impl_forwards_normalized_source(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools
    import src.lib.routing as routing

    source_file = tmp_path / "call.m4a"
    source_file.write_bytes(b"audio")
    captured = {}
    routed = {}

    def fake_run_transcript_case(source_path, **kwargs):
        captured["source_path"] = source_path
        captured.update(kwargs)
        return {
            "success": True,
            "status": "pass",
            "transcript_path": str(tmp_path / "transcript.md"),
            "evidence_path": str(tmp_path / "evidence.md"),
            "backend": "gemini",
            "method": "gemini-transcribe",
            "route_mode": "regular",
            "route_engine_id": "gemini-transcribe",
            "fallback_engine_id": None,
            "cloud_used": True,
            "needs_review": False,
            "route_note": (
                "Airplane mode OFF: using gemini-transcribe; local Whisper "
                "is not the selected route."
            ),
        }

    def fake_transcribe(path: str, **kwargs):
        routed["path"] = path
        routed["kwargs"] = kwargs
        return None

    refresh_calls: list[Path] = []

    def fake_refresh(*, vault_dir: Path):
        refresh_calls.append(vault_dir)
        return {"success": True}

    monkeypatch.setattr(demo_tools, "run_transcript_case", fake_run_transcript_case)
    monkeypatch.setattr(routing, "transcribe", fake_transcribe)
    monkeypatch.setattr(
        "src.lib.ingest.note_index_refresh.refresh_notes_browse_index",
        fake_refresh,
    )
    monkeypatch.setattr(demo_tools, "get_vault_dir", lambda: tmp_path)

    payload = json.loads(
        asyncio.run(
            demo_tools.demo_run_transcript_impl(
                source_path=str(source_file),
                title="Customer Call",
            )
        )
    )

    assert payload["success"] is True
    assert payload["status"] == "pass"
    assert payload["transcript_path"] == str(tmp_path / "transcript.md")
    assert payload["evidence_path"] == str(tmp_path / "evidence.md")
    assert payload["backend"] == "gemini"
    assert payload["method"] == "gemini-transcribe"
    assert payload["route_mode"] == "regular"
    assert payload["route_engine_id"] == "gemini-transcribe"
    assert payload["fallback_engine_id"] is None
    assert payload["cloud_used"] is True
    assert payload["needs_review"] is False
    assert payload["route_note"].startswith("Airplane mode OFF")
    assert payload["title"] == "Customer Call"
    assert captured["source_path"] == source_file
    assert captured["run_eval"] is True
    assert captured["source_title"] == "Customer Call"
    assert captured["replace_existing"] is True
    assert callable(captured["transcribe"])
    assert refresh_calls == [tmp_path]

    captured["transcribe"](source_file)

    assert routed["path"] == str(source_file)
    assert routed["kwargs"] == {"gemini_timeout_s": 10}


def test_demo_run_transcript_impl_rejects_empty_source_path() -> None:
    from skills.demo.scripts.mcp import demo_tools

    payload = json.loads(
        asyncio.run(demo_tools.demo_run_transcript_impl(source_path=""))
    )

    assert payload["success"] is False
    assert "source_path" in payload["error"]


def test_demo_run_meeting_memory_impl_forwards_source_and_transcript(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    source_file = tmp_path / "call.m4a"
    transcript_file = tmp_path / "call.md"
    source_file.write_bytes(b"audio")
    transcript_file.write_text("Decision: proceed.", encoding="utf-8")
    captured = {}

    def fake_run_meeting_memory_case(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "status": "pass",
            "memory_path": str(tmp_path / "memory.md"),
            "evidence_path": str(tmp_path / "evidence.md"),
            "transcript_path": str(transcript_file),
        }

    monkeypatch.setattr(
        demo_tools,
        "run_meeting_memory_case",
        fake_run_meeting_memory_case,
    )

    payload = json.loads(
        asyncio.run(
            demo_tools.demo_run_meeting_memory_impl(
                source_path=str(source_file),
                transcript_path=str(transcript_file),
                title="Customer Call",
            )
        )
    )

    assert payload["success"] is True
    assert payload["memory_path"] == str(tmp_path / "memory.md")
    assert payload["evidence_path"] == str(tmp_path / "evidence.md")
    assert payload["transcript_path"] == str(transcript_file)
    assert payload["title"] == "Customer Call"
    assert captured["source_path"] == source_file
    assert captured["transcript_path"] == transcript_file
    assert captured["run_eval"] is True
    assert captured["source_title"] == "Customer Call"


def test_demo_run_ask_transcript_impl_forwards_question(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    transcript_file = tmp_path / "call.md"
    transcript_file.write_text("Decision: proceed.", encoding="utf-8")
    captured = {}

    def fake_run_ask_transcript_case(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "status": "pass",
            "answer": "Proceed with onboarding.",
            "answer_path": str(tmp_path / "answer.md"),
            "evidence_path": str(tmp_path / "evidence.md"),
            "transcript_path": str(transcript_file),
        }

    monkeypatch.setattr(
        demo_tools,
        "run_ask_transcript_case",
        fake_run_ask_transcript_case,
    )

    payload = json.loads(
        asyncio.run(
            demo_tools.demo_run_ask_transcript_impl(
                transcript_path=str(transcript_file),
                question="What was decided?",
                title="Customer Call",
            )
        )
    )

    assert payload["success"] is True
    assert payload["answer"] == "Proceed with onboarding."
    assert payload["answer_path"] == str(tmp_path / "answer.md")
    assert payload["evidence_path"] == str(tmp_path / "evidence.md")
    assert payload["title"] == "Customer Call"
    assert captured["source_path"] is None
    assert captured["transcript_path"] == transcript_file
    assert captured["question"] == "What was decided?"
    assert captured["run_eval"] is True
    assert captured["source_title"] == "Customer Call"


def test_demo_run_record_evidence_rejects_empty_source_path() -> None:
    from skills.demo.scripts.mcp import demo_tools

    payload = json.loads(
        asyncio.run(
            demo_tools.demo_run_record_evidence_impl(
                source_path="",
                case_id="meeting-transcript",
                command="aug demo-smoke",
                status="pass",
                backend="local",
                useful_snippet="Captured decisions.",
            )
        )
    )

    assert payload["success"] is False
    assert "source_path" in payload["error"]


def test_demo_run_record_evidence_rejects_missing_source_path(tmp_path: Path) -> None:
    from skills.demo.scripts.mcp import demo_tools

    missing_source = tmp_path / "missing transcript.md"

    payload = json.loads(
        asyncio.run(
            demo_tools.demo_run_record_evidence_impl(
                source_path=str(missing_source),
                case_id="meeting-transcript",
                command="aug demo-smoke",
                status="pass",
                backend="local",
                useful_snippet="Captured decisions.",
            )
        )
    )

    assert payload["success"] is False
    assert "source path" in payload["error"].lower()
    assert "missing" in payload["error"].lower()


def test_demo_run_record_evidence_impl_forwards_run_eval_true(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    source_file = tmp_path / "deck critique.md"
    source_file.write_text("Augur Demo Deck critique.", encoding="utf-8")
    evidence_path = tmp_path / "vault" / "notes" / "examples" / "evidence" / "deck.md"
    captured = {}

    def fake_write_demo_evidence(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            path=evidence_path,
            case_id=kwargs["case_id"],
            command=kwargs["command"],
            status=kwargs["status"],
            backend=kwargs["backend"],
            client=kwargs["client"],
            source_file=kwargs["source_file"],
            source_title=kwargs["source_title"],
            eval_run_id="deck-run",
            eval_link="/documents/evals/demo-runs/deck-run.json",
            eval_status="pass",
            eval_error=None,
        )

    monkeypatch.setattr(demo_tools, "write_demo_evidence", fake_write_demo_evidence)

    payload = json.loads(
        asyncio.run(
            demo_tools.demo_run_record_evidence_impl(
                source_path=str(source_file),
                case_id="deck-slide-critique",
                command="demo-run-record-evidence",
                status="pass",
                backend="local-critique",
                source_name="Q2 Launch Deck Review",
                useful_snippet="Augur Demo Deck names Claude and slide metadata.",
            )
        )
    )

    assert payload["success"] is True
    assert captured["run_eval"] is True
    assert captured["source_title"] == "Q2 Launch Deck Review"
    assert payload["source_name"] == "Q2 Launch Deck Review"
    assert payload["eval_run_id"] == "deck-run"
    assert payload["eval_link"] == "/documents/evals/demo-runs/deck-run.json"


def test_demo_run_record_evidence_writes_real_command_and_source(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools
    from skills.demo.scripts import demo_run_acceptance

    vault_dir = tmp_path / "vault"
    source_file = tmp_path / "real meeting transcript.md"
    source_file.write_text("Decision: ship the Browse artifact.", encoding="utf-8")
    monkeypatch.setattr(demo_tools, "get_vault_dir", lambda: vault_dir)
    monkeypatch.setattr(
        demo_run_acceptance,
        "_default_eval_runner",
        lambda **kwargs: {
            "status": "pass",
            "run_id": "meeting-run",
            "record_path": str(tmp_path / "documents" / "evals" / "meeting-run.json"),
            "scores": {
                "grounding": 4,
                "specificity": 4,
                "judge_readiness": 4,
                "speed": 3,
            },
            "findings": ["Meeting evidence was grounded."],
        },
        raising=False,
    )

    payload = json.loads(
        asyncio.run(
            demo_tools.demo_run_record_evidence_impl(
                source_path=str(source_file),
                case_id="meeting-transcript",
                command="aug inbox consume --real-data",
                status="pass",
                backend="local-ocr",
                client="claude",
                duration_seconds=3.5,
                useful_snippet="Decision: ship the Browse artifact.",
            )
        )
    )

    evidence_path = Path(payload["evidence_path"])
    evidence_text = evidence_path.read_text(encoding="utf-8")
    assert payload["success"] is True
    assert evidence_path.exists()
    assert "aug inbox consume --real-data" in evidence_text
    assert str(source_file) in evidence_text
    assert payload["source_path"] == str(source_file)
    assert payload["eval_run_id"] == "meeting-run"


def test_demo_run_record_evidence_reports_partial_on_eval_fail(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools
    from skills.demo.scripts import demo_run_acceptance

    vault_dir = tmp_path / "vault"
    source_file = tmp_path / "real deck critique.md"
    source_file.write_text(
        "Claude and metadata without the source title.", encoding="utf-8"
    )
    monkeypatch.setattr(demo_tools, "get_vault_dir", lambda: vault_dir)
    monkeypatch.setattr(
        demo_run_acceptance,
        "_default_eval_runner",
        lambda **kwargs: {
            "status": "fail",
            "run_id": "deck-fail-run",
            "record_path": str(tmp_path / "documents" / "evals" / "deck-fail.json"),
            "scores": {
                "grounding": 2,
                "specificity": 4,
                "judge_readiness": 2,
                "speed": 3,
            },
            "findings": ["Output did not name the source title."],
        },
        raising=False,
    )

    payload = json.loads(
        asyncio.run(
            demo_tools.demo_run_record_evidence_impl(
                source_path=str(source_file),
                case_id="deck-slide-critique",
                command="aug demo critique",
                status="pass",
                backend="local-critique",
                useful_snippet="Claude and metadata without the source title.",
            )
        )
    )

    assert payload["success"] is False
    assert payload["partial"] is True
    assert payload["status"] == "fail"
    assert payload["command_status"] == "pass"
    assert payload["eval_success"] is False
    assert payload["eval_status"] == "fail"
    assert payload["evidence_path"]
    evidence_path = Path(payload["evidence_path"])
    assert evidence_path.exists()
    from src.lib.frontmatter_utils import parse_frontmatter

    metadata, body = parse_frontmatter(evidence_path)
    assert metadata["demo_status"] == "fail"
    assert metadata["command_status"] == "pass"
    assert "- Status: `pass`" not in body
    assert "- Command outcome: `pass`" in body
    assert "Output did not name the source title." in body


def test_demo_run_record_evidence_reports_partial_on_eval_exception(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools
    from skills.demo.scripts import demo_run_acceptance

    vault_dir = tmp_path / "vault"
    source_file = tmp_path / "real deck critique.md"
    source_file.write_text(
        "Augur Demo Deck names Claude and metadata.", encoding="utf-8"
    )
    monkeypatch.setattr(demo_tools, "get_vault_dir", lambda: vault_dir)

    def failing_eval_runner(**kwargs):
        raise RuntimeError("eval record store unavailable")

    monkeypatch.setattr(
        demo_run_acceptance,
        "_default_eval_runner",
        failing_eval_runner,
        raising=False,
    )

    payload = json.loads(
        asyncio.run(
            demo_tools.demo_run_record_evidence_impl(
                source_path=str(source_file),
                case_id="deck-slide-critique",
                command="aug demo critique",
                status="pass",
                backend="local-critique",
                useful_snippet="Augur Demo Deck names Claude and metadata.",
            )
        )
    )

    assert payload["success"] is False
    assert payload["partial"] is True
    assert payload["status"] == "fail"
    assert payload["command_status"] == "pass"
    assert payload["eval_success"] is False
    assert payload["eval_status"] == "error"
    assert payload["eval_error"] == "eval record store unavailable"
    assert payload["evidence_path"]
    evidence_path = Path(payload["evidence_path"])
    assert evidence_path.exists()
    from src.lib.frontmatter_utils import parse_frontmatter

    metadata, body = parse_frontmatter(evidence_path)
    assert metadata["demo_status"] == "fail"
    assert metadata["command_status"] == "pass"
    assert "- Status: `pass`" not in body
    assert "- Command outcome: `pass`" in body
    assert "eval record store unavailable" in body


def test_demo_run_prompt_builds_grounded_prompt(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    rag_dir = tmp_path / "rag"
    source_file = tmp_path / "docs" / "augur-deck-ignite-v2.pptx"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"pptx placeholder")
    index_file = rag_dir / "documents" / "venture-augur" / "augur-deck-ignite-v2.md"
    index_file.parent.mkdir(parents=True)
    index_file.write_text(
        "\n".join(
            [
                "---",
                "type: document",
                "name: augur-deck-ignite-v2",
                f"source_path: {source_file}",
                "document_summary: Every AI PC runs your company's brains.",
                "document_key_insights:",
                "  - Local-first, in every AI client",
                "  - Cross-vendor governance from one enterprise back end",
                "document_sections:",
                "  - Slide 1 title",
                "document_action_candidates:",
                "  - Show offline transcript and Claude/Gemini review from the same deck",
                "---",
                "",
                "<!-- Slide number: 1 -->",
                "AUGUR",
                "Every AI PC runs your company's brains.",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(demo_tools, "get_rag_dir", lambda: rag_dir, raising=False)

    payload = json.loads(
        asyncio.run(
            demo_tools.demo_run_prompt_impl(
                source_path=str(source_file),
                title="Q2 Launch Deck Review",
                client="claude",
                prompt_kind="judge-value",
            )
        )
    )

    assert payload["success"] is True
    assert payload["client"] == "claude"
    assert payload["prompt_kind"] == "judge-value"
    assert "Q2 Launch Deck Review" in payload["prompt"]
    assert str(source_file) in payload["prompt"]
    assert "claude" in payload["prompt"]
    assert "concrete improvements" in payload["prompt"]
    assert "risk" in payload["prompt"]
    assert payload["artifact_context"]["matched"] is True
    assert "Artifact evidence from Browse index" in payload["prompt"]
    assert "Every AI PC runs your company's brains" in payload["prompt"]
    assert "Local-first, in every AI client" in payload["prompt"]
    assert "Cross-vendor governance from one enterprise back end" in payload["prompt"]
    assert "Slide 1 title" in payload["prompt"]


def test_pending_packet_tool_returns_drop_target(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp import inbox_tools

    packet_dir = tmp_path / "docs" / "inbox" / "claude" / "packet"

    monkeypatch.setattr(
        inbox_tools,
        "create_pending_packet",
        lambda **kwargs: type(
            "Packet",
            (),
            {
                "packet_id": "packet",
                "packet_dir": str(packet_dir),
                "status": "pending_content",
                "failure_state": "pending_content",
            },
        )(),
    )

    payload = json.loads(
        asyncio.run(
            inbox_tools.inbox_pending_packet_impl(
                source_id="claude-chat",
                title="Deck",
                user_instruction="save this deck",
            )
        )
    )

    assert payload["success"] is True
    assert payload["packet_id"] == "packet"
    assert payload["drop_target"] == str(packet_dir)
    assert payload["failure_state"] == "pending_content"


def test_demo_readiness_tool_returns_json(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    monkeypatch.setattr(
        demo_tools,
        "check_demo_readiness",
        lambda **kwargs: {
            "ready": True,
            "failures": [],
            "desktop": str(kwargs["desktop"]),
        },
    )

    payload = json.loads(
        asyncio.run(
            demo_tools.demo_readiness_impl(
                desktop=str(tmp_path),
                require_cloud=True,
            )
        )
    )

    assert payload["success"] is True
    assert payload["ready"] is True
    assert payload["desktop"] == str(tmp_path)


def test_demo_reset_tool_uses_real_reset(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    monkeypatch.setattr(demo_tools, "_store_root", lambda: tmp_path / "state")
    monkeypatch.setattr(demo_tools, "get_vault_dir", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        demo_tools,
        "get_preferences_path",
        lambda: tmp_path / "preferences.yaml",
    )
    monkeypatch.setattr(
        demo_tools,
        "prepare_demo_state",
        lambda **kwargs: {
            "success": True,
            "desktop": str(kwargs["desktop"]),
            "files": [],
            "airplane_mode": kwargs["airplane_mode"],
        },
    )

    payload = json.loads(
        asyncio.run(demo_tools.demo_reset_impl(desktop=str(tmp_path), airplane="off"))
    )

    assert payload["success"] is True
    assert payload["airplane"] == "off"
    assert payload["airplane_mode"] is False


def test_demo_smoke_tool_returns_json(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from skills.demo.scripts.mcp import demo_tools

    monkeypatch.setattr(
        demo_tools,
        "run_demo_smoke",
        lambda **kwargs: {
            "success": True,
            "cloud_calls": 0,
            "desktop": str(kwargs["desktop"]),
        },
    )

    payload = json.loads(
        asyncio.run(
            demo_tools.demo_smoke_impl(
                desktop=str(tmp_path),
                airplane="on",
                require_cloud=False,
            )
        )
    )

    assert payload["success"] is True
    assert payload["cloud_calls"] == 0


def test_scan_folder_mcp_response_truncates_items_and_preserves_counts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools

    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")
    folder_path = tmp_path / "Desktop"
    folder_path.mkdir()
    for index in range(3):
        (folder_path / f"document-{index}.pdf").write_bytes(b"%PDF-1.7\n")

    added = json.loads(
        asyncio.run(
            inbox_tools.inbox_folders_impl(
                action="add",
                name="Desktop",
                path=str(folder_path),
            )
        )
    )
    scanned = json.loads(
        asyncio.run(
            inbox_tools.inbox_scan_folder_impl(
                folder_id=added["folder"]["id"],
                limit=2,
            )
        )
    )

    assert scanned["success"] is True
    assert scanned["folder"]["counts"]["new_files"] == 3
    assert scanned["folder"]["last_scan_at"]
    assert scanned["items_total"] == 3
    assert scanned["items_truncated"] is True
    assert [item["name"] for item in scanned["items"]] == [
        "document-0.pdf",
        "document-1.pdf",
    ]


def test_scan_folder_mcp_response_clamps_to_server_max(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools

    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")
    folder_path = tmp_path / "Desktop"
    folder_path.mkdir()
    for index in range(205):
        (folder_path / f"document-{index:03}.pdf").write_bytes(b"%PDF-1.7\n")

    added = json.loads(
        asyncio.run(
            inbox_tools.inbox_folders_impl(
                action="add",
                name="Desktop",
                path=str(folder_path),
            )
        )
    )
    scanned = json.loads(
        asyncio.run(
            inbox_tools.inbox_scan_folder_impl(
                folder_id=added["folder"]["id"],
                limit=999,
            )
        )
    )

    assert scanned["folder"]["counts"]["new_files"] == 205
    assert scanned["items_total"] == 205
    assert scanned["items_truncated"] is True
    assert len(scanned["items"]) == 200


def test_purge_folder_mcp_moves_only_trash_candidates(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools

    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")
    monkeypatch.setattr(
        "skills.ingest.scripts.inbox_purge.get_runtime_dir",
        lambda: runtime_dir,
    )
    folder_path = tmp_path / "Desktop"
    folder_path.mkdir()
    document = folder_path / "keep.pdf"
    trash = folder_path / "download.tmp"
    document.write_bytes(b"%PDF-1.7\n")
    trash.write_text("partial", encoding="utf-8")
    old_time = 1_700_000_000
    os.utime(trash, (old_time, old_time))

    added = json.loads(
        asyncio.run(
            inbox_tools.inbox_folders_impl(
                action="add",
                name="Desktop",
                path=str(folder_path),
            )
        )
    )
    purged = json.loads(
        asyncio.run(
            inbox_tools.inbox_purge_folder_impl(folder_id=added["folder"]["id"])
        )
    )

    assert purged["success"] is True
    assert purged["files_moved"] == 1
    assert document.exists()
    assert not trash.exists()
    moved_files = list(
        (runtime_dir / "brain" / "inbox" / "trash").rglob("download.tmp")
    )
    assert len(moved_files) == 1

    listed = json.loads(asyncio.run(inbox_tools.inbox_folders_impl(action="list")))
    folder = listed["folders"][0]
    assert folder["counts"]["trash_candidates"] == 0
    assert folder["counts"]["document_candidates"] == 1
    assert folder["last_run_status"] == "success"


def test_consume_folder_mcp_rejects_packet_only_brain(
    monkeypatch, tmp_path: Path
) -> None:
    from skills.ingest.scripts.mcp import inbox_tools
    from src.lib.brain_registry import clear_cache
    from src.lib.brain_registry_io import save_registry
    from src.lib.brain_registry_models import (
        Brain,
        BrainRegistry,
        BrainType,
        GitArrangement,
        GitConfig,
    )

    state = tmp_path / "augur-state"
    registry_path = state / "brains.yaml"
    registry_path.parent.mkdir(parents=True)
    monkeypatch.setenv("AUGUR_STATE_DIR", str(state))
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "personal": Brain(
                    id="personal",
                    type=BrainType.PERSONAL,
                    data_root=tmp_path / "personal",
                    git=GitConfig(arrangement=GitArrangement.UNTRACKED),
                ),
                "team-core": Brain(
                    id="team-core",
                    type=BrainType.TEAM,
                    data_root=tmp_path / "team",
                    git=GitConfig(arrangement=GitArrangement.UNTRACKED),
                    write_policy="packets_only",
                ),
            },
        ),
        registry_path,
    )
    clear_cache()

    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")
    folder_path = tmp_path / "Desktop"
    folder_path.mkdir()
    try:
        added = json.loads(
            asyncio.run(
                inbox_tools.inbox_folders_impl(
                    action="add", name="Desktop", path=str(folder_path)
                )
            )
        )

        result = json.loads(
            asyncio.run(
                inbox_tools.inbox_consume_folder_impl(
                    folder_id=added["folder"]["id"], to="team-core"
                )
            )
        )
    finally:
        clear_cache()

    assert result["success"] is False
    assert "packet" in result["error"]


def test_run_history_mcp_response_limits_and_summarizes_runs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest.inbox_models import InboxFileResult, InboxRunRecord
    from skills.ingest.scripts.mcp import inbox_tools

    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")
    store = inbox_tools._store()
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    for index in range(3):
        store.save_run(
            InboxRunRecord(
                id=f"run_{index}",
                folder_id=folder.id,
                started_at=f"2026-05-07T12:0{index}:00+00:00",
                completed_at=f"2026-05-07T12:0{index}:30+00:00",
                status="success",
                airplane_mode=True,
                files_seen=1,
                files_moved=1,
                files_indexed=1,
                file_results=[
                    InboxFileResult(
                        source_path=f"C:/Desktop/report-{index}.pdf",
                        final_path=f"C:/Vault/sources/report-{index}.md",
                        source_card_path=f"sources/report-{index}.md",
                        content_type="application/pdf",
                        extraction_method="local",
                        hardware_backend="cpu",
                        confidence="high",
                        route="sources/web",
                        renamed_to=f"report-{index}.pdf",
                        rag_indexed=True,
                        status="indexed",
                    )
                ],
            )
        )

    payload = json.loads(asyncio.run(inbox_tools.inbox_run_history_impl(limit=2)))

    assert payload["success"] is True
    assert [run["id"] for run in payload["runs"]] == ["run_2", "run_1"]
    assert "file_results" not in payload["runs"][0]


def test_run_detail_mcp_response_returns_structured_errors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.lib.ingest.inbox_models import InboxRunRecord
    from skills.ingest.scripts.mcp import inbox_tools

    monkeypatch.setattr(inbox_tools, "_store_root", lambda: tmp_path / "state")
    store = inbox_tools._store()
    folder = store.add_folder(name="Desktop", path=tmp_path / "Desktop")
    store.save_run(
        InboxRunRecord(
            id="corrupt_run",
            folder_id=folder.id,
            started_at="2026-05-07T12:00:00+00:00",
            completed_at="2026-05-07T12:01:00+00:00",
            status="success",
            airplane_mode=True,
        )
    )
    store._run_path("corrupt_run").write_text("{not-json", encoding="utf-8")

    missing_id = json.loads(asyncio.run(inbox_tools.inbox_run_detail_impl()))
    missing_run = json.loads(
        asyncio.run(inbox_tools.inbox_run_detail_impl(run_id="missing"))
    )
    corrupt_run = json.loads(
        asyncio.run(inbox_tools.inbox_run_detail_impl(run_id="corrupt_run"))
    )

    assert missing_id == {"success": False, "error": "Missing run_id."}
    assert missing_run["success"] is False
    assert "Run not found: missing" in missing_run["error"]
    assert corrupt_run["success"] is False
    assert "Corrupt inbox run record: corrupt_run" in corrupt_run["error"]
