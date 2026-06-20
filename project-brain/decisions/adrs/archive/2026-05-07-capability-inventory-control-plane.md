# Capability Inventory Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the reviewed-apply control plane for capability inventory so Browse can report exposure drift, draft policy changes, preview impact, and apply reviewed policy updates through MCP.

**Architecture:** Keep current-state discovery and intended-state policy in the existing `src/lib/capabilities/` package. Add a reconciliation layer for reports, a policy editor for draft/apply, MCP hub tools as the only write path, and Browse UI state/components that call MCP through `/api/mcp/tool`. Dashboard code never writes `config/system/capability_exposure.yaml` directly.

**Tech Stack:** Python 3.11 dataclasses, PyYAML, existing Augur MCP/FastMCP tool registration, Next.js/React, React Query MCP client hooks, Jest dashboard tests, existing Augur auto-loop commands.

---

## File Structure

- Create `src/lib/capabilities/reconciliation.py`
  - Builds inventory reports from resolved `CapabilityRecord` objects.
  - Computes grouped counts, duplicate clusters, drift counts, Gemini/OpenCode exposure counts, and deterministic recommendations.
- Create `src/lib/capabilities/policy_editor.py`
  - Builds reviewed policy drafts for supported actions.
  - Computes YAML diffs and impact summaries.
  - Applies drafts atomically after base policy hash validation.
- Modify `src/lib/capabilities/__init__.py`
  - Re-export report, draft, and apply APIs.
- Create `src/mcp/augur_framework/tools/hubs/capability_policy.py`
  - Registers MCP tools `capability-inventory-report`, `capability-policy-draft`, and `capability-policy-apply`.
- Modify `src/mcp/augur_framework/tools/hubs/__init__.py`
  - Registers the new capability policy MCP tools.
- Create `tests/lib/test_capability_reconciliation.py`
  - Unit tests for reports, duplicate clusters, counts, and recommendations.
- Create `tests/lib/test_capability_policy_editor.py`
  - Unit tests for draft/apply behavior, YAML output, impact summaries, invalid actions, and stale draft protection.
- Create `tests/mcp/test_capability_policy_tools.py`
  - MCP wrapper tests for JSON payloads and error envelopes.
- Modify `apps/dashboard/lib/browse/types.ts`
  - Add explicit capability policy/report/draft/apply TypeScript types.
- Create `apps/dashboard/lib/browse/useCapabilityPolicy.ts`
  - Dashboard hook for report, draft, and apply MCP calls.
- Create `apps/dashboard/app/(views)/browse/CapabilityPolicyPanel.tsx`
  - Reviewed-apply UI for a selected capability item.
- Modify `apps/dashboard/components/shared/SkillBrowseCard.tsx`
  - Adds a policy button for skill cards with capability metadata.
- Modify `apps/dashboard/app/(views)/browse/useBrowseState.ts`
  - Adds owner/drift/client capability filters and selected capability state.
- Modify `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`
  - Renders Owner and Drift filters when capability metadata exists.
- Modify `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`
  - Adds capability management action for items with `metadata.capabilityId`.
- Modify `apps/dashboard/app/(views)/browse/page.tsx`
  - Hosts the policy panel and wires draft/apply refresh behavior.
- Modify `tests/dashboard/browse/useBrowseState.test.tsx`
  - Tests owner/drift/client filters and reset behavior.
- Create `tests/dashboard/browse/CapabilityPolicyPanel.test.tsx`
  - Tests preview, apply, stale-draft display, and disabled invalid action state.

## Task 1: Reconciliation Report Layer

**Files:**
- Create: `src/lib/capabilities/reconciliation.py`
- Modify: `src/lib/capabilities/__init__.py`
- Test: `tests/lib/test_capability_reconciliation.py`

- [ ] **Step 1: Write failing report tests**

Create `tests/lib/test_capability_reconciliation.py`:

```python
from src.lib.capabilities.exposure_policy import CapabilityRecord
from src.lib.capabilities.reconciliation import build_capability_report


def _record(
    capability_id: str,
    *,
    capability_type: str = "skill",
    owner_kind: str = "external",
    management: str = "unmanaged",
    scope: str = "global",
    primary_surface: str = "skill",
    preferred_client: str = "none",
    export_to: tuple[str, ...] = (),
    classification_status: str = "unclassified",
    current_exposure: tuple[str, ...] = (),
    drift: tuple[str, ...] = (),
) -> CapabilityRecord:
    return CapabilityRecord(
        id=capability_id,
        type=capability_type,  # type: ignore[arg-type]
        owner_kind=owner_kind,  # type: ignore[arg-type]
        management=management,  # type: ignore[arg-type]
        scope=scope,  # type: ignore[arg-type]
        primary_surface=primary_surface,
        preferred_client=preferred_client,
        export_to=export_to,
        classification_status=classification_status,  # type: ignore[arg-type]
        source_paths=(f"/tmp/{capability_id.replace(':', '-')}",),
        current_exposure=current_exposure,
        drift=drift,
    )


def test_report_counts_records_by_type_owner_status_and_drift() -> None:
    report = build_capability_report(
        [
            _record(
                "skill:geo-audit",
                current_exposure=("claude", "codex"),
                drift=("duplicate", "unclassified_export"),
            ),
            _record(
                "mcp-tool:apple-notes-search",
                capability_type="mcp-tool",
                owner_kind="augur",
                management="generated",
                scope="project",
                primary_surface="mcp",
                current_exposure=("mcp", "browse"),
                drift=("duplicate",),
            ),
        ],
    )

    assert report["counts"]["total"] == 2
    assert report["counts"]["by_type"] == {"mcp-tool": 1, "skill": 1}
    assert report["counts"]["by_owner"] == {"augur": 1, "external": 1}
    assert report["counts"]["by_status"] == {"unclassified": 2}
    assert report["counts"]["by_drift"] == {
        "duplicate": 2,
        "unclassified_export": 1,
    }
    assert report["counts"]["gemini_exposed"] == 0
    assert report["counts"]["opencode_exposed"] == 0


def test_report_builds_duplicate_clusters() -> None:
    report = build_capability_report(
        [
            _record(
                "skill:geo-audit",
                current_exposure=("claude", "codex"),
                drift=("duplicate",),
            ),
            _record(
                "command:dev-build",
                capability_type="command",
                owner_kind="augur",
                management="generated",
                scope="project",
                primary_surface="command",
                current_exposure=("agents-md", "browse"),
                drift=("duplicate",),
            ),
        ],
    )

    assert report["duplicate_clusters"] == [
        {
            "id": "command:dev-build",
            "type": "command",
            "owner_kind": "augur",
            "current_exposure": ["agents-md", "browse"],
        },
        {
            "id": "skill:geo-audit",
            "type": "skill",
            "owner_kind": "external",
            "current_exposure": ["claude", "codex"],
        },
    ]


def test_report_recommends_claude_only_for_geo_external_duplicates() -> None:
    report = build_capability_report(
        [
            _record(
                "skill:geo-audit",
                current_exposure=("claude", "codex"),
                drift=("duplicate", "unclassified_export"),
            ),
        ],
    )

    assert report["records"][0]["recommended_action"] == {
        "id": "keep_only_in_client",
        "label": "Keep only in Claude",
        "params": {"target_client": "claude"},
    }


def test_report_recommends_cli_only_for_augur_mcp_tools() -> None:
    report = build_capability_report(
        [
            _record(
                "mcp-tool:dashboard-cache-clear",
                capability_type="mcp-tool",
                owner_kind="augur",
                management="generated",
                scope="project",
                primary_surface="mcp",
                current_exposure=("mcp", "browse"),
                drift=("duplicate",),
            ),
        ],
    )

    assert report["records"][0]["recommended_action"] == {
        "id": "move_to_cli_only",
        "label": "Move to CLI only",
        "params": {},
    }
```

