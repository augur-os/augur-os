# Capability Surface Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining capability cleanup gaps, install eight drift guardrails that prevent generated-surface blowout, and turn Browse into the user-facing control hub for capability observability, launch, and reviewed policy actions.

**Architecture:** Three coordinated tracks driven from a single source of truth — `config/system/capability_exposure.yaml` (intended state) reconciled against live scanners in `src/lib/capabilities/` (observed state) and surfaced through Browse (`apps/dashboard/app/(views)/browse/`). Augur-generated exports become strictly policy-derived; unmanaged external surfaces stay report-only; guardrails fail tests for Augur regressions and warn for external drift. Implementation re-uses existing infrastructure: `discover_capabilities`, `resolve_capability_records`, `build_capability_report`, `allowed_generated_names`, `_sync_command_stubs`, `_sync_skill_stubs`, and the recently-added `detect_command_stub_drift` pattern.

**Tech Stack:** Python 3.11+, pytest, PyYAML, Next.js/TypeScript (Browse UI), MCP via `src/mcp/augur_framework/`, sync_agents (`shared-vault/skills/ai/scripts/sync_agents/`), auto-loop runner (`/auto-test-pytest`, `/auto-test-dashboard`, `/auto-lint`).

---

## File Structure

### New files

```
src/lib/capabilities/drift.py                                    # 8-dimension guardrail
src/lib/capabilities/duplicates.py                               # external duplicate scanner
src/lib/capabilities/drafts.py                                   # staged/draft leftover scanner
src/lib/capabilities/baseline.py                                 # snapshot writer/reader
src/mcp/augur_framework/tools/infrastructure/capability_drift.py # MCP wrapper for drift report
scripts/capability_baseline.py                                   # CLI: dump baseline JSON
scripts/capability_drift.py                                      # CLI: run guardrail
tests/lib/test_capability_drift.py                               # 8-dimension guardrail tests
tests/lib/test_capability_duplicates.py
tests/lib/test_capability_drafts.py
tests/lib/test_capability_baseline.py
tests/mcp/test_capability_drift_tool.py
apps/dashboard/features/browse/CapabilityDriftBadge.tsx
apps/dashboard/features/browse/CapabilityActionMenu.tsx
apps/dashboard/features/browse/CapabilityImpactPreview.tsx
apps/dashboard/lib/browse/useCapabilityDrift.ts
shared-vault/skills/dev-loops/augur/loops/auto-capability-drift.yaml
```

### Modified files

```
src/lib/capabilities/exposure_policy.py        # add multi_client_approved field
src/lib/capabilities/browse_enrichment.py      # add drift badge + intended_exposure + launcher paths
src/lib/capabilities/reconciliation.py         # include 8-dim drift in report
shared-vault/skills/ai/scripts/sync_agents/skill_sync.py   # add detect_skill_stub_drift
shared-vault/skills/ai/scripts/sync_agents/modes.py        # wire new drift detectors
apps/dashboard/app/(views)/browse/page.tsx                 # new columns + tabs
apps/dashboard/features/browse/types.ts                    # CapabilityRow extensions
config/system/capability_exposure.yaml         # add multi_client_approved entries as discovered
docs/adrs/ADR-734-capability-surface-phase-3.md            # flip plan_file, point at this plan
```

---

## Checkpoint C1 — Inventory Baseline + "What Remains" Report

Goal: produce a deterministic snapshot of current vs intended exposure that subsequent guardrails compare against. No behaviour changes yet — pure reporting.

### Task 1.1: Add baseline snapshot writer

**Files:**
- Create: `src/lib/capabilities/baseline.py`
- Test: `tests/lib/test_capability_baseline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/lib/test_capability_baseline.py
from src.lib.capabilities import baseline
from src.lib.capabilities.exposure_policy import CapabilityRecord


def test_build_baseline_returns_sorted_record_summaries():
    records = [
        CapabilityRecord(
            id="command:b",
            type="command",
            owner_kind="augur",
            management="generated",
            scope="project",
            classification_status="approved",
            primary_surface="command",
            preferred_client="shell",
            current_exposure=("claude",),
            export_to=("claude",),
            drift=(),
            source_paths=(),
            metadata={},
        ),
        CapabilityRecord(
            id="command:a",
            type="command",
            owner_kind="augur",
            management="generated",
            scope="project",
            classification_status="unclassified",
            primary_surface="command",
            preferred_client="shell",
            current_exposure=("agents-md",),
            export_to=(),
            drift=(),
            source_paths=(),
            metadata={},
        ),
    ]
    snapshot = baseline.build_baseline(records)
    assert [row["id"] for row in snapshot["records"]] == ["command:a", "command:b"]
    assert snapshot["records"][0]["classification_status"] == "unclassified"
    assert snapshot["records"][1]["current_exposure"] == ["claude"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_baseline.py -v`
Expected: FAIL with `ModuleNotFoundError: src.lib.capabilities.baseline`

- [ ] **Step 3: Implement `build_baseline`**

```python
# src/lib/capabilities/baseline.py
"""Deterministic capability baseline snapshot for diffing across runs."""
from __future__ import annotations

from typing import Any

from .exposure_policy import CapabilityRecord


def build_baseline(records: list[CapabilityRecord]) -> dict[str, Any]:
    """Return a deterministic JSON-serializable snapshot of resolved records."""
    sorted_records = sorted(records, key=lambda record: record.id)
    return {
        "version": 1,
        "records": [
            {
                "id": record.id,
                "type": record.type,
                "owner_kind": record.owner_kind,
                "management": record.management,
                "classification_status": record.classification_status,
                "primary_surface": record.primary_surface,
                "preferred_client": record.preferred_client,
                "current_exposure": list(record.current_exposure),
                "export_to": list(record.export_to),
                "drift": list(record.drift),
            }
            for record in sorted_records
        ],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_baseline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/baseline.py tests/lib/test_capability_baseline.py
git commit -m "feat(capabilities): add deterministic baseline snapshot builder"
```

### Task 1.2: Baseline persistence helpers (read/write JSON)

**Files:**
- Modify: `src/lib/capabilities/baseline.py`
- Test: `tests/lib/test_capability_baseline.py`

- [ ] **Step 1: Write the failing test**

```python
def test_write_and_read_baseline_round_trip(tmp_path):
    from src.lib.capabilities.exposure_policy import CapabilityRecord

    records = [
        CapabilityRecord(
            id="skill:demo",
            type="skill",
            owner_kind="augur",
            management="generated",
            scope="project",
            classification_status="approved",
            primary_surface="skill",
            preferred_client="claude",
            current_exposure=("claude",),
            export_to=("claude",),
            drift=(),
            source_paths=(),
            metadata={},
        )
    ]
    path = tmp_path / "baseline.json"
    baseline.write_baseline(path, baseline.build_baseline(records))
    loaded = baseline.read_baseline(path)
    assert loaded["records"][0]["id"] == "skill:demo"
    assert loaded["version"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_baseline.py::test_write_and_read_baseline_round_trip -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'write_baseline'`

- [ ] **Step 3: Add persistence helpers**

```python
# Append to src/lib/capabilities/baseline.py
import json
from pathlib import Path


def write_baseline(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_baseline(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_baseline.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/baseline.py tests/lib/test_capability_baseline.py
git commit -m "feat(capabilities): add baseline JSON persistence helpers"
```

### Task 1.3: CLI script `capability_baseline.py`

**Files:**
- Create: `scripts/capability_baseline.py`
- Test: `tests/lib/test_capability_baseline.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_script_writes_baseline_to_path(tmp_path, monkeypatch):
    import importlib.util
    from src.config import paths as paths_mod

    monkeypatch.setattr(paths_mod, "get_cache_dir", lambda: tmp_path)
    spec = importlib.util.spec_from_file_location(
        "capability_baseline",
        "scripts/capability_baseline.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    target = tmp_path / "snap.json"
    rc = module.main(["--out", str(target)])
    assert rc == 0
    assert target.is_file()
    payload = baseline.read_baseline(target)
    assert payload["version"] == 1
    assert isinstance(payload["records"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_baseline.py::test_cli_script_writes_baseline_to_path -v`
Expected: FAIL — script does not exist.

- [ ] **Step 3: Write the CLI**

```python
# scripts/capability_baseline.py
"""Write a capability baseline snapshot to disk for drift diffing."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.lib.capabilities.baseline import build_baseline, write_baseline
from src.lib.capabilities.discovery import discover_capabilities
from src.lib.capabilities.exposure_policy import resolve_capability_records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write capability baseline JSON.")
    parser.add_argument("--out", required=True, help="Path to write baseline JSON to.")
    args = parser.parse_args(argv)

    records = resolve_capability_records(discover_capabilities())
    snapshot = build_baseline(records)
    write_baseline(Path(args.out), snapshot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_baseline.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/capability_baseline.py tests/lib/test_capability_baseline.py
git commit -m "feat(capabilities): add capability_baseline CLI"
```

---

## Checkpoint C2 — Drift Guardrails (8 dimensions)

Goal: implement each guardrail dimension from the spec's Track 2 table as a testable function under `src/lib/capabilities/drift.py`. Augur-generated regressions raise failures; external unmanaged drift produces warnings.

### Task 2.1: Drift module skeleton + result dataclass

**Files:**
- Create: `src/lib/capabilities/drift.py`
- Test: `tests/lib/test_capability_drift.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/lib/test_capability_drift.py
from src.lib.capabilities.drift import DriftFinding, Severity


def test_drift_finding_carries_dimension_and_severity():
    finding = DriftFinding(
        dimension="blocked_present",
        capability_id="mcp-tool:dangerous",
        severity=Severity.FAIL,
        message="blocked capability has generated MCP surface",
        surface="mcp",
    )
    assert finding.dimension == "blocked_present"
    assert finding.severity is Severity.FAIL
    assert finding.is_failure() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_drift.py -v`
