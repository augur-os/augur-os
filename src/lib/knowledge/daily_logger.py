"""
Daily Logger - Layer 1 of Two-Layer Memory Architecture

Captures raw session events (context switches, decisions, tool executions)
in daily markdown files for later distillation into MEMORY.md.

File format: {memory_dir}/daily/YYYY-MM-DD.md
"""

from src.logging import get_entity_logger
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from src.config.paths import get_memory_dir, get_runtime_dir

logger = get_entity_logger(__name__)


class EventType(Enum):
    """Types of events captured in daily logs."""

    CONTEXT_SWITCH = "context_switch"
    DECISION = "decision"
    TOOL_EXECUTION = "tool_execution"
    ERROR = "error"
    USER_PREFERENCE = "user_preference"
    PATTERN_DETECTED = "pattern_detected"


@dataclass
class MemoryEvent:
    """A single event to be logged."""

    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)
    category: Optional[str] = None
    confidence: str = "medium"  # low, medium, high

    def to_markdown(self) -> str:
        """Format event as markdown for daily log."""
        time_str = self.timestamp.strftime("%H:%M")
        lines = [f"## {time_str} - {self.event_type.value.replace('_', ' ').title()}"]

        if self.event_type == EventType.CONTEXT_SWITCH:
            lines.extend(
                [
                    f"- From: {self.data.get('from_page', 'unknown')}",
                    f"- To: {self.data.get('to_page', 'unknown')}",
                ]
            )
            if tools := self.data.get("tools_loaded"):
                lines.append(f"- Tools loaded: {tools}")
            if duration := self.data.get("duration_ms"):
                lines.append(f"- Duration: {duration}ms")

        elif self.event_type == EventType.DECISION:
            lines.extend(
                [
                    f"**Topic**: {self.data.get('topic', 'unspecified')}",
                    f"**Decision**: {self.data.get('decision', 'none')}",
                ]
            )
            if self.category:
                lines.append(f"**Category**: {self.category}")
            if reasoning := self.data.get("reasoning"):
                lines.append(f"**Reasoning**: {reasoning}")
            lines.append(f"**Confidence**: {self.confidence.title()}")

        elif self.event_type == EventType.TOOL_EXECUTION:
            lines.extend(
                [
                    f"- Tool: {self.data.get('tool_name', 'unknown')}",
                    f"- Action: {self.data.get('action', 'unknown')}",
                ]
            )
            if input_data := self.data.get("input"):
                # Truncate long inputs
                input_str = str(input_data)[:200]
                lines.append(f"- Input: {input_str}")
            lines.append(f"- Result: {self.data.get('result', 'unknown')}")

        elif self.event_type == EventType.ERROR:
            lines.extend(
                [
                    f"- Error: {self.data.get('error', 'unknown')}",
                    f"- Context: {self.data.get('context', 'unknown')}",
                ]
            )
            if recovery := self.data.get("recovery_action"):
                lines.append(f"- Recovery: {recovery}")

        elif self.event_type == EventType.USER_PREFERENCE:
            lines.extend(
                [
                    f"**Preference**: {self.data.get('preference', 'unspecified')}",
                    f"**Value**: {self.data.get('value', 'none')}",
                ]
            )
            if source := self.data.get("source"):
                lines.append(f"**Source**: {source}")

        elif self.event_type == EventType.PATTERN_DETECTED:
            lines.extend(
                [
                    f"**Pattern**: {self.data.get('pattern', 'unspecified')}",
                    f"**Frequency**: {self.data.get('frequency', 'unknown')}",
                ]
            )
            if examples := self.data.get("examples"):
                lines.append(f"**Examples**: {examples[:3]}")

        lines.append("")  # Blank line after event
        return "\n".join(lines)


