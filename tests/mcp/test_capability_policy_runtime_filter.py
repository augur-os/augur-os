from pathlib import Path
from types import SimpleNamespace


class CapturingMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, name=None, *args, **kwargs):
        tool_name = kwargs.get("name") or name

        def decorator(func):
            self.tools[tool_name or func.__name__] = func
            return func

        return decorator


def _register_allowed_and_blocked(mcp, *_args, **_kwargs) -> None:
    @mcp.tool(name="allowed-runtime-tool")
    def allowed_runtime_tool():
        return "allowed"

    @mcp.tool(name="blocked-runtime-tool")
    def blocked_runtime_tool():
        return "blocked"


def _allow_only_runtime_tool(monkeypatch) -> None:
    from src.mcp.augur_shared import plugin_tools

    monkeypatch.setattr(
        plugin_tools,
        "allowed_mcp_runtime_tool_names",
        lambda names, target="mcp": {"allowed-runtime-tool"},
    )
    plugin_tools.reset_capability_policy_filter_cache()


def test_framework_registration_filters_direct_tools_through_capability_policy(
    monkeypatch,
) -> None:
    from src.mcp.augur_framework import tools as framework_tools
    from src.mcp.augur_framework.tools import domain, infrastructure

    _allow_only_runtime_tool(monkeypatch)
    monkeypatch.setattr(domain, "register_domain_tools", _register_allowed_and_blocked)
    monkeypatch.setattr(infrastructure, "register_infrastructure_tools", lambda *args: None)

    mcp = CapturingMCP()

    framework_tools.register_framework_tools(mcp, lambda func: func, SimpleNamespace())

    assert set(mcp.tools) == {"allowed-runtime-tool"}


