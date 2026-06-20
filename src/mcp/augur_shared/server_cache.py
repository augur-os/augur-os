"""
Server-level caching and metrics tracking.

Provides SkillCache (TTL in-memory cache) and MetricsTracker (tool usage analytics).
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("mcp")

try:
    import report_bug
except ImportError:
    report_bug = None


class SkillCache:
    """In-memory cache for parsed skill data with TTL."""

    def __init__(self, ttl: int = 300):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any):
        self._cache[key] = (value, time.time())

    def invalidate(self, pattern: str | None = None) -> None:
        """Clear cache entries matching pattern or all."""
        if pattern is None:
            self._cache.clear()
        else:
            keys_to_delete = [k for k in self._cache if pattern in k]
            for k in keys_to_delete:
                del self._cache[k]

    def stats(self) -> dict:
        return {"entries": len(self._cache), "keys": list(self._cache.keys())}


class MetricsTracker:
    """Track tool usage for analytics."""

    def __init__(self, metrics_file: Path):
        self._metrics_file = metrics_file
        self._metrics = self._load()
        self._session_start = datetime.now().isoformat()

    def _load(self) -> dict:
        if self._metrics_file.exists():
            try:
                return json.loads(self._metrics_file.read_text())
            except Exception as exc:
                logger.debug("Failed to load metrics from %s: %s", self._metrics_file, exc)
        return {"tool_calls": {}, "skill_usage": {}, "module_usage": {}, "errors": [], "sessions": 0}

    def _save(self):
        try:
            self._metrics_file.parent.mkdir(parents=True, exist_ok=True)
            self._metrics_file.write_text(json.dumps(self._metrics, indent=2))
        except Exception:
            # Swallow all exceptions (disk full, permission errors, logger failures).
            # Metrics persistence must NEVER propagate and break tool execution.
            pass

    def track_tool(self, tool_name: str, skill: str | None = None, module: str | None = None, **kwargs) -> None:
        try:
            # Tool calls
            self._metrics["tool_calls"][tool_name] = self._metrics["tool_calls"].get(tool_name, 0) + 1

            # Determine skill if not provided directly
            if not skill and "chain" in kwargs:
                skill = kwargs["chain"]

            # Skill usage
            if skill:
                self._metrics["skill_usage"][skill] = self._metrics["skill_usage"].get(skill, 0) + 1

            # Module usage
            if module:
                key = f"{skill}/{module}" if skill else module
                self._metrics["module_usage"][key] = self._metrics["module_usage"].get(key, 0) + 1

            self._save()
        except Exception:
            # Metrics tracking must never fail a tool call (e.g. disk full, logger failure).
            pass

    def track_error(self, tool: str, error: str):
        try:
            self._metrics["errors"].append(
                {"timestamp": datetime.now().isoformat(), "tool": tool, "error": error[:200]}
            )
            # Keep last 100 errors
            self._metrics["errors"] = self._metrics["errors"][-100:]
            self._save()
        except Exception:
            pass

        # Report as P0 bug if it looks like a system failure
        if report_bug:
            report_bug.report_p0_bug(
                title=f"MCP Tool Error: {tool}",
                description=f"Tool '{tool}' encountered an error: {error}",
                source="mcp",
                metadata={"tool": tool, "error_preview": error[:500]},
            )

    def increment_sessions(self):
        self._metrics["sessions"] = self._metrics["sessions"] + 1
        self._save()

    def get_stats(self, skill_cache: "SkillCache | None" = None) -> dict:
        stats = {**self._metrics, "session_start": self._session_start}
        if skill_cache is not None:
            stats["cache_stats"] = skill_cache.stats()
        return stats
