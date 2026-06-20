"""Ripgrep-based search and Python fallback for memory search."""

import json
import re
from pathlib import Path
from subprocess import TimeoutExpired, run as subprocess_run  # nosec B404

from src.logging import get_entity_logger

from ._types import _normalize_path

logger = get_entity_logger(__name__)


class RipgrepMixin:
    """Mixin providing ripgrep and fallback search for MemorySearcher."""

    def _ripgrep_search(
        self,
        query: str,
        path: Path,
        context_lines: int = 2,
        case_insensitive: bool = True,
    ) -> list[dict]:
        """Execute ripgrep search on path.

        Args:
            query: Search query (supports regex)
            path: File or directory to search
            context_lines: Lines of context around match
            case_insensitive: Case insensitive search

        Returns:
            List of match dictionaries with normalized absolute paths.
        """
        if not path.exists():
            return []

        # Sanitize query: escape regex metacharacters for safe ripgrep usage
        safe_query = re.escape(query)
        cmd = ["rg", "--json"]
        if case_insensitive:
            cmd.append("-i")
        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])
        cmd.extend([safe_query, str(path)])

        try:
            result = subprocess_run(  # nosec B603
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            matches = []

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        match_data = data.get("data", {})
                        raw_path = match_data.get("path", {}).get("text", "")
                        matches.append(
                            {
                                "path": _normalize_path(raw_path) or raw_path,
                                "line_number": match_data.get("line_number", 0),
                                "content": match_data.get("lines", {}).get("text", "").strip(),
                                "submatches": match_data.get("submatches", []),
                            }
                        )
                except (json.JSONDecodeError, ValueError):
                    continue

            return matches
        except TimeoutExpired:
            logger.warning(f"Ripgrep search timed out for query: {query}")
            return []
        except FileNotFoundError:
            logger.warning("ripgrep (rg) not found, falling back to basic search")
            return self._fallback_search(query, path)

    def _fallback_search(self, query: str, path: Path) -> list[dict]:
        """Basic Python search fallback when ripgrep unavailable."""
        matches = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)

        if path.is_file():
            files = [path]
        else:
            files = list(path.glob("**/*.md"))

        for file_path in files:
            try:
                content = file_path.read_text()
                for i, line in enumerate(content.split("\n"), 1):
                    if pattern.search(line):
                        matches.append(
                            {
                                "path": _normalize_path(str(file_path)) or str(file_path),
                                "line_number": i,
                                "content": line.strip(),
                                "submatches": [],
                            }
                        )
            except (OSError, UnicodeDecodeError):
                continue

        return matches
