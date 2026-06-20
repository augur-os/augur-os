from pathlib import Path
from types import SimpleNamespace

from src.lib.capabilities.discovery import (
    _command_current_exposure,
    capability_id,
    discover_capabilities,
    discover_command_capabilities,
    discover_declared_skill_capabilities,
    discover_external_skill_bundle_capabilities,
    discover_external_service_capabilities,
    discover_script_mcp_tool_capabilities,
    discover_mcp_server_capabilities,
    discover_skill_capabilities,
)
from src.lib.capabilities.exposure_policy import CapabilityDiscovery


def test_capability_id_normalizes_known_types() -> None:
    assert capability_id("skill", "Geo Audit") == "skill:geo-audit"
    assert capability_id("mcp-server", "augur-framework") == ("mcp-server:augur-framework")
    assert capability_id("command", "/dev-build") == "command:dev-build"


def test_discover_skill_capabilities_from_skill_records(monkeypatch) -> None:
    fake_record = SimpleNamespace(
        name="geo-audit",
        ownership="external",
        source_root="external-client",
        source="claude-global",
        path=Path("/Users/example/.claude/skills/geo-audit"),
        client_sources=("claude-global", "codex-local"),
        mcp_tools=[],
    )

    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_all_skills",
        lambda: [fake_record],
    )

    records = discover_skill_capabilities()

    assert records[0].id == "skill:geo-audit"
    assert records[0].owner_kind == "external"
    assert records[0].management == "unmanaged"
    assert records[0].scope == "mixed"
    assert records[0].current_exposure == ("claude", "codex")


def test_discover_skill_capabilities_excludes_location_tokens_from_exposure(
    monkeypatch,
) -> None:
    fake_record = SimpleNamespace(
        name="apple",
        ownership="augur",
        source_root="project-brain",
        source="project-brain",
        path=Path("/repo/project-brain/capabilities/skills/apple"),
        client_sources=("project-brain", "claude-global"),
        mcp_tools=[],
    )

    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_all_skills",
        lambda: [fake_record],
    )

    records = discover_skill_capabilities()

    assert records[0].current_exposure == ("claude",)
    assert records[0].metadata["source_root"] == "project-brain"


def test_discover_skill_capabilities_counts_claude_plugin_cache_as_claude(
    monkeypatch,
) -> None:
    fake_record = SimpleNamespace(
        name="ui-ux-pro-max",
        ownership="external",
        source_root="plugin-cache",
        source="claude-plugin-cache",
        path=Path("/Users/example/.claude/plugins/cache/ui-ux/.claude/skills/ui-ux-pro-max"),
        client_sources=("claude-plugin-cache",),
        mcp_tools=[],
    )

    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_all_skills",
        lambda: [fake_record],
    )

    records = discover_skill_capabilities()

    assert records[0].id == "skill:ui-ux-pro-max"
    assert records[0].management == "unmanaged"
    assert records[0].current_exposure == ("claude",)


def test_discover_skill_capabilities_preserves_private_vault_user_owner(
    monkeypatch,
) -> None:
    fake_record = SimpleNamespace(
        name="books",
        ownership="user",
        source_root="private-vault",
        source="private-vault",
        path=Path("/Users/example/Projects/Au-vault/skills/books"),
        client_sources=("private-vault",),
        mcp_tools=[],
    )

    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_all_skills",
        lambda: [fake_record],
    )

    records = discover_skill_capabilities()

    assert records[0].id == "skill:books"
    assert records[0].owner_kind == "user"
    assert records[0].management == "generated"
    assert records[0].current_exposure == ()
    assert records[0].metadata["source_root"] == "private-vault"


def test_discover_mcp_server_capabilities(monkeypatch) -> None:
    fake_manifest = SimpleNamespace(
        all_augur_servers=lambda: [
            SimpleNamespace(
                id="augur-framework",
                bundle=None,
                bundle_path=None,
            ),
            SimpleNamespace(
                id="augur-apple",
                bundle="apple",
                bundle_path="~/Projects/Au-vault/skills/apple",
            ),
        ]
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.load_manifest",
        lambda: fake_manifest,
    )

    records = discover_mcp_server_capabilities()

    assert [record.id for record in records] == [
        "mcp-server:augur-framework",
        "mcp-server:augur-apple",
    ]
    assert records[0].metadata["tier"] == "project"
    assert records[1].metadata["tier"] == "vault"