- [ ] **Step 2: Run report tests and confirm failure**

Run:

```bash
/auto-test-pytest tests/lib/test_capability_reconciliation.py
```

Expected: fail because `src.lib.capabilities.reconciliation` does not exist.

- [ ] **Step 3: Implement report layer**

Create `src/lib/capabilities/reconciliation.py`:

```python
"""Capability inventory reconciliation reports."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .exposure_policy import CapabilityRecord


def _list(values: tuple[str, ...]) -> list[str]:
    return list(values)


def _recommend(record: CapabilityRecord) -> dict[str, Any] | None:
    capability_id = record.id.lower()
    if (
        record.type == "skill"
        and record.owner_kind == "external"
        and "duplicate" in record.drift
        and ("geo" in capability_id or "location" in capability_id)
    ):
        return {
            "id": "keep_only_in_client",
            "label": "Keep only in Claude",
            "params": {"target_client": "claude"},
        }
    if (
        record.type == "mcp-tool"
        and record.owner_kind == "augur"
        and record.management == "generated"
    ):
        return {
            "id": "move_to_cli_only",
            "label": "Move to CLI only",
            "params": {},
        }
    if record.classification_status == "unclassified" and record.current_exposure:
        return {
            "id": "review_policy",
            "label": "Review exposure policy",
            "params": {},
        }
    return None


def _record_payload(record: CapabilityRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": record.id,
        "type": record.type,
        "owner_kind": record.owner_kind,
        "management": record.management,
        "scope": record.scope,
        "primary_surface": record.primary_surface,
        "preferred_client": record.preferred_client,
        "export_to": _list(record.export_to),
        "classification_status": record.classification_status,
        "source_paths": _list(record.source_paths),
        "current_exposure": _list(record.current_exposure),
        "drift": _list(record.drift),
        "metadata": dict(record.metadata),
    }
    recommendation = _recommend(record)
    if recommendation is not None:
        payload["recommended_action"] = recommendation
    return payload


def build_capability_report(records: list[CapabilityRecord]) -> dict[str, Any]:
    """Return a serializable reconciliation report for resolved records."""
    by_type = Counter(record.type for record in records)
    by_owner = Counter(record.owner_kind for record in records)
    by_management = Counter(record.management for record in records)
    by_status = Counter(record.classification_status for record in records)
    by_drift = Counter(drift for record in records for drift in record.drift)

    duplicate_clusters = [
        {
            "id": record.id,
            "type": record.type,
            "owner_kind": record.owner_kind,
            "current_exposure": _list(record.current_exposure),
        }
        for record in sorted(records, key=lambda item: item.id)
        if "duplicate" in record.drift
    ]

    return {
        "counts": {
            "total": len(records),
            "by_type": dict(sorted(by_type.items())),
            "by_owner": dict(sorted(by_owner.items())),
            "by_management": dict(sorted(by_management.items())),
            "by_status": dict(sorted(by_status.items())),
            "by_drift": dict(sorted(by_drift.items())),
            "gemini_exposed": sum(
                1 for record in records if "gemini" in record.current_exposure
            ),
            "opencode_exposed": sum(
                1 for record in records if "opencode" in record.current_exposure
            ),
        },
        "duplicate_clusters": duplicate_clusters,
        "records": [_record_payload(record) for record in sorted(records, key=lambda item: item.id)],
    }
```

- [ ] **Step 4: Export report API**

Modify `src/lib/capabilities/__init__.py` to import and export `build_capability_report`:

```python
from .reconciliation import build_capability_report
```

Add `"build_capability_report"` to `__all__`.

- [ ] **Step 5: Run report tests and commit**

Run:

```bash
/auto-test-pytest tests/lib/test_capability_reconciliation.py
```

Expected: all tests pass.

Commit:

```bash
git add src/lib/capabilities/reconciliation.py src/lib/capabilities/__init__.py tests/lib/test_capability_reconciliation.py
git commit -m "feat: add capability reconciliation reports"
```

## Task 2: Policy Draft And Apply Engine

**Files:**
- Create: `src/lib/capabilities/policy_editor.py`
- Modify: `src/lib/capabilities/__init__.py`
- Test: `tests/lib/test_capability_policy_editor.py`

- [ ] **Step 1: Write failing policy editor tests**

Create `tests/lib/test_capability_policy_editor.py`:

```python
from pathlib import Path

import pytest
import yaml

from src.lib.capabilities.exposure_policy import CapabilityRecord
from src.lib.capabilities.policy_editor import (
    CapabilityPolicyError,
    apply_capability_policy_draft,
    draft_capability_policy,
    policy_content_hash,
)


def _record(
    capability_id: str,
    *,
    capability_type: str = "skill",
    owner_kind: str = "external",
    management: str = "unmanaged",
    scope: str = "global",
    primary_surface: str = "skill",
    current_exposure: tuple[str, ...] = ("claude", "codex"),
) -> CapabilityRecord:
    return CapabilityRecord(
        id=capability_id,
        type=capability_type,  # type: ignore[arg-type]
        owner_kind=owner_kind,  # type: ignore[arg-type]
        management=management,  # type: ignore[arg-type]
        scope=scope,  # type: ignore[arg-type]
        primary_surface=primary_surface,
        preferred_client="none",
        export_to=(),
        classification_status="unclassified",
        source_paths=(f"/tmp/{capability_id.replace(':', '-')}",),
        current_exposure=current_exposure,
        drift=("duplicate", "unclassified_export"),
    )


def _policy_file(tmp_path: Path) -> Path:
    path = tmp_path / "capability_exposure.yaml"
    path.write_text("version: 1\ncapabilities: {}\n", encoding="utf-8")
    return path


def test_draft_keep_only_in_client_returns_diff_and_impact(tmp_path: Path) -> None:
    policy_path = _policy_file(tmp_path)
    draft = draft_capability_policy(
        [_record("skill:geo-audit")],
        policy_path=policy_path,
        action="keep_only_in_client",
        capability_ids=["skill:geo-audit"],
        params={"target_client": "claude"},
    )

    assert draft["base_hash"] == policy_content_hash(policy_path.read_text())
    assert draft["entries"]["skill:geo-audit"]["preferred_client"] == "claude"
    assert draft["entries"]["skill:geo-audit"]["export_to"] == ["claude"]
    assert draft["entries"]["skill:geo-audit"]["classification_status"] == "approved"
    assert draft["impact"]["removed_from"] == {"skill:geo-audit": ["codex"]}
    assert "skill:geo-audit" in draft["diff"]


def test_draft_move_to_cli_only_for_augur_generated_mcp_tool(tmp_path: Path) -> None:
    policy_path = _policy_file(tmp_path)
    record = _record(
        "mcp-tool:dashboard-cache-clear",
        capability_type="mcp-tool",
        owner_kind="augur",
        management="generated",
        scope="project",
        primary_surface="mcp",
        current_exposure=("mcp", "browse", "gemini"),
    )

    draft = draft_capability_policy(
        [record],
        policy_path=policy_path,
        action="move_to_cli_only",
        capability_ids=[record.id],
        params={},
    )

    entry = draft["entries"][record.id]
    assert entry["primary_surface"] == "cli"
    assert entry["preferred_client"] == "shell"
    assert entry["export_to"] == ["agents-md", "browse"]
    assert draft["impact"]["gemini_delta"] == -1


def test_draft_rejects_cli_only_for_unmanaged_external_skill(tmp_path: Path) -> None:
    policy_path = _policy_file(tmp_path)

    with pytest.raises(CapabilityPolicyError, match="move_to_cli_only requires"):
        draft_capability_policy(
            [_record("skill:geo-audit")],
            policy_path=policy_path,
            action="move_to_cli_only",
            capability_ids=["skill:geo-audit"],
            params={},
        )


def test_apply_writes_policy_when_base_hash_matches(tmp_path: Path) -> None:
    policy_path = _policy_file(tmp_path)
    draft = draft_capability_policy(
        [_record("skill:geo-audit")],
        policy_path=policy_path,
        action="keep_only_in_client",
        capability_ids=["skill:geo-audit"],
        params={"target_client": "claude"},
    )

    result = apply_capability_policy_draft(policy_path=policy_path, draft=draft)

    written = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    assert result["ok"] is True
    assert written["capabilities"]["skill:geo-audit"]["export_to"] == ["claude"]


def test_apply_rejects_stale_draft(tmp_path: Path) -> None:
    policy_path = _policy_file(tmp_path)
    draft = draft_capability_policy(
        [_record("skill:geo-audit")],
        policy_path=policy_path,
        action="keep_only_in_client",
        capability_ids=["skill:geo-audit"],
        params={"target_client": "claude"},
    )
    policy_path.write_text(
        "version: 1\ncapabilities:\n  skill:other:\n    classification_status: approved\n",
        encoding="utf-8",
    )

    with pytest.raises(CapabilityPolicyError, match="stale draft"):
        apply_capability_policy_draft(policy_path=policy_path, draft=draft)
```

