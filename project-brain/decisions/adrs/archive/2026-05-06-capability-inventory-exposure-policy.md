# Capability Inventory Exposure Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build v1 of the hybrid capability inventory and exposure policy so Augur can see, classify, and enforce generated exposure for skills, MCP servers/tools, commands, workflows, and CLI-backed capabilities.

**Architecture:** Add a small capability policy/resolver library under `src/lib/capabilities/`, feed its resolved metadata into Browse, then make Augur-managed generators consult it before writing skill, command, and MCP client config outputs. Scanners remain the source of current-state truth; `config/system/capability_exposure.yaml` stores intent only.

**Tech Stack:** Python 3.11+, PyYAML, existing Augur path helpers, existing skill/command/MCP discovery, Next.js Browse TypeScript types/transforms.

---

## File Structure

- Create `config/system/capability_exposure.yaml`
  - Stores versioned exposure intent. Starts with an empty `capabilities` map so all unknown records resolve as `unclassified`.
- Create `src/lib/capabilities/__init__.py`
  - Re-exports resolver/discovery APIs.
- Create `src/lib/capabilities/exposure_policy.py`
  - Owns `CapabilityDiscovery`, `CapabilityRecord`, YAML loading, policy merge, drift computation, and `export_allowed()`.
- Create `src/lib/capabilities/discovery.py`
  - Converts existing skill, command, MCP, workflow, and CLI discovery into `CapabilityDiscovery` records.
- Create `src/lib/capabilities/browse_enrichment.py`
  - Converts a Browse category/index entry into capability metadata fields.
- Create `src/lib/capabilities/export_filter.py`
  - Filters generated skill/command/MCP outputs by resolved policy while preserving existing unclassified managed exports until explicitly blocked.
- Modify `src/mcp/augur_framework/tools/infrastructure/browse/index.py`
  - Adds resolved capability metadata to Browse item `metadata`.
- Modify `apps/dashboard/lib/browse/types.ts`
  - Adds explicit capability metadata keys to the shared Browse contract.
- Modify `apps/dashboard/lib/browse/transforms.ts`
  - Preserves capability policy fields from Browse API responses.
- Modify `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`
  - Adds filters for classification/status/surface where values exist.
- Modify `apps/dashboard/app/(views)/browse/useBrowseState.ts`
  - Computes new filter options and applies them.
- Modify `skills/ai/scripts/sync_agents/skill_sync.py`
  - Applies policy to generated skill and command exports.
- Modify `src/cli_config/manifest.py`
  - Exposes client-filtered MCP server entries.
- Modify `src/cli_config/adapters/claude.py`
- Modify `src/cli_config/adapters/gemini.py`
- Modify `src/cli_config/adapters/codex.py`
  - Uses client-filtered MCP entries instead of all manifest entries.
- Add tests:
  - `tests/lib/test_capability_exposure_policy.py`
  - `tests/lib/test_capability_inventory_discovery.py`
  - `tests/lib/test_capability_browse_enrichment.py`
  - Update `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`
  - Update `tests/cli/test_config_adapters.py`
  - Update `tests/dashboard/browse/useBrowseState.test.tsx`

## Task 1: Policy Overlay And Resolver

**Files:**
- Create: `config/system/capability_exposure.yaml`
- Create: `src/lib/capabilities/__init__.py`
- Create: `src/lib/capabilities/exposure_policy.py`
- Test: `tests/lib/test_capability_exposure_policy.py`

- [x] **Step 1: Write the failing resolver tests**

Create `tests/lib/test_capability_exposure_policy.py`:

```python
from pathlib import Path

from src.lib.capabilities.exposure_policy import (
    CapabilityDiscovery,
    export_allowed,
    load_capability_policy,
    resolve_capability_records,
)


def test_missing_policy_resolves_unclassified(tmp_path: Path) -> None:
    discovered = [
        CapabilityDiscovery(
            id="skill:ui-ux-pro-max",
            type="skill",
            owner_kind="external",
            management="unmanaged",
            scope="global",
            source_paths=("~/.codex/skills/ui-ux-pro-max/SKILL.md",),
            current_exposure=("codex",),
        )
    ]

    records = resolve_capability_records(discovered, policy={"capabilities": {}})

    assert records[0].classification_status == "unclassified"
    assert records[0].owner_kind == "external"
    assert records[0].management == "unmanaged"
    assert "unclassified_export" in records[0].drift
    assert export_allowed(records[0], "gemini") is False
    assert export_allowed(records[0], "codex", existing=True) is True


def test_policy_overlay_sets_intended_exposure() -> None:
    discovered = [
        CapabilityDiscovery(
            id="skill:geo-audit",
            type="skill",
            owner_kind="external",
            management="unmanaged",
            scope="global",
            source_paths=("~/.claude/skills/geo-audit/SKILL.md",),
            current_exposure=("claude", "codex"),
        )
    ]
    policy = {
        "capabilities": {
            "skill:geo-audit": {
                "owner_kind": "external",
                "management": "unmanaged",
                "scope": "global",
                "primary_surface": "skill",
                "preferred_client": "claude",
                "export_to": ["claude"],
                "classification_status": "approved",
            }
        }
    }

    record = resolve_capability_records(discovered, policy=policy)[0]

    assert record.classification_status == "approved"
    assert record.export_to == ("claude",)
    assert "duplicate" in record.drift
    assert "unexpected_client" in record.drift
    assert export_allowed(record, "claude") is True
    assert export_allowed(record, "codex") is False


def test_blocked_policy_never_exports_even_if_existing() -> None:
    discovered = [
        CapabilityDiscovery(
            id="mcp-server:augur-obsidian",
            type="mcp-server",
            owner_kind="augur",
            management="generated",
            scope="project",
            source_paths=("config/system/mcp_servers.yaml",),
            current_exposure=("gemini",),
        )
    ]
    policy = {
        "capabilities": {
            "mcp-server:augur-obsidian": {
                "classification_status": "blocked",
                "export_to": [],
                "primary_surface": "mcp",
            }
        }
    }

    record = resolve_capability_records(discovered, policy=policy)[0]

    assert record.classification_status == "blocked"
    assert "unexpected_client" in record.drift
    assert export_allowed(record, "gemini", existing=True) is False


def test_load_capability_policy_missing_file_returns_empty_policy(tmp_path: Path) -> None:
    assert load_capability_policy(tmp_path / "missing.yaml") == {"version": 1, "capabilities": {}}
```