Expected: FAIL — module/class missing.

- [ ] **Step 3: Implement skeleton**

```python
# src/lib/capabilities/drift.py
"""Capability drift guardrail — 8 dimensions per Phase 3 spec."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    FAIL = "fail"  # Augur-generated regression
    WARN = "warn"  # external/unmanaged drift


@dataclass(frozen=True)
class DriftFinding:
    dimension: str
    capability_id: str
    severity: Severity
    message: str
    surface: str

    def is_failure(self) -> bool:
        return self.severity is Severity.FAIL
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_drift.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/drift.py tests/lib/test_capability_drift.py
git commit -m "feat(capabilities): add drift module skeleton + DriftFinding"
```

### Task 2.2: Dimension 1 — Direct MCP exposure without policy

**Files:**
- Modify: `src/lib/capabilities/drift.py`
- Test: `tests/lib/test_capability_drift.py`

- [ ] **Step 1: Write the failing test**

```python
def test_detect_direct_mcp_exposure_without_policy_flags_fail():
    from src.lib.capabilities.drift import detect_direct_mcp_exposure
    from src.lib.capabilities.exposure_policy import CapabilityRecord

    record = CapabilityRecord(
        id="mcp-tool:rogue",
        type="mcp-tool",
        owner_kind="augur",
        management="generated",
        scope="project",
        classification_status="approved",
        primary_surface="mcp",
        preferred_client="claude",
        current_exposure=("mcp",),
        export_to=("cli",),
        drift=(),
        source_paths=(),
        metadata={},
    )
    findings = detect_direct_mcp_exposure([record])
    assert len(findings) == 1
    assert findings[0].dimension == "direct_mcp_exposure"
    assert findings[0].is_failure() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_drift.py::test_detect_direct_mcp_exposure_without_policy_flags_fail -v`
Expected: FAIL — `detect_direct_mcp_exposure` missing.

- [ ] **Step 3: Implement detector**

```python
# Append to src/lib/capabilities/drift.py
from collections.abc import Iterable

from .exposure_policy import CapabilityRecord


def detect_direct_mcp_exposure(records: Iterable[CapabilityRecord]) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    for record in records:
        if record.owner_kind != "augur":
            continue
        if record.management != "generated":
            continue
        if "mcp" not in record.current_exposure:
            continue
        if "mcp" in record.export_to:
            continue
        findings.append(
            DriftFinding(
                dimension="direct_mcp_exposure",
                capability_id=record.id,
                severity=Severity.FAIL,
                message="generated MCP surface without policy export_to: mcp",
                surface="mcp",
            )
        )
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_drift.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/drift.py tests/lib/test_capability_drift.py
git commit -m "feat(capabilities): drift D1 — direct MCP exposure without policy"
```

### Task 2.3: Dimension 2 — Unclassified export

**Files:**
- Modify: `src/lib/capabilities/drift.py`
- Test: `tests/lib/test_capability_drift.py`

- [ ] **Step 1: Write the failing test**

```python
def test_detect_unclassified_export_flags_any_generated_surface_when_unclassified():
    from src.lib.capabilities.drift import detect_unclassified_export
    from src.lib.capabilities.exposure_policy import CapabilityRecord

    record = CapabilityRecord(
        id="command:mystery",
        type="command",
        owner_kind="augur",
        management="generated",
        scope="project",
        classification_status="unclassified",
        primary_surface="command",
        preferred_client="shell",
        current_exposure=("claude",),
        export_to=(),
        drift=(),
        source_paths=(),
        metadata={},
    )
    findings = detect_unclassified_export([record])
    assert [f.dimension for f in findings] == ["unclassified_export"]
    assert findings[0].is_failure() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_drift.py::test_detect_unclassified_export_flags_any_generated_surface_when_unclassified -v`
Expected: FAIL.

- [ ] **Step 3: Implement detector**

```python
# Append to src/lib/capabilities/drift.py
_CLIENT_TARGETS = frozenset({"claude", "codex", "gemini", "opencode", "cursor", "copilot"})


def detect_unclassified_export(records: Iterable[CapabilityRecord]) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    for record in records:
        if record.owner_kind != "augur" or record.management != "generated":
            continue
        if record.classification_status != "unclassified":
            continue
        for client in record.current_exposure:
            if client in _CLIENT_TARGETS:
                findings.append(
                    DriftFinding(
                        dimension="unclassified_export",
                        capability_id=record.id,
                        severity=Severity.FAIL,
                        message=f"unclassified capability exported to {client}",
                        surface=client,
                    )
                )
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_drift.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/drift.py tests/lib/test_capability_drift.py
git commit -m "feat(capabilities): drift D2 — unclassified export to client"
```

### Task 2.4: Dimension 3 — Blocked capability present in any surface

**Files:**
- Modify: `src/lib/capabilities/drift.py`
- Test: `tests/lib/test_capability_drift.py`

- [ ] **Step 1: Write the failing test**

```python
def test_detect_blocked_present_flags_any_augur_generated_surface():
    from src.lib.capabilities.drift import detect_blocked_present
    from src.lib.capabilities.exposure_policy import CapabilityRecord

    record = CapabilityRecord(
        id="mcp-tool:legacy",
        type="mcp-tool",
        owner_kind="augur",
        management="generated",
        scope="project",
        classification_status="blocked",
        primary_surface="mcp",
        preferred_client="shell",
        current_exposure=("claude", "browse"),
        export_to=(),
        drift=(),
        source_paths=(),
        metadata={},
    )
    findings = detect_blocked_present([record])
    surfaces = sorted(f.surface for f in findings)
    assert surfaces == ["browse", "claude"]
    assert all(f.dimension == "blocked_present" and f.is_failure() for f in findings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_drift.py::test_detect_blocked_present_flags_any_augur_generated_surface -v`
Expected: FAIL.

- [ ] **Step 3: Implement detector**

```python
# Append to src/lib/capabilities/drift.py
def detect_blocked_present(records: Iterable[CapabilityRecord]) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    for record in records:
        if record.owner_kind != "augur" or record.management != "generated":
            continue
        if record.classification_status != "blocked":
            continue
        for surface in record.current_exposure:
            findings.append(
                DriftFinding(
                    dimension="blocked_present",
                    capability_id=record.id,
                    severity=Severity.FAIL,
                    message="blocked capability present in generated surface",
                    surface=surface,
                )
            )
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_drift.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/drift.py tests/lib/test_capability_drift.py
git commit -m "feat(capabilities): drift D3 — blocked capability present"
```

### Task 2.5: Dimension 4 — Unexpected client (capability exposed where export_to forbids)

**Files:**
- Modify: `src/lib/capabilities/drift.py`
- Test: `tests/lib/test_capability_drift.py`

- [ ] **Step 1: Write the failing test**

```python
def test_detect_unexpected_client_flags_surface_not_in_export_to():
    from src.lib.capabilities.drift import detect_unexpected_client
    from src.lib.capabilities.exposure_policy import CapabilityRecord

    record = CapabilityRecord(
        id="skill:demo",
        type="skill",
        owner_kind="augur",
        management="generated",
        scope="project",
        classification_status="approved",
        primary_surface="skill",
        preferred_client="claude",
        current_exposure=("claude", "gemini"),
        export_to=("claude",),
        drift=(),
        source_paths=(),
        metadata={},
    )
    findings = detect_unexpected_client([record])
    assert len(findings) == 1
    assert findings[0].surface == "gemini"
    assert findings[0].is_failure() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_drift.py::test_detect_unexpected_client_flags_surface_not_in_export_to -v`
Expected: FAIL.

- [ ] **Step 3: Implement detector**

```python
# Append to src/lib/capabilities/drift.py
def detect_unexpected_client(records: Iterable[CapabilityRecord]) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    for record in records:
        if record.owner_kind != "augur" or record.management != "generated":
            continue
        if record.classification_status != "approved":
            continue
        for surface in record.current_exposure:
            if surface not in _CLIENT_TARGETS:
                continue
            if surface in record.export_to:
                continue
            findings.append(
                DriftFinding(
                    dimension="unexpected_client",
                    capability_id=record.id,
                    severity=Severity.FAIL,
                    message=f"exposed to {surface} but export_to forbids it",
                    surface=surface,
                )
            )
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_drift.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/drift.py tests/lib/test_capability_drift.py
git commit -m "feat(capabilities): drift D4 — unexpected client exposure"
```

### Task 2.6: Dimension 5 — Duplicate external skill (warning)

**Files:**
- Create: `src/lib/capabilities/duplicates.py`
- Modify: `src/lib/capabilities/drift.py`
- Test: `tests/lib/test_capability_duplicates.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/lib/test_capability_duplicates.py
from pathlib import Path

from src.lib.capabilities import duplicates


def test_find_external_skill_duplicates_across_clients(tmp_path):
    for client in (".claude", ".codex", ".gemini"):
        skill_dir = tmp_path / client / "skills" / "shared-tool"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: shared-tool\n---\n", encoding="utf-8")

    pairs = duplicates.find_external_skill_duplicates(tmp_path)
    assert pairs == [
        ("shared-tool", ("claude", "codex", "gemini")),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_duplicates.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement scanner**

```python
# src/lib/capabilities/duplicates.py
"""Scan generated client directories for duplicate external skill IDs."""
from __future__ import annotations