- [ ] **Step 2: Run policy editor tests and confirm failure**

Run:

```bash
/auto-test-pytest tests/lib/test_capability_policy_editor.py
```

Expected: fail because `src.lib.capabilities.policy_editor` does not exist.

- [ ] **Step 3: Implement policy editor**

Create `src/lib/capabilities/policy_editor.py`:

```python
"""Reviewed capability exposure policy draft and apply helpers."""

from __future__ import annotations

import difflib
import hashlib
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .exposure_policy import CapabilityRecord, capability_policy_path, load_capability_policy

_CLIENTS = {"claude", "codex", "gemini", "opencode", "cursor", "copilot"}


class CapabilityPolicyError(ValueError):
    """Raised when a capability policy draft or apply request is invalid."""


def policy_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_policy_text(path: Path) -> str:
    if not path.exists():
        return "version: 1\ncapabilities: {}\n"
    return path.read_text(encoding="utf-8")


def _dump_policy(policy: dict[str, Any]) -> str:
    return yaml.safe_dump(policy, sort_keys=True, allow_unicode=False)


def _records_by_id(records: list[CapabilityRecord]) -> dict[str, CapabilityRecord]:
    return {record.id: record for record in records}


def _entry_for_action(
    record: CapabilityRecord,
    action: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    if action == "keep_only_in_client":
        target = str(params.get("target_client") or "").strip().lower()
        if target not in _CLIENTS:
            raise CapabilityPolicyError("keep_only_in_client requires target_client")
        return {
            "owner_kind": record.owner_kind,
            "management": record.management,
            "scope": record.scope,
            "primary_surface": record.primary_surface,
            "preferred_client": target,
            "export_to": [target],
            "classification_status": "approved",
        }
    if action == "move_to_cli_only":
        if not (
            record.owner_kind == "augur"
            and record.management == "generated"
            and record.type in {"mcp-server", "mcp-tool", "command", "workflow", "cli"}
        ):
            raise CapabilityPolicyError(
                "move_to_cli_only requires an Augur generated technical capability"
            )
        return {
            "owner_kind": record.owner_kind,
            "management": record.management,
            "scope": record.scope,
            "primary_surface": "cli",
            "preferred_client": "shell",
            "export_to": ["agents-md", "browse"],
            "classification_status": "approved",
        }
    if action == "block_from_clients":
        clients = [str(item).strip().lower() for item in params.get("clients", [])]
        if not clients or any(client not in _CLIENTS for client in clients):
            raise CapabilityPolicyError("block_from_clients requires valid clients")
        remaining = [item for item in record.current_exposure if item not in clients]
        return {
            "owner_kind": record.owner_kind,
            "management": record.management,
            "scope": record.scope,
            "primary_surface": record.primary_surface,
            "preferred_client": record.preferred_client,
            "export_to": remaining,
            "classification_status": "approved" if remaining else "blocked",
        }
    if action == "approve_multi_client":
        clients = [str(item).strip().lower() for item in params.get("clients", [])]
        if not clients or any(client not in _CLIENTS for client in clients):
            raise CapabilityPolicyError("approve_multi_client requires valid clients")
        return {
            "owner_kind": record.owner_kind,
            "management": record.management,
            "scope": record.scope,
            "primary_surface": record.primary_surface,
            "preferred_client": clients[0],
            "export_to": clients,
            "classification_status": "approved",
        }
    if action == "mark_external_unmanaged":
        return {
            "owner_kind": "external",
            "management": "unmanaged",
            "scope": record.scope,
            "primary_surface": record.primary_surface,
            "preferred_client": record.preferred_client,
            "export_to": list(record.export_to),
            "classification_status": record.classification_status,
        }
    if action == "adopt_under_augur_policy":
        return {
            "owner_kind": "adopted",
            "management": "managed-policy",
            "scope": record.scope,
            "primary_surface": record.primary_surface,
            "preferred_client": record.preferred_client,
            "export_to": list(record.export_to),
            "classification_status": "approved",
        }
    if action == "leave_unclassified":
        return {
            "owner_kind": record.owner_kind,
            "management": record.management,
            "scope": record.scope,
            "primary_surface": record.primary_surface,
            "preferred_client": "none",
            "export_to": [],
            "classification_status": "unclassified",
        }
    raise CapabilityPolicyError(f"unsupported capability policy action: {action}")


def _impact(
    records: list[CapabilityRecord],
    entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    removed_from: dict[str, list[str]] = {}
    added_to: dict[str, list[str]] = {}
    gemini_delta = 0
    opencode_delta = 0
    for record in records:
        entry = entries[record.id]
        current = set(record.current_exposure)
        intended = set(entry.get("export_to") or [])
        removed = sorted(current - intended)
        added = sorted(intended - current)
        if removed:
            removed_from[record.id] = removed
        if added:
            added_to[record.id] = added
        if "gemini" in current and "gemini" not in intended:
            gemini_delta -= 1
        elif "gemini" not in current and "gemini" in intended:
            gemini_delta += 1
        if "opencode" in current and "opencode" not in intended:
            opencode_delta -= 1
        elif "opencode" not in current and "opencode" in intended:
            opencode_delta += 1
    return {
        "removed_from": removed_from,
        "added_to": added_to,
        "gemini_delta": gemini_delta,
        "opencode_delta": opencode_delta,
    }


def draft_capability_policy(
    records: list[CapabilityRecord],
    *,
    policy_path: Path | None = None,
    action: str,
    capability_ids: list[str],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = policy_path or capability_policy_path()
    base_text = _read_policy_text(path)
    base_hash = policy_content_hash(base_text)
    policy = load_capability_policy(path)
    capabilities = policy.setdefault("capabilities", {})
    if not isinstance(capabilities, dict):
        raise CapabilityPolicyError("policy capabilities must be a mapping")

    by_id = _records_by_id(records)
    selected: list[CapabilityRecord] = []
    for capability_id in capability_ids:
        record = by_id.get(capability_id)
        if record is None:
            raise CapabilityPolicyError(f"capability not found: {capability_id}")
        selected.append(record)

    entries = {
        record.id: _entry_for_action(record, action, params or {})
        for record in selected
    }
    next_policy = dict(policy)
    next_capabilities = dict(capabilities)
    next_capabilities.update(entries)
    next_policy["capabilities"] = next_capabilities
    next_text = _dump_policy(next_policy)
    diff = "".join(
        difflib.unified_diff(
            base_text.splitlines(keepends=True),
            next_text.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )
    fingerprint = policy_content_hash(f"{base_hash}\n{action}\n{entries}")
    return {
        "draft_id": fingerprint,
        "base_hash": base_hash,
        "action": action,
        "capability_ids": capability_ids,
        "entries": entries,
        "diff": diff,
        "impact": _impact(selected, entries),
    }


def apply_capability_policy_draft(
    *,
    policy_path: Path | None = None,
    draft: dict[str, Any],
) -> dict[str, Any]:
    path = policy_path or capability_policy_path()
    base_text = _read_policy_text(path)
    base_hash = policy_content_hash(base_text)
    if draft.get("base_hash") != base_hash:
        raise CapabilityPolicyError("stale draft: policy changed after draft")

    policy = load_capability_policy(path)
    capabilities = policy.setdefault("capabilities", {})
    if not isinstance(capabilities, dict):
        raise CapabilityPolicyError("policy capabilities must be a mapping")
    entries = draft.get("entries")
    if not isinstance(entries, dict) or not entries:
        raise CapabilityPolicyError("draft entries must be a non-empty mapping")

    next_capabilities = dict(capabilities)
    next_capabilities.update(entries)
    policy["capabilities"] = next_capabilities
    next_text = _dump_policy(policy)

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(next_text)
        tmp_path = Path(handle.name)
    tmp_path.replace(path)
    return {
        "ok": True,
        "policy_hash": policy_content_hash(next_text),
        "applied_capabilities": sorted(entries),
    }
```