- [x] **Step 2: Run the resolver tests and confirm they fail**

Run through the project test loop:

```bash
/auto-test-pytest tests/lib/test_capability_exposure_policy.py
```

Expected: failure because `src.lib.capabilities.exposure_policy` does not exist.

- [x] **Step 3: Add the policy file and resolver implementation**

Create `config/system/capability_exposure.yaml`:

```yaml
version: 1
capabilities: {}
```

Create `src/lib/capabilities/__init__.py`:

```python
"""Capability inventory and exposure policy helpers."""

from .exposure_policy import (
    CapabilityDiscovery,
    CapabilityRecord,
    capability_policy_path,
    export_allowed,
    load_capability_policy,
    resolve_capability_records,
)

__all__ = [
    "CapabilityDiscovery",
    "CapabilityRecord",
    "capability_policy_path",
    "export_allowed",
    "load_capability_policy",
    "resolve_capability_records",
]
```

Create `src/lib/capabilities/exposure_policy.py`:

```python
"""Capability exposure policy resolver.

Discovery records describe current state. The policy overlay describes intent.
The resolver merges both into records that Browse and generators can consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from src.config.paths import get_project_root

CapabilityType = Literal["skill", "mcp-server", "mcp-tool", "command", "workflow", "cli"]
OwnerKind = Literal["augur", "external", "adopted"]
Management = Literal["generated", "managed-policy", "unmanaged"]
Scope = Literal["project", "global", "mixed"]
ClassificationStatus = Literal["approved", "unclassified", "deprecated", "blocked"]

_VALID_TYPES = {"skill", "mcp-server", "mcp-tool", "command", "workflow", "cli"}
_VALID_OWNERS = {"augur", "external", "adopted"}
_VALID_MANAGEMENT = {"generated", "managed-policy", "unmanaged"}
_VALID_SCOPES = {"project", "global", "mixed"}
_VALID_STATUSES = {"approved", "unclassified", "deprecated", "blocked"}


@dataclass(frozen=True)
class CapabilityDiscovery:
    id: str
    type: CapabilityType
    owner_kind: OwnerKind = "augur"
    management: Management = "generated"
    scope: Scope = "project"
    source_paths: tuple[str, ...] = ()
    current_exposure: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityRecord:
    id: str
    type: CapabilityType
    owner_kind: OwnerKind
    management: Management
    scope: Scope
    primary_surface: str
    preferred_client: str
    export_to: tuple[str, ...]
    classification_status: ClassificationStatus
    source_paths: tuple[str, ...]
    current_exposure: tuple[str, ...]
    drift: tuple[str, ...]
    metadata: dict[str, str] = field(default_factory=dict)


def capability_policy_path(project_root: Path | None = None) -> Path:
    root = project_root or get_project_root()
    return root / "config" / "system" / "capability_exposure.yaml"


def load_capability_policy(path: Path | None = None) -> dict[str, Any]:
    policy_path = path or capability_policy_path()
    if not policy_path.exists():
        return {"version": 1, "capabilities": {}}
    raw = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return {"version": 1, "capabilities": {}}
    capabilities = raw.get("capabilities")
    if not isinstance(capabilities, dict):
        raw["capabilities"] = {}
    raw.setdefault("version", 1)
    return raw


def _clean_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        values = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        values = [str(part).strip() for part in value]
    else:
        values = []
    return tuple(dict.fromkeys(item for item in values if item))


def _choice(value: Any, default: str, valid: set[str]) -> str:
    candidate = str(value or "").strip()
    return candidate if candidate in valid else default


def _record_drift(
    *,
    classification_status: str,
    export_to: tuple[str, ...],
    current_exposure: tuple[str, ...],
) -> tuple[str, ...]:
    current = set(current_exposure)
    intended = set(export_to)
    drift: list[str] = []
    if len(current) > 1:
        drift.append("duplicate")
    if classification_status == "unclassified" and current:
        drift.append("unclassified_export")
    if classification_status in {"approved", "deprecated", "blocked"}:
        if current - intended:
            drift.append("unexpected_client")
        if classification_status == "approved" and intended - current:
            drift.append("missing_expected_export")
    return tuple(drift)


def resolve_capability_records(
    discovered: list[CapabilityDiscovery],
    *,
    policy: dict[str, Any] | None = None,
) -> list[CapabilityRecord]:
    loaded_policy = policy if policy is not None else load_capability_policy()
    policy_entries = loaded_policy.get("capabilities") or {}
    if not isinstance(policy_entries, dict):
        policy_entries = {}

    records: list[CapabilityRecord] = []
    for item in discovered:
        overlay = policy_entries.get(item.id) or {}
        if not isinstance(overlay, dict):
            overlay = {}
        owner_kind = _choice(overlay.get("owner_kind"), item.owner_kind, _VALID_OWNERS)
        management = _choice(overlay.get("management"), item.management, _VALID_MANAGEMENT)
        scope = _choice(overlay.get("scope"), item.scope, _VALID_SCOPES)
        classification_status = _choice(
            overlay.get("classification_status"),
            "unclassified",
            _VALID_STATUSES,
        )
        capability_type = _choice(overlay.get("type"), item.type, _VALID_TYPES)
        primary_surface = str(overlay.get("primary_surface") or item.metadata.get("primary_surface") or capability_type)
        preferred_client = str(overlay.get("preferred_client") or item.metadata.get("preferred_client") or "none")
        export_to = _clean_list(overlay.get("export_to"))
        current_exposure = _clean_list(item.current_exposure)
        source_paths = _clean_list(item.source_paths)
        drift = _record_drift(
            classification_status=classification_status,
            export_to=export_to,
            current_exposure=current_exposure,
        )
        metadata = {str(k): str(v) for k, v in item.metadata.items() if v is not None}
        for key, value in overlay.items():
            if key not in {
                "type",
                "owner_kind",
                "management",
                "scope",
                "primary_surface",
                "preferred_client",
                "export_to",
                "classification_status",
            }:
                metadata[str(key)] = str(value)
        records.append(
            CapabilityRecord(
                id=item.id,
                type=capability_type,  # type: ignore[arg-type]
                owner_kind=owner_kind,  # type: ignore[arg-type]
                management=management,  # type: ignore[arg-type]
                scope=scope,  # type: ignore[arg-type]
                primary_surface=primary_surface,
                preferred_client=preferred_client,
                export_to=export_to,
                classification_status=classification_status,  # type: ignore[arg-type]
                source_paths=source_paths,
                current_exposure=current_exposure,
                drift=drift,
                metadata=metadata,
            )
        )
    return sorted(records, key=lambda record: record.id)


def export_allowed(record: CapabilityRecord, target: str, *, existing: bool = False) -> bool:
    """Return whether a generated export may be written for target.

    Unclassified records may keep an existing managed export but cannot create
    a new target exposure. Blocked records are never exported.
    """
    if record.classification_status == "blocked":
        return False
    if record.classification_status == "unclassified":
        return existing and target in record.current_exposure
    if record.classification_status == "deprecated":
        return existing and target in record.current_exposure
    return target in record.export_to
```