def test_discover_mcp_server_capabilities_uses_policy_for_current_exposure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    policy_path = tmp_path / "capability_exposure.yaml"
    policy_path.write_text(
        "version: 1\n"
        "capabilities:\n"
        "  mcp-server:augur-core:\n"
        "    classification_status: approved\n"
        "    export_to: [mcp-config]\n"
        "  mcp-server:augur-framework:\n"
        "    classification_status: approved\n"
        "    export_to: []\n",
        encoding="utf-8",
    )
    fake_manifest = SimpleNamespace(
        policy_path=policy_path,
        all_augur_servers=lambda: [
            SimpleNamespace(
                id="augur-core",
                bundle=None,
                bundle_path=None,
            ),
            SimpleNamespace(
                id="augur-framework",
                bundle=None,
                bundle_path=None,
            ),
        ],
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.load_manifest",
        lambda: fake_manifest,
    )

    records = discover_mcp_server_capabilities()

    by_id = {record.id: record for record in records}
    assert by_id["mcp-server:augur-core"].current_exposure == ("mcp-config",)
    assert by_id["mcp-server:augur-framework"].current_exposure == ()


def test_discover_command_capabilities(monkeypatch) -> None:
    command = SimpleNamespace(
        id="dev-build",
        path=Path("/repo/project-brain/capabilities/skills/platform-admin/commands/dev-build.md"),
        visibility="dev",
        bundle="project",
        loop={"name": "build"},
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_commands",
        lambda: [command],
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.get_managed_skill_source_dirs",
        lambda root=None: [],
    )

    records = discover_command_capabilities()

    assert records[0].id == "command:dev-build"
    assert records[0].metadata["visibility"] == "dev"
    assert records[1].id == "workflow:dev-build"
    assert records[1].type == "workflow"


def test_discover_command_capabilities_includes_managed_command_docs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "loop-wiring"
    commands_dir = skill_dir / "commands"
    commands_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n" "name: loop-wiring\n" "description: Wiring checks\n" "---\n",
        encoding="utf-8",
    )
    (commands_dir / "auto-api-wiring.md").write_text(
        "---\n" "description: Validate API wiring\n" "visibility: auto\n" "---\n" "\n" "# auto-api-wiring\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_commands",
        lambda: [],
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.get_managed_skill_source_dirs",
        lambda root=None: [tmp_path / "project-brain" / "capabilities" / "skills"],
    )

    records = discover_command_capabilities(root=tmp_path)

    assert [record.id for record in records] == ["command:auto-api-wiring"]
    assert records[0].current_exposure == ("cli", "agents-md", "browse")
    assert records[0].source_paths == ("project-brain/capabilities/skills/loop-wiring/commands/auto-api-wiring.md",)
    assert records[0].metadata["visibility"] == "auto"
    assert records[0].metadata["skill"] == "loop-wiring"
    # ADR-802 removed x-augur-hub; the owning skill name is the grouping key.
    assert records[0].metadata["hub"] == "loop-wiring"


def test_discover_command_capabilities_dedupes_command_discovery_and_docs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "platform-admin"
    commands_dir = skill_dir / "commands"
    commands_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n" "name: platform-admin\n" "x-augur-hub: dev\n" "---\n",
        encoding="utf-8",
    )
    command_path = commands_dir / "dev-build.md"
    command_path.write_text(
        "---\n" "description: Build dashboard\n" "visibility: dev\n" "---\n",
        encoding="utf-8",
    )
    command = SimpleNamespace(
        id="dev-build",
        path=command_path,
        visibility="dev",
        bundle="project",
        loop=None,
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_commands",
        lambda: [command],
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.get_managed_skill_source_dirs",
        lambda root=None: [tmp_path / "project-brain" / "capabilities" / "skills"],
    )

    records = discover_command_capabilities(root=tmp_path)

    assert [record.id for record in records] == ["command:dev-build"]
    assert records[0].source_paths == (
        str(command_path),
        "project-brain/capabilities/skills/platform-admin/commands/dev-build.md",
    )