- [ ] **Step 4: Export policy editor API**

Modify `src/lib/capabilities/__init__.py`:

```python
from .policy_editor import (
    CapabilityPolicyError,
    apply_capability_policy_draft,
    draft_capability_policy,
    policy_content_hash,
)
```

Add these names to `__all__`.

- [ ] **Step 5: Run policy editor tests and commit**

Run:

```bash
/auto-test-pytest tests/lib/test_capability_policy_editor.py
```

Expected: all tests pass.

Commit:

```bash
git add src/lib/capabilities/policy_editor.py src/lib/capabilities/__init__.py tests/lib/test_capability_policy_editor.py
git commit -m "feat: add capability policy draft apply"
```

## Task 3: MCP Tools For Report, Draft, And Apply

**Files:**
- Create: `src/mcp/augur_framework/tools/hubs/capability_policy.py`
- Modify: `src/mcp/augur_framework/tools/hubs/__init__.py`
- Test: `tests/mcp/test_capability_policy_tools.py`

- [ ] **Step 1: Write failing MCP tool tests**

Create `tests/mcp/test_capability_policy_tools.py`:

```python
import json
from types import SimpleNamespace

from src.mcp.augur_framework.tools.hubs.capability_policy import (
    capability_inventory_report_impl,
    capability_policy_apply_impl,
    capability_policy_draft_impl,
)


def test_inventory_report_tool_returns_json(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.hubs.capability_policy.discover_capabilities",
        lambda: [],
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.hubs.capability_policy.resolve_capability_records",
        lambda discovered: [],
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.hubs.capability_policy.build_capability_report",
        lambda records: {"counts": {"total": 0}, "records": []},
    )

    payload = json.loads(capability_inventory_report_impl())

    assert payload == {"ok": True, "counts": {"total": 0}, "records": []}


def test_policy_draft_tool_returns_error_json(monkeypatch) -> None:
    class BrokenPolicy(Exception):
        pass

    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.hubs.capability_policy.CapabilityPolicyError",
        BrokenPolicy,
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.hubs.capability_policy._resolved_records",
        lambda: [],
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.hubs.capability_policy.draft_capability_policy",
        lambda *args, **kwargs: (_ for _ in ()).throw(BrokenPolicy("invalid action")),
    )

    payload = json.loads(
        capability_policy_draft_impl(
            action="move_to_cli_only",
            capability_ids=["skill:geo-audit"],
            params={},
        )
    )

    assert payload == {"ok": False, "error": "invalid action"}


def test_policy_apply_tool_returns_apply_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.hubs.capability_policy.apply_capability_policy_draft",
        lambda draft: {"ok": True, "applied_capabilities": ["skill:geo-audit"]},
    )

    payload = json.loads(
        capability_policy_apply_impl(
            draft={"base_hash": "abc", "entries": {"skill:geo-audit": {}}},
        )
    )

    assert payload == {
        "ok": True,
        "applied_capabilities": ["skill:geo-audit"],
    }


def test_register_tools_exposes_three_tools() -> None:
    registered: list[str] = []

    class FakeMcp:
        def tool(self, name: str, annotations=None):
            def decorator(func):
                registered.append(name)
                return func
            return decorator

    from src.mcp.augur_framework.tools.hubs.capability_policy import register_tools

    register_tools(FakeMcp(), interceptor=None, metrics=None)

    assert registered == [
        "capability-inventory-report",
        "capability-policy-draft",
        "capability-policy-apply",
    ]
```

- [ ] **Step 2: Run MCP tests and confirm failure**

Run:

```bash
/auto-test-pytest tests/mcp/test_capability_policy_tools.py
```

Expected: fail because `src.mcp.augur_framework.tools.hubs.capability_policy` does not exist.

- [ ] **Step 3: Implement MCP tool module**

Create `src/mcp/augur_framework/tools/hubs/capability_policy.py`:

```python
"""Capability inventory policy MCP tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from src.lib.capabilities.discovery import discover_capabilities
from src.lib.capabilities.exposure_policy import resolve_capability_records
from src.lib.capabilities.policy_editor import (
    CapabilityPolicyError,
    apply_capability_policy_draft,
    draft_capability_policy,
)
from src.lib.capabilities.reconciliation import build_capability_report
from src.mcp.augur_shared.annotations import tool_annotations

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _resolved_records():
    return resolve_capability_records(discover_capabilities())


def capability_inventory_report_impl(
    owner: str = "",
    status: str = "",
    drift: str = "",
    capability_type: str = "",
) -> str:
    records = _resolved_records()
    if owner:
        records = [record for record in records if record.owner_kind == owner]
    if status:
        records = [record for record in records if record.classification_status == status]
    if drift:
        records = [record for record in records if drift in record.drift]
    if capability_type:
        records = [record for record in records if record.type == capability_type]
    report = build_capability_report(records)
    return _json({"ok": True, **report})


def capability_policy_draft_impl(
    action: str,
    capability_ids: list[str],
    params: dict[str, Any] | None = None,
) -> str:
    try:
        draft = draft_capability_policy(
            _resolved_records(),
            action=action,
            capability_ids=capability_ids,
            params=params or {},
        )
        return _json({"ok": True, **draft})
    except CapabilityPolicyError as exc:
        return _json({"ok": False, "error": str(exc)})


def capability_policy_apply_impl(draft: dict[str, Any]) -> str:
    try:
        return _json(apply_capability_policy_draft(draft=draft))
    except CapabilityPolicyError as exc:
        return _json({"ok": False, "error": str(exc)})


def register_tools(
    mcp: "FastMCP",
    interceptor=None,
    metrics: Any = None,
) -> None:
    """Register capability policy tools."""

    @mcp.tool(
        name="capability-inventory-report",
        annotations=tool_annotations(
            {
                "title": "Capability Inventory Report",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def capability_inventory_report(
        owner: str = "",
        status: str = "",
        drift: str = "",
        capability_type: str = "",
    ) -> str:
        if metrics is not None:
            metrics.track_tool("capability_inventory_report")
        return capability_inventory_report_impl(
            owner=owner,
            status=status,
            drift=drift,
            capability_type=capability_type,
        )

    @mcp.tool(
        name="capability-policy-draft",
        annotations=tool_annotations(
            {
                "title": "Draft Capability Policy",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    async def capability_policy_draft(
        action: str,
        capability_ids: list[str],
        params: dict[str, Any] | None = None,
    ) -> str:
        if metrics is not None:
            metrics.track_tool("capability_policy_draft")
        return capability_policy_draft_impl(
            action=action,
            capability_ids=capability_ids,
            params=params or {},
        )

    @mcp.tool(
        name="capability-policy-apply",
        annotations=tool_annotations(
            {
                "title": "Apply Capability Policy",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    async def capability_policy_apply(draft: dict[str, Any]) -> str:
        if metrics is not None:
            metrics.track_tool("capability_policy_apply")
        return capability_policy_apply_impl(draft=draft)
```