- [x] **Step 4: Run the resolver tests and confirm they pass**

```bash
/auto-test-pytest tests/lib/test_capability_exposure_policy.py
```

Expected: all tests pass.

- [x] **Step 5: Commit Task 1**

```bash
git add config/system/capability_exposure.yaml src/lib/capabilities/__init__.py src/lib/capabilities/exposure_policy.py tests/lib/test_capability_exposure_policy.py
git commit -m "feat: add capability exposure resolver"
```

## Task 2: Capability Discovery Collectors

**Files:**
- Create: `src/lib/capabilities/discovery.py`
- Test: `tests/lib/test_capability_inventory_discovery.py`

- [x] **Step 1: Write discovery tests**

Create `tests/lib/test_capability_inventory_discovery.py`:

```python
from pathlib import Path
from types import SimpleNamespace

from src.lib.capabilities.discovery import (
    capability_id,
    discover_command_capabilities,
    discover_declared_skill_capabilities,
    discover_mcp_server_capabilities,
    discover_skill_capabilities,
)


def test_capability_id_normalizes_known_types() -> None:
    assert capability_id("skill", "Geo Audit") == "skill:geo-audit"
    assert capability_id("mcp-server", "augur-framework") == "mcp-server:augur-framework"
    assert capability_id("command", "/dev-build") == "command:dev-build"


def test_discover_skill_capabilities_from_skill_records(monkeypatch) -> None:
    fake_record = SimpleNamespace(
        name="geo-audit",
        ownership="external",
        source_root="external-client",
        source="claude-global",
        path=Path("/Users/example/.claude/skills/geo-audit"),
        client_sources=("claude-global", "codex-local"),
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


def test_discover_mcp_server_capabilities(monkeypatch) -> None:
    fake_manifest = SimpleNamespace(
        all_augur_servers=lambda: [
            SimpleNamespace(id="augur-framework", bundle=None, bundle_path=None),
            SimpleNamespace(id="augur-apple", bundle="apple", bundle_path="~/Projects/Au-vault/skills/apple"),
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


def test_discover_command_capabilities(monkeypatch) -> None:
    command = SimpleNamespace(
        id="dev-build",
        path=Path("/repo/skills/platform-admin/commands/dev-build.md"),
        visibility="dev",
        bundle="project",
        loop={"name": "build"},
    )
    monkeypatch.setattr(
        "src.lib.capabilities.discovery.discover_commands",
        lambda: [command],
    )

    records = discover_command_capabilities()

    assert records[0].id == "command:dev-build"
    assert records[0].metadata["visibility"] == "dev"
    assert records[1].id == "workflow:dev-build"
    assert records[1].type == "workflow"


def test_discover_declared_mcp_tool_and_cli_capabilities(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "apple"
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

    records = discover_declared_skill_capabilities(tmp_path)

    assert [record.id for record in records] == ["mcp-tool:apple-notes-search", "cli:osascript"]
    assert records[0].type == "mcp-tool"
    assert records[1].type == "cli"
```

- [x] **Step 2: Run discovery tests and confirm they fail**

```bash
/auto-test-pytest tests/lib/test_capability_inventory_discovery.py
```

Expected: failure because `src.lib.capabilities.discovery` does not exist.

- [x] **Step 3: Implement discovery collectors**

Create `src/lib/capabilities/discovery.py`:

