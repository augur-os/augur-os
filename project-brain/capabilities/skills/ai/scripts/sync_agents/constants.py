"""
sync_agents/constants.py

Global constants, paths, and configuration for the sync_agents package.

ADR-186: Extracted from monolithic sync_agents.py.
ADR-186 Phase 4: Source paths discovered from SKILL.md frontmatter when available.
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
import os
import sys
from pathlib import Path
from typing import cast

# Bootstrap monorepo root for src.* imports.
try:
    from src.config.paths import get_project_root
    BOOTSTRAP_ROOT = get_project_root()
except ImportError:
    BOOTSTRAP_ROOT = Path(__file__).resolve().parents[5]  # fallback
if str(BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_ROOT))

from src.logging import get_entity_logger  # noqa: E402

# Add lib to path for imports — skill root via get_skill_root or fallback
try:
    from src.config.paths import get_skill_root as _get_skill_root
    _SKILL_ROOT = _get_skill_root("ai")
except ImportError:
    _SKILL_ROOT = Path(__file__).resolve().parent.parent.parent  # fallback
_LIB_PATH = str(_SKILL_ROOT / "augur" / "lib")
if _LIB_PATH not in sys.path:
    sys.path.insert(0, _LIB_PATH)

logger = get_entity_logger("sync_agents")

# --- Project Root Discovery ---

def find_project_root(start: Path) -> Path:
    """Resolve the active repo/worktree root without importing sibling modules.

    Project-brain skills are the canonical repo-owned skill root. Worktree syncs
    must stay anchored to the active checkout unless callers explicitly choose
    another root.
    """
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (
            (candidate / "pyproject.toml").exists()
            and (candidate / "project-brain" / "capabilities" / "skills").exists()
        ):
            return candidate
    raise FileNotFoundError(f"Could not find project root from {start}")

def _explicit_project_root_from_env() -> Path | None:
    """Return an explicit sync root for repo-local bootstrap callers."""
    raw = os.environ.get("AUGUR_SYNC_PROJECT_ROOT")
    if not raw:
        return None
    root = Path(raw).expanduser().resolve()
    if (
        (root / "pyproject.toml").exists()
        and (root / "project-brain" / "capabilities" / "skills").exists()
    ):
        return root
    raise FileNotFoundError(f"AUGUR_SYNC_PROJECT_ROOT is not an Augur checkout: {root}")

try:
    PROJECT_ROOT = _explicit_project_root_from_env() or find_project_root(
        Path(__file__).resolve().parent
    )
except FileNotFoundError:
    PROJECT_ROOT = Path(os.getcwd())
    logger.warning(f"Could not find project root via markers, using cwd: {PROJECT_ROOT}")

# --- Phase 4: Source Path Discovery via SKILL.md frontmatter (ADR-186) ---

def _display_path(path: Path) -> str:
    """Render stable user-facing source labels for generated file headers."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _discover_source_paths() -> dict[str, Path | str]:
    """Discover agent source paths from the active brain projection context."""
    root = PROJECT_ROOT
    try:
        from src.config.paths import get_active_brain_context
        from src.lib.brain_projection import resolve_brain_projection_sources

        ctx = get_active_brain_context(cwd=root)
        sources = resolve_brain_projection_sources(
            brain=ctx.active_brain,
            attached_project=ctx.attached_project,
            project_root=root,
        )
        return {
            "rules": sources.rules,
            "rules_label": sources.rules_label,
            "workflows": sources.workflow_roots[0],
            "workflows_label": _display_path(sources.workflow_roots[0]),
            "skills": sources.skill_roots[0],
            "skills_label": _display_path(sources.skill_roots[0]),
            "topics": sources.topics_root,
            "topics_label": sources.topics_label,
        }
    except Exception:
        pass
    topics_dir = root / "docs" / "agent-topics"
    return {
        "rules": topics_dir / "agent-rules.md",
        "rules_label": _display_path(topics_dir / "agent-rules.md"),
        "workflows": topics_dir,
        "workflows_label": _display_path(topics_dir),
        "skills": topics_dir,
        "skills_label": _display_path(topics_dir),
        "topics": topics_dir,
        "topics_label": _display_path(topics_dir),
    }


_source_paths = _discover_source_paths()

SOURCE_RULES: Path = cast(Path, _source_paths["rules"])
SOURCE_WORKFLOWS: Path = cast(Path, _source_paths["workflows"])
SOURCE_SKILLS: Path = cast(Path, _source_paths["skills"])
SOURCE_TOPICS: Path = cast(Path, _source_paths["topics"])
SOURCE_RULES_LABEL = str(_source_paths["rules_label"])
SOURCE_WORKFLOWS_LABEL = str(_source_paths["workflows_label"])
SOURCE_SKILLS_LABEL = str(_source_paths["skills_label"])
SOURCE_TOPICS_LABEL = str(_source_paths["topics_label"])

# --- Static Paths ---

ANTIGRAVITY_IDE_MANIFEST = PROJECT_ROOT / ".antigravity" / "ide-manifest.json"
CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))

# Phase 3: Bidirectional Plugin Sync (ADR-171)
CLAUDE_PLUGINS_CACHE = Path(os.environ.get(
    "CLAUDE_PLUGINS_CACHE",
    str(Path.home() / ".claude" / "plugins" / "cache" / "claude-plugins-official"),
))
ASSEMBLED_PLUGINS_PATH = PROJECT_ROOT / "config" / "dashboard" / "generated" / "assembled_claude_plugins.json"

# Adapter-specific paths for distributing imported Claude plugin agents (ADR-171)
_ADAPTER_AGENT_PATHS: dict[str, Path] = {
    "cursor": PROJECT_ROOT / ".cursor" / "skills",
    "windsurf": PROJECT_ROOT / ".windsurf" / "workflows",
    "copilot": PROJECT_ROOT / ".github" / "skills",
    "gemini": PROJECT_ROOT / ".antigravity" / "plugins",
    "opencode": PROJECT_ROOT / ".opencode" / "skills",
    "claude_desktop": Path.home() / ".claude" / "skills",
}

HEADER_TEMPLATE = """<!--
⚠️  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
Source: {source}
Generator: project-brain/capabilities/skills/ai/scripts/sync_agents/
-->
"""

# Track all generated files for `check` mode
GENERATED_FILES: list[Path] = []

MCP_CONFIG_TEMPLATE = PROJECT_ROOT / "src" / "config" / "mcp_config.template.json"

# Claude-specific frontmatter fields that should be stripped for non-Claude adapters.
_CLAUDE_ONLY_FIELDS = {"context", "agent"}