- [ ] **Step 4: Register MCP tools**

Modify `src/mcp/augur_framework/tools/hubs/__init__.py`:

```python
from .capability_policy import register_tools as register_capability_policy
```

Call it inside `register_hub_tools` after `register_capabilities`:

```python
register_capability_policy(mcp, interceptor=interceptor, metrics=metrics)
```

- [ ] **Step 5: Run MCP tests and commit**

Run:

```bash
/auto-test-pytest tests/mcp/test_capability_policy_tools.py
```

Expected: all tests pass.

Commit:

```bash
git add src/mcp/augur_framework/tools/hubs/capability_policy.py src/mcp/augur_framework/tools/hubs/__init__.py tests/mcp/test_capability_policy_tools.py
git commit -m "feat: expose capability policy mcp tools"
```

## Task 4: Dashboard Types And Policy Hook

**Files:**
- Modify: `apps/dashboard/lib/browse/types.ts`
- Create: `apps/dashboard/lib/browse/useCapabilityPolicy.ts`
- Test: `tests/dashboard/browse/useCapabilityPolicy.test.tsx`

- [ ] **Step 1: Write failing hook tests**

Create `tests/dashboard/browse/useCapabilityPolicy.test.tsx`:

```tsx
/**
 * @jest-environment jsdom
 */
import { act, renderHook, waitFor } from "@testing-library/react";

const mockMcpCall = jest.fn();

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

describe("useCapabilityPolicy", () => {
  beforeEach(() => {
    mockMcpCall.mockReset();
  });

  it("loads the capability inventory report", async () => {
    mockMcpCall.mockResolvedValueOnce({
      ok: true,
      counts: { total: 1 },
      records: [{ id: "skill:geo-audit" }],
    });

    const { useCapabilityPolicy } = await import("@/lib/browse/useCapabilityPolicy");
    const { result } = renderHook(() => useCapabilityPolicy());

    await act(async () => {
      await result.current.refreshReport();
    });

    expect(mockMcpCall).toHaveBeenCalledWith("capability-inventory-report", {});
    expect(result.current.report?.counts.total).toBe(1);
    expect(result.current.error).toBeNull();
  });

  it("drafts and applies a reviewed policy change", async () => {
    const draft = {
      ok: true,
      draft_id: "draft-1",
      base_hash: "hash-1",
      entries: { "skill:geo-audit": { export_to: ["claude"] } },
      diff: "diff text",
      impact: { removed_from: { "skill:geo-audit": ["codex"] } },
    };
    mockMcpCall.mockResolvedValueOnce(draft);
    mockMcpCall.mockResolvedValueOnce({ ok: true, applied_capabilities: ["skill:geo-audit"] });

    const { useCapabilityPolicy } = await import("@/lib/browse/useCapabilityPolicy");
    const { result } = renderHook(() => useCapabilityPolicy());

    await act(async () => {
      await result.current.draftPolicy({
        action: "keep_only_in_client",
        capabilityIds: ["skill:geo-audit"],
        params: { target_client: "claude" },
      });
    });
    await act(async () => {
      await result.current.applyDraft();
    });

    expect(mockMcpCall).toHaveBeenNthCalledWith(1, "capability-policy-draft", {
      action: "keep_only_in_client",
      capability_ids: ["skill:geo-audit"],
      params: { target_client: "claude" },
    });
    expect(mockMcpCall).toHaveBeenNthCalledWith(2, "capability-policy-apply", {
      draft,
    });
    await waitFor(() => expect(result.current.applyResult?.ok).toBe(true));
  });
});
```

- [ ] **Step 2: Run hook tests and confirm failure**

Run:

```bash
/auto-test-dashboard tests/dashboard/browse/useCapabilityPolicy.test.tsx
```

Expected: fail because `apps/dashboard/lib/browse/useCapabilityPolicy.ts` does not exist.

- [ ] **Step 3: Add capability policy types**

Modify `apps/dashboard/lib/browse/types.ts` and add:

```ts
export interface CapabilityRecommendedAction {
  id: string;
  label: string;
  params: Record<string, unknown>;
}

export interface CapabilityReportRecord {
  id: string;
  type: string;
  owner_kind: string;
  management: string;
  scope: string;
  primary_surface: string;
  preferred_client: string;
  export_to: string[];
  classification_status: string;
  source_paths: string[];
  current_exposure: string[];
  drift: string[];
  metadata?: Record<string, string>;
  recommended_action?: CapabilityRecommendedAction;
}

export interface CapabilityInventoryReport {
  ok: boolean;
  counts: {
    total: number;
    by_type?: Record<string, number>;
    by_owner?: Record<string, number>;
    by_management?: Record<string, number>;
    by_status?: Record<string, number>;
    by_drift?: Record<string, number>;
    gemini_exposed?: number;
    opencode_exposed?: number;
  };
  duplicate_clusters?: Array<{
    id: string;
    type: string;
    owner_kind: string;
    current_exposure: string[];
  }>;
  records?: CapabilityReportRecord[];
  error?: string;
}

export interface CapabilityPolicyDraftRequest {
  action: string;
  capabilityIds: string[];
  params: Record<string, unknown>;
}

export interface CapabilityPolicyDraft {
  ok: boolean;
  draft_id?: string;
  base_hash?: string;
  action?: string;
  capability_ids?: string[];
  entries?: Record<string, Record<string, unknown>>;
  diff?: string;
  impact?: {
    removed_from?: Record<string, string[]>;
    added_to?: Record<string, string[]>;
    gemini_delta?: number;
    opencode_delta?: number;
  };
  error?: string;
}

export interface CapabilityPolicyApplyResult {
  ok: boolean;
  policy_hash?: string;
  applied_capabilities?: string[];
  error?: string;
}
```

- [ ] **Step 4: Implement dashboard hook**

Create `apps/dashboard/lib/browse/useCapabilityPolicy.ts`:

```ts
"use client";

import { useCallback, useState } from "react";
import { mcpCall } from "@/lib/mcp/client";
import type {
  CapabilityInventoryReport,
  CapabilityPolicyApplyResult,
  CapabilityPolicyDraft,
  CapabilityPolicyDraftRequest,
} from "./types";

export function useCapabilityPolicy() {
  const [report, setReport] = useState<CapabilityInventoryReport | null>(null);
  const [draft, setDraft] = useState<CapabilityPolicyDraft | null>(null);
  const [applyResult, setApplyResult] = useState<CapabilityPolicyApplyResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await mcpCall<CapabilityInventoryReport>("capability-inventory-report", {});
      if (next.ok === false) throw new Error(next.error || "Capability report failed");
      setReport(next);
      return next;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Capability report failed";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const draftPolicy = useCallback(async (request: CapabilityPolicyDraftRequest) => {
    setLoading(true);
    setError(null);
    setApplyResult(null);
    try {
      const next = await mcpCall<CapabilityPolicyDraft>("capability-policy-draft", {
        action: request.action,
        capability_ids: request.capabilityIds,
        params: request.params,
      });
      if (next.ok === false) throw new Error(next.error || "Capability policy draft failed");
      setDraft(next);
      return next;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Capability policy draft failed";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const applyDraft = useCallback(async () => {
    if (!draft) throw new Error("No capability policy draft to apply");
    setLoading(true);
    setError(null);
    try {
      const next = await mcpCall<CapabilityPolicyApplyResult>("capability-policy-apply", { draft });
      if (next.ok === false) throw new Error(next.error || "Capability policy apply failed");
      setApplyResult(next);
      return next;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Capability policy apply failed";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [draft]);

  const clearDraft = useCallback(() => {
    setDraft(null);
    setApplyResult(null);
    setError(null);
  }, []);

  return {
    report,
    draft,
    applyResult,
    loading,
    error,
    refreshReport,
    draftPolicy,
    applyDraft,
    clearDraft,
  };
}
```