```python
"""Convert existing Augur discovery sources into capability records."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import yaml

from src.cli_config.manifest import load_manifest
from src.config.paths import get_project_root
from src.plugins.command_discovery import discover_commands
from src.plugins.skill_discovery import discover_all_skills

from .exposure_policy import CapabilityDiscovery


def capability_id(capability_type: str, raw_name: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", str(raw_name).strip().lower()).strip("-")
    return f"{capability_type}:{name}"


def _client_from_source(source: str) -> str:
    if source.startswith("claude"):
        return "claude"
    if source.startswith("codex"):
        return "codex"
    if source.startswith("gemini"):
        return "gemini"
    if source.startswith("opencode"):
        return "opencode"
    if source.startswith("cursor"):
        return "cursor"
    if source.startswith("copilot"):
        return "copilot"
    if source in {"augur", "repo", "vault"}:
        return source
    return source.split("-", 1)[0] if source else "unknown"


def _exposure_from_sources(sources: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_client_from_source(str(source)) for source in sources if str(source)))


def _scope_from_sources(sources: Iterable[str]) -> str:
    tags = set(str(source) for source in sources)
    if any("global" in source for source in tags) and any("local" in source or "project" in source for source in tags):
        return "mixed"
    if any("global" in source for source in tags):
        return "global"
    return "project"


def discover_skill_capabilities() -> list[CapabilityDiscovery]:
    records: list[CapabilityDiscovery] = []
    for skill in discover_all_skills():
        sources = tuple(getattr(skill, "client_sources", ()) or ())
        source_root = str(getattr(skill, "source_root", "") or "")
        ownership = str(getattr(skill, "ownership", "") or "augur")
        owner_kind = "external" if ownership in {"external", "user"} else ("adopted" if ownership == "adopted" else "augur")
        management = "generated" if source_root in {"repo", "vault"} else "unmanaged"
        path = Path(getattr(skill, "path", ""))
        source_paths = (str(path / "SKILL.md"),)
        records.append(
            CapabilityDiscovery(
                id=capability_id("skill", getattr(skill, "name", path.name)),
                type="skill",
                owner_kind=owner_kind,  # type: ignore[arg-type]
                management=management,  # type: ignore[arg-type]
                scope=_scope_from_sources(sources),  # type: ignore[arg-type]
                source_paths=source_paths,
                current_exposure=_exposure_from_sources(sources),
                metadata={
                    "source_root": source_root,
                    "source": str(getattr(skill, "source", "") or ""),
                },
            )
        )
    return records


def discover_mcp_server_capabilities() -> list[CapabilityDiscovery]:
    records: list[CapabilityDiscovery] = []
    try:
        manifest = load_manifest()
    except Exception:
        return records
    for entry in manifest.all_augur_servers():
        tier = "vault" if getattr(entry, "bundle", None) else "project"
        records.append(
            CapabilityDiscovery(
                id=capability_id("mcp-server", entry.id),
                type="mcp-server",
                owner_kind="augur",
                management="generated",
                scope="project",
                source_paths=("config/system/mcp_servers.yaml",),
                current_exposure=("mcp-config",),
                metadata={
                    "tier": tier,
                    "bundle": str(getattr(entry, "bundle", "") or ""),
                    "primary_surface": "mcp",
                },
            )
        )
    return records


def discover_command_capabilities() -> list[CapabilityDiscovery]:
    records: list[CapabilityDiscovery] = []
    for command in discover_commands():
        path = getattr(command, "path", None)
        source_path = str(path) if path else ""
        command_id = capability_id("command", getattr(command, "id", ""))
        records.append(
            CapabilityDiscovery(
                id=command_id,
                type="command",
                owner_kind="augur",
                management="generated",
                scope="project",
                source_paths=(source_path,) if source_path else (),
                current_exposure=("agents_md", "browse"),
                metadata={
                    "visibility": str(getattr(command, "visibility", "") or ""),
                    "primary_surface": "command",
                    "bundle": str(getattr(command, "bundle", "") or ""),
                },
            )
        )
        if getattr(command, "loop", None):
            records.append(
                CapabilityDiscovery(
                    id=capability_id("workflow", getattr(command, "id", "")),
                    type="workflow",
                    owner_kind="augur",
                    management="generated",
                    scope="project",
                    source_paths=(source_path,) if source_path else (),
                    current_exposure=("agents_md", "browse"),
                    metadata={
                        "primary_surface": "workflow",
                        "command": command_id,
                    },
                )
            )
    return records


def _frontmatter_from_skill_md(skill_md: Path) -> dict:
    try:
        raw = skill_md.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not raw.startswith("---"):
        return {}
    try:
        end = raw.index("---", 3)
        parsed = yaml.safe_load(raw[3:end]) or {}
    except (ValueError, yaml.YAMLError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def discover_declared_skill_capabilities(root: Path | None = None) -> list[CapabilityDiscovery]:
    project_root = root or get_project_root()
    records: list[CapabilityDiscovery] = []
    for skill_md in sorted((project_root / "skills").glob("*/SKILL.md")):
        frontmatter = _frontmatter_from_skill_md(skill_md)
        skill_name = skill_md.parent.name
        source_path = str(skill_md)
        mcp_tools = frontmatter.get("x-augur-mcp-tools") or []
        if isinstance(mcp_tools, list):
            for tool in mcp_tools:
                tool_name = str(tool).strip()
                if not tool_name:
                    continue
                records.append(
                    CapabilityDiscovery(
                        id=capability_id("mcp-tool", tool_name),
                        type="mcp-tool",
                        owner_kind="augur",
                        management="generated",
                        scope="project",
                        source_paths=(source_path,),
                        current_exposure=("mcp", "browse"),
                        metadata={
                            "skill": skill_name,
                            "primary_surface": "mcp",
                        },
                    )
                )
        cli_integrations = frontmatter.get("x-augur-cli-integrations") or []
        if isinstance(cli_integrations, list):
            for entry in cli_integrations:
                if isinstance(entry, dict):
                    cli_name = str(entry.get("name") or "").strip()
                else:
                    cli_name = str(entry).strip()
                if not cli_name:
                    continue
                records.append(
                    CapabilityDiscovery(
                        id=capability_id("cli", cli_name),
                        type="cli",
                        owner_kind="augur",
                        management="generated",
                        scope="project",
                        source_paths=(source_path,),
                        current_exposure=("browse",),
                        metadata={
                            "skill": skill_name,
                            "primary_surface": "cli",
                        },
                    )
                )
    return records


def discover_capabilities() -> list[CapabilityDiscovery]:
    records: list[CapabilityDiscovery] = []
    records.extend(discover_skill_capabilities())
    records.extend(discover_mcp_server_capabilities())
    records.extend(discover_command_capabilities())
    records.extend(discover_declared_skill_capabilities())
    return records
```

