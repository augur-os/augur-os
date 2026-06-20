"""
Memory Curator - Distills daily logs into curated MEMORY.md

Part of the Two-Layer Memory Architecture:
- Reads daily logs (Layer 1)
- Extracts decisions, patterns, preferences
- Updates MEMORY.md (Layer 2) with distilled insights

This module enables the "what did we decide" deterministic lookup pattern.
"""

from src.logging import get_entity_logger
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.config.paths import get_memory_dir, get_runtime_dir

logger = get_entity_logger(__name__)


@dataclass
class DistilledEntry:
    """An entry extracted from daily logs for curation."""

    entry_type: str  # decision, pattern, preference
    key: str
    value: str
    date: str
    source_file: str
    confidence: str = "medium"
    category: Optional[str] = None

    def to_memory_item(self) -> str:
        """Format as MEMORY.md entry."""
        return f"- **{self.key}**: {self.value} ({self.date})"


class MemoryCurator:
    """
    Curates daily logs into persistent MEMORY.md.

    Workflow:
    1. Scan daily logs for important entries (decisions, patterns, preferences)
    2. Deduplicate and consolidate similar entries
    3. Update MEMORY.md with new insights
    4. Optionally archive processed daily logs
    """

    def __init__(self):
        """Initialize curator."""
        self._memory_dir = get_memory_dir()
        self._daily_dir = get_runtime_dir() / "memory" / "daily"
        self._memory_file = self._memory_dir / "MEMORY.md"
        self._archive_dir = self._memory_dir / "archive"

    def curate(
        self,
        days_back: int = 7,
        archive_processed: bool = False,
    ) -> dict:
        """
        Run curation process on recent daily logs.

        Args:
            days_back: Number of days to look back
            archive_processed: Move processed logs to archive

        Returns:
            Summary of curation results
        """
        # Extract entries from daily logs
        extracted = self._extract_from_daily_logs(days_back)

        # Consolidate similar entries
        consolidated = self._consolidate_entries(extracted)

        # Update MEMORY.md
        added = self._update_memory_file(consolidated)

        # Archive if requested
        archived = 0
        if archive_processed:
            archived = self._archive_logs(days_back)

        return {
            "logs_processed": len(list(self._get_recent_logs(days_back))),
            "entries_extracted": len(extracted),
            "entries_consolidated": len(consolidated),
            "entries_added": added,
            "logs_archived": archived,
        }

    def _get_recent_logs(self, days_back: int) -> list[Path]:
        """Get daily log files from the last N days."""
        if not self._daily_dir.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days_back)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        logs = []
        for log_file in self._daily_dir.glob("*.md"):
            date_str = log_file.stem
            if date_str >= cutoff_str:
                logs.append(log_file)

        return sorted(logs)

    def _extract_from_daily_logs(self, days_back: int) -> list[DistilledEntry]:
        """Extract important entries from daily logs."""
        entries = []

        for log_file in self._get_recent_logs(days_back):
            date_str = log_file.stem
            content = log_file.read_text()
            entries.extend(self._parse_log_for_entries(content, date_str, str(log_file)))

        return entries

    def _parse_log_for_entries(self, content: str, date_str: str, file_path: str) -> list[DistilledEntry]:
        """Parse a daily log for curate-worthy entries."""
        entries = []
        current_section = None
        current_data = {}

        for line in content.split("\n"):
            # Detect section headers
            if line.startswith("## "):
                # Save previous section if it's a decision/preference
                if current_section and current_data:
                    entry = self._create_entry_from_section(current_section, current_data, date_str, file_path)
                    if entry:
                        entries.append(entry)

                # Start new section
                current_section = line[3:].strip()
                current_data = {"raw_lines": []}
            elif current_section:
                current_data["raw_lines"].append(line)

                # Extract key-value pairs
                if line.startswith("**") and "**:" in line:
                    match = re.match(r"\*\*(.+?)\*\*:\s*(.+)", line)
                    if match:
                        key = match.group(1).lower()
                        value = match.group(2).strip()
                        current_data[key] = value

                # Extract list items with context
                if line.strip().startswith("- "):
                    item = line.strip()[2:]
                    if "items" not in current_data:
                        current_data["items"] = []
                    current_data["items"].append(item)

        # Don't forget last section
        if current_section and current_data:
            entry = self._create_entry_from_section(current_section, current_data, date_str, file_path)
            if entry:
                entries.append(entry)

        return entries

    def _create_entry_from_section(
        self,
        section_header: str,
        data: dict,
        date_str: str,
        file_path: str,
    ) -> Optional[DistilledEntry]:
        """Create a DistilledEntry from parsed section data."""
        header_lower = section_header.lower()

        # Only extract decisions, preferences, and explicit patterns
        if "decision" in header_lower:
            topic = data.get("topic", "Unknown")
            decision = data.get("decision", "")
            if not decision:
                return None

            confidence = data.get("confidence", "medium").lower()
            return DistilledEntry(
                entry_type="decision",
                key=topic,
                value=decision,
                date=date_str,
                source_file=file_path,
                confidence=confidence,
                category=self._infer_category(topic, decision),
            )

        elif "preference" in header_lower:
            preference = data.get("preference", "")
            value = data.get("value", "")
            if not preference or not value:
                return None

            return DistilledEntry(
                entry_type="preference",
                key=preference,
                value=value,
                date=date_str,
                source_file=file_path,
                category=self._infer_category(preference, value),
            )

        elif "pattern" in header_lower:
            pattern = data.get("pattern", "")
            if not pattern:
                # Try to extract from raw lines
                for line in data.get("raw_lines", []):
                    if line.strip() and not line.startswith("#"):
                        pattern = line.strip()
                        break

            if not pattern:
                return None

            return DistilledEntry(
                entry_type="pattern",
                key="Observed Pattern",
                value=pattern,
                date=date_str,
                source_file=file_path,
            )

        return None

    def _infer_category(self, key: str, value: str) -> str:
        """Infer category from content."""
        combined = f"{key} {value}".lower()

        if any(w in combined for w in ["health", "medical", "medication", "vitamin", "exercise"]):
            return "Health"
        elif any(w in combined for w in ["career", "job", "interview", "resume", "work"]):
            return "Career"
        elif any(w in combined for w in ["workflow", "process", "routine", "schedule"]):
            return "Workflow"
        elif any(w in combined for w in ["communication", "response", "format", "style"]):
            return "Communication"
        elif any(w in combined for w in ["interface", "ui", "display", "theme"]):
            return "Interface"
        else:
            return "General"

    def _consolidate_entries(self, entries: list[DistilledEntry]) -> list[DistilledEntry]:
        """Consolidate similar entries, keeping most recent."""
        # Group by type and key
        grouped = defaultdict(list)
        for entry in entries:
            group_key = (entry.entry_type, entry.key.lower())
            grouped[group_key].append(entry)

        # Keep most recent from each group
        consolidated = []
        for group in grouped.values():
            # Sort by date descending, take first
            sorted_group = sorted(group, key=lambda e: e.date, reverse=True)
            consolidated.append(sorted_group[0])

        return consolidated

    def _update_memory_file(self, entries: list[DistilledEntry]) -> int:
        """Update MEMORY.md with new entries."""
        if not entries:
            return 0

        # Ensure MEMORY.md exists
        if not self._memory_file.exists():
            self._create_memory_template()

        content = self._memory_file.read_text()
        added = 0

        for entry in entries:
            # Check if entry already exists (by key)
            if f"**{entry.key}**" in content:
                logger.debug(f"Entry already exists: {entry.key}")
                continue

            # Determine section and subsection
            if entry.entry_type == "decision":
                section = "Decisions"
                subsection = entry.category or "General"
            elif entry.entry_type == "preference":
                section = "User Preferences"
                subsection = entry.category or "General"
            elif entry.entry_type == "pattern":
                section = "Learned Patterns"
                subsection = "Workflow Patterns"
            else:
                continue

            # Insert into appropriate section
            content = self._insert_entry(content, section, subsection, entry.to_memory_item())
            added += 1

        # Update curation date
        content = re.sub(
            r"\*Last curated: \d{4}-\d{2}-\d{2}\*",
            f"*Last curated: {datetime.now().strftime('%Y-%m-%d')}*",
            content,
        )

        self._memory_file.write_text(content)
        logger.info(f"Added {added} entries to MEMORY.md")
        return added

    def _insert_entry(self, content: str, section: str, subsection: str, item: str) -> str:
        """Insert an entry into the appropriate section/subsection."""
        # Find subsection
        pattern = rf"(### {re.escape(subsection)}\s*\n)"
        match = re.search(pattern, content)

        if match:
            # Insert after subsection header
            insert_pos = match.end()
            return content[:insert_pos] + item + "\n" + content[insert_pos:]

        # Subsection doesn't exist, try to add it to section
        section_pattern = rf"(## {re.escape(section)}\s*\n)"
        section_match = re.search(section_pattern, content)

        if section_match:
            insert_pos = section_match.end()
            return content[:insert_pos] + f"\n### {subsection}\n{item}\n" + content[insert_pos:]

        # Section doesn't exist either, append to end
        return content + f"\n## {section}\n\n### {subsection}\n{item}\n"

    def _create_memory_template(self) -> None:
        """Create initial MEMORY.md with template."""
        template = f"""# Augur Memory

*Last curated: {datetime.now().strftime('%Y-%m-%d')}*

## Decisions

### Health

### Career

### Workflow

### General

## Learned Patterns

### Workflow Patterns

### Tool Usage

### Time Patterns

## User Preferences

### Communication

### Interface

### Content

## Session Insights

### Recent Focus Areas

### Emerging Patterns

"""
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        self._memory_file.write_text(template)
        logger.info(f"Created MEMORY.md template at {self._memory_file}")

    def _archive_logs(self, days_back: int) -> int:
        """Move processed logs to archive directory."""
        self._archive_dir.mkdir(parents=True, exist_ok=True)
        archived = 0

        for log_file in self._get_recent_logs(days_back):
            dest = self._archive_dir / log_file.name
            log_file.rename(dest)
            archived += 1
            logger.debug(f"Archived {log_file.name}")

        return archived

    def get_curation_summary(self) -> dict:
        """Get summary of curation state."""
        summary = {
            "memory_file_exists": self._memory_file.exists(),
            "daily_logs_count": 0,
            "archived_logs_count": 0,
            "last_curated": None,
        }

        if self._daily_dir.exists():
            summary["daily_logs_count"] = len(list(self._daily_dir.glob("*.md")))

        if self._archive_dir.exists():
            summary["archived_logs_count"] = len(list(self._archive_dir.glob("*.md")))

        if self._memory_file.exists():
            content = self._memory_file.read_text()
            date_match = re.search(r"\*Last curated: (\d{4}-\d{2}-\d{2})\*", content)
            if date_match:
                summary["last_curated"] = date_match.group(1)

        return summary
