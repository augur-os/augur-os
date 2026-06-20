"""Scan vault, documents, and scraper for sources that could feed wiki pages."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
import subprocess
import time
from typing import Any

from skills.wiki.scripts import wiki_memory_adapters
from skills.wiki.scripts.wiki_signals_config import WikiSignalsConfig, load_config as load_wiki_signals
from skills.wiki.scripts.wiki_tier import (
    normalize_tier,
    rank_for_tier,
    tier_for_surface,
    weight_for_tier,
)
from src.config.paths import get_project_brain_skills_dir, get_wiki_signals_config_path
from src.lib.frontmatter_utils import parse_frontmatter


# Extensions worth scanning
_SCANNABLE = {".md", ".txt", ".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".json"}
_SKIP_DIRS = {"wiki", ".git", "__pycache__", "node_modules", ".augur"}
_NOISE_DIR_NAMES = {
    ".obsidian",
    ".trash",
    "_templates",
    "templates",
    "template",
}
_NOISE_FILE_NAMES = {
    "workspace.json",
}
_NOISE_PATH_PARTS = {
    ".obsidian",
    "_templates",
    "templates",
}
_CURATED_REPO_DOCS: tuple[tuple[str, str], ...] = (
    ("README.md", "dev"),
    ("docs/agent-topics/ARCHITECTURE.md", "dev"),
    ("docs/agent-topics/CODING.md", "dev"),
    ("docs/agent-topics/DEBUGGING.md", "dev"),
    ("docs/agent-topics/WORKFLOWS.md", "dev"),
    ("docs/references/agent-vs-mcp-checklist.md", "dev"),
    ("docs/references/agent-vs-mcp-examples.md", "dev"),
    ("docs/generated/adr-index.md", "dev"),
)
_DEV_ADR_KEYWORDS = (
    "architecture",
    "mcp",
    "plugin",
    "skill",
    "dashboard",
    "workflow",
    "agent",
    "path",
    "build",
    "routing",
    "wiki",
    "rag",
    "local-first",
    "data separation",
)
_MAX_DEV_ADR_TARGETS = 40
_PROJECT_DELTA_ROOTS: tuple[str, ...] = (
    "docs/superpowers/plans",
    "docs/superpowers/specs",
    "docs/generated",
)
_DEV_DELTA_KEYWORDS = (
    "dev",
    "wiki",
    "ask",
    "architecture",
    "mcp",
    "dashboard",
    "build",
    "codex",
    "agent",
    "workflow",
    "coverage",
    "gap",
    "loop",
    "rag",
)
_MAX_PROJECT_DELTAS = 20
_MEANINGFUL_COMMIT_PREFIXES = ("feat", "fix", "refactor", "perf", "revert")
_MAX_GIT_HISTORY_ITEMS = 15


def _extract_title(path: Path) -> str:
    """Extract title from markdown H1 or use filename stem."""
    if path.suffix.lower() in (".md", ".txt"):
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                if stripped.startswith("# "):
                    return stripped[2:].strip()
        except Exception:
            pass
    return path.stem.replace("-", " ").replace("_", " ").title()


def _frontmatter_wiki_tier(path: Path) -> str | None:
    if path.suffix.lower() not in {".md", ".txt"}:
        return None
    try:
        metadata, _body = parse_frontmatter(path)
    except (OSError, ValueError):
        return None
    raw = str(metadata.get("wiki_tier") or "").strip().lower()
    return raw if raw in {"critical", "high", "medium", "low", "noise"} else None


def _guess_hub(path: Path, vault_dir: Path) -> str:
    """Guess hub from path relative to vault."""
    try:
        rel = path.relative_to(vault_dir)
        parts = rel.parts
        if len(parts) >= 1 and parts[0] not in _SKIP_DIRS:
            return parts[0]
    except ValueError:
        pass
    return "general"


class WikiScanner:
    """Scan knowledge sources for wiki-eligible content."""

    def __init__(
        self,
        *,
        vault_dir: Path,
        documents_dir: Path,
        project_root: Path | None = None,
        runtime_dir: Path | None = None,
        logs_dir: Path | None = None,
        ask_outcomes_loader: Callable[[], list[dict[str, Any]]] | None = None,
        git_history_loader: Callable[[], list[dict[str, str]]] | None = None,
        signals_config: WikiSignalsConfig | None = None,
        episodic_loader: Callable[[], list[dict[str, Any]]] | None = None,
    ) -> None:
        self._vault_dir = Path(vault_dir)
        self._documents_dir = Path(documents_dir)
        self._project_root = Path(project_root) if project_root else None
        self._runtime_dir = Path(runtime_dir) if runtime_dir else None
        self._logs_dir = Path(logs_dir) if logs_dir else None
        self._ask_outcomes_loader = ask_outcomes_loader
        self._git_history_loader = git_history_loader
        if signals_config is not None:
            self._signals_config = signals_config
        elif self._project_root is not None:
            self._signals_config = load_wiki_signals(get_wiki_signals_config_path(self._project_root))
        else:
            self._signals_config = WikiSignalsConfig()
        self._episodic_loader = episodic_loader

    def scan(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        """Scan all sources. Returns list of source dicts.

        Each dict has: path, type, title, hub, format.
        """
        sources: list[dict[str, Any]] = []
        sources.extend(self._scan_dir(self._vault_dir, hub=hub, source_surface="vault"))
        if self._documents_dir.is_dir():
            sources.extend(
                self._scan_dir(
                    self._documents_dir,
                    hub=hub,
                    default_hub="documents",
                    source_surface="documents",
                )
            )
        sources.extend(self._scan_skill_defs(hub=hub))
        sources.extend(self._scan_repo_docs(hub=hub))
        sources.extend(self._scan_project_deltas(hub=hub))
        sources.extend(self._scan_git_history(hub=hub))
        sources.extend(self._scan_runtime_memory(hub=hub))
        sources.extend(self._scan_logs(hub=hub))
        sources.extend(self._scan_ask_outcomes(hub=hub))
        sources.extend(self._scan_adr_targets(hub=hub))
        sources.extend(self._scan_client_memory(hub=hub))
        sources.extend(self._scan_episodic_records(hub=hub))
        return self._dedupe_sources([self._annotate_tier(source) for source in sources])

    def _scan_dir(
        self,
        root: Path,
        *,
        hub: str | None = None,
        default_hub: str | None = None,
        source_surface: str,
    ) -> list[dict[str, Any]]:
        """Recursively scan a directory for scannable files."""
        if not root.is_dir():
            return []
        results = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if any(skip in path.parts for skip in _SKIP_DIRS):
                continue
            if self._is_noise_path(path):
                continue
            ext = path.suffix.lower()
            if ext not in _SCANNABLE:
                continue
            source_hub = default_hub or _guess_hub(path, self._vault_dir)
            if hub and source_hub != hub:
                continue
            actual_surface = source_surface
            if source_surface == "vault" and self._is_recent_vault_write(path):
                actual_surface = "save_events"
            results.append(self._annotate_tier({
                "path": str(path),
                "type": ext.lstrip("."),
                "title": _extract_title(path),
                "hub": source_hub,
                "format": ext.lstrip("."),
                "source_surface": actual_surface,
            }, path=path))
        return results

    def _is_recent_vault_write(self, path: Path) -> bool:
        window_seconds = max(0, int(self._signals_config.mtime_window_minutes)) * 60
        if window_seconds <= 0:
            return False
        try:
            return path.stat().st_mtime >= time.time() - window_seconds
        except OSError:
            return False

    @staticmethod
    def _annotate_tier(source: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
        surface = str(source.get("source_surface") or "")
        tier = normalize_tier(source.get("tier"), default=tier_for_surface(surface))
        if path is not None:
            tier = _frontmatter_wiki_tier(path) or tier
        weight = weight_for_tier(tier)
        return {**source, "tier": tier, "weight": weight}

    @staticmethod
    def _is_noise_path(path: Path) -> bool:
        """Return True for transient or machine-managed content."""
        if path.name in _NOISE_FILE_NAMES:
            return True
        lower_parts = {part.lower() for part in path.parts}
        if lower_parts & _NOISE_PATH_PARTS:
            return True
        return any(part.lower() in _NOISE_DIR_NAMES for part in path.parts[:-1])

    def _scan_skill_defs(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        """Collect skill definitions so rebuilds can see the installed skill surface."""
        if self._project_root is None:
            return []
        skills_dir = get_project_brain_skills_dir(self._project_root)
        if not skills_dir.is_dir():
            return []

        results: list[dict[str, Any]] = []
        for path in sorted(skills_dir.glob("*/SKILL.md")):
            meta, _ = parse_frontmatter(path)
            source_hub = str(meta.get("x-augur-hub") or meta.get("hub") or path.parent.name).strip() or "general"
            if hub and source_hub != hub:
                continue
            results.append(self._annotate_tier({
                "path": str(path),
                "type": "skill",
                "title": _extract_title(path),
                "hub": source_hub,
                "format": "md",
                "source_surface": "skills",
            }, path=path))
        return results

    def _scan_runtime_memory(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        """Include retained runtime memory daily notes as a rebuild input surface."""
        if self._runtime_dir is None:
            return []
        return self._scan_dir(
            self._runtime_dir / "memory" / "daily",
            hub=hub,
            default_hub="memory",
            source_surface="runtime_memory",
        )

    def _scan_logs(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        """Include a lightweight operational log surface for wiki maintenance."""
        if not self._signals_config.include_logs:
            return []
        if self._logs_dir is None:
            return []
        return self._scan_dir(
            self._logs_dir,
            hub=hub,
            default_hub="attention",
            source_surface="logs",
        )

    def _scan_repo_docs(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        """Include a curated repo-doc surface for architecture-aware rebuilds."""
        if self._project_root is None:
            return []

        results: list[dict[str, Any]] = []
        for relative_path, source_hub in _CURATED_REPO_DOCS:
            if hub and source_hub != hub:
                continue
            path = self._project_root / relative_path
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            if ext not in _SCANNABLE:
                continue
            results.append({
                "path": str(path),
                "type": ext.lstrip("."),
                "title": _extract_title(path),
                "hub": source_hub,
                "format": ext.lstrip("."),
                "source_surface": "repo_docs",
            })
        return results

    def _scan_client_memory(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        client_memory = self._signals_config.client_memory
        sources = wiki_memory_adapters.scan_client_memory(
            clients=client_memory.get("clients", {}),
            enabled=bool(client_memory.get("enabled", True)),
        )
        return self._filter_hub(sources, hub)

    def _scan_episodic_records(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        if not bool(self._signals_config.episodic.get("enabled", True)):
            return []
        return self._filter_hub(wiki_memory_adapters.scan_episodic(loader=self._episodic_loader), hub)

    @staticmethod
    def _filter_hub(sources: list[dict[str, Any]], hub: str | None) -> list[dict[str, Any]]:
        if not hub:
            return sources
        return [source for source in sources if source.get("hub") == hub]

    def _scan_ask_outcomes(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        """Project retained `/ask` outcomes into the scanner surface model."""
        if self._ask_outcomes_loader is None:
            return []

        results: list[dict[str, Any]] = []
        for item in self._ask_outcomes_loader():
            source_hub = self._guess_outcome_hub(item)
            if hub and source_hub != hub:
                continue
            source_path = str(item.get("path") or f"ask://{item.get('created', '')}")
            results.append({
                "path": source_path,
                "type": str(item.get("source_type") or item.get("kind") or "ask"),
                "title": str(item.get("question") or item.get("title") or "Ask Outcome").strip(),
                "hub": source_hub,
                "format": "md",
                "source_surface": "ask_outcomes",
            })
        return results

    def _scan_project_deltas(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        """Include recent plan/spec/report artifacts as a durable implementation-delta surface."""
        if self._project_root is None or hub not in (None, "dev"):
            return []

        candidates: list[tuple[tuple[int, date], Path, str]] = []
        for relative_root in _PROJECT_DELTA_ROOTS:
            root = self._project_root / relative_root
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*.md")):
                title = _extract_title(path)
                score = self._project_delta_score(path, title)
                if score <= 0:
                    continue
                candidates.append((self._project_delta_sort_key(path, score), path, title))

        candidates.sort(reverse=True)

        results: list[dict[str, Any]] = []
        for _, path, title in candidates[:_MAX_PROJECT_DELTAS]:
            results.append({
                "path": str(path),
                "type": "md",
                "title": title,
                "hub": "dev",
                "format": "md",
                "source_surface": "project_deltas",
            })
        return results

    def _scan_git_history(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        """Include recent meaningful git history as a shipped-change surface for dev."""
        if self._project_root is None or hub not in (None, "dev"):
            return []

        commits = self._load_git_history()
        results: list[dict[str, Any]] = []
        for commit in commits:
            subject = str(commit.get("subject") or "").strip()
            sha = str(commit.get("sha") or "").strip()
            if not subject or not sha:
                continue
            if not self._is_meaningful_commit(subject):
                continue
            results.append({
                "path": f"git:{sha}",
                "type": "commit",
                "title": subject,
                "hub": "dev",
                "format": "git",
                "source_surface": "git_history",
            })
            if len(results) >= _MAX_GIT_HISTORY_ITEMS:
                break
        return results

    def _scan_adr_targets(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        """Project a selective ADR surface into dev rebuilds."""
        if hub not in (None, "dev"):
            return []

        adr_dir = self._documents_dir / "adrs"
        if not adr_dir.is_dir():
            return []

        candidates: list[tuple[int, Path, str]] = []
        for path in sorted(adr_dir.glob("ADR-*.md")):
            title = _extract_title(path)
            score = self._dev_adr_score(title)
            if score <= 0:
                continue
            candidates.append((score, path, title))

        candidates.sort(key=lambda item: (-item[0], item[1].name))

        results: list[dict[str, Any]] = []
        for _, path, title in candidates[:_MAX_DEV_ADR_TARGETS]:
            results.append({
                "path": str(path),
                "type": "md",
                "title": title,
                "hub": "dev",
                "format": "md",
                "source_surface": "adr_targets",
            })
        return results

    @staticmethod
    def _dev_adr_score(title: str) -> int:
        lowered = title.lower()
        return sum(1 for keyword in _DEV_ADR_KEYWORDS if keyword in lowered)

    def _project_delta_score(self, path: Path, title: str) -> int:
        lowered = f"{path.stem} {title}".lower()
        return sum(1 for keyword in _DEV_DELTA_KEYWORDS if keyword in lowered)

    @staticmethod
    def _project_delta_sort_key(path: Path, score: int) -> tuple[int, date]:
        parsed_date = WikiScanner._extract_date_prefix(path.name)
        return score, parsed_date

    @staticmethod
    def _extract_date_prefix(name: str) -> date:
        prefix = name[:10]
        try:
            return date.fromisoformat(prefix)
        except ValueError:
            return date.min

    def _load_git_history(self) -> list[dict[str, str]]:
        """Load recent git commit summaries from the project root."""
        if self._git_history_loader is not None:
            return list(self._git_history_loader())
        if self._project_root is None:
            return []
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--date=short",
                    "--pretty=%H\t%ad\t%s",
                    "-n",
                    "60",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self._project_root,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if result.returncode != 0:
            return []

        commits: list[dict[str, str]] = []
        for line in result.stdout.splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            sha, commit_date, subject = parts
            commits.append({"sha": sha, "date": commit_date, "subject": subject})
        return commits

    @staticmethod
    def _is_meaningful_commit(subject: str) -> bool:
        lowered = subject.strip().lower()
        if not lowered or lowered.startswith("merge "):
            return False
        return lowered.startswith(_MEANINGFUL_COMMIT_PREFIXES)

    def _guess_outcome_hub(self, item: dict[str, Any]) -> str:
        """Infer the most relevant hub for a retained `/ask` outcome."""
        tags = [str(tag).strip() for tag in item.get("tags", []) if str(tag).strip()]
        for tag in tags:
            lowered = tag.lower()
            if lowered != "ask":
                return lowered

        raw_path = str(item.get("path") or "").strip()
        if raw_path:
            path = Path(raw_path)
            for root, default_hub in (
                (self._vault_dir, None),
                (self._documents_dir, "documents"),
                (self._runtime_dir / "memory" / "daily" if self._runtime_dir else None, "memory"),
            ):
                if root is None:
                    continue
                try:
                    rel = path.relative_to(root)
                except ValueError:
                    continue
                if default_hub:
                    return default_hub
                if rel.parts:
                    return rel.parts[0]

        return "knowledge"

    @staticmethod
    def _dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep a stable unique set of sources across surfaces."""
        unique_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        order: list[tuple[str, str]] = []
        for source in sources:
            key = (
                str(source.get("path", "")),
                str(source.get("title", "")),
            )
            current = unique_by_key.get(key)
            if current is None:
                unique_by_key[key] = source
                order.append(key)
                continue
            if rank_for_tier(str(source.get("tier") or "")) > rank_for_tier(str(current.get("tier") or "")):
                unique_by_key[key] = source
        return [unique_by_key[key] for key in order]
