"""
discovery.py

Shared discovery utilities for scanning project assets like skills and workflows.
"""

from pathlib import Path
from typing import List, Dict, Optional

try:
    from src.logging import get_entity_logger

    logger = get_entity_logger("ai_discovery")
except ImportError:
    import importlib

    logger = importlib.import_module("logging").getLogger(__name__)


def find_project_root(start: Path = None, markers: List[str] = None) -> Path:
    """
    Find the project root by searching upward for marker files.

    Args:
        start: Starting directory (defaults to current file's parent)
        markers: List of marker files/dirs to look for (defaults to ['.git', 'pyproject.toml'])

    Returns:
        Path to project root

    Raises:
        FileNotFoundError: If no project root found
    """
    if markers is None:
        markers = ['.git', 'pyproject.toml', 'package.json']

    if start is None:
        start = Path(__file__).resolve().parent

    current = start
    while current != current.parent:
        for marker in markers:
            if (current / marker).exists():
                return current
        current = current.parent

    raise FileNotFoundError(f"Could not find project root from {start} using markers {markers}")


def scan_skills(project_root: Path) -> List[Dict[str, str]]:
    """
    Scan for available skills via canonical skill discovery.

    Each skill is a directory containing a SKILL.md file. The category is
    always ``"uncategorized"`` — the hub field that used to drive it was
    removed by ADR-802; the key is kept for API compatibility.

    Args:
        project_root: Path to project root

    Returns:
        List of skill dictionaries with 'name', 'category', 'path' keys
    """
    from src.config.paths import get_project_brain_skills_dir

    skills_dir = get_project_brain_skills_dir(project_root)
    if not skills_dir.exists():
        logger.debug(f"Skills directory not found: {skills_dir}")
        return []

    skills = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        skills.append(
            {
                "name": skill_dir.name,
                "category": "uncategorized",
                "path": str(skill_dir),
            }
        )

    return sorted(skills, key=lambda x: (x["category"], x["name"]))


def scan_workflows(workflows_dir: Path) -> List[Dict[str, str]]:
    """
    Scan for workflow markdown files and extract their descriptions.

    Args:
        workflows_dir: Path to directory containing workflow .md files

    Returns:
        List of workflow dictionaries with 'name', 'description', 'visibility', 'alias' keys
    """
    workflows = []

    if not workflows_dir.exists():
        logger.debug(f"Workflows directory not found: {workflows_dir}")
        return []

    for wf_file in sorted(workflows_dir.glob("*.md")):
        description = extract_workflow_description(wf_file)
        visibility, alias = extract_workflow_metadata(wf_file)
        workflows.append(
            {
                "name": wf_file.stem,
                "description": description[:80] if description else "Execute workflow",
                "visibility": visibility,
                "alias": alias,
            }
        )

    return workflows


def scan_ai_skills(skills_dir: Path) -> List[Dict[str, str]]:
    """
    Scan for AI skills with SKILL.md files.

    Scans subdirectories of *skills_dir* for SKILL.md files.  The canonical
    shared source location is ``project-brain/capabilities/skills/``, but callers may pass any
    directory that follows the same ``{skill_dir}/SKILL.md`` layout.

    Args:
        skills_dir: Path to the skills root directory (e.g. project_root / "project-brain" / "capabilities" / "skills")

    Returns:
        List of skill dictionaries with 'name', 'description', 'path', 'has_frontmatter' keys
    """
    skills = []

    if not skills_dir.exists():
        logger.debug(f"AI skills directory not found: {skills_dir}")
        return []

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        description = ""
        has_frontmatter = False
        try:
            content = skill_file.read_text(encoding="utf-8")
            has_frontmatter = content.startswith("---")
            # Extract description from frontmatter or first content line
            description = _extract_skill_description(content)
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to read skill {skill_file}: {e}")

        skills.append(
            {
                "name": skill_dir.name,
                "description": description[:80] if description else "Execute skill",
                "path": str(skill_dir),
                "has_frontmatter": has_frontmatter,
            }
        )

    return skills


def _extract_skill_description(content: str) -> Optional[str]:
    """
    Extract description from a SKILL.md file.

    Checks YAML frontmatter 'description' field first, then falls back
    to the first non-header, non-comment line.
    """
    lines = content.splitlines()
    in_frontmatter = False
    frontmatter_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            if in_frontmatter:
                # End of frontmatter
                break
            else:
                in_frontmatter = True
                continue
        if in_frontmatter:
            frontmatter_lines.append(line)

    # Try parsing frontmatter for description
    if frontmatter_lines:
        try:
            import yaml

            fm = yaml.safe_load("\n".join(frontmatter_lines))
            if isinstance(fm, dict) and "description" in fm:
                return fm["description"]
        except Exception:
            # Fall back to simple parsing
            for fml in frontmatter_lines:
                if fml.strip().startswith("description:"):
                    return fml.split(":", 1)[1].strip().strip("'\"")

    # Fall back to first content line
    return extract_workflow_description_from_content(content)