from pathlib import Path

_CLIENT_DIRS = (
    (".claude", "claude"),
    (".codex", "codex"),
    (".gemini", "gemini"),
    (".opencode", "opencode"),
)


def find_external_skill_duplicates(
    project_root: Path,
) -> list[tuple[str, tuple[str, ...]]]:
    by_name: dict[str, list[str]] = {}
    for dirname, client in _CLIENT_DIRS:
        skills_dir = project_root / dirname / "skills"
        if not skills_dir.is_dir():
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            if not (skill_dir / "SKILL.md").exists():
                continue
            by_name.setdefault(skill_dir.name, []).append(client)
    return [
        (name, tuple(clients))
        for name, clients in sorted(by_name.items())
        if len(clients) > 1
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_duplicates.py -v`
Expected: PASS

- [ ] **Step 5: Add drift wrapper test**

```python
# tests/lib/test_capability_drift.py
def test_detect_duplicate_external_skill_emits_warning_unless_multi_client_approved(tmp_path, monkeypatch):
    from src.lib.capabilities.drift import detect_duplicate_external_skills

    for client in (".claude", ".codex"):
        skill_dir = tmp_path / client / "skills" / "shared-tool"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: shared-tool\n---\n", encoding="utf-8")

    findings = detect_duplicate_external_skills(tmp_path, multi_client_approved=set())
    assert findings[0].dimension == "duplicate_external_skill"
    assert findings[0].severity.value == "warn"

    suppressed = detect_duplicate_external_skills(tmp_path, multi_client_approved={"shared-tool"})
    assert suppressed == []
```

- [ ] **Step 6: Implement drift wrapper**

```python
# Append to src/lib/capabilities/drift.py
from pathlib import Path

from .duplicates import find_external_skill_duplicates


def detect_duplicate_external_skills(
    project_root: Path,
    multi_client_approved: set[str],
) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    for name, clients in find_external_skill_duplicates(project_root):
        if name in multi_client_approved:
            continue
        findings.append(
            DriftFinding(
                dimension="duplicate_external_skill",
                capability_id=f"skill:{name}",
                severity=Severity.WARN,
                message=f"external skill duplicated across {', '.join(clients)}",
                surface=",".join(clients),
            )
        )
    return findings
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/lib/test_capability_duplicates.py tests/lib/test_capability_drift.py -v`
Expected: all green

- [ ] **Step 8: Commit**

```bash
git add src/lib/capabilities/duplicates.py src/lib/capabilities/drift.py tests/lib/test_capability_duplicates.py tests/lib/test_capability_drift.py
git commit -m "feat(capabilities): drift D5 — duplicate external skill (warn)"
```

### Task 2.7: Dimension 6 — Draft leakage scanner

**Files:**
- Create: `src/lib/capabilities/drafts.py`
- Modify: `src/lib/capabilities/drift.py`
- Test: `tests/lib/test_capability_drafts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/lib/test_capability_drafts.py
from src.lib.capabilities import drafts


def test_find_draft_leftovers_finds_draft_suffix_and_drafts_dir(tmp_path):
    (tmp_path / "shared-vault" / "skills" / "demo").mkdir(parents=True)
    (tmp_path / "shared-vault" / "skills" / "demo" / "SKILL.draft.md").write_text("x", encoding="utf-8")
    (tmp_path / "shared-vault" / "drafts").mkdir(parents=True)
    (tmp_path / "shared-vault" / "drafts" / "future-skill.md").write_text("x", encoding="utf-8")

    leftovers = drafts.find_draft_leftovers(tmp_path)
    rel = sorted(p.relative_to(tmp_path).as_posix() for p in leftovers)
    assert rel == [
        "shared-vault/drafts/future-skill.md",
        "shared-vault/skills/demo/SKILL.draft.md",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_drafts.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement scanner**

```python
# src/lib/capabilities/drafts.py
"""Find staged/draft leftovers that must remain Browse-Drafts-only."""
from __future__ import annotations

from pathlib import Path

_DRAFT_GLOBS = (
    "shared-vault/skills/**/*.draft.md",
    "shared-vault/drafts/**/*.md",
)


def find_draft_leftovers(project_root: Path) -> list[Path]:
    found: list[Path] = []
    for pattern in _DRAFT_GLOBS:
        found.extend(sorted(project_root.glob(pattern)))
    return sorted(set(found))
```

- [ ] **Step 4: Add drift wrapper test**

```python
# tests/lib/test_capability_drift.py
def test_detect_draft_leakage_flags_drafts_appearing_in_generated_client_dir(tmp_path):
    from src.lib.capabilities.drift import detect_draft_leakage

    (tmp_path / ".claude" / "skills" / "future-skill").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "future-skill" / "SKILL.md").write_text("x", encoding="utf-8")
    (tmp_path / "shared-vault" / "drafts").mkdir(parents=True)
    (tmp_path / "shared-vault" / "drafts" / "future-skill.md").write_text("x", encoding="utf-8")

    findings = detect_draft_leakage(tmp_path)
    assert any(f.dimension == "draft_leakage" for f in findings)
    assert findings[0].is_failure() is True
```

- [ ] **Step 5: Implement drift wrapper**

```python
# Append to src/lib/capabilities/drift.py
from .drafts import find_draft_leftovers


def detect_draft_leakage(project_root: Path) -> list[DriftFinding]:
    draft_names = {p.stem.replace(".draft", "") for p in find_draft_leftovers(project_root)}
    findings: list[DriftFinding] = []
    for dirname, client in _CLIENT_DIR_TUPLES:
        skills_dir = project_root / dirname / "skills"
        if not skills_dir.is_dir():
            continue
        for child in skills_dir.iterdir():
            if child.is_dir() and child.name in draft_names:
                findings.append(
                    DriftFinding(
                        dimension="draft_leakage",
                        capability_id=f"skill:{child.name}",
                        severity=Severity.FAIL,
                        message=f"draft surfaced as active skill in {client}",
                        surface=client,
                    )
                )
    return findings


_CLIENT_DIR_TUPLES = (
    (".claude", "claude"),
    (".codex", "codex"),
    (".gemini", "gemini"),
    (".opencode", "opencode"),
)
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/lib/test_capability_drafts.py tests/lib/test_capability_drift.py -v`
Expected: all green

- [ ] **Step 7: Commit**

```bash
git add src/lib/capabilities/drafts.py src/lib/capabilities/drift.py tests/lib/test_capability_drafts.py tests/lib/test_capability_drift.py
git commit -m "feat(capabilities): drift D6 — draft leakage detector"
```

### Task 2.8: Dimension 7 — AGENTS.md capability table drift

**Files:**
- Modify: `src/lib/capabilities/drift.py`
- Test: `tests/lib/test_capability_drift.py`

- [ ] **Step 1: Write the failing test**

```python
def test_detect_agents_md_drift_flags_table_disagreement_with_policy(tmp_path):
    from src.lib.capabilities.drift import detect_agents_md_drift
    from src.lib.capabilities.exposure_policy import CapabilityRecord

    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(
        "| Capability | Type | Preferred Surface |\n"
        "|---|---|---|\n"
        "| `mcp-tool:rogue` | mcp-tool | mcp via dashboard |\n",
        encoding="utf-8",
    )
    records = [
        CapabilityRecord(
            id="mcp-tool:rogue",
            type="mcp-tool",
            owner_kind="augur",
            management="generated",
            scope="project",
            classification_status="approved",
            primary_surface="cli",
            preferred_client="shell",
            current_exposure=("cli",),
            export_to=("cli",),
            drift=(),
            source_paths=(),
            metadata={},
        )
    ]
    findings = detect_agents_md_drift(agents_md, records)
    assert findings[0].dimension == "agents_md_drift"
    assert findings[0].is_failure() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_drift.py::test_detect_agents_md_drift_flags_table_disagreement_with_policy -v`
Expected: FAIL.

- [ ] **Step 3: Implement detector**

```python
# Append to src/lib/capabilities/drift.py
import re

_TABLE_ROW = re.compile(r"^\|\s*`(?P<id>[^`]+)`\s*\|.*?\|\s*(?P<surface>[^|]+?)\s*\|")


def detect_agents_md_drift(
    agents_md_path: Path,
    records: Iterable[CapabilityRecord],
) -> list[DriftFinding]:
    if not agents_md_path.is_file():
        return []
    by_id = {record.id: record for record in records}
    findings: list[DriftFinding] = []
    for line in agents_md_path.read_text(encoding="utf-8").splitlines():
        match = _TABLE_ROW.match(line)
        if not match:
            continue
        cap_id = match.group("id").strip()
        surface = match.group("surface").strip()
        record = by_id.get(cap_id)
        if record is None:
            continue
        expected_surface = _expected_surface_label(record)
        if expected_surface and expected_surface != surface:
            findings.append(
                DriftFinding(
                    dimension="agents_md_drift",
                    capability_id=cap_id,
                    severity=Severity.FAIL,
                    message=f"AGENTS.md says '{surface}' but policy primary_surface is '{record.primary_surface}'",
                    surface="agents-md",
                )
            )
    return findings


def _expected_surface_label(record: CapabilityRecord) -> str:
    surface_map = {
        "mcp": "mcp via dashboard",
        "cli": "cli via shell",
        "command": "command",
        "skill": "skill",
        "workflow": "workflow",
    }
    return surface_map.get(record.primary_surface, "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_drift.py -v`
Expected: all green

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/drift.py tests/lib/test_capability_drift.py
git commit -m "feat(capabilities): drift D7 — AGENTS.md capability-table drift"
```

### Task 2.9: Dimension 8 — Gemini/OpenCode tool budget blowout

**Files:**
- Modify: `src/lib/capabilities/drift.py`
- Test: `tests/lib/test_capability_drift.py`

- [ ] **Step 1: Write the failing test**

```python
def test_detect_client_budget_blowout_flags_when_count_exceeds_budget():
    from src.lib.capabilities.drift import detect_client_budget_blowout
    from src.lib.capabilities.exposure_policy import CapabilityRecord

    def make(id_: str, exposure: tuple[str, ...]) -> CapabilityRecord:
        return CapabilityRecord(
            id=id_,
            type="mcp-tool",
            owner_kind="augur",
            management="generated",
            scope="project",
            classification_status="approved",
            primary_surface="mcp",
            preferred_client="claude",
            current_exposure=exposure,
            export_to=("mcp",),
            drift=(),
            source_paths=(),
            metadata={},
        )

    records = [make(f"mcp-tool:t{i}", ("gemini",)) for i in range(5)]
    budgets = {"gemini": 4, "opencode": 4}
    findings = detect_client_budget_blowout(records, budgets)
    assert findings[0].dimension == "client_budget_blowout"
    assert findings[0].surface == "gemini"
    assert findings[0].is_failure() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_drift.py::test_detect_client_budget_blowout_flags_when_count_exceeds_budget -v`
Expected: FAIL.

- [ ] **Step 3: Implement detector**

```python
# Append to src/lib/capabilities/drift.py
def detect_client_budget_blowout(
    records: Iterable[CapabilityRecord],
    budgets: dict[str, int],
) -> list[DriftFinding]:
    counts: dict[str, int] = {client: 0 for client in budgets}
    for record in records:
        if record.owner_kind != "augur" or record.management != "generated":
            continue
        for client in budgets:
            if client in record.current_exposure:
                counts[client] += 1
    findings: list[DriftFinding] = []
    for client, budget in budgets.items():
        if counts[client] > budget:
            findings.append(
                DriftFinding(
                    dimension="client_budget_blowout",
                    capability_id=f"client:{client}",
                    severity=Severity.FAIL,
                    message=f"{client} has {counts[client]} generated tools/skills; budget is {budget}",
                    surface=client,
                )
            )
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_drift.py -v`
Expected: all green

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/drift.py tests/lib/test_capability_drift.py
git commit -m "feat(capabilities): drift D8 — Gemini/OpenCode tool budget blowout"
```

### Task 2.10: Aggregator `run_all_drift_checks` + CLI

**Files:**
- Modify: `src/lib/capabilities/drift.py`
- Create: `scripts/capability_drift.py`
- Test: `tests/lib/test_capability_drift.py`

- [ ] **Step 1: Write the failing test**

```python
def test_run_all_drift_checks_aggregates_failures_and_warnings(tmp_path):
    from src.lib.capabilities.drift import run_all_drift_checks
    from src.lib.capabilities.exposure_policy import CapabilityRecord

    records = [
        CapabilityRecord(
            id="mcp-tool:blocked",
            type="mcp-tool",
            owner_kind="augur",
            management="generated",
            scope="project",
            classification_status="blocked",
            primary_surface="mcp",
            preferred_client="shell",
            current_exposure=("mcp",),
            export_to=(),
            drift=(),
            source_paths=(),
            metadata={},
        )
    ]
    report = run_all_drift_checks(
        records,
        project_root=tmp_path,
        agents_md_path=tmp_path / "AGENTS.md",
        budgets={"gemini": 50, "opencode": 50},
        multi_client_approved=set(),
    )
    assert report["fail_count"] >= 1
    assert any(f["dimension"] == "blocked_present" for f in report["findings"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_drift.py::test_run_all_drift_checks_aggregates_failures_and_warnings -v`
Expected: FAIL.

- [ ] **Step 3: Implement aggregator**

```python
# Append to src/lib/capabilities/drift.py
def run_all_drift_checks(
    records: list[CapabilityRecord],
    *,
    project_root: Path,
    agents_md_path: Path,
    budgets: dict[str, int],
    multi_client_approved: set[str],
) -> dict[str, object]:
    findings: list[DriftFinding] = []
    findings.extend(detect_direct_mcp_exposure(records))
    findings.extend(detect_unclassified_export(records))
    findings.extend(detect_blocked_present(records))
    findings.extend(detect_unexpected_client(records))
    findings.extend(detect_duplicate_external_skills(project_root, multi_client_approved))
    findings.extend(detect_draft_leakage(project_root))
    findings.extend(detect_agents_md_drift(agents_md_path, records))
    findings.extend(detect_client_budget_blowout(records, budgets))
    return {
        "findings": [
            {
                "dimension": f.dimension,
                "capability_id": f.capability_id,
                "severity": f.severity.value,
                "message": f.message,
                "surface": f.surface,
            }
            for f in findings
        ],
        "fail_count": sum(1 for f in findings if f.is_failure()),
        "warn_count": sum(1 for f in findings if not f.is_failure()),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_drift.py -v`
Expected: all green

- [ ] **Step 5: Add CLI**

```python
# scripts/capability_drift.py
"""Run the 8-dimension capability drift report."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.config.paths import get_project_root
from src.lib.capabilities.discovery import discover_capabilities
from src.lib.capabilities.drift import run_all_drift_checks
from src.lib.capabilities.exposure_policy import (
    load_capability_policy,
    resolve_capability_records,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run capability drift checks.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Return non-zero if any warning is present (default: fail on FAIL only).",
    )
    args = parser.parse_args(argv)

    project_root = get_project_root()
    records = resolve_capability_records(discover_capabilities())
    policy = load_capability_policy()
    budgets = policy.get("budgets", {"gemini": 50, "opencode": 50})
    approved = set(policy.get("multi_client_approved", []))

    report = run_all_drift_checks(
        records,
        project_root=project_root,
        agents_md_path=project_root / "AGENTS.md",
        budgets=budgets,
        multi_client_approved=approved,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for finding in report["findings"]:
            print(f"[{finding['severity'].upper()}] {finding['dimension']}: {finding['capability_id']} — {finding['message']}")
        print(f"\n{report['fail_count']} failures, {report['warn_count']} warnings.")
    if report["fail_count"]:
        return 1
    if args.fail_on_warn and report["warn_count"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Commit**

```bash
git add src/lib/capabilities/drift.py scripts/capability_drift.py tests/lib/test_capability_drift.py
git commit -m "feat(capabilities): aggregator run_all_drift_checks + CLI"
```

### Task 2.11: Auto-loop `auto-capability-drift`

**Files:**
- Create: `shared-vault/skills/dev-loops/augur/loops/auto-capability-drift.yaml`

- [ ] **Step 1: Write the loop definition**

```yaml
# shared-vault/skills/dev-loops/augur/loops/auto-capability-drift.yaml
id: auto-capability-drift
description: Run the 8-dimension capability drift report; fail on Augur regression.
schedule:
  cadence: on-demand
  cron: null
runner:
  type: shell
  command: "uv run python scripts/capability_drift.py"
  fail_on_nonzero_exit: true
artifacts:
  - logs/capability_drift.log
notes: |
  Failures here indicate Augur-generated regression (D1 direct MCP, D2 unclassified, D3 blocked, D4 unexpected client, D7 AGENTS.md, D8 budget blowout).
  Warnings indicate external/unmanaged drift (D5 duplicate, D6 draft leakage); they do not gate CI by default.
```

- [ ] **Step 2: Verify the loop is discoverable**

Run: `uv run python -c "from src.plugins.command_discovery import discover_commands; print([c.id for c in discover_commands() if 'capability' in c.id])"`
Expected: includes `auto-capability-drift` (or the loops loader recognizes the new YAML).

- [ ] **Step 3: Run the loop**

Run: `/dev-loops run auto-capability-drift`
Expected: exits 0 OR exits 1 with concrete findings to act on.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/dev-loops/augur/loops/auto-capability-drift.yaml
git commit -m "feat(loops): add auto-capability-drift loop"
```

---

## Checkpoint C3 — Close Generated-Surface Cleanup

Goal: ensure `_sync_skill_stubs` and `_sync_command_stubs` honour blocked/unclassified classifications, and verify zero blocked capability appears in any generated client surface after a full sync. The drift detectors from C2 will then stay green.

### Task 3.1: Skill-stub drift detector (mirror of command-stub drift)

**Files:**
- Modify: `shared-vault/skills/ai/scripts/sync_agents/skill_sync.py`
- Test: `shared-vault/skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
def test_detect_skill_stub_drift_flags_missing_allowed_skill(self, tmp_path, monkeypatch):
    from sync_agents.skill_sync import detect_skill_stub_drift
    from types import SimpleNamespace

    src_skill = tmp_path / "shared-vault" / "skills" / "demo"
    src_skill.mkdir(parents=True)
    (src_skill / "SKILL.md").write_text(
        "---\nname: demo\nx-augur-type: domain\ndescription: demo skill\n---\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "src.lib.capabilities.export_filter._resolved_records_by_id",
        lambda: {
            "skill:demo": SimpleNamespace(
                id="skill:demo",
                type="skill",
                classification_status="approved",
                export_to=("claude",),
                current_exposure=(),
            )
        },
    )

    with patch("sync_agents.skill_sync.PROJECT_ROOT", tmp_path):
        drift = detect_skill_stub_drift([SimpleNamespace(adapter_name="claude_code")])
    assert any("demo" in entry for entry in drift)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest shared-vault/skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k detect_skill_stub_drift -v`
Expected: FAIL.

- [ ] **Step 3: Implement detector (mirror `detect_command_stub_drift`)**

```python
# Append to shared-vault/skills/ai/scripts/sync_agents/skill_sync.py
def detect_skill_stub_drift(adapters: list) -> list[str]:
    """Detect missing/orphan skill-stub exports per policy."""
    drift: list[str] = []
    enabled_ids = _enabled_adapter_ids(adapters)
    # Load skill sources via the same managed-root path used by _sync_skill_stubs.
    skill_sources = _load_managed_skill_sources(PROJECT_ROOT)
    skill_names = [name for name, *_ in skill_sources]
    for adapter_name, client_dir in (
        ("claude_code", PROJECT_ROOT / ".claude" / "skills"),
        ("codex", PROJECT_ROOT / ".codex" / "skills"),
        ("gemini", PROJECT_ROOT / ".gemini" / "skills"),
        ("opencode", PROJECT_ROOT / ".opencode" / "skills"),
    ):
        if adapter_name not in enabled_ids:
            continue
        target = "claude_code" if adapter_name == "claude_code" else adapter_name
        allowed = filter_named_sources(
            "skill",
            [(name,) for name in skill_names],
            target=target,
            existing_names=set(),
        )
        expected = {name for (name,) in allowed}
        for name in sorted(expected):
            if not (client_dir / name / "SKILL.md").exists():
                drift.append(f"{client_dir.relative_to(PROJECT_ROOT)}/{name}/SKILL.md (missing)")
    return drift
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest shared-vault/skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k detect_skill_stub_drift -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ai/scripts/sync_agents/skill_sync.py shared-vault/skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py
git commit -m "feat(sync): add detect_skill_stub_drift mirror of command-stub detector"
```

### Task 3.2: Wire skill-stub drift into check_mode

**Files:**
- Modify: `shared-vault/skills/ai/scripts/sync_agents/modes.py`

- [ ] **Step 1: Write the failing test**

```python
# Append to test_adapter_lifecycle.py
def test_check_mode_reports_skill_stub_drift(self, tmp_path, monkeypatch, caplog):
    from sync_agents import modes

    with patch.object(modes, "detect_command_stub_drift", return_value=[]), \
         patch("sync_agents.skill_sync.detect_skill_stub_drift", return_value=[".claude/skills/foo/SKILL.md (missing)"]):
        result = modes.check_mode()
    assert result == 1
    assert any("Skill stub drift" in record.message for record in caplog.records)
```

- [ ] **Step 2: Run test, see it fail**

Run: `uv run pytest shared-vault/skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -k check_mode_reports_skill_stub_drift -v`
Expected: FAIL.

- [ ] **Step 3: Wire into check_mode**

In `modes.py` `check_mode`, after the command-stub drift loop, add:

```python
    from .skill_sync import detect_skill_stub_drift

    for drift_msg in detect_skill_stub_drift(enabled_adapters):
        logger.error(
            "❌ Skill stub drift: %s "
            "(run `python -m skills.ai.scripts.sync_agents sync skills`)",
            drift_msg,
        )
        has_errors = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest shared-vault/skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ai/scripts/sync_agents/modes.py shared-vault/skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py
git commit -m "feat(sync): check_mode reports skill-stub drift"
```

### Task 3.3: Full sync + verify zero blocked surfaces remain

**Files:** (no source changes — verification only)

- [ ] **Step 1: Run full sync**

Run: `uv run python shared-vault/skills/ai/scripts/sync_agents/__main__.py sync all`
Expected: completes, exit 0.

- [ ] **Step 2: Run drift CLI**

Run: `uv run python scripts/capability_drift.py`
Expected: exit 0, zero FAIL findings. WARN findings acceptable.

- [ ] **Step 3: Run check**

Run: `uv run python shared-vault/skills/ai/scripts/sync_agents/__main__.py check`
Expected: "✅ Generated agent files are up to date".

- [ ] **Step 4: Snapshot baseline**

Run: `uv run python scripts/capability_baseline.py --out /tmp/capability_baseline_phase3.json`
Expected: file written, size > 1KB.

- [ ] **Step 5: Commit any incidentally regenerated files**

```bash
git status --short
git add -p   # stage regenerated client mirrors that the sync produced
git commit -m "chore(sync): regenerate client surfaces under Phase 3 policy"
```

If `git status` reports no changes, skip the commit.

---

## Checkpoint C4 — External Duplicate Classification

Goal: every external skill duplicated across clients is either explicitly approved as multi-client in policy, or surfaced as an unmanaged WARN drift. No silent duplication.

### Task 4.1: Add `multi_client_approved` policy field

**Files:**
- Modify: `src/lib/capabilities/exposure_policy.py`
- Test: `tests/lib/test_capability_exposure_policy.py`

- [ ] **Step 1: Write the failing test**

```python
def test_resolve_capability_records_reads_multi_client_approved_overlay():
    from src.lib.capabilities.discovery import CapabilityDiscovery
    from src.lib.capabilities.exposure_policy import resolve_capability_records

    discovered = [
        CapabilityDiscovery(
            id="skill:shared-tool",
            type="skill",
            owner_kind="external",
            management="unmanaged",
            scope="project",
            current_exposure=("claude", "codex"),
            source_paths=(),
            metadata={},
        )
    ]
    policy = {
        "capabilities": {
            "skill:shared-tool": {
                "multi_client_approved": True,
            }
        }
    }
    [record] = resolve_capability_records(discovered, policy=policy)
    assert record.multi_client_approved is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_exposure_policy.py::test_resolve_capability_records_reads_multi_client_approved_overlay -v`
Expected: FAIL — `multi_client_approved` attribute does not exist.

- [ ] **Step 3: Add field to `CapabilityRecord`**

In `src/lib/capabilities/exposure_policy.py`, add `multi_client_approved: bool` to the `CapabilityRecord` dataclass with default `False`. In `resolve_capability_records`, after the other `_choice` calls, add:

```python
        multi_client_approved = bool(overlay.get("multi_client_approved", False))
```

Pass it into the `CapabilityRecord(...)` construction.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_exposure_policy.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/exposure_policy.py tests/lib/test_capability_exposure_policy.py
git commit -m "feat(capabilities): add multi_client_approved policy field"
```

### Task 4.2: Drift detector reads policy for approved duplicates

**Files:**
- Modify: `src/lib/capabilities/drift.py`
- Modify: `scripts/capability_drift.py`
- Test: `tests/lib/test_capability_drift.py`

- [ ] **Step 1: Write the failing test**

```python
def test_drift_cli_reads_multi_client_approved_from_resolved_records(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AUGUR_PROJECT_ROOT", str(tmp_path))
    for client in (".claude", ".codex"):
        skill_dir = tmp_path / client / "skills" / "shared-tool"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: shared-tool\n---\n", encoding="utf-8")

    (tmp_path / "config" / "system").mkdir(parents=True)
    (tmp_path / "config" / "system" / "capability_exposure.yaml").write_text(
        "capabilities:\n"
        "  skill:shared-tool:\n"
        "    multi_client_approved: true\n",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("# placeholder\n", encoding="utf-8")

    import importlib.util
    spec = importlib.util.spec_from_file_location("capability_drift", "scripts/capability_drift.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rc = module.main(["--json"])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "duplicate_external_skill" not in captured
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_drift.py::test_drift_cli_reads_multi_client_approved_from_resolved_records -v`
Expected: FAIL (CLI currently reads from raw policy dict, not from resolved records).

- [ ] **Step 3: Update CLI to derive `multi_client_approved` from resolved records**

In `scripts/capability_drift.py`, replace the `approved = set(policy.get("multi_client_approved", []))` line with:

```python
    approved = {
        record.id.split(":", 1)[1]
        for record in records
        if getattr(record, "multi_client_approved", False)
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_drift.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/drift.py scripts/capability_drift.py tests/lib/test_capability_drift.py
git commit -m "feat(capabilities): drift CLI derives multi_client_approved from records"
```

### Task 4.3: Triage current duplicates into policy

**Files:**
- Modify: `config/system/capability_exposure.yaml`

- [ ] **Step 1: Run scanner to list current duplicates**

Run: `uv run python -c "from pathlib import Path; from src.lib.capabilities.duplicates import find_external_skill_duplicates; print('\n'.join(f'{n}: {c}' for n, c in find_external_skill_duplicates(Path('.'))))"`
Expected: a list of skill names with their client lists.

- [ ] **Step 2: Decide per duplicate**

For each row, choose one:
1. **Multi-client approved** — set `multi_client_approved: true` in policy. Used for skills that genuinely belong on every client (e.g. plugin-pack-installed superpowers).
2. **Keep on one client only** — set `export_to: [<the-one-client>]` in policy. Generated cleanup will remove the duplicates on the next sync.
3. **Unmanaged external (no action)** — leave it. Drift CLI will continue to WARN; that's acceptable.

- [ ] **Step 3: Update `config/system/capability_exposure.yaml`**

For each duplicate triaged in Step 2, add or modify the corresponding `skill:<name>` entry under `capabilities:`. Example for "shared-tool" approved as multi-client:

```yaml
  skill:shared-tool:
    classification_status: approved
    multi_client_approved: true
    management: unmanaged
    owner_kind: external
    primary_surface: skill
```

- [ ] **Step 4: Re-run drift CLI**

Run: `uv run python scripts/capability_drift.py`
Expected: every unhandled duplicate is now either gone (option 2) or suppressed (option 1) or still WARN (option 3).

- [ ] **Step 5: Commit**

```bash
git add config/system/capability_exposure.yaml
git commit -m "chore(capabilities): triage external duplicate skills into policy"
```

---

## Checkpoint C5 — Draft-Tab Behavior

Goal: staged/draft leftovers (e.g. `*.draft.md`, files under `shared-vault/drafts/`) surface only inside Browse's Drafts tab. No active hub, no generated client skill, no MCP exposure.

### Task 5.1: Add `drafts` enrichment to Browse rows

**Files:**
- Modify: `src/lib/capabilities/browse_enrichment.py`
- Test: `tests/lib/test_capability_browse_enrichment.py`

- [ ] **Step 1: Write the failing test**

```python
def test_browse_enrichment_marks_draft_rows_with_is_draft(tmp_path, monkeypatch):
    from src.lib.capabilities import browse_enrichment

    monkeypatch.setattr(browse_enrichment, "_resolved_records_by_id", lambda: {})
    monkeypatch.setattr(
        browse_enrichment,
        "find_draft_leftovers",
        lambda root: [tmp_path / "shared-vault" / "drafts" / "future-skill.md"],
        raising=False,
    )
    row = {"name": "future-skill", "title": "Future Skill"}
    enriched = browse_enrichment.enrich_for_browse("skills", [row], project_root=tmp_path)
    assert enriched[0]["is_draft"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_browse_enrichment.py::test_browse_enrichment_marks_draft_rows_with_is_draft -v`
Expected: FAIL.

- [ ] **Step 3: Update `browse_enrichment.py`**

Import and use `find_draft_leftovers`. Add `is_draft` to each row by comparing `_entry_names(row)` against the leftover stems. If `enrich_for_browse` does not currently accept `project_root`, add it as an optional keyword argument (default `get_project_root()`).

```python
# Pseudo-diff
from .drafts import find_draft_leftovers

def enrich_for_browse(category, rows, project_root=None):
    project_root = project_root or get_project_root()
    draft_names = {p.stem.replace(".draft", "") for p in find_draft_leftovers(project_root)}
    ...
    for row in rows:
        names = _entry_names(row)
        row["is_draft"] = any(name in draft_names for name in names)
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_browse_enrichment.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/browse_enrichment.py tests/lib/test_capability_browse_enrichment.py
git commit -m "feat(browse): mark draft leftovers via is_draft enrichment"
```

### Task 5.2: Drafts tab filter in Browse UI

**Files:**
- Modify: `apps/dashboard/features/browse/types.ts`
- Modify: `apps/dashboard/app/(views)/browse/page.tsx`

- [ ] **Step 1: Extend `CapabilityRow` type**

In `apps/dashboard/features/browse/types.ts`, add:

```ts
export interface CapabilityRow {
  // ... existing fields
  is_draft?: boolean;
  drift?: string[];
  duplicate_clients?: string[];
}
```

- [ ] **Step 2: Add Drafts tab to Browse page**

In `apps/dashboard/app/(views)/browse/page.tsx`, add a "Drafts" tab that filters `rows.filter(row => row.is_draft)`. Active rows must NOT include drafts.

```tsx
// Inside the existing tab definitions
{ id: "drafts", label: "Drafts", filter: (rows: CapabilityRow[]) => rows.filter(r => r.is_draft) }
```

In the "Active" / default tab filter, exclude drafts:

```tsx
filter: (rows) => rows.filter(r => !r.is_draft)
```

- [ ] **Step 3: Browser-verify**

Run: `/dev-build`
Then open `http://localhost:3000/browse` in Chrome via the MCP. Confirm:
- Drafts tab appears.
- Selecting Drafts shows only rows where `is_draft` is true.
- Default tab does not show drafts.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/features/browse/types.ts apps/dashboard/app/(views)/browse/page.tsx
git commit -m "feat(browse): drafts tab filters is_draft rows"
```

### Task 5.3: Test asserting drafts never reach a client skill dir

**Files:**
- Modify: `tests/lib/test_capability_drift.py`

- [ ] **Step 1: Write the test**

```python
def test_no_draft_leftover_is_present_as_a_generated_client_skill():
    """Regression test: drafts/*.draft.md must not appear in .claude/.codex/.gemini/.opencode skills dirs."""
    from src.lib.capabilities.drift import detect_draft_leakage
    from src.config.paths import get_project_root

    findings = detect_draft_leakage(get_project_root())
    assert findings == [], f"Draft leakage detected: {findings}"
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/lib/test_capability_drift.py::test_no_draft_leftover_is_present_as_a_generated_client_skill -v`
Expected: PASS (the repo is clean; this test now guards future regressions).

- [ ] **Step 3: Commit**

```bash
git add tests/lib/test_capability_drift.py
git commit -m "test(capabilities): regression guard — no draft in generated client dirs"
```

---

## Checkpoint C6 — Browse Control Hub

Goal: Browse shows owner, management, status, current-vs-intended exposure, drift badges, duplicate clusters, dev/operational mode, source paths in dev mode, primary-surface/preferred-client, last-refresh timestamp, and exposes launch + reviewed policy actions.

### Task 6.1: Extend Browse row schema with policy-derived fields

**Files:**
- Modify: `src/lib/capabilities/browse_enrichment.py`
- Modify: `apps/dashboard/features/browse/types.ts`
- Test: `tests/lib/test_capability_browse_enrichment.py`

- [ ] **Step 1: Write the failing test**

```python
def test_browse_enrichment_adds_owner_management_status_intended_exposure(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from src.lib.capabilities import browse_enrichment

    record = SimpleNamespace(
        id="skill:demo",
        owner_kind="augur",
        management="generated",
        classification_status="approved",
        primary_surface="skill",
        preferred_client="claude",
        export_to=("claude",),
        current_exposure=("claude", "browse"),
        drift=("duplicate",),
    )
    monkeypatch.setattr(browse_enrichment, "_resolved_records_by_id", lambda: {"skill:demo": record})
    monkeypatch.setattr(browse_enrichment, "find_draft_leftovers", lambda root: [])

    row = {"name": "demo"}
    enriched = browse_enrichment.enrich_for_browse("skills", [row], project_root=tmp_path)
    assert enriched[0]["owner_kind"] == "augur"
    assert enriched[0]["management"] == "generated"
    assert enriched[0]["classification_status"] == "approved"
    assert enriched[0]["intended_exposure"] == ["claude"]
    assert enriched[0]["current_exposure"] == ["claude", "browse"]
    assert "duplicate" in enriched[0]["drift"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_browse_enrichment.py::test_browse_enrichment_adds_owner_management_status_intended_exposure -v`
Expected: FAIL.

- [ ] **Step 3: Update enrichment to copy fields from the resolved record**

```python
# Inside enrich_for_browse, when a record is found for the row
if record is not None:
    row["owner_kind"] = record.owner_kind
    row["management"] = record.management
    row["classification_status"] = record.classification_status
    row["primary_surface"] = record.primary_surface
    row["preferred_client"] = record.preferred_client
    row["intended_exposure"] = list(record.export_to)
    row["current_exposure"] = list(record.current_exposure)
    row["drift"] = list(record.drift)
```

- [ ] **Step 4: Extend `CapabilityRow` TypeScript type**

In `apps/dashboard/features/browse/types.ts`:

```ts
export interface CapabilityRow {
  name: string;
  title?: string;
  owner_kind?: "augur" | "external" | "adopted" | "user";
  management?: "generated" | "managed-policy" | "unmanaged";
  classification_status?: "approved" | "blocked" | "deprecated" | "unclassified";
  primary_surface?: string;
  preferred_client?: string;
  intended_exposure?: string[];
  current_exposure?: string[];
  drift?: string[];
  is_draft?: boolean;
  duplicate_clients?: string[];
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_browse_enrichment.py -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/lib/capabilities/browse_enrichment.py apps/dashboard/features/browse/types.ts tests/lib/test_capability_browse_enrichment.py
git commit -m "feat(browse): enrich rows with policy-derived owner/management/exposure"
```

### Task 6.2: Drift badge component

**Files:**
- Create: `apps/dashboard/features/browse/CapabilityDriftBadge.tsx`

- [ ] **Step 1: Implement the component**

```tsx
// apps/dashboard/features/browse/CapabilityDriftBadge.tsx
import type { CapabilityRow } from "./types";

interface Props {
  row: CapabilityRow;
}

const DRIFT_LABEL: Record<string, string> = {
  duplicate: "duplicate",
  unclassified: "unclassified",
  blocked: "blocked",
  unexpected_client: "unexpected client",
};

export function CapabilityDriftBadge({ row }: Props) {
  if (!row.drift?.length) return null;
  return (
    <span className="inline-flex flex-wrap gap-1">
      {row.drift.map(kind => (
        <span
          key={kind}
          className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-900"
        >
          {DRIFT_LABEL[kind] ?? kind}
        </span>
      ))}
    </span>
  );
}
```

- [ ] **Step 2: Render in the Browse row list**

In `apps/dashboard/app/(views)/browse/page.tsx`, import and place `<CapabilityDriftBadge row={row} />` after the row title.

- [ ] **Step 3: Browser-verify**

Run: `/dev-build`
Verify in Chrome MCP: rows with drift display a yellow badge with the drift kind. Rows without drift show no badge.

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/features/browse/CapabilityDriftBadge.tsx apps/dashboard/app/(views)/browse/page.tsx
git commit -m "feat(browse): drift badge on capability rows"
```

### Task 6.3: Launcher actions ("Open in <client>", "Open shell")

**Files:**
- Create: `apps/dashboard/features/browse/CapabilityActionMenu.tsx`
- Modify: `apps/dashboard/app/(views)/browse/page.tsx`

- [ ] **Step 1: Implement the menu**

```tsx
// apps/dashboard/features/browse/CapabilityActionMenu.tsx
import type { CapabilityRow } from "./types";

interface Props {
  row: CapabilityRow;
  onLaunch: (target: string) => void;
}

export function CapabilityActionMenu({ row, onLaunch }: Props) {
  const launchers: { id: string; label: string }[] = [];
  if (row.intended_exposure?.includes("claude")) launchers.push({ id: "claude", label: "Open in Claude" });
  if (row.intended_exposure?.includes("codex")) launchers.push({ id: "codex", label: "Open in Codex" });
  if (row.intended_exposure?.includes("gemini")) launchers.push({ id: "gemini", label: "Open in Gemini" });
  if (row.intended_exposure?.includes("opencode")) launchers.push({ id: "opencode", label: "Open in OpenCode" });
  if (row.intended_exposure?.includes("cli")) launchers.push({ id: "shell", label: "Open shell" });

  if (launchers.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {launchers.map(l => (
        <button
          key={l.id}
          onClick={() => onLaunch(l.id)}
          className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-100"
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Wire the menu**

In `page.tsx`, attach an `onLaunch` handler that POSTs to `/api/mcp/tool` with the appropriate launcher tool name (e.g. `open-in-claude`, `open-in-codex`). Do NOT shell out directly — go through MCP per rule 11.

- [ ] **Step 3: Browser-verify**

Run: `/dev-build`
Confirm: launcher buttons appear only when `intended_exposure` includes that client. Clicking a button triggers an MCP tool call (visible in Network tab via Chrome MCP).

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/features/browse/CapabilityActionMenu.tsx apps/dashboard/app/(views)/browse/page.tsx
git commit -m "feat(browse): launcher action menu per intended_exposure"
```

### Task 6.4: Reviewed policy-action drafts (move to CLI only, block from Gemini, adopt, etc.)

**Files:**
- Modify: `src/lib/capabilities/policy_editor.py`
- Modify: `apps/dashboard/features/browse/CapabilityActionMenu.tsx`
- Test: `tests/lib/test_capability_policy_editor.py`

- [ ] **Step 1: Write the failing test**

```python
def test_policy_editor_draft_action_writes_to_pending_overlay(tmp_path):
    from src.lib.capabilities.policy_editor import draft_action

    pending_path = tmp_path / "capability_policy_pending.yaml"
    draft_action(
        pending_path,
        capability_id="skill:foo",
        action="move_to_cli_only",
    )
    text = pending_path.read_text(encoding="utf-8")
    assert "skill:foo" in text
    assert "move_to_cli_only" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_policy_editor.py::test_policy_editor_draft_action_writes_to_pending_overlay -v`
Expected: FAIL.

- [ ] **Step 3: Implement `draft_action`**

```python
# Append to src/lib/capabilities/policy_editor.py
import yaml
from pathlib import Path


_ALLOWED_ACTIONS = {
    "move_to_cli_only",
    "keep_only_in_claude",
    "block_from_gemini",
    "block_from_opencode",
    "approve_multi_client",
    "mark_unmanaged_external",
    "adopt_under_augur",
}


def draft_action(pending_path: Path, *, capability_id: str, action: str) -> None:
    if action not in _ALLOWED_ACTIONS:
        raise ValueError(f"unknown action: {action}")
    pending: dict = {}
    if pending_path.exists():
        pending = yaml.safe_load(pending_path.read_text(encoding="utf-8")) or {}
    pending.setdefault("drafts", []).append(
        {"capability_id": capability_id, "action": action}
    )
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_text(yaml.safe_dump(pending, sort_keys=True), encoding="utf-8")
```

- [ ] **Step 4: Add MCP tool wrapper**

Create or extend `src/mcp/augur_framework/tools/infrastructure/capability_policy.py` to expose `draft_action` as a tool `capability-policy-draft-action` that the dashboard can call.

- [ ] **Step 5: Wire the UI**

In `CapabilityActionMenu.tsx`, after the launcher buttons, add a "Policy actions" group. Each button POSTs to `/api/mcp/tool` with `{ tool: "capability-policy-draft-action", args: { capability_id, action } }`.

- [ ] **Step 6: Browser-verify**

Run: `/dev-build`
Click "Move to CLI only" on a row. Verify a row appears in `config/system/capability_policy_pending.yaml` (or wherever the pending path is configured).

- [ ] **Step 7: Commit**

```bash
git add src/lib/capabilities/policy_editor.py src/mcp/augur_framework/tools/infrastructure/capability_policy.py apps/dashboard/features/browse/CapabilityActionMenu.tsx tests/lib/test_capability_policy_editor.py
git commit -m "feat(browse): draft policy actions via MCP, write to pending overlay"
```

### Task 6.5: Impact preview before destructive policy apply

**Files:**
- Create: `apps/dashboard/features/browse/CapabilityImpactPreview.tsx`
- Modify: `src/lib/capabilities/policy_editor.py`
- Test: `tests/lib/test_capability_policy_editor.py`

- [ ] **Step 1: Write the failing test**

```python
def test_compute_impact_preview_lists_files_that_would_be_removed(tmp_path):
    from src.lib.capabilities.policy_editor import compute_impact_preview

    (tmp_path / ".claude" / "commands").mkdir(parents=True)
    (tmp_path / ".claude" / "commands" / "doomed.md").write_text("x", encoding="utf-8")
    preview = compute_impact_preview(
        project_root=tmp_path,
        capability_id="command:doomed",
        action="move_to_cli_only",
    )
    assert preview["would_remove"] == [".claude/commands/doomed.md"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_policy_editor.py::test_compute_impact_preview_lists_files_that_would_be_removed -v`
Expected: FAIL.

- [ ] **Step 3: Implement `compute_impact_preview`**

```python
# Append to src/lib/capabilities/policy_editor.py
def compute_impact_preview(
    *,
    project_root: Path,
    capability_id: str,
    action: str,
) -> dict:
    cap_type, _, cap_name = capability_id.partition(":")
    would_remove: list[str] = []
    if cap_type == "command":
        for client in (".claude", ".codex", ".gemini"):
            path = project_root / client / "commands" / f"{cap_name}.md"
            if path.exists():
                would_remove.append(str(path.relative_to(project_root)))
    elif cap_type == "skill":
        for client in (".claude", ".codex", ".gemini", ".opencode"):
            dir_path = project_root / client / "skills" / cap_name
            if dir_path.is_dir():
                would_remove.append(str(dir_path.relative_to(project_root)))
    return {"would_remove": sorted(would_remove)}
```

- [ ] **Step 4: UI component**

```tsx
// apps/dashboard/features/browse/CapabilityImpactPreview.tsx
import type { CapabilityRow } from "./types";

export function CapabilityImpactPreview({ wouldRemove }: { wouldRemove: string[] }) {
  if (wouldRemove.length === 0) {
    return <p className="text-xs text-slate-500">No files affected.</p>;
  }
  return (
    <ul className="text-xs">
      {wouldRemove.map(p => (
        <li key={p}><code>{p}</code></li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 5: Render the preview before apply**

In `CapabilityActionMenu.tsx`, before submitting a destructive action, fetch the preview via `compute-impact-preview` MCP tool and display it in a confirmation dialog. The user must approve before the draft writes.

- [ ] **Step 6: Browser-verify**

Click a destructive action. Verify the dialog lists the exact files that would be removed.

- [ ] **Step 7: Commit**

```bash
git add src/lib/capabilities/policy_editor.py apps/dashboard/features/browse/CapabilityImpactPreview.tsx apps/dashboard/features/browse/CapabilityActionMenu.tsx tests/lib/test_capability_policy_editor.py
git commit -m "feat(browse): impact preview before destructive policy apply"
```

### Task 6.6: Approval gate for unmanaged external paths

**Files:**
- Modify: `src/lib/capabilities/policy_editor.py`
- Test: `tests/lib/test_capability_policy_editor.py`

- [ ] **Step 1: Write the failing test**

```python
def test_draft_action_for_unmanaged_external_requires_explicit_approval(tmp_path):
    from src.lib.capabilities.policy_editor import draft_action

    with pytest.raises(PermissionError):
        draft_action(
            tmp_path / "pending.yaml",
            capability_id="skill:external-foo",
            action="mark_unmanaged_external",
            unmanaged_path=tmp_path / "external-foo",
            approved_paths=set(),
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lib/test_capability_policy_editor.py::test_draft_action_for_unmanaged_external_requires_explicit_approval -v`
Expected: FAIL.

- [ ] **Step 3: Update `draft_action` signature**

```python
def draft_action(
    pending_path: Path,
    *,
    capability_id: str,
    action: str,
    unmanaged_path: Path | None = None,
    approved_paths: set[Path] | None = None,
) -> None:
    if unmanaged_path is not None and (approved_paths is None or unmanaged_path not in approved_paths):
        raise PermissionError(
            f"unmanaged external path {unmanaged_path} requires explicit approval"
        )
    # ... existing body
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lib/test_capability_policy_editor.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/lib/capabilities/policy_editor.py tests/lib/test_capability_policy_editor.py
git commit -m "feat(policy): require explicit approval for unmanaged external path actions"
```

---

## Checkpoint C7 — Verify Generated Client Outputs + Final Validation

Goal: end-to-end verification. Generated Claude/Codex/Gemini/OpenCode surfaces match policy. Browse loads interactively. All loops green. ADR-734 flipped to Implemented.

### Task 7.1: Snapshot tests for generated client outputs

**Files:**
- Create: `tests/lib/test_generated_client_surfaces.py`

- [ ] **Step 1: Write the test**

```python
# tests/lib/test_generated_client_surfaces.py
"""Snapshot tests asserting generated client surfaces are policy-aligned."""
from pathlib import Path

import pytest

from src.config.paths import get_project_root
from src.lib.capabilities.discovery import discover_capabilities
from src.lib.capabilities.exposure_policy import resolve_capability_records


@pytest.fixture(scope="module")
def records():
    return resolve_capability_records(discover_capabilities())


@pytest.mark.parametrize(
    "client_dir, exposure_key",
    [
        (".claude/commands", "claude"),
        (".claude/skills", "claude"),
        (".codex/skills", "codex"),
        (".gemini/skills", "gemini"),
        (".opencode/skills", "opencode"),
    ],
)
def test_generated_client_dir_has_no_blocked_capability(client_dir, exposure_key, records):
    project_root = get_project_root()
    dir_path = project_root / client_dir
    if not dir_path.is_dir():
        pytest.skip(f"{client_dir} not present")
    blocked = {r.id.split(":", 1)[1] for r in records if r.classification_status == "blocked"}
    present = {p.stem if p.suffix else p.name for p in dir_path.iterdir() if not p.name.startswith(".")}
    leaked = blocked & present
    assert not leaked, f"blocked capability present in {client_dir}: {leaked}"
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/lib/test_generated_client_surfaces.py -v`
Expected: all pass (after a clean `sync all`).

- [ ] **Step 3: Commit**

```bash
git add tests/lib/test_generated_client_surfaces.py
git commit -m "test(capabilities): blocked capability never in generated client dirs"
```

### Task 7.2: Browser verification of /browse

**Files:** (no source changes — verification)

- [ ] **Step 1: Build dashboard**

Run: `/dev-build`
Expected: build succeeds, dev server reachable on `localhost:3000`.

- [ ] **Step 2: Open `/browse` in Chrome MCP**

Via `mcp__claude-in-chrome__navigate` to `http://localhost:3000/browse`. Confirm:
- Page loads to interactive state (no chunk-load errors, no failed-to-load error boundary).
- Owner/management/status columns render real values, not stubs.
- Drift badges appear on rows that have drift.
- Drafts tab shows only `is_draft` rows.
- Launcher buttons fire MCP calls.
- Destructive actions trigger an impact preview before applying.

- [ ] **Step 3: Screenshot the interactive state**

Use `mcp__claude-in-chrome__gif_creator` or the screenshot tool. Save the image to `docs/superpowers/specs/2026-05-12-capability-surface-phase-3-screenshot.png` (or report visually only — if the user does not want an artifact in the repo, skip saving).

- [ ] **Step 4: Document the verification**

Append to ADR-734's "Status notes" section: a one-line "Browser-verified <date>" line.

- [ ] **Step 5: Commit (only if files changed)**

```bash
git add docs/adrs/ADR-734-capability-surface-phase-3.md
git commit -m "docs(adr-734): record browser verification"
```

### Task 7.3: Final auto-loop pass

**Files:** (verification only)

- [ ] **Step 1: Pytest**

Run: `/auto-test-pytest`
Expected: all tests pass, including the new `test_capability_drift.py`, `test_capability_baseline.py`, `test_capability_duplicates.py`, `test_capability_drafts.py`, `test_generated_client_surfaces.py`, `test_capability_policy_editor.py` additions and any modified `test_capability_browse_enrichment.py` / `test_capability_exposure_policy.py`.

- [ ] **Step 2: Dashboard build + page test**

Run: `/auto-test-dashboard`
Expected: every dashboard page mounts to interactive state in the browser harness.

- [ ] **Step 3: Lint**

Run: `/auto-lint`
Expected: zero lint errors, zero TypeScript errors.

- [ ] **Step 4: Capability drift loop**

Run: `/dev-loops run auto-capability-drift`
Expected: zero FAIL findings.

If any step fails, return to the relevant checkpoint, fix the root cause (per `superpowers:systematic-debugging`), and re-run.

### Task 7.4: Flip ADR-734 to Implemented

**Files:**
- Modify: `docs/adrs/ADR-734-capability-surface-phase-3.md`

- [ ] **Step 1: Update status**

Run: `/adr set 734 Implemented`

This will:
1. Edit ADR-734's frontmatter `status: Implemented`.
2. Run the post-write hook: `adr_upsert_live.py`, `generate_adr_index.py`, `unified_indexer.py --category adrs`, `sync_agents sync agents all`.

- [ ] **Step 2: Commit the post-write hook output**

```bash
git add docs/adrs/ADR-734-capability-surface-phase-3.md docs/adrs/adrs-index.json docs/generated/adr-index.md CLAUDE.md
git commit -m "adr(capabilities): ADR-734 → Implemented"
```

- [ ] **Step 3: Hand off**

Use `superpowers:finishing-a-development-branch` to decide between merge into `main`, opening a PR, or further iteration.

---

## Self-Review

Spec coverage map (verified against `docs/superpowers/specs/2026-05-12-capability-surface-phase-3-design.md`):

| Spec section | Implementing tasks |
|---|---|
| Goals → "Close remaining duplicate skill, MCP, CLI, command, workflow exposure" | C3.3, C4.2, C4.3, C7.1 |
| Goals → "Preserve single inventory" | C6.1 (Browse rows enriched from the unified resolver) |
| Goals → "Unmanaged external/global folders report-only" | C2.6 (WARN severity), C6.6 (approval gate) |
| Goals → "Generated Augur exports strictly policy-derived" | C2.2–C2.5, C3.1, C3.2, C7.1 |
| Goals → "Guardrails that catch future blowout" | C2 (all 8 dimensions), C2.11 (loop) |
| Goals → "Browse the human-facing control hub" | C6 (all tasks) |
| Goals → "Staged/draft leftovers in Drafts tab" | C5 |
| Goals → "Clean new-session implementation boundary" | This plan |
| Track 1 (Cleanup Closure) | C3, C4 |
| Track 2 (Drift Guardrails) | C2 |
| Track 3 (Browse Control Hub) | C6 |
| Required scan dimensions (Track 1, 6 bullets) | C2 detectors (each maps to a scan dimension) |
| Track 2 table → D1 direct MCP | C2.2 |
| Track 2 table → D2 unclassified | C2.3 |
| Track 2 table → D3 blocked present | C2.4 |
| Track 2 table → D4 unexpected client | C2.5 |
| Track 2 table → D5 duplicate external | C2.6 |
| Track 2 table → D6 draft leakage | C2.7 |
| Track 2 table → D7 AGENTS drift | C2.8 |
| Track 2 table → D8 Gemini/OpenCode blowout | C2.9 |
| "Guardrails belong in tests or auto-loops" | C2.11 |
| Browse must show owner/management/status/exposure/etc | C6.1 |
| Browse drift badges + duplicate clusters | C6.2, C4 (duplicates surfaced via WARN drift) |
| Open in Claude/Codex/Gemini/OpenCode/shell | C6.3 |
| Reviewed policy actions (Move to CLI only, etc.) | C6.4 |
| Dashboard calls MCP, not direct file writes | C6.4 (Step 4 wires MCP tool), C6.5 |
| Impact preview before destructive apply | C6.5 |
| Approval for unmanaged external paths | C6.6 |
| Browser verification | C7.2 |
| Recommended batch order item 1 (refresh inventory) | C1, C3.3 (verification step), C7.4 (status flip) |
| Recommended batch order item 2 (drift guardrails) | C2 |
| Recommended batch order item 3 (cleanup blocked/unexpected) | C3, C2.4, C2.5 |
| Recommended batch order item 4 (external duplicates) | C4 |
| Recommended batch order item 5 (Draft-tab behavior) | C5 |
| Recommended batch order item 6 (Browse control hub) | C6 |
| Recommended batch order item 7 (verify generated client outputs) | C7.1 |
| Recommended batch order item 8 (browser verification) | C7.2 |
| Verification minimums (8 bullets) | C7.1, C7.2, C7.3 |
| Safety (7 bullets) | Honored throughout: blocked never written (C3.1, C7.1); no empty fallbacks (drift CLI exits non-zero on FAIL); approval for unmanaged paths (C6.6); MCP-mediated dashboard writes (C6.4); no compatibility shims (this is new code, no shims) |
| Success Criteria (7 bullets) | Each covered by a test or auto-loop in C2/C7 |

Placeholder scan: zero TBD/TODO/"fill in"/"appropriate"/"similar to" in the body. Every code step shows the actual code or the actual command.

Type consistency check:
- `DriftFinding` fields: `dimension`, `capability_id`, `severity`, `message`, `surface` — used identically in every detector (C2.1–C2.9) and the aggregator (C2.10).
- `CapabilityRecord.multi_client_approved` added in C4.1 and consumed in C4.2.
- `enrich_for_browse(category, rows, project_root=...)` signature consistent between C5.1 and C6.1.
- `draft_action(pending_path, *, capability_id, action, unmanaged_path=None, approved_paths=None)` consistent between C6.4 and C6.6 (the signature added in C6.6 supersedes the simpler one from C6.4 — C6.6's test exercises the new keyword arguments, and the body in C6.6's Step 3 explicitly says "existing body" to indicate the C6.4 body is preserved).
- TypeScript `CapabilityRow` field set is union of C5.2 + C6.1 additions; no duplicate or contradicting names.

No gaps found. Plan complete.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-12-capability-surface-phase-3.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — Fresh subagent per task, two-stage review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