- [ ] **Step 5: Run hook tests and commit**

Run:

```bash
/auto-test-dashboard tests/dashboard/browse/useCapabilityPolicy.test.tsx
```

Expected: all tests pass.

Commit:

```bash
git add apps/dashboard/lib/browse/types.ts apps/dashboard/lib/browse/useCapabilityPolicy.ts tests/dashboard/browse/useCapabilityPolicy.test.tsx
git commit -m "feat: add dashboard capability policy hook"
```

## Task 5: Browse Owner, Drift, And Client Filters

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts`
- Modify: `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`
- Test: `tests/dashboard/browse/useBrowseState.test.tsx`

- [ ] **Step 1: Add failing filter tests**

Append to `tests/dashboard/browse/useBrowseState.test.tsx`:

```tsx
  it("builds and applies owner, drift, and capability client filters", async () => {
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
              capabilityId: "skill:geo-audit",
              ownerKind: "external",
              currentExposure: "claude,codex",
              drift: "duplicate,unclassified_export",
            },
          },
          {
            id: "mcp-tool:dashboard-cache-clear",
            title: "Dashboard Cache Clear",
            description: "Technical MCP tool",
            hub: "dev",
            type: "mcp-tool",
            metadata: {
              capabilityId: "mcp-tool:dashboard-cache-clear",
              ownerKind: "augur",
              currentExposure: "mcp,browse,gemini",
              drift: "duplicate",
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
      expect(result.current.ownerItems).toEqual([
        { id: "augur", label: "Augur" },
        { id: "external", label: "External" },
      ]);
      expect(result.current.driftItems).toEqual([
        { id: "duplicate", label: "Duplicate" },
        { id: "unclassified_export", label: "Unclassified Export" },
      ]);
      expect(result.current.capabilityClientItems).toEqual([
        { id: "browse", label: "Browse" },
        { id: "claude", label: "Claude" },
        { id: "codex", label: "Codex" },
        { id: "gemini", label: "Gemini" },
        { id: "mcp", label: "Mcp" },
      ]);
    });

    act(() => {
      result.current.setOwnerFilter("external");
    });
    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual(["skill:geo-audit"]);
    });

    act(() => {
      result.current.setOwnerFilter(null);
      result.current.setCapabilityClientFilter("gemini");
    });
    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual(["mcp-tool:dashboard-cache-clear"]);
    });
  });
```

- [ ] **Step 2: Run state tests and confirm failure**

Run:

```bash
/auto-test-dashboard tests/dashboard/browse/useBrowseState.test.tsx
```

Expected: fail because `ownerItems`, `driftItems`, and `capabilityClientItems` are not exposed.

- [ ] **Step 3: Extend Browse state**

Modify `apps/dashboard/app/(views)/browse/useBrowseState.ts`:

Add state fields to `BrowseState`:

```ts
  ownerFilter: string | null;
  setOwnerFilter: (owner: string | null) => void;
  ownerItems: { id: string; label: string }[];
  driftFilter: string | null;
  setDriftFilter: (drift: string | null) => void;
  driftItems: { id: string; label: string }[];
  capabilityClientFilter: string | null;
  setCapabilityClientFilter: (client: string | null) => void;
  capabilityClientItems: { id: string; label: string }[];
```

Add state variables next to current capability policy filters:

```ts
  const [ownerFilter, setOwnerFilter] = useState<string | null>(null);
  const [driftFilter, setDriftFilter] = useState<string | null>(null);
  const [capabilityClientFilter, setCapabilityClientFilter] = useState<string | null>(null);
```

Add helper:

```ts
function splitCapabilityList(value: string | undefined): string[] {
  return value ? value.split(",").map((item) => item.trim()).filter(Boolean) : [];
}
```

Add computed items:

```ts
  const ownerItems = useMemo(() => {
    const values = new Set<string>();
    for (const item of items) {
      const owner = item.metadata?.ownerKind;
      if (owner) values.add(owner);
    }
    return [...values].sort().map((id) => ({ id, label: formatMetadataFilterLabel(id) }));
  }, [items]);

  const driftItems = useMemo(() => {
    const values = new Set<string>();
    for (const item of items) {
      for (const drift of splitCapabilityList(item.metadata?.drift)) values.add(drift);
    }
    return [...values].sort().map((id) => ({ id, label: formatMetadataFilterLabel(id) }));
  }, [items]);

  const capabilityClientItems = useMemo(() => {
    const values = new Set<string>();
    for (const item of items) {
      for (const client of splitCapabilityList(item.metadata?.currentExposure)) values.add(client);
    }
    return [...values].sort().map((id) => ({ id, label: formatMetadataFilterLabel(id) }));
  }, [items]);
```

Extend filtering:

```ts
    if (ownerFilter) {
      result = result.filter((item) => item.metadata?.ownerKind === ownerFilter);
    }
    if (driftFilter) {
      result = result.filter((item) => splitCapabilityList(item.metadata?.drift).includes(driftFilter));
    }
    if (capabilityClientFilter) {
      result = result.filter((item) =>
        splitCapabilityList(item.metadata?.currentExposure).includes(capabilityClientFilter),
      );
    }
```

Include the three filters in the `useMemo` dependency list and returned object. Reset them in `changeView` alongside exposure and surface filters.

- [ ] **Step 4: Render toolbar filters**

Modify `apps/dashboard/app/(views)/browse/BrowseToolbar.tsx`:

Add props for owner, drift, and capability client filters. Add filter controls after Exposure/Surface:

```tsx
    ...(ownerItems.length > 0 ? [{
      id: "capability-owner",
      node: (
        <FilterSelect
          label="Owner"
          value={ownerFilter}
          onChange={onOwnerFilterChange}
          options={ownerItems}
          showWhenSingle
        />
      ),
    }] : []),
    ...(driftItems.length > 0 ? [{
      id: "drift",
      node: (
        <FilterSelect
          label="Drift"
          value={driftFilter}
          onChange={onDriftFilterChange}
          options={driftItems}
          showWhenSingle
        />
      ),
    }] : []),
    ...(capabilityClientItems.length > 0 ? [{
      id: "capability-client",
      node: (
        <FilterSelect
          label="Capability Client"
          value={capabilityClientFilter}
          onChange={onCapabilityClientFilterChange}
          options={capabilityClientItems}
          showWhenSingle
        />
      ),
    }] : []),
