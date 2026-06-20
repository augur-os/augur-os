#!/usr/bin/env python3
"""
Context Injection for IDEs.

Reading the current active task state and updating:
1. .cursorrules (for Cursor)
2. .windsurfrules (for Windsurf) -> pointing to .cursorrules or specific if needed

Usage:
    python3 src/lib/scripts/context_injector.py [--task-id ID]
"""


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
import sys

from pathlib import Path
from src.config.paths import get_project_root, get_runtime_dir
import yaml

# Setup paths
PROJECT_ROOT = get_project_root()
AUGUR_ROOT = get_project_root()

ACTIVE_TASK_FILE = get_runtime_dir() / "active_task.yaml"
CURSOR_RULES_FILE = PROJECT_ROOT / ".cursorrules"

BASE_RULES = """# Augur Project Rules

## Core Principles
1. **Validation**: Always run `python3 .github/scripts/validate_dashboard.py` after UI changes.
2. **Architecture**: Operations layer separates Reasoning from Execution.
3. **Skills**: Implementation logic lives in `plugins/`.

## Active Context
"""


def get_active_task():
    """Load active task context."""
    if not ACTIVE_TASK_FILE.exists():
        return None
    try:
        with open(ACTIVE_TASK_FILE) as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def get_active_sprint_context():
    """Load active sprint context from sprint markdown files."""
    sprints_dir = AUGUR_ROOT / "plugins" / "core" / "skills" / "executor" / "data" / "sprints"
    if not sprints_dir.exists():
        return None

    # Get most recent sprint file
    sprint_files = sorted(sprints_dir.glob("sprint-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not sprint_files:
        return None

    latest_sprint = sprint_files[0]
    context = {"id": latest_sprint.stem, "goals": [], "items": []}

    try:
        content = latest_sprint.read_text(encoding="utf-8")
        import re

        # Extract goals
        goals_section = re.search(r'## Goals\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        if goals_section:
            for line in goals_section.group(1).split('\n'):
                if line.strip().startswith('-'):
                    context["goals"].append(line.strip()[1:].strip())

        # Extract items (looking for ### Title (pts))
        # Format: ### id: Title (X pts) or ### Title (X pts)
        item_pattern = r'###\s*(?:.+?:\s*)?(.+?)\s*\((\d+)\s*pts?\)'
        for match in re.finditer(item_pattern, content):
            title = match.group(1).strip()
            points = match.group(2)
            context["items"].append(f"{title} ({points} pts)")

        # Extract user priorities updates if present
        priorities_section = re.search(r'## Priorities Update.*?\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        if priorities_section:
            context["priorities"] = priorities_section.group(1).strip()

    except Exception:
        pass

    return context


def generate_rules(task):
    """Generate .cursorrules content."""
    content = BASE_RULES

    # Inject Sprint Context
    sprint = get_active_sprint_context()
    if sprint:
        content += f"\n## Active Sprint: {sprint['id']}\n"

        if sprint['goals']:
            content += "**Goals**:\n"
            for goal in sprint['goals']:
                content += f"- {goal}\n"

        if sprint.get('priorities'):
            content += f"\n**Latest Priorities**:\n{sprint['priorities']}\n"

        if sprint['items']:
            content += "\n**Sprint Items**:\n"
            for item in sprint['items'][:10]:  # Limit to top 10
                content += f"- {item}\n"

    if task:
        content += f"\n### Current Task: {task.get('title', 'Unknown')}\n"
        content += f"**ID**: {task.get('id', 'N/A')}\n"
        content += f"**Objective**: {task.get('objective', '')}\n"

        if "relevant_files" in task:
            content += "**Relevant Files**:\n"
            for f in task["relevant_files"]:
                content += f"- {f}\n"

        if "guidelines" in task:
            content += "**Specific Guidelines**:\n"
            if isinstance(task["guidelines"], list):
                for g in task["guidelines"]:
                    content += f"- {g}\n"
            else:
                content += f"{task['guidelines']}\n"
    else:
        content += "\n*No active task context detected.*\n"

    return content


def main():
    task = get_active_task()
    content = generate_rules(task)

    with open(CURSOR_RULES_FILE, "w") as f:
        f.write(content)

    sys.stdout.write(f"✅ Updated .cursorrules with active context: {task.get('title') if task else 'None'}\n")


if __name__ == "__main__":
    main()
