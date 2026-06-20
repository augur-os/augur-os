"""Filter generated capability exports through exposure policy."""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from typing import TypeVar

from src.logging import get_entity_logger

from .discovery import capability_id, discover_capabilities
from .exposure_policy import (
    CapabilityRecord,
    export_allowed,
    load_capability_policy,
    reset_capability_policy_cache,
    resolve_capability_records,
)

_CLAUDE_TARGET_ALIASES = frozenset({"claude", "claude-code", "claude_code"})
_STABLE_TARGETS = frozenset({"antigravity", "codex", "gemini", "opencode", "cursor", "copilot"})
logger = get_entity_logger("lib.capabilities.export_filter")

TSource = TypeVar("TSource", bound=tuple)


def normalize_export_target(target: str) -> str:
    """Return the canonical policy target for a generated client surface."""
    cleaned = str(target or "").strip().lower()
    if cleaned in _CLAUDE_TARGET_ALIASES:
        return "claude"
    if cleaned in _STABLE_TARGETS:
        return cleaned
    return cleaned


@lru_cache(maxsize=1)
def _resolved_records_by_id() -> dict[str, CapabilityRecord]:
    records = resolve_capability_records(discover_capabilities())
    return {record.id: record for record in records}


def reset_export_filter_cache() -> None:
    """Clear cached capability policy records used by export filtering."""
    _resolved_records_by_id.cache_clear()
    reset_capability_policy_cache()


def allowed_generated_names(
    capability_type: str,
    names: list[str],
    target: str,
    existing_names: set[str],
) -> set[str]:
    """Return source names allowed for generated export to a client target."""
    normalized_target = normalize_export_target(target)
    existing = {str(name) for name in existing_names}

    try:
        records_by_id = _resolved_records_by_id()
    except Exception:
        logger.warning(
            "Capability export policy resolution failed for %s exports to %s; "
            "preserving existing generated exports and blocking new exports",
            capability_type,
            normalized_target,
            exc_info=True,
        )
        return {name for name in names if name in existing}

    allowed: set[str] = set()
    policy_entries = load_capability_policy().get("capabilities", {})
    if not isinstance(policy_entries, dict):
        policy_entries = {}

    for name in names:
        record_id = capability_id(capability_type, name)
        record = records_by_id.get(record_id)
        if record is None:
            policy_entry = policy_entries.get(record_id, {})
            if (
                isinstance(policy_entry, dict)
                and policy_entry.get("classification_status") == "approved"
                and normalized_target in (policy_entry.get("export_to") or [])
            ):
                allowed.add(name)
                continue
            if name in existing:
                allowed.add(name)
            continue
        is_existing = name in existing
        if is_existing and normalized_target not in record.current_exposure:
            record = replace(
                record,
                current_exposure=tuple(dict.fromkeys((*record.current_exposure, normalized_target))),
            )
        if export_allowed(
            record,
            normalized_target,
            existing=is_existing,
        ):
            allowed.add(name)
    return allowed


_INTERNAL_MCP_SURFACES = frozenset({"mcp", "mcp via dashboard"})


def allowed_mcp_runtime_tool_names(names: list[str], target: str = "mcp") -> set[str]:
    """Return MCP tools approved for runtime registration on ``target``.

    Per docs/references/surface-decision-matrix.md, MCP exposure has three
    distinct layers that must not be conflated:

    - **CLI runtime** (``target="cli"``): the `aug` CLI's in-process MCP
      runtime, used so shell scripts and agent-via-Bash callers can invoke
      any approved tool through `aug <tool-name>`. The CLI is internal to
      this Python process and is not consumed by an AI client; it must
      register every approved tool regardless of ``primary_surface``.
      Blocked tools (``classification_status: blocked``) are still excluded.

    - **Dashboard / internal MCP target** (``target="mcp"`` or any
      ``dashboard-*`` client-id): register tools whose ``primary_surface``
      is ``mcp`` or ``mcp via dashboard``. The dashboard's MCPBridge spawns
      the server with a ``dashboard-*`` client-id (see
      ``apps/dashboard/lib/mcp/preflight.ts``) and falls into this branch.
      Tools without a policy entry are permitted so dashboard callers with
      missing classifications don't break — the audit
      (``scripts/mcp_surface_audit.py``) tracks them for follow-up.

    - **Strict AI client target** (``claude``, ``codex``, ``gemini``, etc.):
      require ``mcp`` in ``export_to`` AND
      ``classification_status: approved``. Tools meant only for the
      dashboard (``primary_surface: mcp via dashboard``) must not include
      ``mcp`` in ``export_to``, which keeps them off the AI client tool list
      while remaining dashboard-reachable.
    """
    normalized_target = normalize_export_target(target)
    if normalized_target == "cli":
        try:
            records_by_id = _resolved_records_by_id()
        except Exception:
            logger.warning(
                "Capability export policy resolution failed for CLI runtime tools; " "preserving runtime registration",
                exc_info=True,
            )
            return set(names)

        allowed: set[str] = set()
        for name in names:
            record = records_by_id.get(capability_id("mcp-tool", name))
            if record is None:
                allowed.add(name)
                continue
            if record.classification_status == "blocked":
                continue
            allowed.add(name)
        return allowed

    if normalized_target not in _STABLE_TARGETS and normalized_target not in {"claude", "client-mcp"}:
        try:
            records_by_id = _resolved_records_by_id()
        except Exception:
            logger.warning(
                "Capability export policy resolution failed for internal MCP runtime tools; "
                "preserving runtime registration",
                exc_info=True,
            )
            return set(names)

        allowed: set[str] = set()
        for name in names:
            record = records_by_id.get(capability_id("mcp-tool", name))
            if record is None:
                allowed.add(name)
                continue
            if record.classification_status == "blocked":
                continue
            if record.classification_status == "approved":
                if record.primary_surface in _INTERNAL_MCP_SURFACES:
                    allowed.add(name)
                continue
            if record.primary_surface in _INTERNAL_MCP_SURFACES:
                allowed.add(name)
        return allowed

    try:
        records_by_id = _resolved_records_by_id()
    except Exception:
        logger.warning(
            "Capability export policy resolution failed for client MCP runtime tools; "
            "preserving runtime registration",
            exc_info=True,
        )
        return set(names)

    policy_entries = load_capability_policy().get("capabilities", {})
    if not isinstance(policy_entries, dict):
        policy_entries = {}

    allowed: set[str] = set()
    for name in names:
        record_id = capability_id("mcp-tool", name)
        record = records_by_id.get(record_id)
        if record is not None and record.classification_status == "approved" and "mcp" in record.export_to:
            allowed.add(name)
            continue
        if record is None:
            policy_entry = policy_entries.get(record_id, {})
            if (
                isinstance(policy_entry, dict)
                and policy_entry.get("classification_status") == "approved"
                and "mcp" in (policy_entry.get("export_to") or [])
            ):
                allowed.add(name)
    return allowed


def filter_named_sources(
    capability_type: str,
    sources: list[TSource],
    target: str,
    existing_names: set[str],
) -> list[TSource]:
    """Filter tuple sources whose first item is a generated capability name."""
    names = [str(source[0]) for source in sources]
    allowed = allowed_generated_names(
        capability_type,
        names,
        target,
        existing_names,
    )
    return [source for source in sources if str(source[0]) in allowed]
