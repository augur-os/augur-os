#!/usr/bin/env python3
"""
Generate active config.yaml for markdown-rag plugin.

This script generates the config.yaml file with paths configured for
the current environment (standalone or Exo integration).

Usage:
    # For Exo integration (auto-detects paths)
    python3 scripts/generate_config.py

    # For standalone with custom paths
    python3 scripts/generate_config.py --data-dir ~/my-rag-data

    # Force regeneration
    python3 scripts/generate_config.py --force
"""

import argparse
import os
import sys
from pathlib import Path

import yaml


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def get_script_dir() -> Path:
    """Get the directory containing this script."""
    return Path(__file__).parent


def get_plugin_dir() -> Path:
    """Get the plugin root directory."""
    return get_script_dir().parent


def find_exo_root() -> Path | None:
    """Find the Exo project root by looking for markers."""
    current = get_plugin_dir()
    for parent in [current] + list(current.parents):
        # Look for Exo-specific markers
        if (parent / "apps" / "dashboard").exists():
            return parent
        if (parent / "CLAUDE.md").exists() and (parent / "plugins").exists():
            return parent
    return None


def find_exo_data_dir(exo_root: Path) -> Path | None:
    """Find the Exo data directory."""
    # Check for data/ in monorepo
    data_dir = exo_root / "data"
    if data_dir.exists():
        return data_dir

    # Check environment variable
    env_data = os.environ.get("AUGUR_ROOT")
    if env_data:
        return Path(env_data)

    return None


def generate_config(
    data_dir: str | None = None,
    cache_dir: str | None = None,
    project_root: str | None = None,
    force: bool = False,
) -> Path:
    """
    Generate the config.yaml file.

    Args:
        data_dir: Override data directory
        cache_dir: Override cache directory
        project_root: Override project root
        force: Overwrite existing config

    Returns:
        Path to generated config file
    """
    plugin_dir = get_plugin_dir()
    config_path = plugin_dir / "config.yaml"
    template_path = plugin_dir / "config.template.yaml"

    # Check if config already exists
    if config_path.exists() and not force:
        _out(f"Config already exists: {config_path}")
        _out("Use --force to overwrite")
        return config_path

    # Load template
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    with open(template_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Auto-detect Exo paths if not specified
    if data_dir is None or project_root is None:
        exo_root = find_exo_root()
        if exo_root:
            _out(f"Detected Exo project at: {exo_root}")

            if project_root is None:
                project_root = str(exo_root)

            if data_dir is None:
                exo_data = find_exo_data_dir(exo_root)
                if exo_data:
                    data_dir = str(exo_data / "services" / "rag")
                    _out(f"Using Exo data directory: {data_dir}")

    # Update config with paths
    if "paths" not in config:
        config["paths"] = {}

    if data_dir:
        config["paths"]["data_dir"] = data_dir

    if cache_dir:
        config["paths"]["cache_dir"] = cache_dir

    if project_root:
        config["paths"]["project_root"] = project_root

    # Write config
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write("# Auto-generated config for markdown-rag\n")
        f.write("# Edit this file to customize settings for your environment.\n")
        f.write("# This file is gitignored - your changes won't be committed.\n")
        f.write("#\n")
        f.write("# To regenerate: python3 scripts/generate_config.py --force\n")
        f.write("\n")
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    _out(f"Generated config: {config_path}")
    return config_path


def main():
    parser = argparse.ArgumentParser(description="Generate config.yaml for markdown-rag plugin")
    parser.add_argument(
        "--data-dir",
        help="Override data directory path",
    )
    parser.add_argument(
        "--cache-dir",
        help="Override cache directory path",
    )
    parser.add_argument(
        "--project-root",
        help="Override project root path",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config",
    )

    args = parser.parse_args()

    try:
        config_path = generate_config(
            data_dir=args.data_dir,
            cache_dir=args.cache_dir,
            project_root=args.project_root,
            force=args.force,
        )
        _out(f"\nConfig generated at: {config_path}")
        _out("\nTo verify, run:")
        _out(f"  cat {config_path}")

    except Exception as e:
        _out(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