def test_command_current_exposure_detects_native_command_wrappers(tmp_path: Path) -> None:
    (tmp_path / ".claude" / "commands").mkdir(parents=True)
    (tmp_path / ".claude" / "commands" / "routines.md").write_text(
        "# /routines\n",
        encoding="utf-8",
    )
    (tmp_path / ".codex" / "skills" / "routines").mkdir(parents=True)
    (tmp_path / ".codex" / "skills" / "routines" / "SKILL.md").write_text(
        "# /routines\n",
        encoding="utf-8",
    )
    (tmp_path / ".gemini" / "skills" / "routines").mkdir(parents=True)
    (tmp_path / ".gemini" / "skills" / "routines" / "SKILL.md").write_text(
        "# /routines\n",
        encoding="utf-8",
    )

    assert _command_current_exposure(tmp_path, "routines") == (
        "cli",
        "agents-md",
        "browse",
        "claude",
        "codex",
        "gemini",
    )


def test_discover_declared_mcp_tool_and_cli_capabilities(
    tmp_path: Path,
    monkeypatch,
) -> None:
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "apple"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: apple\n"
        "description: Apple integration\n"
        "x-augur-mcp-tools:\n"
        "  - apple-notes-search\n"
        "x-augur-cli-integrations:\n"
        "  - name: osascript\n"
        "---\n"
        "\n"
        "Apple integration.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.get_managed_skill_source_dirs",
        lambda project_root=None: [tmp_path / "project-brain" / "capabilities" / "skills"],
    )

    records = discover_declared_skill_capabilities(tmp_path)

    assert [record.id for record in records] == [
        "mcp-tool:apple-notes-search",
        "cli:osascript",
    ]
    assert records[0].type == "mcp-tool"
    assert records[1].type == "cli"


def test_discover_declared_mcp_tool_exposure_moves_policy_denied_mcp_to_agents_md(
    tmp_path: Path,
    monkeypatch,
) -> None:
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "attention"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n" "name: attention\n" "x-augur-mcp-tools:\n" "  - act-on-attention-item\n" "---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.get_managed_skill_source_dirs",
        lambda project_root=None: [tmp_path / "project-brain" / "capabilities" / "skills"],
    )

    records = discover_declared_skill_capabilities(
        tmp_path,
        policy={
            "capabilities": {
                "mcp-tool:act-on-attention-item": {
                    "classification_status": "approved",
                    "export_to": ["cli", "agents-md", "browse"],
                }
            }
        },
    )

    assert len(records) == 1
    assert records[0].id == "mcp-tool:act-on-attention-item"
    assert records[0].current_exposure == ("cli", "agents-md", "browse")


def test_discover_script_mcp_tool_capabilities_from_active_skill_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "ingest"
    mcp_dir = skill_dir / "scripts" / "mcp"
    mcp_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: ingest\nx-augur-hub: workspace\n---\n",
        encoding="utf-8",
    )
    (mcp_dir / "inbox_tools.py").write_text(
        "def register_tools(mcp, interceptor, metrics):\n"
        "    @mcp.tool(name='inbox-folders')\n"
        "    async def inbox_folders():\n"
        "        return '{}'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.get_managed_skill_source_dirs",
        lambda project_root=None: [tmp_path / "project-brain" / "capabilities" / "skills"],
    )

    records = discover_script_mcp_tool_capabilities(tmp_path)

    assert len(records) == 1
    assert records[0].id == "mcp-tool:inbox-folders"
    assert records[0].type == "mcp-tool"
    assert records[0].source_paths == ("project-brain/capabilities/skills/ingest/scripts/mcp/inbox_tools.py",)
    assert records[0].current_exposure == ("mcp", "browse")
    assert records[0].metadata == {
        "skill": "ingest",
        "primary_surface": "mcp",
    }


def test_discover_external_service_capabilities_from_registry(tmp_path: Path) -> None:
    registry_path = tmp_path / "config" / "integrations" / "external_mcp_registry.yaml"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        "version: 2\n"
        "services:\n"
        "  gh:\n"
        "    name: GitHub CLI\n"
        "    type: cli\n"
        "    enabled: true\n"
        "    check_command: gh --version\n"
        "    used_by:\n"
        "      - developer\n"
        "    setup_url: https://cli.github.com/\n"
        "  context7:\n"
        "    name: Context7\n"
        "    type: mcp\n"
        "    enabled: true\n"
        "    command: npx\n"
        "    args:\n"
        "      - -y\n"
        "      - '@upstash/context7-mcp'\n",
        encoding="utf-8",
    )

    records = discover_external_service_capabilities(tmp_path)

    assert [record.id for record in records] == [
        "cli:gh",
        "mcp-server:context7",
    ]
    cli_record = records[0]
    assert cli_record.type == "cli"
    assert cli_record.owner_kind == "external"
    assert cli_record.management == "unmanaged"
    assert cli_record.scope == "global"
    assert cli_record.source_paths == (str(registry_path),)
    assert cli_record.current_exposure == ("browse", "shell")
    assert cli_record.metadata == {
        "external_service_id": "gh",
        "primary_surface": "cli",
        "service_type": "cli",
        "enabled": "true",
        "used_by": "developer",
        "setup_url": "https://cli.github.com/",
        "check_command": "gh --version",
    }


