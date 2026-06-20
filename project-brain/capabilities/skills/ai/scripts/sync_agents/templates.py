"""
sync_agents/templates.py

Centralized template rendering with safe placeholder resolution (ADR-186 Phase 3).

Extracted from monolithic sync_agents.py (ADR-186).
Provides TemplateRenderer, resolve_placeholders(), and all table-generation helpers.
"""

from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import os
import re
from pathlib import Path

from src.config.runtime_identity import (
    global_mcp_project_root as _shared_global_mcp_project_root,
)

from .constants import (
    PROJECT_ROOT,
    SOURCE_RULES,
    logger,
)


def global_mcp_project_root(project_root: Path | None = None) -> Path:
    """Return the root that user-global MCP configs should embed."""
    return _shared_global_mcp_project_root(project_root or PROJECT_ROOT)


def locate_mcp_python(project_root: Path | None = None) -> str:
    """Return a POSIX-style Python interpreter path for MCP config substitution.

    Prefers the project venv (Windows ``Scripts/python.exe`` or Unix ``bin/python3``);
    otherwise falls back to ``python``/``python3`` on PATH. Forward-slash paths so
    JSON serialization in MCP configs stays safe across platforms.
    """
    root = project_root or PROJECT_ROOT
    venv_win = root / ".venv" / "Scripts" / "python.exe"
    venv_unix = root / ".venv" / "bin" / "python3"
    if venv_win.exists():
        return venv_win.as_posix()
    if venv_unix.exists():
        return venv_unix.as_posix()
    return "python" if os.name == "nt" else "python3"


def _generate_workflows_table() -> str:
    """Generate a compact slash command reference for CLAUDE.md.

    ADR-252: Commands are standalone skills, but generated client docs must
    show only the native primary slash-command surface.
    """
    try:
        from src.plugins.command_listing import render_commands_payload

        payload = render_commands_payload()
    except Exception:
        return "## Slash Commands\n\nCall the `list-commands` MCP tool to discover all available commands.\n"

    sections = payload.get("slash_commands", [])
    if not sections:
        return "## Slash Commands\n\nCall the `list-commands` MCP tool to discover all available commands.\n"

    text = "## Slash Commands\n\n"
    text += "Run `/commands` for full descriptions. In Gemini/Codex, call the `list-commands` MCP tool instead.\n\n"

    labels = {"app": "App", "core": "Core", "dev": "Dev", "test": "Test", "ops": "Ops"}
    for section in sections:
        key = str(section.get("key", ""))
        label = labels.get(key, str(section.get("label", key.title())).removesuffix(" Commands"))
        group = section.get("commands", [])
        if group:
            names = ", ".join(f"`/{c['id']}`" for c in sorted(group, key=lambda c: c["id"]))
            text += f"**{label}** ({len(group)}): {names}\n\n"

    return text


def _cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").strip()


# Relative path (from PROJECT_ROOT) of the full per-tool capability surface map.
# The client instruction files carry only the policy paragraph plus a pointer to
# this doc; the full ~180-row table is written here by the sync engine so
# CLAUDE.md/AGENTS.md/CODEX.md stay under the agent-doc size-warning threshold.
CAPABILITY_EXPOSURE_REF = "docs/generated/capability-exposure.md"

_CAPABILITY_POLICY_TEXT = (
    "These capabilities are intentionally exposed through agent instructions "
    "and Browse instead of broad direct client MCP tool lists. Do not expose "
    "them as direct client MCP tools unless `config/system/capability_exposure.yaml` "
    "includes `mcp` in `export_to`."
)

CANONICAL_AGENT_COMMANDS = (
    ("core", ("ask", "discover", "keep", "project")),
    ("dev", ("routines", "skillify")),
)


def _agents_md_capability_records() -> list:
    """Return approved, agents-md-exported capability records (excludes commands/workflows)."""
    try:
        from src.lib.capabilities.discovery import discover_capabilities
        from src.lib.capabilities.exposure_policy import resolve_capability_records
    except Exception:
        return []

    try:
        records = resolve_capability_records(discover_capabilities())
    except Exception:
        logger.warning("Failed to resolve capability records", exc_info=True)
        return []

    return [
        record
        for record in records
        if getattr(record, "classification_status", "") == "approved"
        and getattr(record, "type", "") not in {"command", "workflow"}
        and "agents-md" in tuple(getattr(record, "export_to", ()) or ())
    ]

def _capability_preferred_surface(record) -> str:
    preferred_client = getattr(record, "preferred_client", "")
    primary_surface = getattr(record, "primary_surface", "")
    if preferred_client and preferred_client != "none":
        return f"{primary_surface} via {preferred_client}"
    return primary_surface


