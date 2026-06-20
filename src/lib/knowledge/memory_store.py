"""
Memory Store - Layer 2 of Two-Layer Memory Architecture

Manages the curated MEMORY.md file containing persistent decisions,
patterns, and user preferences distilled from daily logs.

File: get_memory_dir()/MEMORY.md
"""

from src.logging import get_entity_logger
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.config.paths import get_memory_dir
from src.lib.brain_stack import BrainStack, resolve_active_stack

logger = get_entity_logger(__name__)


@dataclass
class MemoryEntry:
    """A single entry in MEMORY.md."""

    category: str  # decisions, patterns, preferences
    subcategory: Optional[str]  # health, career, workflow, etc.
    key: str  # Entry identifier
    value: str  # The actual content
    date: datetime
    source: Optional[str] = None
    confidence: str = "medium"
    metadata: dict = field(default_factory=dict)

    def to_markdown_item(self) -> str:
        """Format as markdown list item for MEMORY.md."""
        date_str = self.date.strftime("%Y-%m-%d")
        lines = [f"- **{self.key}**: {self.value} ({date_str})"]
        if self.source:
            lines.append(f"  - Source: {self.source}")
        if self.confidence != "medium":
            lines.append(f"  - Confidence: {self.confidence.title()}")
        return "\n".join(lines)