def test_disabled_external_cli_is_browse_only(tmp_path: Path) -> None:
    registry_path = tmp_path / "config" / "integrations" / "external_mcp_registry.yaml"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        "version: 2\n"
        "services:\n"
        "  gcloud:\n"
        "    name: Google Cloud CLI\n"
        "    type: cli\n"
        "    enabled: false\n"
        "    check_command: gcloud version\n",
        encoding="utf-8",
    )

    records = discover_external_service_capabilities(tmp_path)

    assert records[0].id == "cli:gcloud"
    assert records[0].current_exposure == ("browse",)


def test_discover_external_skill_bundle_capabilities_from_config(tmp_path: Path) -> None:
    bundle_root = tmp_path / "vendor" / "skills" / "obsidian-skills"
    skill_dir = bundle_root / "skills" / "obsidian-markdown"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: obsidian-markdown\ndescription: Markdown\n---\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "config" / "external_skills.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "external_skill_bundles:\n"
        "  - id: kepano-obsidian-skills\n"
        "    source: vendor/skills/obsidian-skills\n"
        "    upstream: https://example.invalid/kepano\n"
        "    pinned_sha: deadbeef\n"
        "    skills: [obsidian-markdown]\n"
        "    targets:\n"
        "      claude_code: marketplace\n",
        encoding="utf-8",
    )

    records = discover_external_skill_bundle_capabilities(tmp_path)

    assert len(records) == 1
    assert records[0].id == "skill:obsidian-markdown"
    assert records[0].type == "skill"
    assert records[0].owner_kind == "external"
    assert records[0].management == "unmanaged"
    assert records[0].scope == "project"
    assert records[0].current_exposure == ("claude",)
    assert records[0].source_paths == (str(skill_dir / "SKILL.md"),)
    assert records[0].metadata["external_bundle"] == "kepano-obsidian-skills"
    assert records[0].metadata["upstream"] == "https://example.invalid/kepano"


def test_discover_capabilities_merges_duplicate_records(monkeypatch) -> None:
    duplicate_records = [
        CapabilityDiscovery(
            id="mcp-tool:get-skill-health",
            type="mcp-tool",
            source_paths=("/repo/project-brain/capabilities/skills/apple/SKILL.md",),
            current_exposure=("mcp",),
            metadata={"skill": "apple", "primary_surface": "mcp"},
        ),
        CapabilityDiscovery(
            id="mcp-tool:get-skill-health",
            type="mcp-tool",
            source_paths=("/repo/project-brain/capabilities/skills/codex/SKILL.md",),
            current_exposure=("browse", "mcp"),
            metadata={"skill": "codex", "primary_surface": "mcp"},
        ),
    ]
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_skill_capabilities",
        lambda: [],
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_mcp_server_capabilities",
        lambda: [],
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_command_capabilities",
        lambda: [],
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_declared_skill_capabilities",
        lambda: duplicate_records,
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_script_mcp_tool_capabilities",
        lambda: [],
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_external_service_capabilities",
        lambda: [],
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_external_skill_bundle_capabilities",
        lambda: [],
    )

    records = discover_capabilities()

    assert len(records) == 1
    assert records[0].id == "mcp-tool:get-skill-health"
    assert records[0].source_paths == (
        "/repo/project-brain/capabilities/skills/apple/SKILL.md",
        "/repo/project-brain/capabilities/skills/codex/SKILL.md",
    )
    assert records[0].current_exposure == ("mcp", "browse")
    assert records[0].metadata["skill"] == "apple,codex"
    assert records[0].metadata["primary_surface"] == "mcp"