def extract_workflow_description_from_content(content: str) -> Optional[str]:
    """Extract first meaningful line from markdown content."""
    in_frontmatter = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        if stripped.startswith(("#", "<!--", "//")) or not stripped:
            continue
        return stripped
    return None


def strip_yaml_frontmatter(content: str) -> str:
    """
    Strip YAML frontmatter from markdown content.

    Used by adapters for clients that don't support YAML frontmatter
    (e.g., Windsurf, Gemini).

    Note: For file-based operations, prefer parse_frontmatter() which provides
    caching and returns both frontmatter dict and clean content.

    Args:
        content: Markdown content potentially with YAML frontmatter

    Returns:
        Content with frontmatter removed
    """
    if not content.startswith("---"):
        return content

    lines = content.splitlines()
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return content

    # Return everything after the closing ---
    remaining = "\n".join(lines[end_idx + 1 :])
    return remaining.lstrip("\n")


# Cache for parsed frontmatter to avoid re-reading files
_frontmatter_cache: dict[Path, tuple[Optional[dict], str]] = {}


def parse_frontmatter(file_path: Path, use_cache: bool = True) -> tuple[Optional[dict], str]:
    """
    Parse YAML frontmatter from a markdown file.

    # TODO_IMPROVE(maintainability): Consider using 'python-frontmatter' library
    # for more robust frontmatter parsing (handles edge cases, preserves content)

    Args:
        file_path: Path to markdown file
        use_cache: Whether to use cached result if available

    Returns:
        Tuple of (frontmatter_dict, content_without_frontmatter)
        frontmatter_dict is None if no valid frontmatter found

    Example:
        >>> fm, content = parse_frontmatter(Path("workflow.md"))
        >>> fm.get("visibility")
        'core'
    """
    if use_cache and file_path in _frontmatter_cache:
        return _frontmatter_cache[file_path]

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to read file {file_path}: {e}")
        return None, ""

    if not content.startswith("---"):
        result = (None, content)
        if use_cache:
            _frontmatter_cache[file_path] = result
        return result

    # Extract frontmatter
    lines = content.splitlines()
    frontmatter_lines = []
    content_start = 1

    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            content_start = i + 1
            break
        frontmatter_lines.append(line)

    # Parse YAML
    fm = None
    if frontmatter_lines:
        try:
            import yaml

            fm = yaml.safe_load("\n".join(frontmatter_lines))
            if not isinstance(fm, dict):
                fm = None
        except Exception:
            pass

    # Get content without frontmatter
    remaining = "\n".join(lines[content_start:])
    result = (fm, remaining)

    if use_cache:
        _frontmatter_cache[file_path] = result

    return result


def clear_frontmatter_cache() -> None:
    """Clear the frontmatter cache (useful for testing or file watching)."""
    _frontmatter_cache.clear()


def scan_distributed_commands(project_root: Path) -> List[Dict]:
    """Scan SKILL.md frontmatter for x-augur-commands declarations (ADR-178).

    Discovers commands declared in per-skill SKILL.md frontmatter under
    ``project-brain/capabilities/skills/``, resolving source file paths by convention:
    - type: workflow -> {skill_dir}/commands/{id}.md
    - type: skill   -> {skill_dir}/commands/{id}/SKILL.md

    Returns list of command dicts with keys:
    - id, type, visibility, description, alias
    - source_path: absolute Path to the .md or SKILL.md file
    - plugin: skill directory name
    """
    commands = []

    for cmd, plugin_id, skill_dir in _iter_declared_commands(project_root):
        cmd_id = cmd["id"]
        cmd_type = cmd.get("type", "workflow")
        source_path = _resolve_command_source_path(skill_dir, cmd_id, cmd_type)

        if not source_path.exists():
            logger.warning(
                f"Command '{cmd_id}' declared in {plugin_id}/SKILL.md but " f"source file not found: {source_path}"
            )
            continue

        commands.append(
            {
                "id": cmd_id,
                "type": cmd_type,
                "visibility": cmd.get("visibility", "core"),
                "description": cmd.get("description", ""),
                "alias": cmd.get("alias"),
                "source_path": source_path,
                "plugin": plugin_id,
            }
        )

    return sorted(commands, key=lambda c: (c["visibility"], c["id"]))


