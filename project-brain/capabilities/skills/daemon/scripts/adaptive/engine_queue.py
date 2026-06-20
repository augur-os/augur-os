"""Post-execution queue draining for the adaptive engine.

Extracted from engine.py to keep each module under ~400 lines.
Provides QueueMixin which AdaptiveLoopEngine inherits.
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
import json
from datetime import datetime, timezone
from pathlib import Path

from src.logging import get_entity_logger


logger = get_entity_logger("adaptive_engine_queue")


class QueueMixin:
    """Mixin providing post-execution queue materialization helpers."""

    def _resolve_post_exec_queue_path(self) -> Path:
        """Resolve the configured post-execution queue path."""
        queue_path_str = self._config.get("engine", {}).get("post_exec_queue", "")
        if not queue_path_str:
            return Path()
        queue_path_value = Path(queue_path_str)
        if queue_path_value.is_absolute():
            return queue_path_value

        normalized = queue_path_str.replace("\\", "/")
        if normalized == "state" or normalized.startswith("state/"):
            relative = normalized.removeprefix("state/").removeprefix("state")
            return self._runtime_dir / relative
        return self._runtime_dir / queue_path_value.name

    def consume_post_exec_queue(self) -> list[dict]:
        """Consume and clear queued post-execution events."""
        queue_path = self._resolve_post_exec_queue_path()
        if not str(queue_path) or not queue_path.exists():
            return []

        content = queue_path.read_text(encoding="utf-8").strip()
        if not content:
            queue_path.write_text("", encoding="utf-8")
            return []

        events: list[dict] = []
        invalid_lines = 0
        for line in content.splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                invalid_lines += 1
                continue
            if isinstance(payload, dict):
                events.append(payload)
            else:
                invalid_lines += 1

        queue_path.write_text("", encoding="utf-8")
        if invalid_lines:
            logger.warning(
                "Skipped %d malformed post-execution queue entr%s from %s",
                invalid_lines,
                "y" if invalid_lines == 1 else "ies",
                queue_path,
            )
        return events

    def materialize_post_exec_events(self, events: list[dict]) -> None:
        """Write queued events into command-evolution execution logs."""
        for event in events:
            cmd = event.get("command", "unknown")
            log_dir = self._runtime_dir / "command-evolution" / cmd / "executions"
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = event.get("timestamp", datetime.now(timezone.utc).isoformat()).replace(":", "-")[:19]
            log_path = log_dir / f"{ts}.json"
            if not log_path.exists():
                log_path.write_text(
                    json.dumps(
                        {
                        "command": cmd,
                        "outcome": event.get("outcome", "success"),
                        "started_at": event.get("timestamp", ""),
                        "completed_at": event.get("timestamp", ""),
                        "duration_ms": event.get("duration_ms", 0),
                        "phases": event.get("phases", []),
                        "learnings": event.get("learnings", []),
                        "tools_called": event.get("tools_called", []),
                        "errors": event.get("errors", []),
                        "files_changed": event.get("files_changed", []),
                        "assessment": event.get("assessment", {}),
                        "metrics": {"duration_seconds": event.get("duration_ms", 0) / 1000},
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )

    def drain_post_exec_queue(self) -> int:
        """Consume and materialize post-execution events without executing loops."""
        events = self.consume_post_exec_queue()
        self.materialize_post_exec_events(events)
        return len(events)