class DailyLogger:
    """
    Manages daily session logs (Layer 1 of memory architecture).

    Creates and appends to daily markdown files in the configured memory
    directory's `daily/` subfolder.
    Files are automatically named by date (YYYY-MM-DD.md).
    """

    def __init__(
        self,
        retention_days: int = 14,
        *,
        memory_dir: Path | None = None,
        daily_dir: Path | None = None,
    ):
        """
        Initialize daily logger.

        Args:
            retention_days: Number of days to keep daily logs (default 14)
        """
        self.retention_days = retention_days
        self._memory_dir = memory_dir or get_memory_dir()
        self._daily_dir = daily_dir or get_runtime_dir() / "memory" / "daily"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create memory directories if they don't exist."""
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        self._daily_dir.mkdir(parents=True, exist_ok=True)

    def _get_daily_file(self, date: Optional[datetime] = None) -> Path:
        """Get path to daily log file for given date."""
        if date is None:
            date = datetime.now()
        filename = date.strftime("%Y-%m-%d.md")
        return self._daily_dir / filename

    def _ensure_daily_file(self, date: Optional[datetime] = None) -> Path:
        """Ensure daily log file exists with header."""
        filepath = self._get_daily_file(date)
        if not filepath.exists():
            if date is None:
                date = datetime.now()
            header = f"# Session Log: {date.strftime('%Y-%m-%d')}\n\n"
            filepath.write_text(header)
            logger.info(f"Created daily log: {filepath}")
        return filepath

    def log_event(self, event: MemoryEvent) -> None:
        """
        Log an event to today's daily log.

        Args:
            event: MemoryEvent to log
        """
        filepath = self._ensure_daily_file(event.timestamp)
        with open(filepath, "a") as f:
            f.write(event.to_markdown())
        logger.debug(f"Logged {event.event_type.value} to {filepath}")

    def log_context_switch(
        self,
        from_page: str,
        to_page: str,
        tools_loaded: Optional[list[str]] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Log a context/page switch event."""
        self.log_event(
            MemoryEvent(
                event_type=EventType.CONTEXT_SWITCH,
                data={
                    "from_page": from_page,
                    "to_page": to_page,
                    "tools_loaded": tools_loaded,
                    "duration_ms": duration_ms,
                },
            )
        )

    def log_decision(
        self,
        topic: str,
        decision: str,
        reasoning: Optional[str] = None,
        confidence: str = "medium",
        category: Optional[str] = None,
    ) -> None:
        """Log a decision made during the session."""
        self.log_event(
            MemoryEvent(
                event_type=EventType.DECISION,
                data={
                    "topic": topic,
                    "decision": decision,
                    "reasoning": reasoning,
                },
                category=category,
                confidence=confidence,
            )
        )

    def log_tool_execution(
        self,
        tool_name: str,
        action: str,
        input_data: Optional[Any] = None,
        result: str = "success",
    ) -> None:
        """Log a tool execution event."""
        self.log_event(
            MemoryEvent(
                event_type=EventType.TOOL_EXECUTION,
                data={
                    "tool_name": tool_name,
                    "action": action,
                    "input": input_data,
                    "result": result,
                },
            )
        )

    def log_error(
        self,
        error: str,
        context: str,
        recovery_action: Optional[str] = None,
    ) -> None:
        """Log an error event."""
        self.log_event(
            MemoryEvent(
                event_type=EventType.ERROR,
                data={
                    "error": error,
                    "context": context,
                    "recovery_action": recovery_action,
                },
            )
        )

    def log_user_preference(
        self,
        preference: str,
        value: str,
        source: Optional[str] = None,
    ) -> None:
        """Log a user preference discovered during session."""
        self.log_event(
            MemoryEvent(
                event_type=EventType.USER_PREFERENCE,
                data={
                    "preference": preference,
                    "value": value,
                    "source": source,
                },
            )
        )

    def get_today_log(self) -> Optional[str]:
        """Get contents of today's log file."""
        filepath = self._get_daily_file()
        if filepath.exists():
            return filepath.read_text()
        return None

    def get_log_for_date(self, date: datetime) -> Optional[str]:
        """Get contents of log file for specific date."""
        filepath = self._get_daily_file(date)
        if filepath.exists():
            return filepath.read_text()
        return None

    def get_recent_logs(self, days: int = 7) -> dict[str, str]:
        """
        Get logs for the last N days.

        Returns:
            Dict mapping date strings to log contents
        """
        logs = {}
        today = datetime.now()
        for i in range(days):
            date = today.replace(day=today.day - i)
            date_str = date.strftime("%Y-%m-%d")
            content = self.get_log_for_date(date)
            if content:
                logs[date_str] = content
        return logs

    def cleanup_old_logs(self) -> int:
        """
        Remove logs older than retention_days.

        Returns:
            Number of files removed
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=self.retention_days)
        removed = 0

        for filepath in self._daily_dir.glob("*.md"):
            try:
                # Parse date from filename
                date_str = filepath.stem  # YYYY-MM-DD
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    filepath.unlink()
                    removed += 1
                    logger.info(f"Removed old daily log: {filepath}")
            except (ValueError, OSError) as e:
                logger.warning(f"Error processing {filepath}: {e}")

        return removed
