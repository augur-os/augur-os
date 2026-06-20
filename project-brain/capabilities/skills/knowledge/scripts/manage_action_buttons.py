#!/usr/bin/env python3
"""
Manage Action Buttons
Skill to create and manage 'Action Buttons' in the system.
Updates action_buttons.yaml and creates template files.
"""

import argparse
import sys
from pathlib import Path

import yaml

from bootstrap_paths import ensure_project_paths


_PROJECT_ROOT = ensure_project_paths(__file__)


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


try:
    from src.config.paths import get_project_root
except ImportError:
    sys.path.insert(0, str(_PROJECT_ROOT))
    from src.config.paths import get_project_root  # noqa: E402


def load_config(config_path):
    if not config_path.exists():
        return {"buttons": []}
    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {"buttons": []}


def save_config(config_path, data):
    with open(config_path, "w") as f:
        yaml.dump(data, f, sort_keys=False, default_flow_style=False)


def create_button(args):
    data_dir = get_project_root()  # Should return correct augur from environment/config
    # Fallback if path resolution implies a different configured root.
    # Prefer the current Augur project root in this scripting context.

    # Logic: Use the configured data directory
    data_repo = data_dir

    config_path = data_repo / "config" / "action_buttons.yaml"
    templates_dir = data_repo / "knowledge" / "prompts" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(config_path)

    # Check if id exists
    existing = next((b for b in config["buttons"] if b["id"] == args.id), None)

    if existing and not args.force:
        _out(f"Error: Button with ID '{args.id}' already exists. Use --force to update.")
        return False

    # Create Template
    template_filename = f"{args.id}.md"
    template_path = templates_dir / template_filename

    if args.template_content:
        content = args.template_content
    elif args.template_file:
        with open(args.template_file, 'r') as f:
            content = f.read()
    else:
        content = f"# {args.name}\n\nRunning action: {args.name}\n\nCONTEXT: {{{{user_context}}}}\n"

    with open(template_path, "w") as f:
        f.write(content)

    if existing:
        # Build new button starting from existing to preserve extra fields like 'evals'
        new_button = existing.copy()
        new_button.update(
            {
                "id": args.id,
                "name": args.name or args.id,
                "description": args.description or f"Action: {args.name}",
                "mode": args.mode,
                "template_path": template_filename,
            }
        )
    else:
        new_button = {
            "id": args.id,
            "name": args.name or args.id,
            "description": args.description or f"Action: {args.name}",
            "mode": args.mode,
            "template_path": template_filename,
        }

    if args.category:
        new_button["category"] = args.category

    if args.tool:
        new_button["tool"] = args.tool

    if existing:
        # Update existing
        index = config["buttons"].index(existing)
        config["buttons"][index] = new_button
        _out(f"Updated button '{args.id}'")
    else:
        config["buttons"].append(new_button)
        _out(f"Created button '{args.id}'")

    save_config(config_path, config)
    return True


def main():
    parser = argparse.ArgumentParser(description="Manage Action Buttons")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create
    create_parser = subparsers.add_parser("create", help="Create or update an action button")
    create_parser.add_argument("--id", required=True, help="Unique ID (slug) for the button")
    create_parser.add_argument("--name", required=True, help="Display Name")
    create_parser.add_argument("--description", help="Description")
    create_parser.add_argument("--mode", default="ide", choices=["ide", "local", "remote"], help="Execution Mode")
    create_parser.add_argument("--category", help="Button Category (e.g. development, verification)")
    create_parser.add_argument("--tool", help="Specific tool to use")
    create_parser.add_argument("--template-content", help="Inline template Markdown content")
    create_parser.add_argument("--template-file", help="Path to template Markdown file")
    create_parser.add_argument("--force", action="store_true", help="Overwrite existing button")

    args = parser.parse_args()

    if args.command == "create":
        create_button(args)


if __name__ == "__main__":
    main()