MEMORY_TEMPLATE = """# Augur Memory

*Last curated: {date}*

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


class MemoryStore:
    """
    Manages the curated MEMORY.md file (Layer 2 of memory architecture).

    Provides structured access to persistent memory including:
    - Decisions (with topic categories)
    - Learned patterns (workflow, tool usage, time)
    - User preferences (communication, interface, content)
    - Session insights (recent focus, emerging patterns)
    """

    def __init__(self, *, stack: BrainStack | None = None, ensure_file: bool = True):
        """Initialize memory store."""
        self._stack = stack if stack is not None else self._resolve_stack()
        self._memory_dir = self._resolve_write_memory_dir()
        self._memory_file = self._memory_dir / "MEMORY.md"
        if ensure_file:
            self._ensure_memory_file()

    def _resolve_stack(self) -> BrainStack | None:
        try:
            return resolve_active_stack()
        except Exception:  # noqa: BLE001 - legacy singleton fallback remains available
            return None

    def _resolve_write_memory_dir(self):
        if self._stack is None:
            return get_memory_dir()
        try:
            from src.lib.brain_memory_tiers import resolve_memory_write_target

            return resolve_memory_write_target(self._stack) or get_memory_dir()
        except Exception:  # noqa: BLE001 - keep existing singleton behavior on resolver failure
            return get_memory_dir()

    def _ensure_memory_file(self) -> None:
        """Create MEMORY.md with template if it doesn't exist."""
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        if not self._memory_file.exists():
            content = MEMORY_TEMPLATE.format(date=datetime.now().strftime("%Y-%m-%d"))
            self._memory_file.write_text(content)
            logger.info(f"Created MEMORY.md at {self._memory_file}")

    def get_memory_content(self) -> str:
        """Get full contents of MEMORY.md."""
        if self._stack is not None:
            try:
                from src.lib.brain_memory_tiers import render_memory_union_markdown

                union = render_memory_union_markdown(self._stack)
                if union.strip():
                    return union
            except Exception:  # noqa: BLE001 - fall back to direct file read
                pass
        if not self._memory_file.exists():
            return MEMORY_TEMPLATE.format(date=datetime.now().strftime("%Y-%m-%d"))
        return self._memory_file.read_text()

    def _get_write_memory_content(self) -> str:
        self._ensure_memory_file()
        return self._memory_file.read_text()

    def get_section(self, section_name: str) -> Optional[str]:
        """
        Extract a specific section from MEMORY.md.

        Args:
            section_name: Section header (e.g., "Decisions", "Learned Patterns")

        Returns:
            Section content or None if not found
        """
        content = self.get_memory_content()

        # Match section header and capture until next ## header
        pattern = rf"^## {re.escape(section_name)}\s*\n(.*?)(?=^## |\Z)"
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

        if match:
            return match.group(1).strip()
        return None

    def get_subsection(self, section: str, subsection: str) -> Optional[str]:
        """
        Extract a subsection (### header) from a section.

        Args:
            section: Main section (e.g., "Decisions")
            subsection: Subsection (e.g., "Health")

        Returns:
            Subsection content or None if not found
        """
        section_content = self.get_section(section)
        if not section_content:
            return None

        # Match subsection header
        pattern = rf"^### {re.escape(subsection)}\s*\n(.*?)(?=^### |\Z)"
        match = re.search(pattern, section_content, re.MULTILINE | re.DOTALL)

        if match:
            return match.group(1).strip()
        return None

    def add_decision(
        self,
        topic: str,
        decision: str,
        category: str = "General",
        source: Optional[str] = None,
        confidence: str = "medium",
    ) -> None:
        """
        Add a decision to MEMORY.md.

        Args:
            topic: Decision topic/key
            decision: The actual decision
            category: Category (Health, Career, Workflow, General)
            source: Source of decision (e.g., "doctor recommendation")
            confidence: Confidence level (low, medium, high)
        """
        entry = MemoryEntry(
            category="decisions",
            subcategory=category,
            key=topic,
            value=decision,
            date=datetime.now(),
            source=source,
            confidence=confidence,
        )
        self._add_to_subsection("Decisions", category, entry.to_markdown_item())

    def add_pattern(
        self,
        pattern_type: str,
        description: str,
        frequency: Optional[str] = None,
    ) -> None:
        """
        Add a learned pattern to MEMORY.md.

        Args:
            pattern_type: Type (Workflow Patterns, Tool Usage, Time Patterns)
            description: Pattern description
            frequency: How often pattern occurs
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        item = f"- {description} ({date_str})"
        if frequency:
            item += f"\n  - Frequency: {frequency}"
        self._add_to_subsection("Learned Patterns", pattern_type, item)

    def add_preference(
        self,
        preference_type: str,
        key: str,
        value: str,
        source: Optional[str] = None,
    ) -> None:
        """
        Add a user preference to MEMORY.md.

        Args:
            preference_type: Type (Communication, Interface, Content)
            key: Preference name
            value: Preference value
            source: How preference was discovered
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        item = f"- **{key}**: {value} ({date_str})"
        if source:
            item += f"\n  - Source: {source}"
        self._add_to_subsection("User Preferences", preference_type, item)

    def _add_to_subsection(self, section: str, subsection: str, item: str) -> None:
        """
        Add an item to a specific subsection.

        Args:
            section: Main section header
            subsection: Subsection header
            item: Markdown item to add
        """
        content = self._get_write_memory_content()

        # Find subsection location
        pattern = rf"(^### {re.escape(subsection)}\s*\n)"
        match = re.search(pattern, content, re.MULTILINE)

        if match:
            # Insert after subsection header
            insert_pos = match.end()
            new_content = content[:insert_pos] + item + "\n" + content[insert_pos:]
        else:
            # Subsection doesn't exist, add it to section
            section_pattern = rf"(^## {re.escape(section)}\s*\n)"
            section_match = re.search(section_pattern, content, re.MULTILINE)
            if section_match:
                insert_pos = section_match.end()
                new_content = content[:insert_pos] + f"\n### {subsection}\n{item}\n" + content[insert_pos:]
            else:
                logger.warning(f"Section '{section}' not found in MEMORY.md")
                return

        # Update last curated date
        new_content = re.sub(
            r"\*Last curated: \d{4}-\d{2}-\d{2}\*",
            f"*Last curated: {datetime.now().strftime('%Y-%m-%d')}*",
            new_content,
        )

        self._memory_file.write_text(new_content)
        logger.info(f"Added to {section}/{subsection}: {item[:50]}...")

    def search_decisions(self, query: str) -> list[str]:
        """
        Search decisions section for matching entries.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching decision entries
        """
        decisions = self.get_section("Decisions") or ""
        results = []

        for line in decisions.split("\n"):
            if line.strip().startswith("-") and query.lower() in line.lower():
                results.append(line.strip())

        return results

    def search_all(self, query: str) -> dict[str, list[str]]:
        """
        Search all sections of MEMORY.md.

        Args:
            query: Search query (case-insensitive)

        Returns:
            Dict mapping section names to matching entries
        """
        sections = ["Decisions", "Learned Patterns", "User Preferences"]
        results = {}

        for section in sections:
            content = self.get_section(section) or ""
            matches = []
            for line in content.split("\n"):
                if line.strip().startswith("-") and query.lower() in line.lower():
                    matches.append(line.strip())
            if matches:
                results[section] = matches

        return results

    def get_recent_decisions(self, days: int = 7) -> list[str]:
        """
        Get decisions from the last N days.

        Args:
            days: Number of days to look back

        Returns:
            List of recent decision entries
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        decisions = self.get_section("Decisions") or ""
        results = []

        # Match date pattern in entries
        date_pattern = r"\((\d{4}-\d{2}-\d{2})\)"

        for line in decisions.split("\n"):
            if line.strip().startswith("-"):
                match = re.search(date_pattern, line)
                if match and match.group(1) >= cutoff_str:
                    results.append(line.strip())

        return results

    def update_curation_date(self) -> None:
        """Update the last curated date in MEMORY.md."""
        self._ensure_memory_file()
        content = self.get_memory_content()
        new_content = re.sub(
            r"\*Last curated: \d{4}-\d{2}-\d{2}\*",
            f"*Last curated: {datetime.now().strftime('%Y-%m-%d')}*",
            content,
        )
        self._memory_file.write_text(new_content)
