#!/usr/bin/env python3
"""augur config fix — discover moved vault/documents and update project.yaml."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Fix stale paths in project.yaml")
    parser.add_argument("--deep", action="store_true", help="Include /Volumes scan")
    args = parser.parse_args()

    from src.config.paths import get_vault_dir, get_documents_dir, get_project_paths, get_skills_dir
    from src.config.path_discovery import (
        create_marker,
        discover_path,
        prompt_update,
        update_project_yaml,
        default_search_roots,
    )

    project_paths = get_project_paths()
    checks = [
        ("vault", project_paths.get("vault")),
        ("documents", project_paths.get("documents")),
    ]

    for path_type, configured in checks:
        if configured is None:
            print(f"  {path_type}: not configured in project.yaml, skipping")
            continue
        if configured.exists():
            print(f"  {path_type}: OK at {configured}")
            create_marker(path_type, configured)
            continue

        search_roots = default_search_roots(configured)
        if args.deep:
            volumes = Path("/Volumes")
            if volumes.exists():
                search_roots.append(volumes)

        discovered = discover_path(
            path_type,
            configured=configured,
            skills_dir=get_skills_dir(),
            search_roots=search_roots,
        )
        if discovered:
            if prompt_update(path_type, configured, discovered):
                update_project_yaml(path_type, discovered)
                create_marker(path_type, discovered)
                print(f"  {path_type}: updated to {discovered}")
            else:
                print(f"  {path_type}: skipped (user declined)")
        else:
            print(f"  {path_type}: NOT FOUND (configured: {configured})")

    # Regenerate daemon plist with updated paths
    plist = Path.home() / "Library" / "LaunchAgents" / "com.augur.daemon.plist"
    if plist.exists():
        try:
            import plistlib

            with open(plist, "rb") as f:
                plist_data = plistlib.load(f)
            env = plist_data.get("EnvironmentVariables", {})
            vault_path = get_vault_dir()
            docs_path = get_documents_dir()
            changed = False
            if str(env.get("AUGUR_VAULT")) != str(vault_path):
                env["AUGUR_VAULT"] = str(vault_path)
                changed = True
            if str(env.get("AUGUR_DOCUMENTS")) != str(docs_path):
                env["AUGUR_DOCUMENTS"] = str(docs_path)
                changed = True
            if changed:
                plist_data["EnvironmentVariables"] = env
                with open(plist, "wb") as f:
                    plistlib.dump(plist_data, f)
                print("\nUpdated daemon plist paths")
        except Exception as e:
            print(f"\nWarning: could not update daemon plist: {e}")

    print("\nDone. Restart the daemon to pick up changes:")
    print("  launchctl unload ~/Library/LaunchAgents/com.augur.daemon.plist")
    print("  launchctl load -w ~/Library/LaunchAgents/com.augur.daemon.plist")


if __name__ == "__main__":
    main()
