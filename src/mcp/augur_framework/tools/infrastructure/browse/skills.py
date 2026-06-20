"""Skill content listing tools: prompts, scripts, and command docs."""

import json
import re

import yaml
from src.config.paths import get_project_brain_skills_dir, get_project_root


def _read_markdown_frontmatter(path) -> tuple[dict, str]:
    content = path.read_text(errors="ignore")
    fm_match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
    if not fm_match:
        return {}, content
    try:
        frontmatter = yaml.safe_load(fm_match.group(1))
    except Exception:
        frontmatter = {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    return frontmatter, content[fm_match.end() :]


def _first_body_line(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("<"):
            return stripped
    return ""


async def list_prompts_impl() -> str:
    """List all prompt templates across skills.

    Scans Agent Skills ``prompts/`` directories, older command-doc prompts,
    and legacy seed prompt files.
    """
    project_root = get_project_root()
    skills_dir = get_project_brain_skills_dir(project_root)
    items: list[dict] = []
    if not skills_dir.exists():
        return json.dumps({"items": [], "count": 0})

    # Primary source: managed project skills' prompts/*.md
    for prompt_file in sorted(skills_dir.glob("*/prompts/*.md")):
        parts = prompt_file.relative_to(skills_dir).parts
        if len(parts) < 3:
            continue
        skill = parts[0]
        fm, body = _read_markdown_frontmatter(prompt_file)
        prompt_id = fm.get("id", prompt_file.stem)
        label = fm.get("label") or str(prompt_id).replace("-", " ").title()
        description = fm.get("description") or _first_body_line(body) or f"Prompt template for {skill}"

        items.append(
            {
                "id": f"{skill}/prompts/{prompt_id}",
                "title": label,
                "description": description,
                "hub": skill,
                "skill": skill,
                "source": "skill",
                "path": str(prompt_file),
                "file_type": "md",
            }
        )

    # Older source: managed project skills' commands/*.md with ``skill:`` frontmatter
    for prompt_file in sorted(skills_dir.glob("*/commands/*.md")):
        parts = prompt_file.relative_to(skills_dir).parts
        if len(parts) < 3:
            continue
        skill = parts[0]

        # Parse frontmatter to distinguish prompts from CLI command docs
        fm, _body = _read_markdown_frontmatter(prompt_file)

        # Only include files that have the ``skill`` field (prompt files)
        if "skill" not in fm:
            continue

        prompt_id = fm.get("id", prompt_file.stem)
        description = fm.get("description", f"Prompt template for {skill}")

        items.append(
            {
                "id": f"{skill}/prompts/{prompt_id}",
                "title": prompt_id.replace("-", " ").title(),
                "description": description,
                "hub": skill,
                "skill": skill,
                "source": "skill",
                "path": str(prompt_file),
                "file_type": "md",
            }
        )

    # Legacy source: managed project skills' assets/seeds/prompts/*.md (e.g. ide-prompt-.md)
    for prompt_file in sorted(skills_dir.glob("*/assets/seeds/prompts/*.md")):
        parts = prompt_file.relative_to(skills_dir).parts
        if len(parts) >= 4:
            skill = parts[0]
            items.append(
                {
                    "id": f"{skill}/prompts/{prompt_file.stem}",
                    "title": prompt_file.stem.replace("-", " ").title(),
                    "description": f"Prompt template for {skill}",
                    "hub": skill,
                    "skill": skill,
                    "source": "skill",
                    "path": str(prompt_file),
                    "file_type": "md",
                }
            )

    # ADR-748 + ADR-751: user-saved prompts from the vault.
    # Per ADR-751 prompt cards carry `x-augur-note-type: prompt` frontmatter
    # (alongside other note kinds). write_prompt_card lands them in the brain's
    # capture dir (knowledge/notes legacy; inbox/ domains) — scan the same dir.
    # Local import so tests can monkeypatch paths._vault_home_dir before this
    # resolves — get_vault_dir() caches on first call (ADR-748).
    from src.config.paths import get_vault_dir
    from src.lib.brain_layout import brain_capture_dir, is_machine_path

    vault_root = get_vault_dir()
    vault_capture_dir = brain_capture_dir(vault_root)
    if vault_capture_dir.is_dir():
        for prompt_file in sorted(vault_capture_dir.glob("*.md")):
            if prompt_file.is_symlink() or is_machine_path(vault_root, prompt_file):
                continue
            fm, body = _read_markdown_frontmatter(prompt_file)
            # Filter to prompt-type notes — notes/ also holds url-ingest cards
            # and other note kinds that aren't prompts.
            if str(fm.get("x-augur-note-type") or "").strip() != "prompt":
                continue
            prompt_id = fm.get("id", prompt_file.stem)
            label = fm.get("label") or str(prompt_id).replace("-", " ").title()
            description = fm.get("description") or _first_body_line(body) or "User-saved prompt"
            items.append(
                {
                    "id": f"vault/prompts/{prompt_id}",
                    "title": label,
                    "description": description,
                    "hub": "workspace",  # ADR-748: vault prompts live in the Workspace hub
                    "skill": None,
                    "source": "vault",
                    "path": str(prompt_file),
                    "file_type": "md",
                }
            )

    return json.dumps({"items": items, "count": len(items)})


async def list_scripts_impl() -> str:
    """List all scripts across skills."""
    project_root = get_project_root()
    skills_dir = get_project_brain_skills_dir(project_root)
    items = []
    if not skills_dir.exists():
        return json.dumps({"items": [], "count": 0})
    for script_file in sorted(skills_dir.glob("*/scripts/*")):
        if not script_file.is_file() or script_file.name.startswith("."):
            continue
        parts = script_file.relative_to(skills_dir).parts
        if len(parts) >= 3:
            skill = parts[0]
            ext = script_file.suffix.lstrip(".")
            lang = "Python" if ext == "py" else "Shell" if ext in ("sh", "bash") else ext
            items.append(
                {
                    "id": f"{skill}/scripts/{script_file.name}",
                    "title": script_file.stem,
                    "description": f"{lang} script for {skill}",
                    "skill": skill,
                    "path": str(script_file),
                    "language": lang,
                }
            )
    return json.dumps({"items": items, "count": len(items)})


async def list_cli_commands_impl() -> str:
    """List explicit command docs from managed project skills' commands/*.md.

    Prompt files live in the same folder after the prompt extraction migration,
    so any file with a ``skill`` frontmatter key is treated as a prompt and
    excluded from the command listing.
    """
    project_root = get_project_root()
    skills_dir = get_project_brain_skills_dir(project_root)
    items: list[dict] = []
    if not skills_dir.exists():
        return json.dumps({"items": [], "count": 0})

    for cmd_file in sorted(skills_dir.glob("*/commands/*.md")):
        parts = cmd_file.relative_to(skills_dir).parts
        if len(parts) < 3:
            continue
        skill = parts[0]

        content = cmd_file.read_text(errors="ignore")
        fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            continue
        try:
            fm = yaml.safe_load(fm_match.group(1))
        except Exception:
            continue
        if not isinstance(fm, dict):
            continue

        # Skip prompt files (they have ``skill`` field from the migration)
        if "skill" in fm:
            continue

        description = fm.get("description", "")
        visibility = fm.get("visibility", "")
        cmd_name = cmd_file.stem
        cmd_id = f"/{cmd_name}"

        # Hub-derived categorization removed with ADR-802; visibility is the
        # only remaining signal.
        hub = ""
        category = visibility.upper() if visibility else "APP"

        items.append(
            {
                "id": cmd_id,
                "title": cmd_id,
                "description": description,
                "hub": hub,
                "skill": skill,
                "path": str(cmd_file),
                "category": category,
            }
        )

    return json.dumps({"items": items, "count": len(items)})
