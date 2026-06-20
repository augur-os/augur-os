"""
Incident normalization and aggregation for adaptive command evolution.

ADR-249 adds a structured incident layer so repeated infra/setup failures can
be tracked as stable fingerprints instead of disconnected blocker strings.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class IncidentRecord:
    """Structured incident captured from a command execution."""

    fingerprint: str
    category: str
    severity: str
    owner_path: str
    message: str
    command: str
    first_seen_at: str
    last_seen_at: str
    occurrences: int = 1
    commands: list[str] = field(default_factory=list)
    worktrees: list[str] = field(default_factory=list)
    sample_errors: list[str] = field(default_factory=list)
    auto_heal_status: str = "not_attempted"
    verify_status: str = "not_run"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_worktree(project_root: Path | None) -> str:
    if project_root is None:
        return str(Path.cwd())
    return str(project_root)


def _build_incident(
    *,
    fingerprint: str,
    category: str,
    severity: str,
    owner_path: str,
    message: str,
    command: str,
    project_root: Path | None,
    auto_heal_status: str = "not_attempted",
    verify_status: str = "not_run",
) -> IncidentRecord:
    timestamp = _now_iso()
    worktree = _normalize_worktree(project_root)
    return IncidentRecord(
        fingerprint=fingerprint,
        category=category,
        severity=severity,
        owner_path=owner_path,
        message=message,
        command=command,
        first_seen_at=timestamp,
        last_seen_at=timestamp,
        occurrences=1,
        commands=[command],
        worktrees=[worktree],
        sample_errors=[message],
        auto_heal_status=auto_heal_status,
        verify_status=verify_status,
    )


def normalize_incident(
    message: str,
    *,
    command: str,
    project_root: Path | None = None,
) -> IncidentRecord | None:
    """Map raw setup/runtime failures into stable incident fingerprints."""

    normalized = message.strip()
    if not normalized:
        return None

    lowered = normalized.lower()

    if "no available worktree ports" in lowered or "port collision" in lowered:
        return _build_incident(
            fingerprint="worktree/bootstrap/port-collision",
            category="bootstrap",
            severity="high",
            owner_path="scripts/worktree-launch.sh",
            message=normalized,
            command=command,
            project_root=project_root,
        )

    if "lock contention" in lowered or ("mcp" in lowered and "lock" in lowered):
        return _build_incident(
            fingerprint="worktree/mcp/lock-contention",
            category="mcp",
            severity="high",
            owner_path="apps/dashboard/lib/mcp/MCPBridge.ts",
            message=normalized,
            command=command,
            project_root=project_root,
        )

    if "augur_root path does not exist" in lowered or (
        "augur_root" in lowered and ("drift" in lowered or "invalid" in lowered)
    ):
        return _build_incident(
            fingerprint="worktree/root/env-drift",
            category="environment",
            severity="high",
            owner_path="wrap.sh",
            message=normalized,
            command=command,
            project_root=project_root,
        )

    if "runtime directory not available" in lowered or (
        "runtime" in lowered and ("not writable" in lowered or "missing" in lowered)
    ):
        return _build_incident(
            fingerprint="worktree/bootstrap/missing-runtime",
            category="bootstrap",
            severity="high",
            owner_path="scripts/worktree-launch.sh",
            message=normalized,
            command=command,
            project_root=project_root,
        )

    if ".venv-test" in lowered and ("not found" in lowered or "missing" in lowered):
        return _build_incident(
            fingerprint="worktree/bootstrap/missing-venv-test",
            category="bootstrap",
            severity="medium",
            owner_path="scripts/worktree-launch.sh",
            message=normalized,
            command=command,
            project_root=project_root,
        )

    if (
        "venv python not found" in lowered
        or ".venv/bin/python" in lowered
        or ".venv\\scripts\\python" in lowered
    ):
        return _build_incident(
            fingerprint="worktree/bootstrap/missing-venv",
            category="bootstrap",
            severity="high",
            owner_path="wrap.sh",
            message=normalized,
            command=command,
            project_root=project_root,
        )

    if "node_modules" in lowered or "'next' binary not found" in lowered:
        return _build_incident(
            fingerprint="worktree/bootstrap/missing-dashboard-node-modules",
            category="bootstrap",
            severity="high",
            owner_path="apps/dashboard/scripts/start-dev.sh",
            message=normalized,
            command=command,
            project_root=project_root,
        )

    if "404" in lowered and ("route" in lowered or "page" in lowered):
        return _build_incident(
            fingerprint="worktree/bootstrap/route-drift",
            category="bootstrap",
            severity="medium",
            owner_path="apps/dashboard/scripts/start-dev.sh",
            message=normalized,
            command=command,
            project_root=project_root,
        )

    return None


def _load_index(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        return {"incidents": {}, "recurringIncidents": []}
    try:
        loaded = json.loads(index_path.read_text())
        if "incidents" not in loaded:
            loaded["incidents"] = {}
        return loaded
    except json.JSONDecodeError:
        return {"incidents": {}, "recurringIncidents": []}


def _merge_unique(values: list[str], new_value: str, *, limit: int | None = None) -> list[str]:
    merged = list(values)
    if new_value and new_value not in merged:
        merged.append(new_value)
    if limit is not None:
        return merged[-limit:]
    return merged


def aggregate_incidents(
    runtime_dir: Path,
    incidents: list[IncidentRecord],
) -> Path:
    """Persist incident events and an aggregated incident index."""

    incidents_dir = runtime_dir / "command-evolution" / "incidents"
    incidents_dir.mkdir(parents=True, exist_ok=True)
    index_path = incidents_dir / "index.json"
    events_path = incidents_dir / "events.jsonl"
    index = _load_index(index_path)
    incident_index = index.setdefault("incidents", {})

    for incident in incidents:
        current = incident_index.get(incident.fingerprint)
        if current is None:
            incident_index[incident.fingerprint] = incident.to_dict()
        else:
            current["occurrences"] = int(current.get("occurrences", 0)) + incident.occurrences
            current["last_seen_at"] = incident.last_seen_at
            current["commands"] = _merge_unique(current.get("commands", []), incident.command)
            worktree = incident.worktrees[0] if incident.worktrees else ""
            current["worktrees"] = _merge_unique(current.get("worktrees", []), worktree)
            sample = incident.sample_errors[0] if incident.sample_errors else incident.message
            current["sample_errors"] = _merge_unique(
                current.get("sample_errors", []),
                sample,
                limit=5,
            )
            current["auto_heal_status"] = incident.auto_heal_status
            current["verify_status"] = incident.verify_status
            current["message"] = incident.message

        event = incident.to_dict()
        event["recorded_at"] = _now_iso()
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")

    _apply_promotions(runtime_dir.parent, incident_index)
    index["generatedAt"] = _now_iso()
    index["recurringIncidents"] = summarize_incident_values(incident_index)
    index_path.write_text(json.dumps(index, indent=2))
    return index_path


def extract_incidents(log_data: dict[str, Any]) -> list[IncidentRecord]:
    """Rehydrate incidents from saved log data when needed by callers/tests."""

    incidents: list[IncidentRecord] = []
    for item in log_data.get("incidents", []):
        incidents.append(IncidentRecord(**item))
    return incidents


def should_promote_incident(summary: dict[str, Any]) -> bool:
    """Tier-1 recurrence rule for repeated setup incidents."""

    if int(summary.get("occurrences", 0)) >= 3:
        return True
    return len(summary.get("commands", [])) >= 2 or len(summary.get("worktrees", [])) >= 2


def summarize_incidents(index_path: Path) -> list[dict[str, Any]]:
    """Return aggregated incidents sorted by recurrence for reporting."""

    index = _load_index(index_path)
    incidents = list(index.get("incidents", {}).values())
    incidents.sort(
        key=lambda item: (
            int(item.get("occurrences", 0)),
            item.get("last_seen_at", ""),
        ),
        reverse=True,
    )
    for item in incidents:
        item["should_promote"] = should_promote_incident(item)
    return incidents


def summarize_incident_values(incident_index: dict[str, Any]) -> list[dict[str, Any]]:
    incidents = list(incident_index.values())
    incidents.sort(
        key=lambda item: (
            int(item.get("occurrences", 0)),
            item.get("last_seen_at", ""),
        ),
        reverse=True,
    )
    for item in incidents:
        item["should_promote"] = should_promote_incident(item)
    return incidents


def incident_owner_sort_key(owner_path: str) -> tuple[int, str]:
    """Prefer code owners over docs when selecting a promotion target."""

    if owner_path.startswith("docs/"):
        return (1, owner_path)
    return (0, owner_path)


_TODO_MARKER_RE = re.compile(r"TODO_(?:BUG|CLEANUP|OUTDATED)")
_UNMARKABLE_SUFFIXES = {".json", ".jsonl"}
_GENERATED_CLIENT_OWNER_PREFIXES = (
    ".agent/",
    ".antigravity/",
    ".claude/",
    ".codex/",
    ".cursor/",
    ".gemini/",
    ".opencode/",
)
_GENERATED_CLIENT_OWNER_FILES = {
    "CLAUDE.md",
    "CODEX.md",
    "GEMINI.md",
}


def _comment_prefix(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        return ("// ", "")
    if suffix == ".md":
        return ("<!-- ", " -->")
    return ("# ", "")


def _build_marker(summary: dict[str, Any]) -> str:
    fingerprint = summary.get("fingerprint", "incident")
    owner_path = str(summary.get("owner_path", ""))
    category = str(summary.get("category", "bootstrap"))
    severity = str(summary.get("severity", "medium"))
    unresolved = summary.get("verify_status") == "failed" or severity == "high"

    if owner_path.startswith("docs/"):
        todo_prefix = "TODO_OUTDATED"
    elif unresolved:
        todo_prefix = "TODO_BUG(integration/high)"
    elif category in {"bootstrap", "environment", "mcp"}:
        todo_prefix = "TODO_CLEANUP"
    else:
        todo_prefix = "TODO_BUG(integration/high)"

    message = str(summary.get("message", "")).strip()
    compact_message = message.replace("\n", " ")[:120]
    return f"{todo_prefix}: [incident:{fingerprint}] Prevent repeated failure: {compact_message}"


def _owner_key(project_root: Path, owner_path: str) -> str:
    candidate = Path(owner_path)
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve().relative_to(project_root.resolve())
        except ValueError:
            return ""
    return candidate.as_posix().lstrip("./")


def _can_insert_marker(project_root: Path, owner_path: str, owner_file: Path) -> bool:
    if owner_file.suffix.lower() in _UNMARKABLE_SUFFIXES:
        return False

    owner_key = _owner_key(project_root, owner_path)
    if owner_key in _GENERATED_CLIENT_OWNER_FILES:
        return False
    return not owner_key.startswith(_GENERATED_CLIENT_OWNER_PREFIXES)


def _insert_marker(owner_file: Path, marker: str) -> None:
    content = owner_file.read_text(encoding="utf-8") if owner_file.exists() else ""
    if f"[incident:{marker.split('[incident:', 1)[1].split(']', 1)[0]}]" in content:
        return

    prefix, suffix = _comment_prefix(owner_file)
    line = f"{prefix}{marker}{suffix}\n"
    if content.startswith("#!"):
        first_line, _, rest = content.partition("\n")
        owner_file.write_text(f"{first_line}\n{line}{rest}", encoding="utf-8")
    else:
        owner_file.write_text(line + content, encoding="utf-8")


def _apply_promotions(project_root: Path, incident_index: dict[str, Any]) -> None:
    for summary in summarize_incident_values(incident_index):
        if not should_promote_incident(summary):
            continue
        if summary.get("promoted"):
            continue

        owner_path = str(summary.get("owner_path", "")).strip()
        if not owner_path:
            continue

        owner_file = (project_root / owner_path).resolve()
        if not owner_file.exists():
            continue
        if not _can_insert_marker(project_root, owner_path, owner_file):
            continue

        marker = _build_marker(summary)
        _insert_marker(owner_file, marker)
        summary["promoted"] = True
        summary["promoted_marker"] = marker
        summary["promoted_todo_path"] = str(owner_file)