def build_capability_exposure_doc() -> str | None:
    """Build the full per-tool capability surface map markdown (pure, no writes).

    Returns None when there are no agents-md capability exports. The sync engine
    writes the result to ``CAPABILITY_EXPOSURE_REF``.
    """
    records = _agents_md_capability_records()
    if not records:
        return None

    rows = ""
    for record in sorted(records, key=lambda item: item.id):
        metadata = getattr(record, "metadata", {}) or {}
        owner = metadata.get("skill") or getattr(record, "owner_kind", "")
        rows += (
            f"| `{_cell(getattr(record, 'id', ''))}` "
            f"| {_cell(getattr(record, 'type', ''))} "
            f"| {_cell(_capability_preferred_surface(record))} "
            f"| {_cell(owner)} |\n"
        )

    return (
        "# Capability Policy Exports\n\n"
        "> Auto-generated by sync_agents. Do not hand-edit.\n\n"
        f"{_CAPABILITY_POLICY_TEXT}\n\n"
        "| Capability | Type | Preferred Surface | Owner |\n"
        "|---|---|---|---|\n"
        f"{rows}"
    )


def _generate_capability_policy_table() -> str:
    """Render the compact capability-policy pointer for client instruction files.

    Keeps the load-bearing policy paragraph inline and links the full per-tool
    table (written separately to ``CAPABILITY_EXPOSURE_REF``) to keep agent docs
    under the size-warning threshold.
    """
    records = _agents_md_capability_records()
    if not records:
        return ""

    return (
        "## Capability Policy Exports\n\n"
        f"{_CAPABILITY_POLICY_TEXT}\n\n"
        f"Full per-tool surface map ({len(records)} capabilities): "
        f"`{CAPABILITY_EXPOSURE_REF}`.\n"
    )


def _generate_adr_status_table() -> str:
    """Generate a compact ADR status summary for CLAUDE.md."""
    from collections import Counter as _Counter
    from src.lib.adr_utils import get_adr_dir, scan_adrs

    decisions_dir = get_adr_dir()
    if not decisions_dir.exists():
        return ""

    STATUS_ORDER = [
        "Implemented",
        "Accepted",
        "Proposed",
        "Future",
        "Superseded",
        "Deprecated",
        "Cancelled",
        "Other",
    ]

    adrs = [{"number": adr["number"], "status": adr["status"]} for adr in scan_adrs(decisions_dir)]

    if not adrs:
        return ""

    counts = _Counter(a["status"] for a in adrs)
    summary_parts = []
    for s in STATUS_ORDER:
        c = counts.get(s, 0)
        if c:
            summary_parts.append(f"{c} {s}")

    text = "## ADR Status\n\n"
    text += f"**{len(adrs)} ADRs** ({', '.join(summary_parts)}) — see `docs/generated/adr-index.md` for the full index and recent decisions.\n"
    return text


def _generate_chains_table() -> str:
    """Generate a markdown table of all chains."""
    chains_dir = PROJECT_ROOT / "plugins" / "core" / "skills" / "executor" / "chains"
    if not chains_dir.exists():
        return ""

    chains = []
    for chain_file in sorted(chains_dir.glob("*.yaml")):
        try:
            import yaml

            with open(chain_file, "r", encoding="utf-8") as f:
                chain_data = yaml.safe_load(f)
                if chain_data:
                    chains.append(
                        {
                            "name": chain_file.stem,
                            "description": chain_data.get("description", "No description"),
                        }
                    )
        except Exception:
            chains.append({"name": chain_file.stem, "description": "Failed to parse"})

    if not chains:
        return ""

    text = "## 🔗 Available Chains\n\n| Chain | Description |\n|---|---|\n"
    for c in chains:
        text += f"| `{c['name']}` | {c['description']} |\n"
    return text


def _generate_commands_full_table() -> str:
    """Generate the canonical slash command reference table for /commands."""
    rows = []
    descriptions = {
        "ask": "Ask the personal/global second brain with reflective context and optional retention.",
        "discover": "Show Augur capabilities, commands, and system state without mutating the current folder.",
        "keep": "Capture inbound content or persist generated artifacts to personal/global context.",
        "project": "Initialize, inspect, and operate on the current project folder.",
        "routines": "Run and inspect personal/global routines, automation, and daemon work.",
        "skillify": "Convert a durable gap into a reusable Augur skill.",
    }
    for _, names in CANONICAL_AGENT_COMMANDS:
        for name in names:
            rows.append((name, descriptions[name]))

    text = "## Primary Commands\n\n| Command | Description |\n|---|---|\n"
    for name, description in rows:
        text += f"| `/{name}` | {description} |\n"
    return text + "\n"


