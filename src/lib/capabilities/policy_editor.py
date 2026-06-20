"""Reviewed draft/apply helpers for capability exposure policy edits."""

from __future__ import annotations

from collections.abc import Mapping
import difflib
import hashlib
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .exposure_policy import CapabilityRecord, capability_policy_path

_MISSING_POLICY_TEXT = "version: 1\ncapabilities: {}\n"
_VALID_CLIENTS = {"claude", "codex", "gemini", "opencode", "cursor", "copilot"}
_CLI_EXPORTS = ["cli", "agents-md", "browse"]
_CLI_TYPES = {"mcp-server", "mcp-tool", "command", "workflow", "cli"}


class CapabilityPolicyError(ValueError):
    """Raised when a capability policy draft cannot be created or applied."""


def policy_content_hash(text: str) -> str:
    """Return the SHA-256 hex digest for UTF-8 policy text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def draft_capability_policy(
    records: list[CapabilityRecord],
    policy_path: Path | None = None,
    *,
    action: str,
    capability_ids: list[str],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a reviewed policy-edit draft without writing the policy file."""
    if not capability_ids:
        raise CapabilityPolicyError("capability_ids is required")

    path = policy_path or capability_policy_path()
    base_text = _read_policy_text(path)
    base_hash = policy_content_hash(base_text)
    policy = _load_policy_text(base_text)
    current_entries = policy.get("capabilities") or {}
    if not isinstance(current_entries, dict):
        current_entries = {}

    records_by_id = {record.id: record for record in records}
    entries: dict[str, dict[str, Any]] = {}
    before_entries: dict[str, dict[str, Any]] = {}

    for capability_id in capability_ids:
        record = records_by_id.get(capability_id)
        if record is None:
            raise CapabilityPolicyError(f"unknown capability id: {capability_id}")

        current_entry = current_entries.get(capability_id)
        before_entries[capability_id] = (
            _normalize_entry(current_entry)
            if isinstance(current_entry, dict)
            else _entry_from_record(record, export_to=record.current_exposure)
        )
        entries[capability_id] = _entry_for_action(record, action, params or {})

    draft_id = _draft_fingerprint(
        action=action,
        base_hash=base_hash,
        capability_ids=capability_ids,
        entries=entries,
    )

    return {
        "draft_id": draft_id,
        "base_hash": base_hash,
        "action": action,
        "capability_ids": list(capability_ids),
        "entries": entries,
        "diff": _policy_diff(before_entries, entries),
        "impact": _impact(
            [records_by_id[capability_id] for capability_id in capability_ids],
            entries,
        ),
    }


def apply_capability_policy_draft(policy_path: Path | None = None, *, draft: dict[str, Any]) -> dict[str, Any]:
    """Atomically merge a reviewed draft into the capability exposure policy."""
    path = policy_path or capability_policy_path()
    current_text = _read_policy_text(path)
    current_hash = policy_content_hash(current_text)
    expected_hash = str(draft.get("base_hash") or "")
    if current_hash != expected_hash:
        raise CapabilityPolicyError(f"stale draft: current policy hash {current_hash} != {expected_hash}")

    action = str(draft.get("action") or "")
    if not action:
        raise CapabilityPolicyError("draft action is required")

    capability_ids = draft.get("capability_ids")
    if not isinstance(capability_ids, list) or not capability_ids:
        raise CapabilityPolicyError("draft capability_ids must be a non-empty list")
    normalized_capability_ids = [str(capability_id) for capability_id in capability_ids]

    entries = draft.get("entries")
    if not isinstance(entries, Mapping):
        raise CapabilityPolicyError("draft entries must be a mapping")
    if not entries:
        raise CapabilityPolicyError("draft entries cannot be empty")

    normalized_entries: dict[str, dict[str, Any]] = {}
    for capability_id, entry in entries.items():
        if not isinstance(entry, Mapping):
            raise CapabilityPolicyError(f"draft entry must be a mapping: {capability_id}")
        normalized_entries[str(capability_id)] = _normalize_entry(dict(entry))

    if set(normalized_entries) != set(normalized_capability_ids):
        raise CapabilityPolicyError("draft entries must match draft capability_ids")

    expected_draft_id = _draft_fingerprint(
        action=action,
        base_hash=expected_hash,
        capability_ids=normalized_capability_ids,
        entries=normalized_entries,
    )
    if str(draft.get("draft_id") or "") != expected_draft_id:
        raise CapabilityPolicyError("draft fingerprint mismatch: request was not the reviewed draft")

    policy = _load_policy_text(current_text)
    current_entries = policy.get("capabilities")
    if not isinstance(current_entries, dict):
        current_entries = {}
    current_entries.update(normalized_entries)
    policy["version"] = policy.get("version") or 1
    policy["capabilities"] = current_entries

    next_text = yaml.safe_dump(policy, sort_keys=True, allow_unicode=False)
    _atomic_write_text(path, next_text)
    try:
        from .export_filter import reset_export_filter_cache

        reset_export_filter_cache()
    except Exception:  # noqa: BLE001
        pass
    return {
        "ok": True,
        "policy_hash": policy_content_hash(next_text),
        "applied_capabilities": sorted(normalized_entries),
    }


