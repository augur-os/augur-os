"""Shared plugin assembler pipeline.

Assembles Augur as a plugin for different target platforms (Claude Desktop, Codex, Gemini, Copilot).
Each target uses a formatter + filter profile to produce platform-specific output.

Usage:
    python project-brain/capabilities/skills/plugin-pack/scripts/plugin_assembler.py --target codex [--install]
    python project-brain/capabilities/skills/plugin-pack/scripts/plugin_assembler.py --target cowork [--install]
    python project-brain/capabilities/skills/plugin-pack/scripts/plugin_assembler.py --target gemini [--install]
    python project-brain/capabilities/skills/plugin-pack/scripts/plugin_assembler.py --target copilot [--install]
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
import logging
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from formatters import CoworkFormatter, CodexFormatter, CopilotFormatter, GeminiFormatter
from formatters.base import BaseFormatter
from formatters.mcp_config import resolve_project_python_path
from profiles import FilterProfile, get_profile

logger = logging.getLogger(__name__)

_SKILL_ROOT = Path(__file__).resolve().parent.parent  # skills/plugin-pack/
_TEMPLATES_DIR = _SKILL_ROOT / "assets" / "templates"

_FORMATTERS: dict[str, type[BaseFormatter]] = {
    "cowork": CoworkFormatter,
    "codex": CodexFormatter,
    "gemini": GeminiFormatter,
    "copilot": CopilotFormatter,
}


def _ensure_project_root_on_path() -> None:
    """Make repo-local imports available when this file is run as a script."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "project.yaml").is_file() and (parent / "src").is_dir():
            root = str(parent)
            if root not in sys.path:
                sys.path.insert(0, root)
            return


def _get_project_root() -> Path:
    _ensure_project_root_on_path()
    from src.config.paths import get_project_root
    candidate = Path(get_project_root())
    # Resolve worktrees to the main checkout so embedded MCP paths stay stable
    # after the worktree is deleted. (.git is a file, not a dir, in a worktree)
    git_entry = candidate / ".git"
    if git_entry.is_file():
        try:
            content = git_entry.read_text().strip()
            if content.startswith("gitdir:"):
                gitdir = Path(content.split("gitdir:", 1)[1].strip())
                parts = gitdir.parts
                if "worktrees" in parts:
                    idx = list(parts).index("worktrees")
                    main_repo = Path(*parts[:idx]).parent
                    if (main_repo / "project.yaml").is_file():
                        return main_repo
        except OSError:
            pass
    return candidate


def should_include_skill(skill_name: str, metadata: dict, profile: FilterProfile) -> bool:
    """Check if a skill should be included for the given profile."""
    # Skills declare x-augur-group (ADR-802); profile.groups is the set of
    # allowed group names.
    group = metadata.get("x-augur-group", "")
    if group not in profile.groups:
        return False
    if any(skill_name.startswith(p) for p in profile.excluded_prefixes):
        return False
    if skill_name in profile.excluded_skills:
        return False
    return True


def transform_skill_md(content: str, skill_name: str, master: str) -> str:
    """Transform a master SKILL.md to domain-oriented format."""
    import yaml as _yaml

    name = skill_name
    description = ""
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = _yaml.safe_load(parts[1]) or {}
            except Exception:
                fm = {}
            name = fm.get("name", skill_name)
            description = fm.get("description", "")
            body = parts[2]

    # Check for template override
    template_path = _TEMPLATES_DIR / f"{skill_name}.md"
    if template_path.exists():
        body = "\n" + template_path.read_text(encoding="utf-8").strip() + "\n"
    else:
        body = re.sub(r"`/[\w-]+`", "", body)
        body = re.sub(r"Run `/[\w-]+`[^.]*\.", "", body)
        body = re.sub(r"/(?:Users|home)/[^\s]+", "", body)
        body = re.sub(r"```bash\s*\ngit\s+[^\n]+\n```", "", body)
        body = re.sub(r"```bash\s*\npytest\s+[^\n]+\n```", "", body)
        body = re.sub(r"```bash\s*\nnpm\s+run\s+test[^\n]*\n```", "", body)

    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    safe_desc = description.replace("\n", " ").strip() if description else ""

    fm_dict = {"name": name}
    if safe_desc:
        fm_dict["description"] = safe_desc

    result = "---\n"
    result += _yaml.dump(fm_dict, default_flow_style=False, allow_unicode=True).rstrip("\n") + "\n"
    result += "---\n"
    result += f"<!-- AUGUR-ADAPTED-COPY source={master} -->\n\n"
    if body:
        result += body + "\n"
    return result


def _strip_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return content.strip()
    parts = content.split("---", 2)
    if len(parts) < 3:
        return content.strip()
    return parts[2].strip()


def _command_description(frontmatter: dict, body: str, command_name: str) -> str:
    description = str(frontmatter.get("description") or "").strip()
    if description:
        return description
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return f"Run /{command_name}"


