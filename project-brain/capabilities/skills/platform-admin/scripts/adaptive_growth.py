"""
Adaptive Growth Script - DevOps Agent

Generates structured improvement tasks based on architectural designs and analysis
passed from the agent chain context.
"""

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Add project root to path for imports if needed
from bootstrap_paths import ensure_project_paths  # noqa: E402

PROJECT_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_runtime_dir


def _get_data_dir() -> Path:
    """Resolve the data directory.

    Raises:
        FileNotFoundError: If data directory cannot be found
    """
    env = os.environ.get("AUGUR_ROOT")
    if env:
        path = Path(env).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"AUGUR_ROOT path does not exist: {path}")
        return path

    # Monorepo structure: project root contains config/ and plugins/
    if PROJECT_ROOT.exists():
        return PROJECT_ROOT

    raise FileNotFoundError(f"Project root not found at {PROJECT_ROOT}. " f"Set AUGUR_ROOT environment variable.")


def _ensure_inbox() -> Path:
    """Ensure inbox directory exists."""
    root = _get_data_dir()
    canonical_inbox = (
        root
        / "plugins"
        / "orchestration"
        / "skills"
        / "executor"
        / "augur"
        / "data"
        / "agent-tasks"
        / "inbox"
    )
    legacy_inbox = root / "plugins" / "core" / "skills" / "executor" / "data" / "agent-tasks" / "inbox"
    generic_inbox = root / "tasks" / "inbox"

    if canonical_inbox.exists():
        return canonical_inbox
    if legacy_inbox.exists():
        return legacy_inbox
    if generic_inbox.exists():
        return generic_inbox

    canonical_inbox.mkdir(parents=True, exist_ok=True)
    return canonical_inbox


def _load_incident_summary(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    del root
    incident_index = get_runtime_dir() / "command-evolution" / "incidents" / "index.json"
    if not incident_index.exists():
        return [], []

    try:
        raw = json.loads(incident_index.read_text(encoding="utf-8"))
    except Exception:
        return [], []

    if isinstance(raw, dict):
        source = raw.get("recurringIncidents") or raw.get("incidents") or raw
    else:
        source = raw

    incidents: list[dict[str, Any]] = []
    if isinstance(source, dict):
        items = source.items()
    elif isinstance(source, list):
        items = [
            (item.get("fingerprint"), item)  # type: ignore[union-attr]
            for item in source
            if isinstance(item, dict)
        ]
    else:
        items = []

    for fingerprint, payload in items:
        if not fingerprint or not isinstance(payload, dict):
            continue
        incidents.append(
            {
                "fingerprint": str(fingerprint),
                "category": str(payload.get("category") or "other"),
                "severity": str(payload.get("severity") or "medium"),
                "occurrences": int(payload.get("occurrences") or 1),
                "owner_path": payload.get("owner_path") or payload.get("ownerPath") or "",
                "last_seen_at": payload.get("last_seen_at") or payload.get("lastSeenAt") or "",
                "promoted": bool(payload.get("promoted")),
                "promoted_todo_path": payload.get("promoted_todo_path")
                or payload.get("promotedTodoPath")
                or "",
            }
        )

    incidents.sort(key=lambda item: item["occurrences"], reverse=True)
    promoted = [
        {
            "fingerprint": item["fingerprint"],
            "owner_path": item["owner_path"],
            "promoted_todo_path": item["promoted_todo_path"],
        }
        for item in incidents
        if item["promoted"]
    ]
    return incidents[:10], promoted[:10]


def generate_tasks(params: Dict[str, Any]) -> str:
    """
    Generate markdown tasks from chain context.

    Args:
        params: Dictionary containing 'context', 'user_request', etc.

    Returns:
        JSON string with result summary.
    """
    inbox_dir = _ensure_inbox()
    created_files = []
    root = _get_data_dir()
    recurring_incidents, promoted_todos = _load_incident_summary(root)

    # Extract context from various possible keys
    context = params.get("context", {})
    if not context:
        # Try finding previous outputs
        prev_outputs = params.get("previous_outputs", {})
        if prev_outputs:
            context = prev_outputs

    # Look for architectural design or analysis in context
    # This structure depends on what architect.design returns
    # Flatten nested structure to find the design
    def find_design(obj):
        if isinstance(obj, dict):
            if "system_refactor_plan" in obj:
                return obj["system_refactor_plan"]
            for k, v in obj.items():
                res = find_design(v)
                if res:
                    return res
        return None

    design = find_design(context) or {}

    # Extract requirements/approach
    # If explicit design isn't found, use user request or generic fallback
    user_request = params.get("user_request", "Adaptive growth task")

    # Construct task content
    # In a real scenario, we'd parse the 'design' object to split into multiple tasks
    # For now, we create one consolidated task if specific subtasks aren't clear

    # Try to extract specific recommendations from text fields if possible
    # (Simple heuristic for demo purposes)
    task_content = f"""# Adaptive Growth: {user_request[:50]}...

## Context
Generated by Adaptive Growth Cycle at {datetime.now().isoformat()}

## Objective
{user_request}

## Analysis / Design
{json.dumps(design, indent=2) if design else "No specific design document found in context."}

## Recurring Incidents
{json.dumps(recurring_incidents, indent=2) if recurring_incidents else "No recurring incident index found."}

## Promoted TODOs
{json.dumps(promoted_todos, indent=2) if promoted_todos else "No promoted TODO markers found."}

## Action Items
- [ ] Review generated analysis
- [ ] Implement recommended changes
"""

    # Create the file
    task_id = f"growth-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    filename = f"{task_id}.md"
    filepath = inbox_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        # Write frontmatter
        f.write("---\n")
        f.write(f"id: {task_id}\n")
        f.write("type: feature\n")
        f.write("source: adaptive-growth\n")
        f.write(f"created: {datetime.now().isoformat()}\n")
        f.write("status: ready\n")
        f.write("---\n\n")
        f.write(task_content)

    created_files.append(str(filepath))

    return json.dumps(
        {
            "status": "success",
            "generated_tasks": created_files,
            "recurring_incidents": recurring_incidents,
            "promoted_todos": promoted_todos,
            "message": f"Generated {len(created_files)} task(s) in {inbox_dir}",
        }
    )


if __name__ == "__main__":
    # If run as script, parse specific args or read stdin if params passed that way
    # For simplicity in orchestrator, we often pass params as a JSON string argument or via stdin
    # Here we'll assume the orchestrator calls main logic.

    if any(arg in {"-h", "--help"} for arg in sys.argv[1:]):
        _out("usage: adaptive_growth.py [JSON_PARAMS | USER_REQUEST]")
        _out()
        _out("Generate structured improvement tasks from adaptive-growth context.")
        raise SystemExit(0)

    if len(sys.argv) > 1:
        # Attempt to parse first arg as JSON params
        try:
            params = json.loads(sys.argv[1])
        except json.JSONDecodeError:
            params = {"user_request": sys.argv[1]}
    else:
        # Read from stdin if available
        if not sys.stdin.isatty():
            try:
                content = sys.stdin.read()
                params = json.loads(content)
            except Exception:
                params = {}
        else:
            params = {}

    _out(generate_tasks(params))
