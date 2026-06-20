"""sync_agents/adapters/base.py — Base adapter interface."""
from __future__ import annotations

import os
import shutil as _shutil
from pathlib import Path

from src.lib.brain_stack import resolve_active_stack

from ..constants import PROJECT_ROOT, logger

_LEGACY_HANDOFF_INTRO = (
    "*Compact startup context generated from legacy Augur memory. Full recall is "
    "pull-based: use `/ask`, `memory-search`, or `knowledge-memory-read` when "
    "deeper history is needed.*"
)
_HANDOFF_POLICY = [
    "## Retrieval Policy",
    "",
    "- Treat this file as a startup handoff, not canonical memory.",
    "- Use `/ask` or Augur memory tools for targeted recall across clients, brains, and older work.",
    "",
]


def projected_memory_content(project_root: Path | None = None) -> str | None:
    """Return compact memory handoff projected to native client memory."""
    root = project_root or PROJECT_ROOT
    try:
        from src.lib.brain_memory_tiers import render_memory_handoff_markdown

        content = render_memory_handoff_markdown(resolve_active_stack(cwd=root))
        if content.strip():
            return content
    except Exception as exc:  # noqa: BLE001 - fall back to legacy singleton projection
        logger.debug("Tier memory projection unavailable: %s", exc)

    try:
        from src.config.paths import get_memory_dir

        memory_file = get_memory_dir() / "MEMORY.md"
        if memory_file.exists():
            content = _compact_legacy_memory_text(memory_file.read_text(encoding="utf-8"))
            if content.strip():
                return content
    except Exception as exc:  # noqa: BLE001 - sync should skip memory, not abort all adapters
        logger.debug("Legacy memory projection unavailable: %s", exc)
    return None


def _compact_legacy_memory_text(text: str, *, max_items: int = 8, max_bytes: int = 2400) -> str:
    items: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- **"):
            continue
        items.append(stripped)
        if len(items) >= max_items:
            break
    if not items:
        return ""
    rendered = _render_legacy_handoff(items)
    while len(rendered.encode("utf-8")) > max_bytes and items:
        items.pop()
        rendered = _render_legacy_handoff(items)
    return rendered if items else ""


def _render_legacy_handoff(items: list[str]) -> str:
    lines = [
        "# Augur Cross-Client Handoff",
        "",
        _LEGACY_HANDOFF_INTRO,
        "",
        "## Recent Work",
        "",
        *items,
        "",
        *_HANDOFF_POLICY,
    ]
    rendered = "\n".join(lines)
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