- [x] **Step 4: Run discovery tests and resolver tests**

```bash
/auto-test-pytest tests/lib/test_capability_inventory_discovery.py tests/lib/test_capability_exposure_policy.py
```

Expected: all tests pass.

- [x] **Step 5: Commit Task 2**

```bash
git add src/lib/capabilities/discovery.py tests/lib/test_capability_inventory_discovery.py
git commit -m "feat: discover capability inventory records"
```

## Task 3: Browse Metadata Enrichment

**Files:**
- Create: `src/lib/capabilities/browse_enrichment.py`
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/index.py`
- Test: `tests/lib/test_capability_browse_enrichment.py`

- [x] **Step 1: Write the Browse enrichment tests**

Create `tests/lib/test_capability_browse_enrichment.py`:

```python
from src.lib.capabilities.browse_enrichment import capability_metadata_for_browse_entry


def test_skill_entry_receives_policy_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.lib.capabilities.browse_enrichment._resolved_records_by_id",
        lambda: {
            "skill:geo-audit": {
                "capabilityId": "skill:geo-audit",
                "ownerKind": "external",
                "management": "unmanaged",
                "classificationStatus": "approved",
                "primarySurface": "skill",
                "preferredClient": "claude",
                "exportTo": "claude",
                "currentExposure": "claude,codex",
                "drift": "duplicate,unexpected_client",
            }
        },
    )

    metadata = capability_metadata_for_browse_entry("skills", {"name": "geo-audit"})

    assert metadata["capabilityId"] == "skill:geo-audit"
    assert metadata["classificationStatus"] == "approved"
    assert metadata["drift"] == "duplicate,unexpected_client"


def test_unknown_entry_returns_empty_metadata(monkeypatch) -> None:
    monkeypatch.setattr("src.lib.capabilities.browse_enrichment._resolved_records_by_id", lambda: {})

    assert capability_metadata_for_browse_entry("commands", {"name": "missing"}) == {}
```

- [x] **Step 2: Run Browse enrichment tests and confirm they fail**

```bash
/auto-test-pytest tests/lib/test_capability_browse_enrichment.py
```

Expected: failure because `src.lib.capabilities.browse_enrichment` does not exist.

- [x] **Step 3: Implement Browse enrichment**

Create `src/lib/capabilities/browse_enrichment.py`:

```python
"""Capability metadata enrichment for Browse index entries."""

from __future__ import annotations

import re
import time
from typing import Any

from .discovery import capability_id, discover_capabilities
from .exposure_policy import resolve_capability_records

_CACHE_TS = 0.0
_CACHE_TTL = 120.0
_CACHE: dict[str, dict[str, str]] = {}

_CATEGORY_TYPE = {
    "skills": "skill",
    "mcp-servers": "mcp-server",
    "mcp-tools": "mcp-tool",
    "commands": "command",
    "workflows": "workflow",
    "workflow-definitions": "workflow",
    "scripts": "cli",
}