def _entry_for_action(record: CapabilityRecord, action: str, params: dict[str, Any]) -> dict[str, Any]:
    if action == "keep_only_in_client":
        target = _required_client(params, "target_client")
        return _entry_from_record(
            record,
            preferred_client=target,
            export_to=(target,),
            classification_status="approved",
        )

    if action == "move_to_cli_only":
        if not (record.owner_kind == "augur" and record.management == "generated" and record.type in _CLI_TYPES):
            raise CapabilityPolicyError(
                f"move_to_cli_only is only valid for Augur generated technical capabilities: {record.id}"
            )
        return _entry_from_record(
            record,
            primary_surface="cli",
            preferred_client="shell",
            export_to=tuple(_CLI_EXPORTS),
            classification_status="approved",
        )

    if action == "block_from_clients":
        clients = _required_clients(params, "clients")
        remaining = tuple(client for client in record.current_exposure if client not in clients)
        return _entry_from_record(
            record,
            export_to=remaining,
            classification_status="approved" if remaining else "blocked",
        )

    if action == "approve_multi_client":
        clients = _required_clients(params, "clients")
        return _entry_from_record(
            record,
            preferred_client=clients[0],
            export_to=clients,
            classification_status="approved",
        )

    if action == "approve_current_exposure":
        if not record.current_exposure:
            raise CapabilityPolicyError(f"approve_current_exposure requires current exposure: {record.id}")
        return _entry_from_record(
            record,
            preferred_client=_preferred_current_surface(record),
            export_to=record.current_exposure,
            classification_status="approved",
        )

    if action == "mark_external_unmanaged":
        return _entry_from_record(
            record,
            owner_kind="external",
            management="unmanaged",
            export_to=record.export_to,
        )

    if action == "adopt_under_augur_policy":
        return _entry_from_record(
            record,
            owner_kind="adopted",
            management="managed-policy",
            export_to=record.export_to,
            classification_status="approved",
        )

    if action == "leave_unclassified":
        return _entry_from_record(
            record,
            preferred_client="none",
            export_to=(),
            classification_status="unclassified",
        )

    raise CapabilityPolicyError(f"unsupported action: {action}")


def _preferred_current_surface(record: CapabilityRecord) -> str:
    if record.preferred_client and record.preferred_client != "none":
        return record.preferred_client
    for surface in ("shell", "mcp-config", "mcp", "cli", "agents-md", "browse"):
        if surface in record.current_exposure:
            return surface
    return record.current_exposure[0] if record.current_exposure else "none"


def _entry_from_record(
    record: CapabilityRecord,
    *,
    owner_kind: str | None = None,
    management: str | None = None,
    scope: str | None = None,
    primary_surface: str | None = None,
    preferred_client: str | None = None,
    export_to: tuple[str, ...] | list[str] | None = None,
    classification_status: str | None = None,
) -> dict[str, Any]:
    return {
        "owner_kind": owner_kind or record.owner_kind,
        "management": management or record.management,
        "scope": scope or record.scope,
        "primary_surface": primary_surface or record.primary_surface,
        "preferred_client": preferred_client if preferred_client is not None else record.preferred_client,
        "export_to": list(export_to if export_to is not None else record.export_to),
        "classification_status": classification_status or record.classification_status,
    }


def _required_client(params: dict[str, Any], key: str) -> str:
    value = str(params.get(key) or "").strip()
    if value not in _VALID_CLIENTS:
        raise CapabilityPolicyError(f"invalid {key}: {value or '<missing>'}")
    return value


def _required_clients(params: dict[str, Any], key: str) -> tuple[str, ...]:
    raw = params.get(key)
    values = raw if isinstance(raw, (list, tuple)) else []
    clients = tuple(dict.fromkeys(str(value).strip() for value in values if value))
    invalid = [client for client in clients if client not in _VALID_CLIENTS]
    if not clients or invalid:
        bad = ", ".join(invalid) if invalid else "<missing>"
        raise CapabilityPolicyError(f"invalid {key}: {bad}")
    return clients