```

Add active chips for the three filters so they can be cleared.

- [ ] **Step 5: Wire page props**

Modify `apps/dashboard/app/(views)/browse/page.tsx` where `BrowseToolbar` is rendered. Pass:

```tsx
ownerFilter={state.ownerFilter}
onOwnerFilterChange={state.setOwnerFilter}
ownerItems={state.ownerItems}
driftFilter={state.driftFilter}
onDriftFilterChange={state.setDriftFilter}
driftItems={state.driftItems}
capabilityClientFilter={state.capabilityClientFilter}
onCapabilityClientFilterChange={state.setCapabilityClientFilter}
capabilityClientItems={state.capabilityClientItems}
```

- [ ] **Step 6: Run dashboard state tests and commit**

Run:

```bash
/auto-test-dashboard tests/dashboard/browse/useBrowseState.test.tsx
```

Expected: all tests pass.

Commit:

```bash
git add 'apps/dashboard/app/(views)/browse/useBrowseState.ts' 'apps/dashboard/app/(views)/browse/BrowseToolbar.tsx' 'apps/dashboard/app/(views)/browse/page.tsx' tests/dashboard/browse/useBrowseState.test.tsx
git commit -m "feat: add browse capability filters"
```

## Task 6: Reviewed Apply Panel

**Files:**
- Create: `apps/dashboard/app/(views)/browse/CapabilityPolicyPanel.tsx`
- Modify: `apps/dashboard/components/shared/SkillBrowseCard.tsx`
- Modify: `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`
- Modify: `apps/dashboard/app/(views)/browse/page.tsx`
- Test: `tests/dashboard/browse/CapabilityPolicyPanel.test.tsx`

- [ ] **Step 1: Write failing panel tests**

Create `tests/dashboard/browse/CapabilityPolicyPanel.test.tsx`:

```tsx
/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const draftPolicy = jest.fn();
const applyDraft = jest.fn();
const clearDraft = jest.fn();

jest.mock("@/lib/browse/useCapabilityPolicy", () => ({
  useCapabilityPolicy: () => ({
    draft: {
      ok: true,
      diff: "--- before\n+++ after\n+skill:geo-audit",
      impact: {
        removed_from: { "skill:geo-audit": ["codex"] },
        gemini_delta: 0,
        opencode_delta: 0,
      },
    },
    applyResult: null,
    loading: false,
    error: null,
    draftPolicy,
    applyDraft,
    clearDraft,
  }),
}));

