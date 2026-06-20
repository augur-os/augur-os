"""sync_agents/adapters/copilot.py — GitHub Copilot adapter."""
from __future__ import annotations
import os
import shutil
from pathlib import Path

from .base import BaseAdapter
from ..constants import (
    PROJECT_ROOT,
    SOURCE_RULES_LABEL,
    logger,
)
from ..engine import write_generated_file
from ..templates import render_rules_projection

_GENERATED_MARKERS = ("AUGUR-GENERATED", "AUGUR-ADAPTED-COPY")


class CopilotAdapter(BaseAdapter):
    adapter_name = "copilot"

    def get_managed_files(self) -> list[str]:
        return [
            ".github/copilot-instructions.md",
            ".github/instructions/",
            ".github/prompts/",
            ".github/agents/",
            ".github/skills/",
            ".github/copilot/",
            ".github/copilot-memory.md",
        ]

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
        required: list[str] = []
        if do_rules:
            required.append(".github/copilot-instructions.md")
        if do_skill_exports and self._has_external_instruction_exports(project_root):
            required.append(".github/instructions/")
        if do_memory and (project_root / "docs" / "memory" / "MEMORY.md").exists():
            required.append(".github/copilot-memory.md")
        # NOTE: .github/instructions/ and the cloud plugin dirs are listed in
        # get_managed_files() (cleanup contract) but are only required when an
        # active producer exists. Empty cleanup-only dirs should not block fresh
        # worktree bootstrap.
        return required

    def _has_external_instruction_exports(self, project_root: Path) -> bool:
        try:
            from ..external_skills import load_external_bundles
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to load external skill bundle policy for Copilot: %s",
                exc,
            )
            return False

        bundles = load_external_bundles(project_root=project_root)
        return any(
            bundle.targets.get("copilot") == "convert_to_instructions"
            for bundle in bundles
        )

    def detect_installed(self) -> bool:
        import glob as _glob
        import shutil as _shutil

        if _shutil.which("copilot"):
            return True

        copilot_extensions = _glob.glob(
            str(Path.home() / ".vscode" / "extensions" / "github.copilot-*")
        )
        return bool(copilot_extensions)

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        """Delete only Augur-owned Copilot files while preserving user .github content."""
        from .. import constants as _constants

        project_root = _constants.PROJECT_ROOT
        excluded = {path.resolve() for path in (exclude_paths or set())}
        deleted: list[str] = []

        def _is_excluded(path: Path) -> bool:
            try:
                return path.resolve() in excluded
            except OSError:
                return path in excluded

        def _delete_file(path: Path, relative_path: str) -> None:
            if not path.exists() or _is_excluded(path):
                return
            deleted.append(relative_path)
            if dry_run:
                return
            if not os.access(path, os.W_OK):
                path.chmod(0o666)
            path.unlink()
            _constants.logger.info(f"Cleaned up: {relative_path}")

        def _delete_dir(path: Path, relative_path: str) -> None:
            if not path.exists() or _is_excluded(path):
                return
            deleted.append(relative_path)
            if dry_run:
                return
            if path.is_dir():
                for item in path.rglob("*"):
                    if item.is_file() and not os.access(item, os.W_OK):
                        item.chmod(0o666)
                shutil.rmtree(path)
            else:
                if not os.access(path, os.W_OK):
                    path.chmod(0o666)
                path.unlink()
            _constants.logger.info(f"Cleaned up: {relative_path}")

        def _prune_empty_subdirs(start: Path, stop_dir: Path) -> None:
            current = start
            while current != stop_dir and current.exists():
                try:
                    current.rmdir()
                except OSError:
                    break
                current = current.parent

        for relative_path in (
            ".github/copilot-instructions.md",
            ".github/copilot-memory.md",
        ):
            _delete_file(project_root / relative_path, relative_path)

        _delete_dir(project_root / ".github" / "copilot", ".github/copilot/")

        for relative_dir in (
            ".github/instructions",
            ".github/prompts",
            ".github/agents",
            ".github/skills",
        ):
            root_dir = project_root / relative_dir
            if not root_dir.exists():
                continue
            for item in sorted(root_dir.rglob("*")):
                if not item.is_file() or _is_excluded(item):
                    continue
                try:
                    content = item.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if not any(marker in content for marker in _GENERATED_MARKERS):
                    continue
                relative_path = item.relative_to(project_root).as_posix()
                deleted.append(relative_path)
                if dry_run:
                    continue
                if not os.access(item, os.W_OK):
                    item.chmod(0o666)
                item.unlink()
                _prune_empty_subdirs(item.parent, root_dir)
                _constants.logger.info(f"Cleaned up: {relative_path}")

        return deleted

    def distribute_external_skills(self, bundles: list) -> None:
        """Convert external skills into ``.github/instructions/<name>.instructions.md`` (ADR-605)."""
        from ..external_skills import _distribute_for_copilot
        _distribute_for_copilot(
            bundles,
            target_root=PROJECT_ROOT / ".github" / "instructions",
        )

    def sync_rules(self, content: str) -> None:
        resolved = render_rules_projection(content)
        write_generated_file(
            PROJECT_ROOT / ".github" / "copilot-instructions.md",
            resolved,
            source=SOURCE_RULES_LABEL,
        )

    def sync_memory(self) -> None:
        """Sync canonical memory to .github/copilot-memory.md (ADR-057)."""
        try:
            memory_content = self.get_projected_memory_content()
            if not memory_content:
                return
            target = PROJECT_ROOT / ".github" / "copilot-memory.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(memory_content, encoding="utf-8")
            logger.info(f"✅ Synced memory to {target.relative_to(PROJECT_ROOT)}")
        except Exception as e:
            logger.error(f"Failed to sync memory for Copilot: {e}")