def test_core_registration_filters_direct_tools_through_capability_policy(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.mcp.augur_core import tools as core_tools
    from src.mcp.augur_core.tools import core as core_registry
    from src.mcp.augur_framework.tools.infrastructure import browse
    from src.mcp.augur_framework.tools.hubs import agent_registry, capabilities
    from src.mcp.augur_shared import compat, config, server_cache

    _allow_only_runtime_tool(monkeypatch)
    monkeypatch.setattr(config, "get_config", lambda: SimpleNamespace(plugins_dir=tmp_path))
    monkeypatch.setattr(compat, "list_skills", lambda **_kwargs: [])
    monkeypatch.setattr(compat, "resolve_skill", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server_cache, "SkillCache", lambda: SimpleNamespace())
    monkeypatch.setattr(core_registry, "register_core_tools", _register_allowed_and_blocked)
    monkeypatch.setattr(browse, "register_browse_tools", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_registry, "register_tools", lambda *args, **kwargs: None)
    monkeypatch.setattr(capabilities, "register_tools", lambda *args, **kwargs: None)

    mcp = CapturingMCP()

    core_tools.register_core_tools(mcp, lambda func: func, SimpleNamespace())

    assert set(mcp.tools) == {"allowed-runtime-tool"}


def test_policy_filtered_mcp_uses_configured_policy_target(monkeypatch) -> None:
    from src.mcp.augur_shared import plugin_tools

    observed_targets: list[str] = []

    def allow_only_cli_target(names: list[str], target: str = "mcp") -> set[str]:
        observed_targets.append(target)
        if target == "cli":
            return set(names)
        return set()

    monkeypatch.setattr(
        plugin_tools,
        "allowed_mcp_runtime_tool_names",
        allow_only_cli_target,
    )
    plugin_tools.reset_capability_policy_filter_cache()

    mcp = CapturingMCP()
    filtered = plugin_tools.create_capability_policy_filtered_mcp(
        mcp,
        source_name="test",
        target="cli",
    )

    _register_allowed_and_blocked(filtered)

    assert set(mcp.tools) == {"allowed-runtime-tool", "blocked-runtime-tool"}
    assert observed_targets == ["cli", "cli"]


def test_cli_target_registers_every_approved_tool_regardless_of_primary_surface(
    monkeypatch,
) -> None:
    """The `aug` CLI's in-process runtime must register every approved tool
    so shell callers and agent-via-Bash invocations of `aug <tool>` work
    regardless of whether the tool's `primary_surface` is `cli`, `mcp`, or
    `mcp via dashboard`. Only `classification_status: blocked` excludes a
    tool from the CLI runtime.
    """
    from src.lib.capabilities import export_filter
    from src.lib.capabilities.exposure_policy import (
        CapabilityDiscovery,
        resolve_capability_records,
    )

    policy = {
        "version": 1,
        "capabilities": {
            "mcp-tool:cli-tool": {
                "classification_status": "approved",
                "export_to": ["cli", "agents-md", "browse"],
                "primary_surface": "cli",
            },
            "mcp-tool:mcp-tool": {
                "classification_status": "approved",
                "export_to": ["cli", "agents-md", "browse", "mcp"],
                "primary_surface": "mcp",
            },
            "mcp-tool:dashboard-tool": {
                "classification_status": "approved",
                "export_to": ["cli", "agents-md", "browse"],
                "primary_surface": "mcp via dashboard",
            },
            "mcp-tool:blocked-tool": {
                "classification_status": "blocked",
                "export_to": [],
                "primary_surface": "cli",
            },
        },
    }
    monkeypatch.setattr(
        export_filter,
        "discover_capabilities",
        lambda: [
            CapabilityDiscovery(id=f"mcp-tool:{name}", type="mcp-tool")
            for name in ("cli-tool", "mcp-tool", "dashboard-tool", "blocked-tool")
        ],
    )
    monkeypatch.setattr(
        export_filter,
        "resolve_capability_records",
        lambda discovered: resolve_capability_records(discovered, policy=policy),
    )
    export_filter.reset_export_filter_cache()

    allowed = export_filter.allowed_mcp_runtime_tool_names(
        ["cli-tool", "mcp-tool", "dashboard-tool", "blocked-tool", "unclassified-tool"],
        target="cli",
    )
    assert allowed == {"cli-tool", "mcp-tool", "dashboard-tool", "unclassified-tool"}


def test_internal_mcp_runtime_uses_primary_surface_for_dashboard_only_tools(
    monkeypatch,
) -> None:
    """Internal target registers tools whose `primary_surface` is
    `mcp` or `mcp via dashboard`. Tools whose `primary_surface` is `cli`
    (even if they have `browse` in export_to) are NOT registered — that
    enforces the separation between dashboard MCP registration and the
    CLI-only operations that should never reach an MCP runtime.
    """
    from src.lib.capabilities import export_filter
    from src.lib.capabilities.exposure_policy import (
        CapabilityDiscovery,
        resolve_capability_records,
    )

    policy = {
        "version": 1,
        "capabilities": {
            "mcp-tool:dashboard-only-tool": {
                "classification_status": "approved",
                "export_to": ["cli", "agents-md", "browse"],
                "primary_surface": "mcp via dashboard",
            },
            "mcp-tool:ai-mcp-tool": {
                "classification_status": "approved",
                "export_to": ["cli", "agents-md", "browse", "mcp"],
                "primary_surface": "mcp",
            },
            "mcp-tool:cli-only-tool": {
                "classification_status": "approved",
                "export_to": ["cli", "agents-md", "browse"],
                "primary_surface": "cli",
            },
        },
    }

    monkeypatch.setattr(
        export_filter,
        "discover_capabilities",
        lambda: [
            CapabilityDiscovery(
                id=f"mcp-tool:{name}",
                type="mcp-tool",
                current_exposure=("cli", "agents-md", "browse"),
            )
            for name in ("dashboard-only-tool", "ai-mcp-tool", "cli-only-tool")
        ],
    )
    monkeypatch.setattr(
        export_filter,
        "resolve_capability_records",
        lambda discovered: resolve_capability_records(discovered, policy=policy),
    )
    export_filter.reset_export_filter_cache()

    allowed = export_filter.allowed_mcp_runtime_tool_names(
        ["dashboard-only-tool", "ai-mcp-tool", "cli-only-tool"],
        target="mcp",
    )
    assert allowed == {"dashboard-only-tool", "ai-mcp-tool"}


def test_runtime_filter_reuses_resolved_capability_records(monkeypatch) -> None:
    from src.lib.capabilities import export_filter
    from src.mcp.augur_shared import plugin_tools

    calls = 0

    def discover_once():
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(export_filter, "discover_capabilities", discover_once)
    monkeypatch.setattr(export_filter, "resolve_capability_records", lambda records: [])
    plugin_tools.reset_capability_policy_filter_cache()

    for index in range(5):
        assert plugin_tools._mcp_tool_policy_allows_runtime_registration(
            f"uncatalogued-runtime-tool-{index}",
            "mcp",
        )

    assert calls == 1


def test_private_vault_dashboard_tools_are_available_to_dashboard_runtime() -> None:
    import yaml
    from src.config.paths import get_vault_skills_dir
    from src.lib.capabilities import export_filter

    required_tools = {
        "vault-status",
        "vault-health-repairs",
        "vault-search",
        "vault-scaffold",
    }

    skill_path = get_vault_skills_dir() / "vault" / "SKILL.md"
    if skill_path.exists():
        _, skill_yaml, _ = skill_path.read_text(encoding="utf-8").split("---\n", 2)
        skill_meta = yaml.safe_load(skill_yaml)
        assert required_tools <= set(skill_meta["x-augur-mcp-tools"])

    capability_path = Path("config/system/capability_exposure.yaml")
    capability = yaml.safe_load(capability_path.read_text(encoding="utf-8"))
    capabilities = capability["capabilities"]
    for tool in required_tools:
        record = capabilities[f"mcp-tool:{tool}"]
        assert record["classification_status"] == "approved"
        assert record["preferred_client"] == "dashboard"
        assert record["primary_surface"] == "mcp via dashboard"

    export_filter.reset_export_filter_cache()
    allowed = export_filter.allowed_mcp_runtime_tool_names(
        sorted(required_tools),
        target="dashboard-augur-wt-smoke",
    )
    assert required_tools <= allowed


def test_ai_dashboard_tools_are_available_to_dashboard_runtime() -> None:
    import yaml
    from src.lib.capabilities import export_filter

    required_tools = {
        "get-ai-status",
        "get-sync-status",
        "list-agent-capabilities",
        "list-client-skills",
        "manage-cli-agents",
    }

    skill_path = Path("project-brain/capabilities/skills/ai/SKILL.md")
    _, skill_yaml, _ = skill_path.read_text(encoding="utf-8").split("---\n", 2)
    skill_meta = yaml.safe_load(skill_yaml)
    assert required_tools <= set(skill_meta["x-augur-mcp-tools"])

    capability_path = Path("config/system/capability_exposure.yaml")
    capability = yaml.safe_load(capability_path.read_text(encoding="utf-8"))
    capabilities = capability["capabilities"]
    for tool in required_tools - {"manage-cli-agents"}:
        record = capabilities[f"mcp-tool:{tool}"]
        assert record["classification_status"] == "approved"
        assert record["preferred_client"] == "dashboard"
        assert record["primary_surface"] == "mcp via dashboard"

    export_filter.reset_export_filter_cache()
    allowed = export_filter.allowed_mcp_runtime_tool_names(
        sorted(required_tools),
        target="dashboard-augur-wt-smoke",
    )
    assert required_tools <= allowed