class BaseAdapter:
    """Base class for all IDE/CLI sync adapters."""

    adapter_name: str = ""

    # ── Lifecycle Methods (ADR-219) ──────────────────────────────

    def get_managed_files(self) -> list[str]:
        """Return list of file/directory paths this adapter manages.

        Paths are relative to PROJECT_ROOT for in-repo files,
        or absolute for home-directory files (e.g. ~/.codex/).
        Override in each adapter.
        """
        return []

    def get_required_outputs(
        self,
        project_root: Path,
        *,
        do_rules: bool = True,
        do_subagents: bool = True,
        do_memory: bool = True,
        do_plugins: bool = True,
        do_skill_exports: bool = True,
        do_prompt_exports: bool = True,
        do_command_exports: bool = True,
    ) -> list[str]:
        """Return paths this adapter is contractually expected to produce
        for the given sync flags AND project state.

        This is the verification contract: a worktree-preflight or smoke test
        can ask "given these sync flags, which paths must materialize for
        THIS project?" and check only those. Returns a subset of
        get_managed_files().

        Implementations should inspect project_root for any preconditions
        (e.g. presence of memory files, augur.yaml plugin imports) and only
        return paths whose producer would actually run.

        Default implementation is empty — override per adapter to encode the
        actual producer mapping. Returning [] means the adapter has no
        verifiable output contract yet.
        """
        return []

    def get_state_files(self) -> list[str]:
        """Return list of state file/directory paths this adapter manages."""
        return []

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        """Delete all managed files/dirs. Returns list of deleted/would-delete paths.

        Args:
            exclude_paths: Paths to preserve even if managed.
            dry_run: If True, collect paths to delete but do not actually delete.

        Idempotent — missing files are silently skipped.
        """
        return self._cleanup_paths(self.get_managed_files(), exclude_paths=exclude_paths, dry_run=dry_run)

    def cleanup_state(self, dry_run: bool = False) -> list[str]:
        """Delete all adapter state files/dirs. Returns list of deleted/would-delete paths."""
        return self._cleanup_paths(self.get_state_files(), dry_run=dry_run)

    def _cleanup_paths(
        self,
        paths: list[str],
        exclude_paths: set[Path] | None = None,
        dry_run: bool = False,
    ) -> list[str]:
        """Shared cleanup helper for managed files and adapter state."""
        from ..constants import PROJECT_ROOT, logger

        excluded = {path.resolve() for path in (exclude_paths or set())}

        def _prune_empty_parents(start: Path) -> None:
            current = start
            project_root = PROJECT_ROOT.resolve()
            while True:
                try:
                    current_resolved = current.resolve()
                except OSError:
                    break
                if current_resolved == project_root or not current.exists():
                    break
                try:
                    current.rmdir()
                except OSError:
                    break
                current = current.parent

        deleted = []
        for path_str in paths:
            path = Path(path_str)
            managed_in_repo = not path.is_absolute()
            if managed_in_repo:
                path = PROJECT_ROOT / path
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if resolved in excluded:
                if not dry_run:
                    logger.info(f"Preserving shared managed path: {path_str}")
                continue
            if not path.exists():
                continue
            deleted.append(path_str)
            if dry_run:
                continue
            try:
                if path.is_dir():
                    for item in path.rglob("*"):
                        if item.is_file() and not os.access(item, os.W_OK):
                            item.chmod(0o666)
                    _shutil.rmtree(path)
                else:
                    if not os.access(path, os.W_OK):
                        path.chmod(0o666)
                    path.unlink()
                if managed_in_repo:
                    _prune_empty_parents(path.parent)
                logger.info(f"Cleaned up: {path_str}")
            except OSError as e:
                logger.warning(f"Failed to clean up {path_str}: {e}")
        return deleted

    def detect_installed(self) -> bool:
        """Check if this IDE/CLI is installed on the local machine.

        Override in each adapter with binary/config detection.
        """
        return False

    # ── Sync Methods (existing) ──────────────────────────────────

    def sync_rules(self, content: str) -> None:
        """Sync global rules to this adapter's target file(s).

        ADR-145 WP11: All adapters receive the full agent-rules.md content
        (Critical Rules, Directory Layout, Hub list, Key References, etc.)
        via resolve_placeholders(). No sections are stripped for non-Claude
        targets — cross-agent parity is maintained at the rules level.
        """
        pass

    def generate_mcp_config(self) -> None:
        """Generate resolved MCP config for this client (ADR-030)."""
        pass

    def sync_subagents(self) -> None:
        """Generate subagent profiles from crew skills (ADR-046). Claude Code only."""
        pass

    def sync_topic_docs(self, content: str | None = None) -> None:
        """Copy topic docs from agent-topics/ to docs/agent-topics/ (ADR-096).

        Topic docs provide deep guidance loaded on demand. They are synced
        to docs/agent-topics/ so all agents and tools can reference them
        from a canonical location within docs/.
        """
        from ..constants import PROJECT_ROOT, SOURCE_TOPICS, SOURCE_TOPICS_LABEL, logger
        from ..engine import write_generated_file

        if not SOURCE_TOPICS.exists():
            logger.warning(f"Topic docs source not found: {SOURCE_TOPICS}")
            return

        target_dir = PROJECT_ROOT / "docs" / "agent-topics"
        target_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for topic_file in sorted(SOURCE_TOPICS.glob("*.md")):
            try:
                content = topic_file.read_text(encoding="utf-8")
                write_generated_file(
                    target_dir / topic_file.name,
                    content,
                    source=f"{SOURCE_TOPICS_LABEL.rstrip('/')}/{topic_file.name}",
                )
                count += 1
            except OSError as e:
                logger.error(f"Failed to sync topic doc {topic_file.name}: {e}")

        if count:
            logger.info(f"✅ Synced {count} topic docs to docs/agent-topics/")

    def _sync_agent_topics(self, target_dir: Path, source_ref_prefix: str) -> None:
        """Helper to sync topic docs to an agent-specific directory."""
        from ..constants import SOURCE_TOPICS, logger
        from ..engine import write_generated_file, clean_directory

        if not SOURCE_TOPICS.exists():
            return

        target_dir.mkdir(parents=True, exist_ok=True)
        clean_directory(target_dir)

        count = 0
        for topic_file in sorted(SOURCE_TOPICS.glob("*.md")):
            try:
                content = topic_file.read_text(encoding="utf-8")
                write_generated_file(
                    target_dir / topic_file.name,
                    content,
                    source=f"{source_ref_prefix}/{topic_file.name}",
                )
                count += 1
            except OSError as e:
                logger.error(f"Failed to sync agent topic {topic_file.name}: {e}")

        if count:
            logger.info(f"✅ Synced {count} topics to {target_dir}")

    def _cleanup_orphan_agents(self, agents_dir: Path, generated_names: set[str]) -> None:
        """Remove adapted copies whose master no longer exists (ADR-464).

        Scans agents_dir for .md files with AUGUR-ADAPTED-COPY or AUTO-GENERATED
        markers that aren't in generated_names, and deletes them.
        """
        from ..constants import logger

        if not agents_dir.exists():
            return
        for entry in sorted(agents_dir.iterdir()):
            if not entry.is_file() or entry.suffix != ".md":
                continue
            if entry.stem in generated_names:
                continue
            try:
                text = entry.read_text(encoding="utf-8")
                if "AUGUR-ADAPTED-COPY" in text or "AUTO-GENERATED" in text:
                    if not (entry.stat().st_mode & 0o200):
                        entry.chmod(0o666)
                    entry.unlink()
                    logger.info(f"  → Removed orphaned agent: {entry.name}")
            except OSError:
                pass

    def distribute_external_skills(self, bundles: list) -> None:
        """Distribute vendored external skill bundles to this client (ADR-605 Phase 3).

        Default implementation is a no-op — adapters opt in by overriding.
        ``bundles`` is a list of ``ExternalSkillBundle`` instances loaded from
        ``config/external_skills.yaml``. Each adapter consults its entry in
        ``bundle.targets`` (e.g. ``file_copy``, ``convert_and_copy``,
        ``convert_to_instructions``, ``marketplace``) to decide what to do.
        """
        return None

    def get_projected_memory_content(self) -> str | None:
        return projected_memory_content(PROJECT_ROOT)

    def sync_memory(self) -> None:
        """Sync canonical memory to agent-specific location (ADR-057).

        Base implementation handles project-local markdown copy for
        Antigravity, Gemini, Cursor, etc.
        """
        memory_content = self.get_projected_memory_content()
        if not memory_content:
            return

        # Map adapter_name to project-local target
        targets = {
            "antigravity": PROJECT_ROOT / ".antigravity" / "memory" / "augur-memory.md",
            "gemini": PROJECT_ROOT / ".gemini" / "memory" / "augur-memory.md",
            "cursor": PROJECT_ROOT / ".cursor" / "memory" / "augur-memory.md",
            "copilot": PROJECT_ROOT / ".github" / "copilot-memory.md",
        }

        if self.adapter_name in targets:
            target_path = targets[self.adapter_name]
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(memory_content, encoding="utf-8")
                logger.info(f"✅ Synced memory to {target_path}")
            except OSError as e:
                logger.error(f"Failed to sync memory for {self.adapter_name}: {e}")