describe("CapabilityPolicyPanel", () => {
  beforeEach(() => {
    draftPolicy.mockReset();
    applyDraft.mockReset();
    clearDraft.mockReset();
  });

  it("drafts and applies keep only in Claude for a selected capability", async () => {
    const { CapabilityPolicyPanel } = await import("@/app/(views)/browse/CapabilityPolicyPanel");

    render(
      <CapabilityPolicyPanel
        item={{
          id: "skill:geo-audit",
          title: "Geo Audit",
          description: "Geo skill",
          hub: "ai",
          primaryAction: { label: "View", type: "navigate", target: "/browse/geo-audit" },
          metadata: {
            capabilityId: "skill:geo-audit",
            ownerKind: "external",
            currentExposure: "claude,codex",
            recommendedAction: "keep_only_in_client",
          },
        }}
        onClose={() => undefined}
        onApplied={() => undefined}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Keep only in Claude" }));

    await waitFor(() => {
      expect(draftPolicy).toHaveBeenCalledWith({
        action: "keep_only_in_client",
        capabilityIds: ["skill:geo-audit"],
        params: { target_client: "claude" },
      });
    });

    expect(screen.getByText("Removed from codex")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Apply policy change" }));
    expect(applyDraft).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run panel tests and confirm failure**

Run:

```bash
/auto-test-dashboard tests/dashboard/browse/CapabilityPolicyPanel.test.tsx
```

Expected: fail because `CapabilityPolicyPanel` does not exist.

- [ ] **Step 3: Implement panel component**

Create `apps/dashboard/app/(views)/browse/CapabilityPolicyPanel.tsx`:

```tsx
"use client";

import { X } from "lucide-react";
import type { BrowseItem } from "@/lib/browse/types";
import { useCapabilityPolicy } from "@/lib/browse/useCapabilityPolicy";

interface CapabilityPolicyPanelProps {
  item: BrowseItem;
  onClose: () => void;
  onApplied: () => void;
}

function split(value: string | undefined): string[] {
  return value ? value.split(",").map((item) => item.trim()).filter(Boolean) : [];
}

function impactLines(impact: Record<string, any> | undefined): string[] {
  const lines: string[] = [];
  const removed = impact?.removed_from ?? {};
  for (const [capabilityId, clients] of Object.entries(removed)) {
    const clientList = Array.isArray(clients) ? clients.join(", ") : String(clients);
    lines.push(`Removed from ${clientList}`);
  }
  if (typeof impact?.gemini_delta === "number" && impact.gemini_delta !== 0) {
    lines.push(`Gemini count change: ${impact.gemini_delta}`);
  }
  if (typeof impact?.opencode_delta === "number" && impact.opencode_delta !== 0) {
    lines.push(`OpenCode count change: ${impact.opencode_delta}`);
  }
  return lines;
}

export function CapabilityPolicyPanel({
  item,
  onClose,
  onApplied,
}: CapabilityPolicyPanelProps) {
  const capabilityId = item.metadata?.capabilityId;
  const ownerKind = item.metadata?.ownerKind ?? "unknown";
  const currentExposure = split(item.metadata?.currentExposure);
  const { draft, applyResult, loading, error, draftPolicy, applyDraft, clearDraft } = useCapabilityPolicy();
  const lines = impactLines(draft?.impact);

  const runDraft = async (action: string, params: Record<string, unknown>) => {
    if (!capabilityId) return;
    await draftPolicy({ action, capabilityIds: [capabilityId], params });
  };

  const apply = async () => {
    await applyDraft();
    onApplied();
  };

  return (
    <aside className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-4 shadow-sm" aria-label="Capability policy panel">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">{item.title}</h2>
          <p className="text-xs text-[var(--text-muted)]">{capabilityId}</p>
        </div>
        <button
          type="button"
          aria-label="Close capability policy panel"
          onClick={() => {
            clearDraft();
            onClose();
          }}
          className="rounded-md p-1 text-[var(--text-muted)] hover:bg-[var(--bg-hover)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <dl className="mt-3 grid gap-2 text-xs">
        <div><dt className="text-[var(--text-muted)]">Owner</dt><dd>{ownerKind}</dd></div>
        <div><dt className="text-[var(--text-muted)]">Current exposure</dt><dd>{currentExposure.join(", ") || "none"}</dd></div>
      </dl>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!capabilityId || loading}
          onClick={() => runDraft("keep_only_in_client", { target_client: "claude" })}
          className="rounded-lg border border-[var(--border-color)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--bg-hover)] disabled:opacity-50"
        >
          Keep only in Claude
        </button>
        <button
          type="button"
          disabled={!capabilityId || loading || ownerKind !== "augur"}
          onClick={() => runDraft("move_to_cli_only", {})}
          className="rounded-lg border border-[var(--border-color)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--bg-hover)] disabled:opacity-50"
        >
          Move to CLI only
        </button>
      </div>

      {error && <p className="mt-3 text-xs text-[var(--accent-danger)]">{error}</p>}

      {draft?.diff && (
        <section className="mt-4 space-y-3">
          <div>
            <h3 className="text-xs font-semibold text-[var(--text-primary)]">Impact</h3>
            {lines.length > 0 ? (
              <ul className="mt-1 list-disc pl-5 text-xs text-[var(--text-secondary)]">
                {lines.map((line) => <li key={line}>{line}</li>)}
              </ul>
            ) : (
              <p className="mt-1 text-xs text-[var(--text-muted)]">No exposure changes detected.</p>
            )}
          </div>
          <pre className="max-h-56 overflow-auto rounded-lg bg-[var(--bg-secondary)] p-3 text-[11px] text-[var(--text-secondary)]">
            {draft.diff}
          </pre>
          <button
            type="button"
            disabled={loading}
            onClick={apply}
            className="rounded-lg bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
          >
            Apply policy change
          </button>
        </section>
      )}

      {applyResult?.ok && (
        <p className="mt-3 text-xs text-[var(--accent-success)]">Policy change applied.</p>
      )}
    </aside>
  );
}
```

- [ ] **Step 4: Wire selectable capability items**

Modify `apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx`:

Add prop:

```ts
onSelectCapability: (item: BrowseItem) => void;
```

For non-skill `BrowseCard`, pass:

```tsx
onSelect={item.metadata?.capabilityId ? () => onSelectCapability(item) : undefined}
```

Modify `apps/dashboard/components/shared/SkillBrowseCard.tsx`:

Add prop:

```ts
onManageCapability?: () => void;
```

Update the component signature:

```ts
export function SkillBrowseCard({
  item,
  onRunMcp,
  onSelect,
  onManageCapability,
  availableClients: _availableClients,
}: SkillBrowseCardProps) {
```

Render the policy button in the footer before the overflow menu:

```tsx
{item.metadata?.capabilityId && onManageCapability ? (
  <button
    type="button"
    onClick={(event) => {
      event.stopPropagation();
      onManageCapability();
    }}
    className="min-h-[36px] cursor-pointer rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition-colors duration-200 hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
  >
    Policy
  </button>
) : null}
```

In `BrowseContentGrid`, pass:

```tsx
<SkillBrowseCard
  item={item}
  onRunMcp={onRunMcp}
  onSelect={() => onSelectSkill(item.id)}
  onManageCapability={item.metadata?.capabilityId ? () => onSelectCapability(item) : undefined}
/>
```

- [ ] **Step 5: Host panel in Browse page**

Modify `apps/dashboard/app/(views)/browse/page.tsx`:

Import:

```ts
import { CapabilityPolicyPanel } from "./CapabilityPolicyPanel";
import type { BrowseItem } from "@/lib/browse/types";
```

Add state inside `BrowsePageInner`:

```ts
const [selectedCapability, setSelectedCapability] = useState<BrowseItem | null>(null);
```

Pass `onSelectCapability={setSelectedCapability}` to `BrowseContentGrid`.

Render panel above or beside the grid:

```tsx
{selectedCapability ? (
  <CapabilityPolicyPanel
    item={selectedCapability}
    onClose={() => setSelectedCapability(null)}
    onApplied={() => {
      setSelectedCapability(null);
      state.refetch();
    }}
  />
) : null}
```

- [ ] **Step 6: Run panel tests and commit**

Run:

```bash
/auto-test-dashboard tests/dashboard/browse/CapabilityPolicyPanel.test.tsx
```

Expected: all tests pass.

Commit:

```bash
git add 'apps/dashboard/app/(views)/browse/CapabilityPolicyPanel.tsx' apps/dashboard/components/shared/SkillBrowseCard.tsx 'apps/dashboard/app/(views)/browse/BrowseContentGrid.tsx' 'apps/dashboard/app/(views)/browse/page.tsx' tests/dashboard/browse/CapabilityPolicyPanel.test.tsx
git commit -m "feat: add capability policy review panel"
```

## Task 7: End-To-End Verification And First Policy Report Smoke

**Files:**
- No required source edits unless verification exposes a defect.
- Verify: Python tests, dashboard tests, MCP smoke, browser load.

- [ ] **Step 1: Run backend capability tests**

Run:

```bash
/auto-test-pytest tests/lib/test_capability_exposure_policy.py tests/lib/test_capability_inventory_discovery.py tests/lib/test_capability_reconciliation.py tests/lib/test_capability_policy_editor.py tests/mcp/test_capability_policy_tools.py
```

Expected: all tests pass.

- [ ] **Step 2: Run dashboard Browse tests**

Run:

```bash
/auto-test-dashboard tests/dashboard/browse/useBrowseState.test.tsx tests/dashboard/browse/useCapabilityPolicy.test.tsx tests/dashboard/browse/CapabilityPolicyPanel.test.tsx
```

Expected: all tests pass.

- [ ] **Step 3: Run live inventory report smoke**

Run:

```bash
uv run python - <<'PY'
from src.lib.capabilities.discovery import discover_capabilities
from src.lib.capabilities.exposure_policy import resolve_capability_records
from src.lib.capabilities.reconciliation import build_capability_report

records = resolve_capability_records(discover_capabilities())
report = build_capability_report(records)
print("total", report["counts"]["total"])
print("by_status", report["counts"].get("by_status", {}))
print("gemini_exposed", report["counts"].get("gemini_exposed", 0))
print("opencode_exposed", report["counts"].get("opencode_exposed", 0))
print("duplicates", report["counts"].get("by_drift", {}).get("duplicate", 0))
PY
```

Expected: command exits 0 and prints non-negative counts for total, Gemini, OpenCode, and duplicates.

- [ ] **Step 4: Rebuild and verify dashboard through approved workflow**

Run:

```bash
/dev-build
```

Expected: dashboard build completes and the dev server is healthy.

- [ ] **Step 5: Verify Browse in a browser**

Open `/browse` in a screenshot-capable browser or Playwright. Verify:

- page loads interactively;
- no client-side error boundary;
- Owner, Exposure, Surface, Drift, and Capability Client filters appear when inventory metadata exists;
- clicking a capability item opens the reviewed-apply panel;
- drafting a policy change shows a diff and impact summary;
- closing the panel clears draft state.

- [ ] **Step 6: Commit any verification fixes**

If verification requires source fixes, return to the task that introduced the failing behavior, make a focused patch there, rerun that task's verification command, and commit with that task's file list. If no source edits are needed, do not create an empty commit.

## Task 8: First Cleanup Batch Preparation

**Files:**
- Modify: `config/system/capability_exposure.yaml`
- Verify: report smoke and client export checks

- [ ] **Step 1: Generate a reviewed draft for one external duplicate skill**

Use Browse or MCP to draft a Claude-only policy for a geo/location external duplicate. The MCP shape is:

```json
{
  "action": "keep_only_in_client",
  "capability_ids": ["skill:geo-audit"],
  "params": { "target_client": "claude" }
}
```

Expected: draft shows Codex/Gemini/OpenCode removal only if those clients are in current exposure. No external source folder deletion is proposed.

- [ ] **Step 2: Generate a reviewed draft for one Augur technical MCP tool**

Use Browse or MCP to draft CLI-only policy for one Augur generated MCP tool:

```json
{
  "action": "move_to_cli_only",
  "capability_ids": ["mcp-tool:act-on-attention-item"],
  "params": {}
}
```

Expected: draft sets `primary_surface: cli`, `preferred_client: shell`, and `export_to: [agents-md, browse]`.

- [ ] **Step 3: Apply only after user approval**

Do not apply the cleanup batch until the user approves the specific draft diff. After approval, apply through Browse or MCP.

- [ ] **Step 4: Verify policy file and report**

Run:

```bash
/auto-test-pytest tests/lib/test_capability_policy_editor.py tests/lib/test_capability_reconciliation.py
```

Expected: all tests pass.

Run the live inventory smoke from Task 7 Step 3 again. Expected: target records move from unclassified to approved and relevant Gemini/OpenCode counts do not increase.

- [ ] **Step 5: Commit the first approved policy batch**

Commit only after approval and verification:

```bash
git add config/system/capability_exposure.yaml
git commit -m "chore: classify initial capability exposure policy"
```

## Execution Notes

- Do not push without explicit user approval.
- Do not physically uninstall or delete external/global skill folders in this plan.
- Use MCP for dashboard policy writes; do not add direct `fs` or shell execution to dashboard code.
- For dashboard verification, HTTP 200 is insufficient. Use browser verification for `/browse`.
- Keep each task commit focused. If a task exposes unrelated dirty files, leave them out of the commit.

## Execution Options

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.