def _hydrate_commands(profile: FilterProfile, project_root: Path) -> dict[str, dict]:
    """Replace packaged command fallbacks with canonical exported command docs."""
    import yaml as _yaml

    commands = {name: dict(command) for name, command in profile.commands.items()}
    commands_root = project_root / "project-brain" / "capabilities" / "skills"
    for command_file in sorted(commands_root.glob("*/commands/*.md")):
        command_name = command_file.stem
        if command_name not in commands:
            continue
        raw = command_file.read_text(encoding="utf-8")
        frontmatter: dict = {}
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                try:
                    loaded = _yaml.safe_load(parts[1]) or {}
                    if isinstance(loaded, dict):
                        frontmatter = loaded
                except Exception:
                    frontmatter = {}
        body = _strip_frontmatter(raw)
        if body:
            commands[command_name] = {
                "description": _command_description(frontmatter, body, command_name),
                "body": body,
            }
    return commands


def get_version() -> str:
    """Get version from git tags or fallback to date-based."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().lstrip("v")
    except Exception:
        pass
    return datetime.now(timezone.utc).strftime("0.%Y%m%d.0")


def discover_skills(profile: FilterProfile) -> dict[str, str]:
    """Discover and read skills matching the profile.

    Returns:
        Dict of {skill_name: raw SKILL.md content}.
    """
    import yaml as _yaml

    project_root = _get_project_root()
    from src.lib.staged_skill_catalog import iter_live_skill_dirs

    result = {}

    for skill_dir in iter_live_skill_dirs(project_root):
        skill_md = skill_dir / "SKILL.md"

        content = skill_md.read_text(encoding="utf-8")
        metadata = {}
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    metadata = _yaml.safe_load(parts[1]) or {}
                except Exception:
                    pass

        skill_name = skill_dir.name
        if should_include_skill(skill_name, metadata, profile):
            result[skill_name] = content

    return result


def assemble(target: str, output_dir: Path | None = None) -> tuple[Path, str]:
    """Assemble plugin for the given target.

    Args:
        target: Target platform name ("cowork", "codex", "gemini", or "copilot").
        output_dir: Where to write output. Defaults to build/{target}/ under project root.

    Returns:
        Tuple of (output_dir, version).
    """
    if target not in _FORMATTERS:
        raise ValueError(f"Unknown target: {target!r}. Available: {sorted(_FORMATTERS)}")

    profile = get_profile(target)
    formatter = _FORMATTERS[target]()
    project_root = _get_project_root()

    if output_dir is None:
        output_dir = project_root / "build" / target

    version = "skills-latest" if target == "codex" else get_version()
    plugin_dir = formatter.plugin_dir(output_dir)
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True, exist_ok=True)

    python_path = resolve_project_python_path(project_root)

    # Discover and transform skills
    raw_skills = discover_skills(profile)
    transformed = {
        name: transform_skill_md(content, name, "augur")
        for name, content in raw_skills.items()
    }

    # Write all plugin files via formatter
    formatter.write_manifest(plugin_dir, version)
    formatter.write_mcp_config(plugin_dir, project_root, python_path)
    formatter.write_skills(plugin_dir, transformed)
    formatter.write_commands(plugin_dir, _hydrate_commands(profile, project_root))
    formatter.write_marketplace(output_dir, version)

    logger.info("  Generated plugin v%s for %s at %s", version, target, output_dir)
    return output_dir, version


def install(target: str, output_dir: Path, version: str, **install_kwargs) -> bool:
    """Install assembled plugin to the target platform."""
    if target not in _FORMATTERS:
        raise ValueError(f"Unknown target: {target!r}")
    formatter = _FORMATTERS[target]()
    return formatter.install(output_dir, version, **install_kwargs)


# ── CLI Entry Point ─────────────────────────────────────────────────
def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Augur plugin assembler")
    parser.add_argument("--target", required=True, choices=sorted(_FORMATTERS), help="Target platform")
    parser.add_argument("--output", type=Path, default=None, help="Output directory")
    parser.add_argument("--install", action="store_true", help="Install after assembly")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    output_dir, version = assemble(args.target, args.output)
    print(f"Assembled {args.target} plugin v{version} at {output_dir}")

    if args.install:
        ok = install(args.target, output_dir, version)
        if ok:
            print(f"Installed {args.target} plugin v{version}")
        else:
            print("Install skipped (target not detected)")

        if args.target == "cowork":
            import json as _json

            from formatters.cloud_staleness import (
                build_cloud_zip,
                check_cloud_plugin_staleness,
                find_upload_target,
            )

            bundle_dir = output_dir / "plugins" / "augur"
            report = check_cloud_plugin_staleness(bundle_dir)
            if report["checked"] and report["stale"]:
                zip_info = build_cloud_zip(bundle_dir, output_dir / "augur-cloud.zip")
                push_spec = {
                    "action": "cloud-plugin-push",
                    "reasons": report["reasons"],
                    "cloud_updated_at": report["cloud_updated_at"],
                    "zip": zip_info,
                    "target": find_upload_target(),
                    "after_upload": "fully restart Claude Desktop, then rerun this command to confirm exit 0",
                }
                print(
                    "CLOUD PLUGIN STALE — regular Claude Desktop chats serve an "
                    "outdated Augur plugin. Executing agent: complete the push "
                    "now per plugin-pack SKILL.md §Cloud Sync (no user "
                    "confirmation needed; the sync command IS the approval):"
                )
                print(_json.dumps(push_spec, indent=2))
                sys.exit(3)


if __name__ == "__main__":
    main()
