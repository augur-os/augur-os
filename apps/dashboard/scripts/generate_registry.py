#!/usr/bin/env python3
"""
Generate the unified IDE registry consumed by MCP context injection.

Canonical output:
  get_runtime_dir()/ide-integration/registry.yaml

The registry is generated from real project sources:
- Shared skills from project-brain/capabilities/skills/*/SKILL.md
- Private skills from configured vault skills roots when enabled by discovery
- Workflows from managed skill SKILL.md frontmatter (ADR-178)
- Page contexts from managed skill SKILL.md frontmatter and augur/dashboard/
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

# Bootstrap imports from monorepo root.
BOOTSTRAP_ROOT = Path(__file__).resolve().parents[3]
if str(BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_ROOT))

from src.config.paths import get_ide_registry_path, get_project_root, get_vault_config_dir, get_vault_dir  # noqa: E402
from src.lib.generated_artifacts import write_stable_yaml  # noqa: E402

PROJECT_ROOT = get_project_root().resolve()
VAULT_ROOT = get_vault_dir().resolve()
REGISTRY_OUTPUT = get_ide_registry_path().resolve()

REGISTRY_KEYS = ("skills", "workflows", "page_contexts")

# Hub to mode mapping (ADR-426: team skills live in project-brain/capabilities/skills/).
BUNDLE_MODE_MAP = {
    "brain": "operation",
    "career": "operation",
    "command": "operation",
    "life": "operation",
    "hidden": "operation",
    "studio": "dev",
    "adaptive": "dev",
}

DEV_WORKFLOWS = {
    "ci-check",
    "code-review",
    "debug-protocol",
    "dependency-audit",
    "file-bug",
    "nightly",
    "performance-profiling",
    "rebuild-ui",
    "run-coverage",
    "structure-cleanup",
    "sync-agents",
    "sync-repos",
    "auto-tech-debt",
}


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse markdown frontmatter if present."""
    if not content.startswith("---"):
        return {}, content

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content

    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            frontmatter_text = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1 :])
            try:
                parsed = yaml.safe_load(frontmatter_text) or {}
            except Exception:
                return {}, body
            if isinstance(parsed, dict):
                return parsed, body
            return {}, body

    return {}, content


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    for base in (PROJECT_ROOT, VAULT_ROOT):
        try:
            return resolved.relative_to(base).as_posix()
        except ValueError:
            continue
    return resolved.as_posix()


def _extract_skill_description(skill_md: Path, fallback: str) -> str:
    try:
        content = _read_text(skill_md)
    except OSError:
        return fallback

    frontmatter, body = _parse_frontmatter(content)
    fm_description = frontmatter.get("description")
    if isinstance(fm_description, str) and fm_description.strip():
        return fm_description.strip()

    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("#", "-", "*", "`")):
            continue
        if line.startswith("|"):  # table row
            continue
        if line.endswith(":") and " " not in line:
            continue
        return line[:160]

    return fallback


def _bundle_mode(bundle: str) -> str:
    return BUNDLE_MODE_MAP.get(bundle, "operation")