def _clean_name(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("/"):
        text = text[1:]
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _resolved_records_by_id() -> dict[str, dict[str, str]]:
    global _CACHE_TS, _CACHE
    now = time.time()
    if _CACHE and now - _CACHE_TS < _CACHE_TTL:
        return _CACHE
    records = resolve_capability_records(discover_capabilities())
    resolved: dict[str, dict[str, str]] = {}
    for record in records:
        resolved[record.id] = {
            "capabilityId": record.id,
            "ownerKind": record.owner_kind,
            "management": record.management,
            "scope": record.scope,
            "primarySurface": record.primary_surface,
            "preferredClient": record.preferred_client,
            "exportTo": ",".join(record.export_to),
            "classificationStatus": record.classification_status,
            "currentExposure": ",".join(record.current_exposure),
            "drift": ",".join(record.drift),
        }
    _CACHE = resolved
    _CACHE_TS = now
    return resolved


def capability_metadata_for_browse_entry(category: str, entry: dict[str, Any]) -> dict[str, str]:
    capability_type = _CATEGORY_TYPE.get(category)
    if not capability_type:
        return {}
    raw_name = entry.get("name") or entry.get("title") or entry.get("id") or ""
    normalized_id = capability_id(capability_type, _clean_name(raw_name))
    return dict(_resolved_records_by_id().get(normalized_id, {}))
```

Modify `src/mcp/augur_framework/tools/infrastructure/browse/index.py` in `browse_index_impl()` after the `metadata` dict is built and after skill enrichment is applied:

```python
        try:
            from src.lib.capabilities.browse_enrichment import capability_metadata_for_browse_entry
            metadata.update(capability_metadata_for_browse_entry(category, entry))
        except Exception:
            metadata.setdefault("capabilityStatus", "inventory_error")
```

- [x] **Step 4: Run Browse enrichment tests**

```bash
/auto-test-pytest tests/lib/test_capability_browse_enrichment.py
```

Expected: all tests pass.

- [x] **Step 5: Commit Task 3**

```bash
git add src/lib/capabilities/browse_enrichment.py src/mcp/augur_framework/tools/infrastructure/browse/index.py tests/lib/test_capability_browse_enrichment.py
git commit -m "feat: enrich browse inventory with exposure policy"
```

## Task 4: Generated Skill And Command Export Enforcement

**Files:**
- Create: `src/lib/capabilities/export_filter.py`
- Modify: `skills/ai/scripts/sync_agents/skill_sync.py`
- Test: `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`

- [x] **Step 1: Add failing sync export tests**

Append focused tests near the existing skill/command export tests in `skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`:

```python
def test_skill_stub_sync_blocks_new_unclassified_export_but_preserves_existing(tmp_path, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    from sync_agents import skill_sync

    project_root = tmp_path
    skills_dir = project_root / "skills"
    skill_dir = skills_dir / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: Demo\n---\n\nDemo body\n", encoding="utf-8")
    target = project_root / ".gemini" / "skills"
    existing = target / "demo" / "SKILL.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("existing\n", encoding="utf-8")
    (target / ".augur-generated-prompts.json").write_text('{"files":["demo/SKILL.md"]}', encoding="utf-8")

    monkeypatch.setattr(skill_sync, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(skill_sync, "get_managed_skill_source_dirs", lambda _root: [skills_dir])
    monkeypatch.setattr(skill_sync, "_resolve_client_skill_dirs", lambda _root: [("gemini-local", target, True)])

    written = skill_sync._sync_skill_stubs([SimpleNamespace(adapter_name="gemini")], cleanup_disabled=False)

    assert written == 1
    assert existing.exists()


def test_command_sync_does_not_create_new_unclassified_command_export(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from sync_agents import skill_sync

    project_root = tmp_path
    skill_dir = project_root / "skills" / "ai"
    command_dir = skill_dir / "commands"
    command_dir.mkdir(parents=True)
    command_file = command_dir / "new-command.md"
    command_file.write_text(
        "---\ndescription: New Command\nx-augur-export-command: true\n---\n\nRun new command.\n",
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text("---\nname: ai\ndescription: AI\n---\n", encoding="utf-8")
    target = project_root / ".gemini" / "skills"

    monkeypatch.setattr(skill_sync, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(skill_sync, "get_managed_skill_source_dirs", lambda _root: [project_root / "skills"])

    written = skill_sync._sync_command_stubs([SimpleNamespace(adapter_name="gemini")], cleanup_disabled=False)

    assert written == 0
    assert not (target / "new-command" / "SKILL.md").exists()
```

- [x] **Step 2: Run sync export tests and confirm they fail**

```bash
/auto-test-pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::test_skill_stub_sync_blocks_new_unclassified_export_but_preserves_existing skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::test_command_sync_does_not_create_new_unclassified_command_export
```

Expected: first test may pass accidentally from legacy behavior, second should fail because new unclassified commands are still exported.

- [x] **Step 3: Implement generated export filtering**

Create `src/lib/capabilities/export_filter.py`:

```python
"""Filtering helpers for Augur-generated capability exports."""

from __future__ import annotations

from pathlib import Path

from .discovery import capability_id, discover_capabilities
from .exposure_policy import export_allowed, resolve_capability_records


def _records_by_id():
    return {record.id: record for record in resolve_capability_records(discover_capabilities())}


def allowed_generated_names(
    *,
    capability_type: str,
    names: list[str],
    target: str,
    existing_names: set[str],
) -> set[str]:
    records = _records_by_id()
    allowed: set[str] = set()
    for name in names:
        record = records.get(capability_id(capability_type, name))
        if record is None:
            if name in existing_names:
                allowed.add(name)
            continue
        if export_allowed(record, target, existing=name in existing_names):
            allowed.add(name)
    return allowed


def filter_named_sources(
    *,
    capability_type: str,
    sources: list[tuple],
    target: str,
    existing_names: set[str],
) -> list[tuple]:
    names = [str(source[0]) for source in sources]
    allowed = allowed_generated_names(
        capability_type=capability_type,
        names=names,
        target=target,
        existing_names=existing_names,
    )
    return [source for source in sources if str(source[0]) in allowed]
```

Modify `skills/ai/scripts/sync_agents/skill_sync.py`:

Add this import inside `_sync_skill_exports()` before looping through client dirs:

```python
    from src.lib.capabilities.export_filter import filter_named_sources
```

Replace the skill write loop setup with:

```python
        old_files = _load_manifest_entries(manifest_path, "files")
        existing_names = {entry.split("/", 1)[0].removesuffix(".md") for entry in old_files}
        eligible_sources = filter_named_sources(
            capability_type="skill",
            sources=sources,
            target=adapter_name,
            existing_names=existing_names,
        )

        written: list[str] = []
        for name, _source_dir, raw, body, _description, _codex_native in eligible_sources:
```

Modify `_sync_command_stubs()` before the Claude write loop:

```python
    from src.lib.capabilities.export_filter import filter_named_sources
```

Inside the Claude branch, after `old_files`:

```python
        existing_names = {entry.removesuffix(".md") for entry in old_files}
        claude_commands = filter_named_sources(
            capability_type="command",
            sources=commands,
            target="claude",
            existing_names=existing_names,
        )
```

Change the loop to:

```python
        for name, source_path, raw in claude_commands:
```

Inside the Codex/Gemini command wrapper loop, before `_sync_command_skill_dir()`:

```python
            manifest_path = client_dir / _COMMANDS_MANIFEST
            old_entries = _load_manifest_entries(manifest_path, "files")
            existing_names = set(old_entries)
            eligible_commands = filter_named_sources(
                capability_type="command",
                sources=commands,
                target=adapter_name,
                existing_names=existing_names,
            )
            written = _sync_command_skill_dir(
                client_dir,
                eligible_commands,
                write_generated_file=write_generated_file,
            )
```

- [x] **Step 4: Run sync export tests**

```bash
/auto-test-pytest skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::test_skill_stub_sync_blocks_new_unclassified_export_but_preserves_existing skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py::test_command_sync_does_not_create_new_unclassified_command_export
```

Expected: both tests pass.

- [x] **Step 5: Commit Task 4**

```bash
git add src/lib/capabilities/export_filter.py skills/ai/scripts/sync_agents/skill_sync.py skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py
git commit -m "feat: enforce capability policy for generated skill exports"
```

## Task 5: MCP Config Export Enforcement

**Files:**
- Modify: `src/cli_config/manifest.py`
- Modify: `src/cli_config/adapters/claude.py`
- Modify: `src/cli_config/adapters/gemini.py`
- Modify: `src/cli_config/adapters/codex.py`
- Test: `tests/cli/test_config_adapters.py`

- [x] **Step 1: Add failing MCP adapter tests**

Add to `tests/cli/test_config_adapters.py`:

```python
def test_manifest_filters_mcp_servers_by_capability_policy(monkeypatch):
    from src.cli_config.manifest import _build_manifest

    manifest = _build_manifest(
        {
            "project_tier": [
                {"id": "augur-core", "command": "python", "args": ["-m", "src.mcp.augur_core"]},
                {"id": "augur-framework", "command": "python", "args": ["-m", "src.mcp.augur_framework"]},
            ]
        }
    )

    monkeypatch.setattr(
        "src.cli_config.manifest.resolve_capability_records",
        lambda _discovered: [
            type("Record", (), {
                "id": "mcp-server:augur-core",
                "classification_status": "approved",
                "export_to": ("gemini",),
                "current_exposure": (),
            })(),
            type("Record", (), {
                "id": "mcp-server:augur-framework",
                "classification_status": "blocked",
                "export_to": (),
                "current_exposure": ("gemini",),
            })(),
        ],
    )

    assert [entry.id for entry in manifest.all_augur_servers_for_client("gemini")] == ["augur-core"]
```

- [x] **Step 2: Run the MCP adapter test and confirm it fails**

```bash
/auto-test-pytest tests/cli/test_config_adapters.py::test_manifest_filters_mcp_servers_by_capability_policy
```

Expected: failure because `Manifest.all_augur_servers_for_client()` does not exist.

- [x] **Step 3: Implement client-filtered MCP entries**

Modify `src/cli_config/manifest.py` imports:

```python
from src.lib.capabilities.discovery import discover_mcp_server_capabilities
from src.lib.capabilities.exposure_policy import export_allowed, resolve_capability_records
```

Add this method to `Manifest`:

```python
    def all_augur_servers_for_client(self, client: str, platform_name: str | None = None) -> list[ServerEntry]:
        """Return server entries allowed for a generated client config."""
        entries = self.all_augur_servers(platform_name)
        records = {
            record.id: record
            for record in resolve_capability_records(discover_mcp_server_capabilities())
        }
        allowed: list[ServerEntry] = []
        for entry in entries:
            record = records.get(f"mcp-server:{entry.id}")
            if record is None:
                allowed.append(entry)
                continue
            if export_allowed(record, client, existing=client in record.current_exposure):
                allowed.append(entry)
        return allowed
```

Modify `src/cli_config/adapters/claude.py`:

```python
    def _managed_entries(self, manifest: Manifest) -> list[ServerEntry]:
        return manifest.all_augur_servers_for_client(self.name)
```

Modify `src/cli_config/adapters/gemini.py`:

```python
    def _managed_entries(self, manifest: Manifest) -> list[ServerEntry]:
        return [entry for entry in manifest.all_augur_servers_for_client(self.name) if not entry.bundle]
```

Search for other direct adapter calls and apply the same pattern:

```bash
rg -n "all_augur_servers\\(" src/cli_config skills/ai scripts
```

Modify `src/cli_config/adapters/codex.py` so both `diff()` and `apply()` use:

```python
        entries = manifest.all_augur_servers_for_client(self.name)
```

Then replace the two existing `manifest.all_augur_servers()` loops with `entries`.

- [x] **Step 4: Run MCP config tests**

```bash
/auto-test-pytest tests/cli/test_config_adapters.py tests/cli/test_config_sync.py
```

Expected: all tests pass.

- [x] **Step 5: Commit Task 5**

```bash
git add src/cli_config/manifest.py src/cli_config/adapters/claude.py src/cli_config/adapters/gemini.py src/cli_config/adapters/codex.py tests/cli/test_config_adapters.py tests/cli/test_config_sync.py
git commit -m "feat: enforce capability policy for mcp config exports"
```

## Task 6: Browse Filters And TypeScript Metadata

**Files:**
- Modify: `apps/dashboard/lib/browse/types.ts`
- Modify: `apps/dashboard/lib/browse/transforms.ts`
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts`
- Modify: `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`
- Test: `tests/dashboard/browse/useBrowseState.test.tsx`

- [x] **Step 1: Add dashboard state tests**

Add a test to `tests/dashboard/browse/useBrowseState.test.tsx`:

```tsx
  it("builds exposure status and surface filters from capability metadata", async () => {
    localStorage.setItem("augur:browse:view", "skills");
    mockUseMcpQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "skill:geo-audit",
            title: "Geo Audit",
            description: "Geo skill",
            hub: "ai",
            type: "skill",
            metadata: {
              classificationStatus: "approved",
              primarySurface: "skill",
              ownerKind: "external",
              management: "unmanaged",
              preferredClient: "claude",
            },
          },
          {
            id: "skill:ui-ux-pro-max",
            title: "UI UX Pro Max",
            description: "Design skill",
            hub: "ai",
            type: "skill",
            metadata: {
              classificationStatus: "unclassified",
              primarySurface: "skill",
              ownerKind: "external",
              management: "unmanaged",
              preferredClient: "none",
            },
          },
        ],
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.exposureItems).toEqual(
        expect.arrayContaining([
          { id: "approved", label: "Approved" },
          { id: "unclassified", label: "Unclassified" },
        ]),
      );
      expect(result.current.surfaceItems).toEqual([{ id: "skill", label: "Skill" }]);
    });
  });
```

- [x] **Step 2: Run dashboard state test and confirm it fails**

```bash
/auto-test-dashboard tests/dashboard/browse/useBrowseState.test.tsx
```

Expected: failure because `exposureItems` and `surfaceItems` are not in `BrowseState`.

- [x] **Step 3: Add Browse state fields and metadata passthrough**

Modify `apps/dashboard/lib/browse/types.ts` comment on `metadata`:

```ts
  // Known metadata fields: ownership, source tag, category, plugin, masterClient,
  // skillType, skillTags, pageTags, capabilityId, ownerKind, management,
  // classificationStatus, primarySurface, preferredClient, exportTo,
  // currentExposure, drift
  metadata?: Record<string, string>;
```

Modify `apps/dashboard/app/(views)/browse/useBrowseState.ts` `BrowseState`:

```ts
  exposureFilter: string | null;
  setExposureFilter: (status: string | null) => void;
  exposureItems: { id: string; label: string }[];
  surfaceFilter: string | null;
  setSurfaceFilter: (surface: string | null) => void;
  surfaceItems: { id: string; label: string }[];
```

Add state:

```ts
  const [exposureFilter, setExposureFilter] = useState<string | null>(null);
  const [surfaceFilter, setSurfaceFilter] = useState<string | null>(null);
```

Reset these in `changeView()`:

```ts
    setExposureFilter(null);
    setSurfaceFilter(null);
```

Add item builders:

```ts
  const exposureItems = useMemo(() => {
    const values = new Set(items.map((item) => item.metadata?.classificationStatus).filter(Boolean) as string[]);
    return Array.from(values).sort().map((id) => ({ id, label: id.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) }));
  }, [items]);

  const surfaceItems = useMemo(() => {
    const values = new Set(items.map((item) => item.metadata?.primarySurface).filter(Boolean) as string[]);
    return Array.from(values).sort().map((id) => ({ id, label: id.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) }));
  }, [items]);
```

Include filters in the filtered item predicate:

```ts
      if (exposureFilter && item.metadata?.classificationStatus !== exposureFilter) return false;
      if (surfaceFilter && item.metadata?.primarySurface !== surfaceFilter) return false;
```

Return the new fields from `useBrowseState()`.

Modify `BrowseToolbar.tsx` props and render two `FilterSelect` controls using labels `Exposure` and `Surface`, shown only when their option arrays are non-empty.

- [x] **Step 4: Run dashboard Browse tests**

```bash
/auto-test-dashboard tests/dashboard/browse/useBrowseState.test.tsx
```

Expected: all tests pass.

- [x] **Step 5: Commit Task 6**

```bash
git add apps/dashboard/lib/browse/types.ts apps/dashboard/lib/browse/transforms.ts 'apps/dashboard/app/(views)/browse/useBrowseState.ts' 'apps/dashboard/app/(views)/browse/BrowseToolbar.tsx' tests/dashboard/browse/useBrowseState.test.tsx
git commit -m "feat: add browse filters for capability exposure"
```

## Task 7: Full Verification And Inventory Smoke

**Files:**
- Modify only if verification exposes a real defect in files already touched by Tasks 1-6.

- [x] **Step 1: Run Python capability and sync tests**

```bash
/auto-test-pytest tests/lib/test_capability_exposure_policy.py tests/lib/test_capability_inventory_discovery.py tests/lib/test_capability_browse_enrichment.py skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py tests/cli/test_config_adapters.py tests/cli/test_config_sync.py
```

Expected: all selected tests pass.

- [x] **Step 2: Run dashboard Browse tests**

```bash
/auto-test-dashboard tests/dashboard/browse/useBrowseState.test.tsx
```

Expected: all selected dashboard tests pass.

- [x] **Step 3: Rebuild affected Browse index categories through the approved loop**

```bash
/auto-test-build
```

Expected: dashboard build passes. If the loop reports stale index data, run the repo-approved reindex action named in the loop output.

- [x] **Step 4: Browser-verify Browse**

Use the in-app browser or an approved browser tool to inspect:

- `/browse?category=skills`
- `/browse?category=mcp-servers` in development mode
- `/browse?category=commands` in development mode

Expected:

- pages reach interactive state;
- capability metadata badges/filters are visible where data exists;
- no client chunk-load error appears;
- console has no new errors from the changed Browse components.

- [x] **Step 5: Check generated export behavior without destructive external cleanup**

Run the smallest repo-approved sync command and inspect generated diffs before committing:

```bash
/dev-sync
```

Expected:

- unclassified new exports are not added to new targets;
- existing unclassified managed exports are preserved unless policy marks them `blocked`;
- unmanaged external/global skill folders are not changed.

Inspect the repo-local generated output diff:

```bash
git diff --name-status -- .claude .codex .gemini .opencode
```

Expected: changed files are only Augur-managed generated outputs; no external unmanaged skill source is deleted.

- [x] **Step 6: Commit final verification fixes**

If verification required fixes, stage only files in this implementation plan:

```bash
git add config/system/capability_exposure.yaml src/lib/capabilities src/mcp/augur_framework/tools/infrastructure/browse/index.py apps/dashboard/lib/browse/types.ts apps/dashboard/lib/browse/transforms.ts 'apps/dashboard/app/(views)/browse/useBrowseState.ts' 'apps/dashboard/app/(views)/browse/BrowseToolbar.tsx' skills/ai/scripts/sync_agents/skill_sync.py src/cli_config/manifest.py src/cli_config/adapters/claude.py src/cli_config/adapters/gemini.py src/cli_config/adapters/codex.py tests/lib/test_capability_exposure_policy.py tests/lib/test_capability_inventory_discovery.py tests/lib/test_capability_browse_enrichment.py skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py tests/cli/test_config_adapters.py tests/dashboard/browse/useBrowseState.test.tsx
git commit -m "fix: harden capability exposure inventory"
```

If no fixes were required, do not create an empty commit.

## Task 8: Handoff Report

**Files:**
- No required file changes.

- [x] **Step 1: Summarize policy status**

Prepare a short implementation report with:

- list of created files;
- list of modified generator/Browse files;
- tests and browser checks run;
- unresolved classification backlog;
- exact external/global surfaces that were reported but not modified.

- [x] **Step 2: Confirm no external/global deletion happened**

Run:

```bash
git status --short
```

Expected:

- no unexpected deletions in `.claude/skills`, `.codex/skills`, `.gemini/skills`, `.opencode/skills`, or user home skill folders;
- only files from this plan are in the final diff.

- [x] **Step 3: Present next choices**

Offer the next spec choices:

1. Browse launcher and internal chat broker.
2. Classification/pruning wave for external skills.
3. MCP-to-Augur-CLI reduction for technical Augur tools.