class TemplateRenderer:
    """Renders templates with safe placeholder resolution (ADR-186 Phase 3).

    Replaces placeholders only in designated slots. Validates that no
    unreplaced placeholders remain in the final output.
    """

    PLACEHOLDER_PATTERN = re.compile(r"\{\{([A-Z_]+)\}\}")

    def render(self, template: str, context: dict[str, str]) -> str:
        """Replace placeholders with generated content.

        Args:
            template: Template string with {{PLACEHOLDER}} markers.
            context: Mapping of placeholder names to replacement content.

        Returns:
            Rendered string with all placeholders replaced.

        Raises:
            ValueError: If unreplaced placeholders remain in the output.
        """
        result = template
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, value)

        # Validate no placeholders leaked through
        remaining = self.PLACEHOLDER_PATTERN.findall(result)
        if remaining:
            logger.warning(
                f"Unreplaced template placeholders found: {remaining}. "
                "This may indicate placeholder strings in generated content."
            )

        return result


# Module-level renderer instance
_renderer = TemplateRenderer()


def resolve_placeholders(content: str) -> str:
    """Replace template placeholders with generated content.

    Uses TemplateRenderer for safe placeholder resolution (ADR-186 Phase 3).
    Only generates tables when their placeholder is present in the content (lazy).
    """
    generators = {
        "WORKFLOWS_TABLE": _generate_workflows_table,
        "CAPABILITY_POLICY_TABLE": _generate_capability_policy_table,
        "CHAINS_TABLE": _generate_chains_table,
        "COMMANDS_FULL_TABLE": _generate_commands_full_table,
        "ADR_STATUS_TABLE": _generate_adr_status_table,
    }
    context = {
        key: fn() for key, fn in generators.items() if f"{{{{{key}}}}}" in content
    }
    return _renderer.render(content, context)


def render_rules_projection(content: str) -> str:
    """Render generated client rules with the ADR-781 Augur stack envelope."""
    rendered = resolve_placeholders(content)
    try:
        from src.config.paths import get_active_brain_stack
        from src.lib.brain_projection import render_augur_stack_envelope

        stack = get_active_brain_stack(cwd=PROJECT_ROOT)
        envelope = render_augur_stack_envelope(stack).rstrip()
    except Exception as exc:
        logger.warning("Could not render Augur context envelope: %s", exc)
        return rendered

    standard_context = ""
    try:
        from src.lib.brain_projection import render_standard_brain_files_context

        standard_context = render_standard_brain_files_context(
            stack,
            project_root=PROJECT_ROOT,
        ).strip()
    except Exception as exc:
        logger.warning("Could not render standard brain file context: %s", exc)

    sections = [f"## Augur Context\n\n```yaml\n{envelope}\n```"]
    if standard_context:
        sections.append(standard_context)
    sections.append(rendered)
    return "\n\n".join(sections)


def _load_project_context(project_root: Path) -> str | None:
    """Load a compact project context summary for injection into agent profiles.

    Reads the vault-backed project-context.md if it exists.
    Falls back to extracting key sections from the vault-backed agent-rules.md.
    Returns None if no context is available.
    """
    # 1. Check for explicit project context file
    context_file = SOURCE_RULES.parent / "project-context.md"
    if context_file.exists():
        try:
            content = context_file.read_text(encoding="utf-8").strip()
            if content:
                return content
        except OSError:
            pass

    # 2. Fall back: extract Architecture section from agent-rules.md
    rules_file = SOURCE_RULES
    if not rules_file.exists():
        return None

    try:
        rules = rules_file.read_text(encoding="utf-8")
    except OSError:
        return None

    # Extract the Architecture and Code Style sections (compact summary)
    import re

    sections = []

    # Extract monorepo structure
    match = re.search(
        r"###\s+Monorepo Structure\s*\n(```[\s\S]*?```)",
        rules,
    )
    if match:
        sections.append("**Monorepo Structure**:\n" + match.group(1))

    # Key conventions (compact)
    sections.append(
        "**Key Conventions**:\n"
        "- `src/`, `skills/`, `plugins/`, `docs/` = CODE; vault/documents/state are external storage layers\n"
        "- Path resolution: `from src.config.paths import get_project_root, get_config_dir, get_skill_vault_dir`\n"
        "- Dashboard: Next.js 14, App Router, Tailwind + shadcn/ui\n"
        "- Skill UI mounted from `skills/{skill}/augur/dashboard/` or `skills/{skill}/augur/pages/` at build time\n"
        "- Python: 4-space indent, snake_case, Google docstrings\n"
        "- TypeScript: 2-space indent, camelCase, named exports\n"
        "- Commits: Conventional Commits (feat:, fix:, refactor:, docs:, test:, chore:)"
    )

    return "\n\n".join(sections) if sections else None