def _resolve_command_source_path(skill_dir: Path, cmd_id: str, cmd_type: str) -> Path:
    """Resolve the expected source file path for a command declaration."""
    if cmd_type == "skill":
        return skill_dir / "commands" / cmd_id / "SKILL.md"
    return skill_dir / "commands" / f"{cmd_id}.md"


def validate_commands(project_root: Path) -> Dict[str, List[str]]:
    """Validate command declarations for parity and uniqueness (ADR-251).

    Checks:
    1. Every declared command has a matching source file.
    2. No duplicate command IDs across plugins.

    Reuses _iter_declared_commands() to avoid duplicating the SKILL.md walk
    that scan_distributed_commands() also performs.

    Returns:
        Dict with 'errors' and 'warnings' lists. Empty 'errors' means valid.
    """
    errors: List[str] = []
    warnings: List[str] = []
    id_to_plugins: Dict[str, List[str]] = {}

    for cmd, plugin_id, skill_dir in _iter_declared_commands(project_root):
        cmd_id = cmd["id"]
        cmd_type = cmd.get("type", "workflow")
        source_path = _resolve_command_source_path(skill_dir, cmd_id, cmd_type)
        has_source = source_path.exists()
        if not has_source and cmd.get("callable"):
            callable_path = skill_dir / cmd["callable"]
            has_source = callable_path.exists()
        if not has_source:
            errors.append(
                f"Command '{cmd_id}' declared in {plugin_id}/SKILL.md "
                f"but source file missing: {source_path.relative_to(project_root)}"
            )
        id_to_plugins.setdefault(cmd_id, []).append(plugin_id)

    for cmd_id, plugins in id_to_plugins.items():
        if len(plugins) > 1:
            errors.append(f"Duplicate command ID '{cmd_id}' declared in: {', '.join(plugins)}")

    return {"errors": errors, "warnings": warnings}


def _iter_declared_commands(project_root: Path):
    """Yield (cmd_dict, plugin_id, skill_dir) for every declared command.

    Reads ``x-augur-commands`` from each skill's SKILL.md frontmatter under
    ``project-brain/capabilities/skills/``.  Used by both scan_distributed_commands() and
    validate_commands().
    """
    from src.config.paths import get_project_brain_skills_dir

    skills_dir = get_project_brain_skills_dir(project_root)
    if not skills_dir.exists():
        return

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        fm, _ = parse_frontmatter(skill_file)
        if not isinstance(fm, dict):
            continue

        cmd_list = fm.get("x-augur-commands", [])
        if not isinstance(cmd_list, list):
            continue

        plugin_id = skill_dir.name
        for cmd in cmd_list:
            if not isinstance(cmd, dict) or "id" not in cmd:
                logger.warning(f"Invalid command entry in {skill_file}: {cmd}")
                continue
            yield cmd, plugin_id, skill_dir


def extract_workflow_metadata(wf_path: Path) -> tuple:
    """
    Extract visibility and alias from a workflow file's YAML frontmatter.

    Uses centralized parse_frontmatter() for consistency and caching.

    Returns:
        Tuple of (visibility, alias) where visibility is 'core'|'ops'|'hidden'
        and alias is Optional[str]. Defaults to ('core', None) if not specified.
    """
    fm, _ = parse_frontmatter(wf_path)

    if fm is None:
        return "core", None

    visibility = fm.get("visibility", "core")
    alias = fm.get("alias", None)

    return visibility, alias


def extract_workflow_description(wf_path: Path) -> Optional[str]:
    """
    Extract the description from a workflow file.

    Priority:
    1. YAML frontmatter 'description' field (via cached parse_frontmatter)
    2. First non-comment, non-header line of content

    Args:
        wf_path: Path to workflow markdown file

    Returns:
        Description string or None if not found
    """
    # 1. Try YAML frontmatter (using centralized parser with caching)
    fm, content = parse_frontmatter(wf_path)
    if fm and "description" in fm:
        return fm["description"]

    # 2. Fall back to content parsing
    try:
        # Remove frontmatter first (already done by parse_frontmatter)
        clean_content = content

        # Remove multi-line comments <!-- ... -->
        import re

        # Dotall to match newlines inside comments
        clean_content = re.sub(r'<!--.*?-->', '', clean_content, flags=re.DOTALL)

        lines = clean_content.splitlines()
        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Skip headers
            if stripped.startswith("#"):
                continue

            # Skip single line comments if any remain (e.g. // turbo)
            if stripped.startswith("//"):
                continue

            return stripped

    except OSError as e:
        logger.warning(f"Failed to read workflow {wf_path}: {e}")
    except UnicodeDecodeError as e:
        logger.warning(f"Encoding error reading workflow {wf_path}: {e}")

    return None
