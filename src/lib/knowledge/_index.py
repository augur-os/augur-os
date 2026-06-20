"""Index building and staleness detection for memory search.

Incremental YAML index with checksums, daily log parsing, and MEMORY.md parsing.
"""

import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from src.logging import get_entity_logger

from ._types import MemoryEntry

logger = get_entity_logger(__name__)

# Current index schema version
INDEX_VERSION = "2.0"


class IndexMixin:
    """Mixin providing index building and staleness checking for MemorySearcher.

    Expects the host class to have:
      - self._memory_dir: Path
      - self._index_path: Path
      - self._daily_dir: Path
      - self._memory_file: Path
      - self._config: dict
    """

    # ------------------------------------------------------------------
    # File checksum and index staleness
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_file_checksum(path: Path) -> str:
        """Compute SHA256 checksum for a file.

        Args:
            path: File to checksum.

        Returns:
            String in format 'sha256:{hex_digest}'.
        """
        h = hashlib.sha256()
        try:
            h.update(path.read_bytes())
        except OSError:
            return "sha256:error"
        return f"sha256:{h.hexdigest()}"

    def _get_source_files(self) -> list[Path]:
        """Get all source files that should be indexed."""
        files: list[Path] = []
        if self._daily_dir.exists():
            files.extend(sorted(self._daily_dir.glob("*.md")))
        if self._memory_file.exists():
            files.append(self._memory_file)
        return files

    def _is_index_stale(self) -> bool:
        """Check if the YAML index is stale and needs rebuilding.

        Returns True when:
        - Index file doesn't exist
        - Any source file checksum differs from stored checksum
        - A new file exists that isn't in the checksums
        - An indexed file has been deleted
        - The index is older than auto_rebuild_hours
        """
        if not self._index_path.exists():
            return True

        try:
            index_data = yaml.safe_load(self._index_path.read_text()) or {}
        except Exception:
            return True

        # Check version -- v1.0 indexes lack checksums, force rebuild
        if index_data.get("version") != INDEX_VERSION:
            return True

        stored_checksums: dict[str, str] = index_data.get("file_checksums", {})
        current_files = self._get_source_files()
        current_paths = {str(f) for f in current_files}
        stored_paths = set(stored_checksums.keys())

        # New or deleted files
        if current_paths != stored_paths:
            return True

        # Changed files
        for f in current_files:
            stored = stored_checksums.get(str(f))
            if stored != self._compute_file_checksum(f):
                return True

        # Time-based staleness
        auto_rebuild_hours = self._config.get("indexing", {}).get("auto_rebuild_hours", 24)
        updated_str = index_data.get("updated")
        if updated_str:
            try:
                updated_dt = datetime.fromisoformat(updated_str)
                if datetime.now() - updated_dt > timedelta(hours=auto_rebuild_hours):
                    return True
            except (ValueError, TypeError):
                return True

        return False

    # ------------------------------------------------------------------
    # Index build
    # ------------------------------------------------------------------

    def build_index(self, force: bool = False) -> int:
        """Build/update YAML index from memory files.

        When incremental mode is enabled and an existing v2.0 index exists,
        only re-parses files whose checksum changed.

        Args:
            force: If True, always do a full rebuild regardless of checksums.

        Returns:
            Number of entries indexed.
        """
        incremental = self._config.get("indexing", {}).get("incremental", True) and not force

        # Load existing index for incremental merge
        existing_entries: dict[str, list[dict]] = {}  # file_path -> entries
        existing_checksums: dict[str, str] = {}
        if incremental and self._index_path.exists():
            try:
                index_data = yaml.safe_load(self._index_path.read_text()) or {}
                if index_data.get("version") == INDEX_VERSION:
                    existing_checksums = index_data.get("file_checksums", {})
                    for entry in index_data.get("entries", []):
                        fp = entry.get("file_path", "")
                        existing_entries.setdefault(fp, []).append(entry)
            except Exception:
                existing_entries = {}
                existing_checksums = {}

        entries: list[MemoryEntry] = []
        file_checksums: dict[str, str] = {}
        files_parsed = 0

        # Index daily logs
        if self._daily_dir.exists():
            for log_file in sorted(self._daily_dir.glob("*.md")):
                file_key = str(log_file)
                current_checksum = self._compute_file_checksum(log_file)
                file_checksums[file_key] = current_checksum

                if incremental and existing_checksums.get(file_key) == current_checksum:
                    # Unchanged -- reuse existing entries
                    for ed in existing_entries.get(file_key, []):
                        entries.append(MemoryEntry(**{k: ed[k] for k in MemoryEntry.__dataclass_fields__}))
                    continue

                files_parsed += 1
                date_str = log_file.stem
                content = log_file.read_text()
                parsed = self._parse_daily_log(content, date_str, file_key)
                entries.extend(parsed)

        # Index MEMORY.md
        if self._memory_file.exists():
            file_key = str(self._memory_file)
            current_checksum = self._compute_file_checksum(self._memory_file)
            file_checksums[file_key] = current_checksum

            if incremental and existing_checksums.get(file_key) == current_checksum:
                for ed in existing_entries.get(file_key, []):
                    entries.append(MemoryEntry(**{k: ed[k] for k in MemoryEntry.__dataclass_fields__}))
            else:
                files_parsed += 1
                content = self._memory_file.read_text()
                parsed = self._parse_memory_md(content, file_key)
                entries.extend(parsed)

        # Write index (v2.0 with checksums)
        index_data = {
            "version": INDEX_VERSION,
            "updated": datetime.now().isoformat(),
            "entry_count": len(entries),
            "file_checksums": file_checksums,
            "entries": [e.to_dict() for e in entries],
        }

        self._index_path.write_text(yaml.dump(index_data, default_flow_style=False, allow_unicode=True))
        logger.info(f"Built memory index with {len(entries)} entries ({files_parsed} files parsed)")
        return len(entries)

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def _parse_daily_log(self, content: str, date_str: str, file_path: str) -> list[MemoryEntry]:
        """Parse daily log into indexable entries."""
        entries = []
        current_event: list[str] = []
        current_category = "event"
        event_start_line = 0
        event_header = ""

        for i, line in enumerate(content.split("\n"), 1):
            if line.startswith("## "):
                # Save previous event
                if current_event and event_header:
                    entry_content = "\n".join(current_event)
                    key_match = re.search(r"- (.+)$", event_header)
                    key = key_match.group(1) if key_match else event_header

                    entries.append(
                        MemoryEntry(
                            key=key,
                            content=entry_content,
                            category=current_category,
                            source="daily",
                            date=date_str,
                            file_path=file_path,
                            line_number=event_start_line,
                            tags=self._extract_tags(entry_content),
                        )
                    )

                # Start new event
                event_header = line
                current_event = [line]
                event_start_line = i

                # Detect category
                line_lower = line.lower()
                if "decision" in line_lower:
                    current_category = "decision"
                elif "preference" in line_lower:
                    current_category = "preference"
                elif "pattern" in line_lower:
                    current_category = "pattern"
                elif "context switch" in line_lower:
                    current_category = "context_switch"
                elif "tool" in line_lower:
                    current_category = "tool_execution"
                elif "error" in line_lower:
                    current_category = "error"
                else:
                    current_category = "event"
            elif line.strip():
                current_event.append(line)

        # Save last event
        if current_event and event_header:
            entry_content = "\n".join(current_event)
            key_match = re.search(r"- (.+)$", event_header)
            key = key_match.group(1) if key_match else event_header

            entries.append(
                MemoryEntry(
                    key=key,
                    content=entry_content,
                    category=current_category,
                    source="daily",
                    date=date_str,
                    file_path=file_path,
                    line_number=event_start_line,
                    tags=self._extract_tags(entry_content),
                )
            )

        return entries

    def _parse_memory_md(self, content: str, file_path: str) -> list[MemoryEntry]:
        """Parse MEMORY.md into indexable entries."""
        entries = []
        current_section = ""
        current_subsection = ""
        date_pattern = r"\((\d{4}-\d{2}-\d{2})\)"

        for i, line in enumerate(content.split("\n"), 1):
            if line.startswith("## "):
                current_section = line[3:].strip()
            elif line.startswith("### "):
                current_subsection = line[4:].strip()
            elif line.strip().startswith("-"):
                entry_content = line.strip()

                # Determine category
                section_lower = current_section.lower()
                if "decision" in section_lower:
                    category = "decision"
                elif "pattern" in section_lower:
                    category = "pattern"
                elif "preference" in section_lower:
                    category = "preference"
                else:
                    category = "insight"

                # Extract date
                date_match = re.search(date_pattern, entry_content)
                date = date_match.group(1) if date_match else ""

                # Extract key (bolded text)
                key_match = re.search(r"\*\*(.+?)\*\*", entry_content)
                key = key_match.group(1) if key_match else current_subsection

                full_content = f"{current_subsection}: {entry_content}" if current_subsection else entry_content

                entries.append(
                    MemoryEntry(
                        key=key,
                        content=full_content,
                        category=category,
                        source="curated",
                        date=date,
                        file_path=file_path,
                        line_number=i,
                        tags=self._extract_tags(full_content) + [current_subsection.lower()],
                    )
                )

        return entries

    def _extract_tags(self, content: str) -> list[str]:
        """Extract searchable tags from content."""
        tags = []

        # Extract words that look like topics (capitalized words)
        words = re.findall(r"\b[A-Z][a-z]+\b", content)
        tags.extend([w.lower() for w in words[:5]])

        # Extract quoted strings
        quoted = re.findall(r'"([^"]+)"', content)
        tags.extend([q.lower() for q in quoted[:3]])

        return list(set(tags))
