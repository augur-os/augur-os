#!/usr/bin/env python3
"""
Documentation Indexer
Indexes all skill documentation for the Librarian agent.

Usage:
    python index_docs.py [--skill NAME] [--hub HUB] [--stats]
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from bootstrap_paths import ensure_project_paths  # noqa: E402

BOOTSTRAP_ROOT = ensure_project_paths(__file__)

from src.config.paths import get_runtime_dir


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def get_repo_root() -> Path:
    """Find the repository root."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def parse_skill_md(filepath: Path) -> dict:
    """Parse a SKILL.md file and extract metadata."""
    content = filepath.read_text(encoding="utf-8")

    # Extract frontmatter
    frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    metadata = {}
    if frontmatter_match:
        for line in frontmatter_match.group(1).split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

    # Extract sections
    sections = {}
    current_section = None
    current_content = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(current_content)
            current_section = line[3:].strip()
            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content)

    # Extract commands
    commands = []
    if "Commands" in sections:
        for line in sections["Commands"].split("\n"):
            if "|" in line and "Command" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2:
                    commands.append({"command": parts[0].strip("`"), "action": parts[1]})

    # Extract version
    version_match = re.search(r"\*\*Version\*\*:\s*(\d+\.\d+\.\d+)", content)
    version = version_match.group(1) if version_match else None

    return {
        "name": metadata.get("name", filepath.parent.name),
        "description": metadata.get("description", ""),
        "commands": commands,
        "sections": list(sections.keys()),
        "version": version,
        "line_count": len(content.split("\n")),
        "path": str(filepath),
    }


def index_skill_package(skill_path: Path) -> dict | None:
    """Index an entire skill package."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return None

    index_entry = parse_skill_md(skill_md)

    # Check for references
    refs_dir = skill_path / "references"
    if refs_dir.exists():
        index_entry["references"] = [f.name for f in refs_dir.glob("*.md")]
    else:
        index_entry["references"] = []

    # Check for modules
    modules_dir = skill_path / "modules"
    if modules_dir.exists():
        index_entry["modules"] = [f.name for f in modules_dir.glob("*.md")]
    else:
        index_entry["modules"] = []

    # Check for scripts
    scripts_dir = skill_path / "scripts"
    if scripts_dir.exists():
        index_entry["scripts"] = [f.name for f in scripts_dir.glob("*.py")]
    else:
        index_entry["scripts"] = []

    return index_entry


def iter_skill_packages(plugins_dir: Path, selected_hub: str | None = None):
    """Yield (hub, skill_name, skill_path) across plugins/{hub}/skills/{skill}/."""
    for hub_dir in sorted(plugins_dir.iterdir()):
        if not hub_dir.is_dir() or hub_dir.name.startswith("."):
            continue
        if selected_hub and hub_dir.name != selected_hub:
            continue

        skills_dir = hub_dir / "skills"
        if not skills_dir.exists() or not skills_dir.is_dir():
            continue

        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            if not (skill_dir / "SKILL.md").exists():
                continue
            yield hub_dir.name, skill_dir.name, skill_dir


def build_cross_references(index: dict) -> dict:
    """Build cross-reference map between skills."""
    cross_refs = {}

    for skill_name, skill_data in index.items():
        refs = set()
        description = skill_data.get("description", "").lower()

        # Check if other skills are mentioned
        for other_skill in index.keys():
            if other_skill != skill_name:
                if other_skill.lower() in description:
                    refs.add(other_skill)

        cross_refs[skill_name] = sorted(refs)

    return cross_refs


def generate_stats(index: dict) -> dict:
    """Generate statistics about the documentation."""
    total_skills = len(index)
    total_commands = sum(len(s.get("commands", [])) for s in index.values())
    total_references = sum(len(s.get("references", [])) for s in index.values())
    total_modules = sum(len(s.get("modules", [])) for s in index.values())

    # Skills with issues
    incomplete = []
    for name, data in index.items():
        issues = []
        if data.get("line_count", 0) < 50:
            issues.append("short documentation")
        if not data.get("references"):
            issues.append("no references")
        if not data.get("version"):
            issues.append("no version")
        if issues:
            incomplete.append({"skill": name, "issues": issues})

    return {
        "total_skills": total_skills,
        "total_commands": total_commands,
        "total_references": total_references,
        "total_modules": total_modules,
        "incomplete_skills": incomplete,
        "average_line_count": sum(s.get("line_count", 0) for s in index.values()) // max(total_skills, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="Index skill documentation")
    parser.add_argument("--skill", type=str, help="Index specific skill only")
    parser.add_argument("--hub", type=str, help="Index specific plugin hub (plugins/{hub})")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")
    parser.add_argument(
        "--layer",
        type=str,
        help="Legacy alias for --hub (kept for backward compatibility)",
    )
    args = parser.parse_args()

    repo_root = get_repo_root()
    plugins_dir = repo_root / "plugins"
    selected_hub = args.hub or args.layer

    _out(f"📚 Documentation Indexer - {repo_root.name}")
    _out("=" * 50)

    if selected_hub and not (plugins_dir / selected_hub).exists():
        _out(f"❌ Hub not found: {selected_hub}")
        _out("   Tip: list hubs with `find plugins -maxdepth 1 -mindepth 1 -type d`")
        return 1

    full_index = {}
    current_hub = None

    for hub, skill_name, skill_path in iter_skill_packages(plugins_dir, selected_hub):
        if current_hub != hub:
            _out(f"\n📁 Indexing {hub} hub...")
            current_hub = hub

        if args.skill and skill_name != args.skill:
            continue

        index_entry = index_skill_package(skill_path)
        if not index_entry:
            continue

        skill_key = f"{hub}/{skill_name}"
        full_index[skill_key] = {**index_entry, "hub": hub}
        _out(
            f"   ✓ {skill_key} ({index_entry.get('line_count', 0)} lines, {len(index_entry.get('commands', []))} commands)"
        )

    # Build cross-references
    cross_refs = build_cross_references(full_index)

    # Generate stats
    stats = generate_stats(full_index)

    if args.stats:
        _out("\n📊 Statistics")
        _out(f"   Total skills: {stats['total_skills']}")
        _out(f"   Total commands: {stats['total_commands']}")
        _out(f"   Total references: {stats['total_references']}")
        _out(f"   Total modules: {stats['total_modules']}")
        _out(f"   Average doc length: {stats['average_line_count']} lines")

        if stats['incomplete_skills']:
            _out("\n⚠️  Skills needing attention:")
            for item in stats['incomplete_skills'][:10]:
                _out(f"   - {item['skill']}: {', '.join(item['issues'])}")

    # Save index
    data_dir = get_runtime_dir() / "factory" / "knowledge"
    data_dir.mkdir(parents=True, exist_ok=True)

    index_path = data_dir / "documentation_index.json"
    index_path.write_text(
        json.dumps(
            {
                "generated": datetime.now().isoformat(),
                "skills": full_index,
                "cross_references": cross_refs,
                "stats": stats,
            },
            indent=2,
        )
    )

    _out(f"\n💾 Index saved to: {index_path}")
    _out(f"✅ Indexed {len(full_index)} skills")

    return 0


if __name__ == "__main__":
    sys.exit(main())