def _impact(records: list[CapabilityRecord], entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    removed_from: dict[str, list[str]] = {}
    added_to: dict[str, list[str]] = {}
    gemini_delta = 0
    opencode_delta = 0

    for record in records:
        intended = set(_clean_list(entries[record.id].get("export_to")))
        current = set(record.current_exposure)
        removed = sorted(current - intended)
        added = sorted(intended - current)
        if removed:
            removed_from[record.id] = removed
        if added:
            added_to[record.id] = added
        if "gemini" in added:
            gemini_delta += 1
        if "gemini" in removed:
            gemini_delta -= 1
        if "opencode" in added:
            opencode_delta += 1
        if "opencode" in removed:
            opencode_delta -= 1

    return {
        "removed_from": dict(sorted(removed_from.items())),
        "added_to": dict(sorted(added_to.items())),
        "gemini_delta": gemini_delta,
        "opencode_delta": opencode_delta,
    }


def _policy_diff(before_entries: dict[str, dict[str, Any]], entries: dict[str, dict[str, Any]]) -> str:
    before = yaml.safe_dump(
        {"capabilities": before_entries},
        sort_keys=True,
        allow_unicode=False,
    ).splitlines()
    after = yaml.safe_dump(
        {"capabilities": entries},
        sort_keys=True,
        allow_unicode=False,
    ).splitlines()
    lines = list(
        difflib.unified_diff(
            before,
            after,
            fromfile="current",
            tofile="draft",
            lineterm="",
        )
    )
    return "\n".join(lines) + ("\n" if lines else "")


def _draft_fingerprint(
    *,
    action: str,
    base_hash: str,
    capability_ids: list[str],
    entries: dict[str, dict[str, Any]],
) -> str:
    return policy_content_hash(
        yaml.safe_dump(
            {
                "action": action,
                "base_hash": base_hash,
                "capability_ids": capability_ids,
                "entries": entries,
            },
            sort_keys=True,
            allow_unicode=False,
        )
    )[:16]


def _read_policy_text(path: Path) -> str:
    if not path.exists():
        return _MISSING_POLICY_TEXT
    return path.read_text(encoding="utf-8")


def _load_policy_text(text: str) -> dict[str, Any]:
    loaded = yaml.safe_load(text) or {}
    if not isinstance(loaded, dict):
        loaded = {}
    if not isinstance(loaded.get("capabilities"), dict):
        loaded["capabilities"] = {}
    loaded.setdefault("version", 1)
    return loaded


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(entry)
    normalized["export_to"] = list(_clean_list(normalized.get("export_to")))
    return normalized


def _clean_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        values = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        values = [str(part).strip() for part in value]
    else:
        values = []
    return tuple(dict.fromkeys(item for item in values if item))


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(path)


_IMPACT_PREVIEW_CLIENTS = (".claude", ".codex", ".gemini", ".opencode")


def compute_impact_preview(
    *,
    project_root: Path,
    capability_id: str,
    action: str,
) -> dict[str, Any]:
    """Return the list of generated client files that ``action`` would remove.

    Pure predicate — does not mutate the policy or filesystem. Used by Browse
    to render a "would remove" preview before the user confirms a destructive
    policy action (ADR-734 C6.5).

    Currently models the file-removal impact for actions that strip a
    capability from all AI-client surfaces (``move_to_cli_only``,
    ``block_from_gemini``, ``block_from_opencode``). Non-removing actions
    return an empty list — callers can still surface ``action`` in the UI.

    The capability type is parsed from the id prefix:
    ``command:foo`` → ``.<client>/commands/foo.md``
    ``skill:foo``   → ``.<client>/skills/foo/``
    """
    cap_type, _, cap_name = capability_id.partition(":")
    if not cap_name:
        return {"would_remove": []}

    targeted: tuple[str, ...]
    if action == "move_to_cli_only":
        targeted = _IMPACT_PREVIEW_CLIENTS
    elif action == "block_from_gemini":
        targeted = (".gemini",)
    elif action == "block_from_opencode":
        targeted = (".opencode",)
    elif action == "keep_only_in_claude":
        targeted = tuple(c for c in _IMPACT_PREVIEW_CLIENTS if c != ".claude")
    else:
        # Non-destructive actions (approve_multi_client, adopt_under_augur,
        # mark_unmanaged_external) don't remove existing files.
        return {"would_remove": []}

    would_remove: list[str] = []
    for client_dir in targeted:
        if cap_type == "command":
            path = project_root / client_dir / "commands" / f"{cap_name}.md"
            if path.exists():
                would_remove.append(str(path.relative_to(project_root)))
        elif cap_type == "skill":
            dir_path = project_root / client_dir / "skills" / cap_name
            if dir_path.is_dir():
                would_remove.append(str(dir_path.relative_to(project_root)))
    return {"would_remove": sorted(would_remove)}