def _safe_yaml(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(_read_text(path)) or {}
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass
    return {}


def _get_discovered_skills():
    """Get canonical skill records from skill_discovery."""
    from src.plugins.skill_discovery import discover_all_skills
    return discover_all_skills(tiers=(0,), project_root=PROJECT_ROOT)


def _is_registry_skill(rec: Any) -> bool:
    """Return whether a discovered skill belongs in dashboard generator output."""
    origin = str(getattr(rec, "origin", "") or "")
    source = str(getattr(rec, "source", "") or "")
    source_root = str(getattr(rec, "source_root", "") or "")
    if "repo-root-transitional" in {origin, source, source_root}:
        return False

    try:
        Path(getattr(rec, "path")).resolve()
    except Exception:
        return False
    return True


def _iter_skill_dirs() -> list[tuple[str, Path]]:
    """Discover skill directories via canonical discovery (Phase 4b).

    Returns (hub, skill_dir) pairs, same shape as before for scan_workflows compat.
    """
    return [
        (rec.hub or "unknown", rec.path)
        for rec in _get_discovered_skills()
        if _is_registry_skill(rec)
    ]


def scan_skills() -> dict[str, dict[str, Any]]:
    """Scan all skill metadata from canonical discovery."""
    skills: dict[str, dict[str, Any]] = {}

    for rec in _get_discovered_skills():
        if not _is_registry_skill(rec):
            continue
        skill_dir = rec.path
        bundle = rec.hub or "unknown"

        actions: list[str] = []
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            for script in sorted(scripts_dir.glob("*.py")):
                if not script.name.startswith("_"):
                    actions.append(script.stem)

        fallback_description = f"{skill_dir.name} skill"
        description = rec.description or _extract_skill_description(
            skill_dir / "SKILL.md", fallback_description
        )

        try:
            rel_path = skill_dir.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            rel_path = skill_dir.as_posix()

        skills[skill_dir.name] = {
            "bundle": bundle,
            "mode": _bundle_mode(bundle),
            "path": rel_path,
            "description": description,
            "actions": actions[:10],
        }

    return skills


def scan_workflows() -> dict[str, dict[str, Any]]:
    """Scan workflow markdown files from canonical workflow sources.

    ADR-178: Merges distributed commands (from SKILL.md frontmatter)
    with ai fallback. Distributed commands take priority.
    """
    workflows: dict[str, dict[str, Any]] = {}

    # 1. ADR-178: Commands from SKILL.md frontmatter (x-augur-commands + x-augur-config.contributions.commands)
    for _hub, skill_dir in _iter_skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            content = _read_text(skill_md)
            fm, _ = _parse_frontmatter(content)
        except Exception:
            continue

        # Collect commands from both frontmatter locations
        cmd_lists: list[list[Any]] = []
        top_cmds = fm.get("x-augur-commands")
        if isinstance(top_cmds, list):
            cmd_lists.append(top_cmds)

        augur_config = fm.get("x-augur-config")
        if isinstance(augur_config, dict):
            contributions = augur_config.get("contributions", {})
            if isinstance(contributions, dict):
                nested_cmds = contributions.get("commands", [])
                if isinstance(nested_cmds, list):
                    cmd_lists.append(nested_cmds)

        for cmd_list in cmd_lists:
            for cmd in cmd_list:
                if not isinstance(cmd, dict) or "id" not in cmd:
                    continue
                name = cmd["id"]
                if name in workflows:
                    continue

                cmd_type = cmd.get("type", "workflow")
                if cmd_type == "skill":
                    source_file = skill_dir / "commands" / name / "SKILL.md"
                else:
                    source_file = skill_dir / "commands" / f"{name}.md"

                if not source_file.exists():
                    continue

                visibility = cmd.get("visibility", "core")
                mode = "dev" if visibility in ("dev", "ops", "orch") else "operation"
                description = cmd.get("description", f"Execute {name} command")

                workflows[name] = {
                    "mode": mode,
                    "description": description,
                    "file": _display_path(source_file),
                    "command": f"/{name}",
                }

    # 2. Fallback: vault config ai agent-workflows (for unmigrated commands)
    workflows_dir = get_vault_config_dir() / "ai" / "agent-workflows"
    if workflows_dir.exists():
        for workflow_file in sorted(workflows_dir.glob("*.md")):
            if workflow_file.name.startswith("_"):
                continue

            name = workflow_file.stem
            if name in workflows:
                continue

            description = f"Execute {name} workflow"
            mode = "dev" if name in DEV_WORKFLOWS else "operation"

            try:
                content = _read_text(workflow_file)
                frontmatter, _body = _parse_frontmatter(content)
                fm_description = frontmatter.get("description")
                fm_mode = frontmatter.get("mode")

                if isinstance(fm_description, str) and fm_description.strip():
                    description = fm_description.strip()
                if fm_mode in {"dev", "operation"}:
                    mode = str(fm_mode)
            except OSError:
                pass

            workflows[name] = {
                "mode": mode,
                "description": description,
                "file": _display_path(workflow_file),
                "command": f"/{name}",
            }

    return workflows


def build_page_contexts(
    skills: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build page contexts from skill bundle (hub) metadata."""
    page_contexts: dict[str, dict[str, Any]] = {}

    for skill_name, skill_meta in skills.items():
        hub_id = skill_meta.get("bundle", "")
        if not hub_id or hub_id == "unknown":
            continue

        page = f"/{hub_id}"
        entry = page_contexts.setdefault(
            page,
            {
                "mode": skill_meta["mode"],
                "skills": [],
                "workflows": [],
            },
        )

        if skill_meta["mode"] == "dev":
            entry["mode"] = "dev"

        if skill_name not in entry["skills"]:
            entry["skills"].append(skill_name)

    for page, entry in page_contexts.items():
        entry["skills"] = sorted(entry["skills"])
        entry["workflows"] = sorted(entry["workflows"])
        page_contexts[page] = entry

    return page_contexts


def build_registry() -> dict[str, Any]:
    skills = scan_skills()
    workflows = scan_workflows()
    page_contexts = build_page_contexts(skills)

    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "description": "Unified registry of all skills, workflows, and page contexts",
        "skills": skills,
        "workflows": workflows,
        "page_contexts": page_contexts,
    }


def write_registry(path: Path, registry: dict[str, Any]) -> None:
    write_stable_yaml(path, registry, volatile_keys=("generated_at",))


def load_registry(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def compare_registry(existing: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    """Return list of mismatched top-level sections."""
    mismatches: list[str] = []

    if existing.get("version") != expected.get("version"):
        mismatches.append("version")
    if existing.get("description") != expected.get("description"):
        mismatches.append("description")

    for key in REGISTRY_KEYS:
        if existing.get(key) != expected.get(key):
            mismatches.append(key)

    return mismatches


def check_registry(path: Path) -> int:
    expected = build_registry()
    existing = load_registry(path)

    if existing is None:
        print(f"❌ Registry missing or invalid: {path}")
        return 1

    mismatches = compare_registry(existing, expected)
    if mismatches:
        print(f"❌ Registry is stale ({', '.join(mismatches)} changed): {path}")
        print("   Run: python3 apps/dashboard/scripts/generate_registry.py")
        return 1

    print(f"✅ Registry is up to date: {path}")
    return 0


def generate(path: Path, quiet: bool = False) -> int:
    registry = build_registry()
    write_registry(path, registry)

    if not quiet:
        skills = registry["skills"]
        workflows = registry["workflows"]
        page_contexts = registry["page_contexts"]
        dev_skills = sum(1 for data in skills.values() if data.get("mode") == "dev")
        op_skills = len(skills) - dev_skills

        print(f"✅ Generated registry at {path}")
        print(
            f"   Skills: {len(skills)} ({dev_skills} dev, {op_skills} operation), "
            f"Workflows: {len(workflows)}, Pages: {len(page_contexts)}"
        )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate unified IDE registry")
    parser.add_argument(
        "--output",
        default=str(REGISTRY_OUTPUT),
        help="Registry output file path (default: runtime ide-integration/registry.yaml)",
    )
    parser.add_argument("--check", action="store_true", help="Validate that the registry is up to date")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-error output")
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve()
    if args.check:
        return check_registry(output_path)
    return generate(output_path, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
