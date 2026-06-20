from __future__ import annotations

from pathlib import Path

import yaml


def test_registry_bootstraps_default_personal_vault_and_sources(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_registry as mod

    runtime = tmp_path / "runtime"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    project_root = tmp_path / "repo"
    config_dir = project_root / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "inbox.yaml").write_text(
        "version: 1\n"
        "default_sources:\n"
        "  - id: claude-chat\n"
        "    type: chat_mcp\n"
        "    domain: docs\n"
        "    write_modes: [mcp_content, filesystem_mcp, pending_drop]\n"
        "    filesystem_roots: [documents/inbox/claude]\n"
        "    default_target_vault: personal\n"
        "  - id: gmail-drop\n"
        "    type: email_drop_folder\n"
        "    domain: auto\n"
        "    path: documents/inbox/email\n"
        "    default_target_vault: personal\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(mod, "get_config_dir", lambda: project_root / "config")

    registry = mod.load_inbox_registry()

    assert registry.config_root == runtime / "brain" / "inbox" / "config"
    assert [target.id for target in registry.vaults] == ["personal"]
    assert registry.vaults[0].docs_root == str(docs)
    assert registry.vaults[0].vault_root == str(vault)
    assert {source.id for source in registry.sources} == {"claude-chat", "gmail-drop"}
    assert registry.source_by_id("claude-chat").drop_root == str(docs / "inbox" / "claude")
    assert registry.source_by_id("gmail-drop").drop_root == str(docs / "inbox" / "email")


def test_registry_loads_complete_builtin_source_lane_surface(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_registry as mod

    runtime = tmp_path / "runtime"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"

    monkeypatch.setattr(mod, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)

    registry = mod.load_inbox_registry()

    assert {source.id for source in registry.sources} == {
        "chat-save",
        "chatgpt",
        "claude-chat",
        "desktop",
        "filesystem",
        "gmail-drop",
        "manual-save",
    }
    desktop = registry.source_by_id("desktop")
    assert desktop.type == "watched_folder"
    assert desktop.drop_root == str(docs / "inbox" / "default")
    assert desktop.write_modes == ["filesystem_drop"]
    assert desktop.default_target_vault == "personal"
    assert desktop.allowed_targets == ["personal"]
    assert registry.source_by_id("filesystem").drop_root == str(docs / "inbox" / "filesystem")
    assert registry.source_by_id("manual-save").drop_root == str(docs / "inbox" / "manual")
    assert registry.source_by_id("chat-save").drop_root == str(docs / "inbox" / "chat")


def test_registry_persists_approved_vault_and_source(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_registry as mod
    from skills.ingest.scripts.inbox_unified_models import InboxSourceLane, InboxVaultTarget

    runtime = tmp_path / "runtime"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    config_dir = tmp_path / "repo" / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "inbox.yaml").write_text("version: 1\ndefault_sources: []\n", encoding="utf-8")

    monkeypatch.setattr(mod, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(mod, "get_config_dir", lambda: tmp_path / "repo" / "config")

    target = InboxVaultTarget(
        id="project-alpha",
        kind="project",
        name="Project Alpha",
        vault_root=str(tmp_path / "alpha" / "vault"),
        docs_root=str(tmp_path / "alpha" / "docs"),
        default=False,
        writable=True,
    )
    source = InboxSourceLane(
        id="desktop",
        type="watched_folder",
        name="Desktop",
        domain="auto",
        drop_root=str(tmp_path / "Desktop"),
        write_modes=["filesystem_drop"],
        default_target_vault="personal",
        allowed_targets=["personal", "project-alpha"],
        enabled=True,
    )

    saved_target = mod.register_vault_target(target)
    saved_source = mod.register_source_lane(source)
    reloaded = mod.load_inbox_registry()

    assert saved_target.id == "project-alpha"
    assert saved_source.id == "desktop"
    assert reloaded.vault_by_id("project-alpha").docs_root.endswith("alpha/docs")
    assert reloaded.source_by_id("desktop").allowed_targets == ["personal", "project-alpha"]
    assert (runtime / "brain" / "inbox" / "config" / "vaults.yaml").exists()
    assert (runtime / "brain" / "inbox" / "config" / "sources.yaml").exists()


def test_register_source_lane_persists_only_user_sources(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_registry as mod
    from skills.ingest.scripts.inbox_unified_models import InboxSourceLane

    runtime = tmp_path / "runtime"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    config_dir = tmp_path / "repo" / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "inbox.yaml").write_text(
        "version: 1\n"
        "default_sources:\n"
        "  - id: claude-chat\n"
        "    type: chat_mcp\n"
        "    domain: docs\n"
        "    filesystem_roots: [documents/inbox/claude]\n"
        "    default_target_vault: personal\n"
        "  - id: chatgpt\n"
        "    type: chat_mcp\n"
        "    domain: docs\n"
        "    filesystem_roots: [documents/inbox/chatgpt]\n"
        "    default_target_vault: personal\n"
        "  - id: gmail-drop\n"
        "    type: email_drop_folder\n"
        "    domain: auto\n"
        "    path: documents/inbox/email\n"
        "    default_target_vault: personal\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(mod, "get_config_dir", lambda: tmp_path / "repo" / "config")

    mod.register_source_lane(
        InboxSourceLane(
            id="manual",
            type="watched_folder",
            name="Manual",
            domain="auto",
            drop_root="documents/inbox/manual",
            write_modes=["filesystem_drop"],
        )
    )

    payload = yaml.safe_load((runtime / "brain" / "inbox" / "config" / "sources.yaml").read_text())
    persisted_ids = {source["id"] for source in payload["sources"]}
    assert persisted_ids == {"manual"}
    assert not {"claude-chat", "chatgpt", "gmail-drop"} & persisted_ids
    assert payload["sources"][0]["drop_root"] == str(docs / "inbox" / "manual")
    assert mod.load_inbox_registry().source_by_id("manual").drop_root == str(docs / "inbox" / "manual")


def test_registry_normalizes_persisted_drop_root(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_registry as mod

    runtime = tmp_path / "runtime"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    config_dir = tmp_path / "repo" / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "inbox.yaml").write_text("version: 1\ndefault_sources: []\n", encoding="utf-8")
    user_config_dir = runtime / "brain" / "inbox" / "config"
    user_config_dir.mkdir(parents=True)
    (user_config_dir / "sources.yaml").write_text(
        "sources:\n"
        "  - id: manual\n"
        "    type: watched_folder\n"
        "    name: Manual\n"
        "    domain: auto\n"
        "    drop_root: documents/inbox/manual\n"
        "    default_target_vault: personal\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(mod, "get_config_dir", lambda: tmp_path / "repo" / "config")

    registry = mod.load_inbox_registry()

    assert registry.source_by_id("manual").drop_root == str(docs / "inbox" / "manual")


def test_registry_merges_partial_runtime_source_override_with_default(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_registry as mod
    from skills.ingest.scripts.inbox_unified_models import InboxVaultTarget

    runtime = tmp_path / "runtime"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    config_dir = tmp_path / "repo" / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "inbox.yaml").write_text(
        "version: 1\n"
        "default_sources:\n"
        "  - id: claude-chat\n"
        "    type: chat_mcp\n"
        "    domain: docs\n"
        "    write_modes: [mcp_content, filesystem_mcp, pending_drop]\n"
        "    filesystem_roots: [documents/inbox/claude]\n"
        "    default_target_vault: personal\n",
        encoding="utf-8",
    )
    user_config_dir = runtime / "brain" / "inbox" / "config"
    user_config_dir.mkdir(parents=True)
    (user_config_dir / "sources.yaml").write_text(
        "sources:\n"
        "  - id: claude-chat\n"
        "    allowed_targets: [personal, project-alpha]\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(mod, "get_config_dir", lambda: tmp_path / "repo" / "config")
    mod.register_vault_target(
        InboxVaultTarget(
            id="project-alpha",
            kind="project",
            name="Project Alpha",
            vault_root=str(tmp_path / "alpha" / "vault"),
            docs_root=str(tmp_path / "alpha" / "docs"),
        )
    )

    registry = mod.load_inbox_registry()
    source = registry.source_by_id("claude-chat")

    assert source.type == "chat_mcp"
    assert source.domain == "docs"
    assert source.write_modes == ["mcp_content", "filesystem_mcp", "pending_drop"]
    assert source.drop_root == str(docs / "inbox" / "claude")
    assert source.default_target_vault == "personal"
    assert source.allowed_targets == ["personal", "project-alpha"]


def test_register_builtin_source_lane_persists_only_overrides(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_registry as mod
    from skills.ingest.scripts.inbox_unified_models import InboxSourceLane, InboxVaultTarget

    runtime = tmp_path / "runtime"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    config_dir = tmp_path / "repo" / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "inbox.yaml").write_text(
        "version: 1\n"
        "default_sources:\n"
        "  - id: claude-chat\n"
        "    type: chat_mcp\n"
        "    name: Claude Chat\n"
        "    domain: docs\n"
        "    write_modes: [mcp_content, filesystem_mcp, pending_drop]\n"
        "    filesystem_roots: [documents/inbox/claude]\n"
        "    default_target_vault: personal\n"
        "    allowed_targets: [personal]\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(mod, "get_config_dir", lambda: tmp_path / "repo" / "config")
    mod.register_vault_target(
        InboxVaultTarget(
            id="project-alpha",
            kind="project",
            name="Project Alpha",
            vault_root=str(tmp_path / "alpha" / "vault"),
            docs_root=str(tmp_path / "alpha" / "docs"),
        )
    )

    saved = mod.register_source_lane(
        InboxSourceLane(
            id="claude-chat",
            type="chat_mcp",
            name="Claude Chat",
            domain="docs",
            drop_root=str(docs / "inbox" / "claude"),
            write_modes=["mcp_content", "filesystem_mcp", "pending_drop"],
            default_target_vault="personal",
            allowed_targets=["personal", "project-alpha"],
        )
    )

    payload = yaml.safe_load((runtime / "brain" / "inbox" / "config" / "sources.yaml").read_text())
    assert payload["sources"] == [{"id": "claude-chat", "allowed_targets": ["personal", "project-alpha"]}]
    assert saved.allowed_targets == ["personal", "project-alpha"]
    reloaded = mod.load_inbox_registry().source_by_id("claude-chat")
    assert reloaded.type == "chat_mcp"
    assert reloaded.domain == "docs"
    assert reloaded.write_modes == ["mcp_content", "filesystem_mcp", "pending_drop"]
    assert reloaded.drop_root == str(docs / "inbox" / "claude")


def test_register_source_lane_compacts_existing_builtin_snapshots(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_registry as mod
    from skills.ingest.scripts.inbox_unified_models import InboxSourceLane, InboxVaultTarget

    runtime = tmp_path / "runtime"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    config_dir = tmp_path / "repo" / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "inbox.yaml").write_text(
        "version: 1\n"
        "default_sources:\n"
        "  - id: claude-chat\n"
        "    type: chat_mcp\n"
        "    name: Claude Chat\n"
        "    domain: docs\n"
        "    write_modes: [mcp_content, filesystem_mcp, pending_drop]\n"
        "    filesystem_roots: [documents/inbox/claude]\n"
        "    default_target_vault: personal\n"
        "    allowed_targets: [personal]\n",
        encoding="utf-8",
    )
    user_config_dir = runtime / "brain" / "inbox" / "config"
    user_config_dir.mkdir(parents=True)
    (user_config_dir / "sources.yaml").write_text(
        "sources:\n"
        "  - id: claude-chat\n"
        "    type: chat_mcp\n"
        "    name: Claude Chat\n"
        "    domain: docs\n"
        f"    drop_root: {docs / 'inbox' / 'claude'}\n"
        "    write_modes: [mcp_content, filesystem_mcp, pending_drop]\n"
        "    default_target_vault: personal\n"
        "    allowed_targets: [personal, project-alpha]\n"
        "    enabled: true\n"
        "    health_state: ready\n"
        "    health_error: ''\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(mod, "get_config_dir", lambda: tmp_path / "repo" / "config")
    mod.register_vault_target(
        InboxVaultTarget(
            id="project-alpha",
            kind="project",
            name="Project Alpha",
            vault_root=str(tmp_path / "alpha" / "vault"),
            docs_root=str(tmp_path / "alpha" / "docs"),
        )
    )

    mod.register_source_lane(
        InboxSourceLane(
            id="manual",
            type="watched_folder",
            name="Manual",
            domain="auto",
            drop_root="documents/inbox/manual",
            write_modes=["filesystem_drop"],
        )
    )

    payload = yaml.safe_load((runtime / "brain" / "inbox" / "config" / "sources.yaml").read_text())
    sources_by_id = {source["id"]: source for source in payload["sources"]}
    assert sources_by_id["claude-chat"] == {
        "id": "claude-chat",
        "allowed_targets": ["personal", "project-alpha"],
    }
    assert sources_by_id["manual"]["drop_root"] == str(docs / "inbox" / "manual")
    assert mod.load_inbox_registry().source_by_id("claude-chat").write_modes == [
        "mcp_content",
        "filesystem_mcp",
        "pending_drop",
    ]


def test_registry_resets_stale_source_health_when_targets_exist(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_registry as mod
    from skills.ingest.scripts.inbox_unified_models import InboxVaultTarget

    runtime = tmp_path / "runtime"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    config_dir = tmp_path / "repo" / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "inbox.yaml").write_text("version: 1\ndefault_sources: []\n", encoding="utf-8")
    user_config_dir = runtime / "brain" / "inbox" / "config"
    user_config_dir.mkdir(parents=True)
    (user_config_dir / "sources.yaml").write_text(
        "sources:\n"
        "  - id: manual\n"
        "    type: watched_folder\n"
        "    domain: auto\n"
        "    drop_root: documents/inbox/manual\n"
        "    default_target_vault: project-alpha\n"
        "    allowed_targets: [personal, project-alpha]\n"
        "    health_state: needs_target\n"
        "    health_error: 'Missing inbox target vault id(s): project-alpha'\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(mod, "get_config_dir", lambda: tmp_path / "repo" / "config")
    mod.register_vault_target(
        InboxVaultTarget(
            id="project-alpha",
            kind="project",
            name="Project Alpha",
            vault_root=str(tmp_path / "alpha" / "vault"),
            docs_root=str(tmp_path / "alpha" / "docs"),
        )
    )

    source = mod.load_inbox_registry().source_by_id("manual")

    assert source.health_state == "ready"
    assert source.health_error == ""


def test_registry_marks_source_with_missing_targets_unhealthy(monkeypatch, tmp_path: Path) -> None:
    from skills.ingest.scripts import inbox_registry as mod

    runtime = tmp_path / "runtime"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    config_dir = tmp_path / "repo" / "config" / "system"
    config_dir.mkdir(parents=True)
    (config_dir / "inbox.yaml").write_text(
        "version: 1\n"
        "default_sources:\n"
        "  - id: bad-target\n"
        "    type: watched_folder\n"
        "    domain: auto\n"
        "    path: documents/inbox/bad\n"
        "    default_target_vault: missing-default\n"
        "    allowed_targets: [personal, missing-allowed]\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "get_runtime_dir", lambda: runtime)
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(mod, "get_config_dir", lambda: tmp_path / "repo" / "config")

    registry = mod.load_inbox_registry()
    source = registry.source_by_id("bad-target")

    assert source.health_state == "needs_target"
    assert "missing-default" in source.health_error
    assert "missing-allowed" in source.health_error
