#!/usr/bin/env python3
"""
Checkpoint Manager - Development savepoints for safe experimentation.

Creates named checkpoints using git tags for easy rollback during development.

Usage:
    python3 checkpoint_manager.py create "name" [--stash] [--message "desc"]
    python3 checkpoint_manager.py list
    python3 checkpoint_manager.py restore "name" [--hard]
    python3 checkpoint_manager.py delete "name"
"""

import argparse
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class Checkpoint:
    """A development checkpoint."""
    name: str
    tag: str
    commit: str
    branch: str
    created: str
    message: Optional[str] = None
    had_stash: bool = False
    stash_ref: Optional[str] = None


class CheckpointManager:
    """Manage development checkpoints using git tags."""

    TAG_PREFIX = "checkpoint/"

    def __init__(self):
        self.project_root = self._get_project_root()
        self.registry_path = self._get_registry_path()
        self.checkpoints = self._load_registry()

    def _get_project_root(self) -> Path:
        """Get project root using git."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True
            )
            return Path(result.stdout.strip())
        except subprocess.CalledProcessError:
            return Path(__file__).parent.parent.parent

    def _get_registry_path(self) -> Path:
        """Get path to checkpoints registry (runtime, gitignored)."""
        runtime_dir = self.project_root / "data" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        return runtime_dir / "checkpoints.yaml"

    def _load_registry(self) -> list[Checkpoint]:
        """Load checkpoints from registry file."""
        if not self.registry_path.exists():
            return []

        content = self.registry_path.read_text()
        if not content.strip():
            return []

        if HAS_YAML:
            data = yaml.safe_load(content) or {}
        else:
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return []

        return [Checkpoint(**cp) for cp in data.get("checkpoints", [])]

    def _save_registry(self):
        """Save checkpoints to registry file."""
        data = {
            "version": "1.0",
            "description": "Development checkpoint registry",
            "last_updated": datetime.now().isoformat(),
            "checkpoints": [asdict(cp) for cp in self.checkpoints],
        }

        if HAS_YAML:
            content = yaml.dump(data, default_flow_style=False, sort_keys=False)
        else:
            content = json.dumps(data, indent=2)

        self.registry_path.write_text(content)

    def _run_git(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command."""
        return subprocess.run(
            ["git"] + args,
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
            check=check
        )

    def _get_current_commit(self) -> str:
        """Get current HEAD commit hash (short)."""
        result = self._run_git(["rev-parse", "--short", "HEAD"])
        return result.stdout.strip()

    def _get_current_branch(self) -> str:
        """Get current branch name."""
        result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return result.stdout.strip()

    def _has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        result = self._run_git(["status", "--porcelain"], check=False)
        return bool(result.stdout.strip())

    def _make_tag_name(self, name: str) -> str:
        """Generate tag name with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{self.TAG_PREFIX}{name}-{timestamp}"

    def create(
        self,
        name: str,
        stash: bool = False,
        message: Optional[str] = None,
        force: bool = False
    ) -> Checkpoint:
        """Create a new checkpoint."""
        # Validate name
        if not name or "/" in name or " " in name:
            raise ValueError("Checkpoint name must be non-empty and cannot contain '/' or spaces")

        # Check if name already exists
        existing = next((cp for cp in self.checkpoints if cp.name == name), None)
        if existing and not force:
            raise ValueError(
                f"Checkpoint '{name}' already exists (created {existing.created[:10]}). "
                f"Use --force to overwrite."
            )

        # Handle uncommitted changes
        had_stash = False
        stash_ref = None

        if self._has_uncommitted_changes():
            if stash:
                print("📦 Stashing uncommitted changes...")
                self._run_git(["stash", "push", "-m", f"checkpoint-{name}"])
                had_stash = True
                # Get stash reference
                result = self._run_git(["stash", "list", "--format=%gd", "-n", "1"])
                stash_ref = result.stdout.strip() or "stash@{0}"
            else:
                print("⚠️  Warning: You have uncommitted changes. Consider using --stash")

        # Get current state
        commit = self._get_current_commit()
        branch = self._get_current_branch()
        tag_name = self._make_tag_name(name)

        # Create annotated tag
        tag_message = message or f"Checkpoint: {name}"
        self._run_git(["tag", "-a", tag_name, "-m", tag_message])

        # Create checkpoint record
        checkpoint = Checkpoint(
            name=name,
            tag=tag_name,
            commit=commit,
            branch=branch,
            created=datetime.now().isoformat(),
            message=message,
            had_stash=had_stash,
            stash_ref=stash_ref
        )

        # Remove existing if force
        if existing:
            self.checkpoints = [cp for cp in self.checkpoints if cp.name != name]
            # Delete old tag
            self._run_git(["tag", "-d", existing.tag], check=False)

        self.checkpoints.append(checkpoint)
        self._save_registry()

        print(f"\n✅ Checkpoint '{name}' created")
        print(f"   Tag: {tag_name}")
        print(f"   Commit: {commit}")
        print(f"   Branch: {branch}")
        if had_stash:
            print(f"   Stash: {stash_ref}")
        print(f"\n   To restore: python3 {Path(__file__).name} restore \"{name}\"")

        return checkpoint

    def list_checkpoints(self):
        """List all checkpoints."""
        if not self.checkpoints:
            print("\n📋 No checkpoints found.\n")
            print("   Create one with: python3 checkpoint_manager.py create \"name\"")
            return

        print(f"\n📋 Checkpoints ({len(self.checkpoints)}):\n")

        # Sort by creation date (newest first)
        sorted_cps = sorted(self.checkpoints, key=lambda x: x.created, reverse=True)

        for cp in sorted_cps:
            stash_indicator = " 📦" if cp.had_stash else ""
            print(f"  • {cp.name}{stash_indicator}")
            print(f"    Commit: {cp.commit} | Branch: {cp.branch}")
            print(f"    Created: {cp.created[:19].replace('T', ' ')}")
            if cp.message:
                print(f"    Message: {cp.message}")
            print()

    def restore(
        self,
        name: str,
        hard: bool = False
    ):
        """Restore to a checkpoint."""
        checkpoint = next((cp for cp in self.checkpoints if cp.name == name), None)
        if not checkpoint:
            available = [cp.name for cp in self.checkpoints]
            raise ValueError(
                f"Checkpoint '{name}' not found. "
                f"Available: {', '.join(available) if available else 'none'}"
            )

        # Check for uncommitted changes
        if self._has_uncommitted_changes():
            if hard:
                print("⚠️  Warning: --hard will discard all uncommitted changes!")
                try:
                    confirm = input("   Continue? [y/N]: ").lower().strip()
                    if confirm != 'y':
                        print("   Aborted.")
                        return
                except EOFError:
                    print("   Non-interactive mode, aborting for safety.")
                    return
            else:
                print("❌ You have uncommitted changes.")
                print("   Options:")
                print("     1. Use --hard to discard them")
                print("     2. Commit or stash your changes first")
                print("     3. Create a new checkpoint before restoring")
                return

        # Perform restore
        if hard:
            self._run_git(["reset", "--hard", checkpoint.tag])
            print(f"\n✅ Hard reset to checkpoint '{name}'")
        else:
            # Checkout the tag (detached HEAD)
            self._run_git(["checkout", checkpoint.tag])
            print(f"\n✅ Checked out checkpoint '{name}'")
            print("   ⚠️  You are in 'detached HEAD' state.")
            print(f"   To return to branch: git checkout {checkpoint.branch}")

        print(f"   Commit: {checkpoint.commit}")

        # Handle stash
        if checkpoint.had_stash and checkpoint.stash_ref:
            print(f"\n📦 This checkpoint had stashed changes: {checkpoint.stash_ref}")
            try:
                apply = input("   Apply stashed changes? [y/N]: ").lower().strip()
                if apply == 'y':
                    result = self._run_git(["stash", "pop", checkpoint.stash_ref], check=False)
                    if result.returncode == 0:
                        print("   ✅ Stashed changes applied.")
                    else:
                        print(f"   ⚠️  Could not apply stash: {result.stderr.strip()}")
            except EOFError:
                print("   Skipping stash application (non-interactive).")

    def delete(self, name: str):
        """Delete a checkpoint."""
        checkpoint = next((cp for cp in self.checkpoints if cp.name == name), None)
        if not checkpoint:
            raise ValueError(f"Checkpoint '{name}' not found.")

        # Delete git tag
        self._run_git(["tag", "-d", checkpoint.tag], check=False)

        # Remove from registry
        self.checkpoints = [cp for cp in self.checkpoints if cp.name != name]
        self._save_registry()

        print(f"✅ Checkpoint '{name}' deleted.")


def main():
    parser = argparse.ArgumentParser(
        description="Checkpoint Manager - Development savepoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create "pre-refactor" --message "Before auth changes"
  %(prog)s create "experiment" --stash
  %(prog)s list
  %(prog)s restore "pre-refactor"
  %(prog)s restore "pre-refactor" --hard
  %(prog)s delete "old-checkpoint"
        """
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create
    create_parser = subparsers.add_parser("create", help="Create a checkpoint")
    create_parser.add_argument("name", help="Checkpoint name (no spaces or slashes)")
    create_parser.add_argument("--stash", action="store_true",
                               help="Stash uncommitted changes")
    create_parser.add_argument("--message", "-m", help="Checkpoint description")
    create_parser.add_argument("--force", action="store_true",
                               help="Overwrite existing checkpoint with same name")

    # List
    subparsers.add_parser("list", help="List all checkpoints")

    # Restore
    restore_parser = subparsers.add_parser("restore", help="Restore to a checkpoint")
    restore_parser.add_argument("name", help="Checkpoint name")
    restore_parser.add_argument("--hard", action="store_true",
                                help="Hard reset (discard uncommitted changes)")

    # Delete
    delete_parser = subparsers.add_parser("delete", help="Delete a checkpoint")
    delete_parser.add_argument("name", help="Checkpoint name")

    args = parser.parse_args()
    manager = CheckpointManager()

    try:
        if args.command == "create":
            manager.create(args.name, args.stash, args.message, args.force)
        elif args.command == "list":
            manager.list_checkpoints()
        elif args.command == "restore":
            manager.restore(args.name, args.hard)
        elif args.command == "delete":
            manager.delete(args.name)
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"❌ Git error: {e.stderr.strip()}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
