#!/usr/bin/env python3
"""Manage staged release payloads under the vault drafts/staging tree."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_vault_staging_dir
from src.lib.frontmatter_utils import write_frontmatter
from src.lib.porting_payload import ensure_valid_staged_release, validate_payload_tree


def init_release(drafts_root: Path, release: str, motive: str) -> Path:
    ensure_valid_staged_release(release)

    release_root = drafts_root / release
    (release_root / "skills").mkdir(parents=True, exist_ok=True)
    pages_dir = release_root / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    keep_path = pages_dir / ".gitkeep"
    if not keep_path.exists():
        keep_path.write_text("", encoding="utf-8")

    manifest_path = release_root / "manifest.md"
    if not manifest_path.exists():
        write_frontmatter(
            manifest_path,
            {
                "release": release,
                "motive": motive,
                "skills": [],
                "pages": [],
                "prerequisites": [],
            },
            f"# {release.upper()} Payload",
        )

    return release_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage staged release payloads under the vault drafts/staging tree."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-release")
    init_parser.add_argument(
        "--drafts-root",
        default=None,
        help="Path to the staging root; defaults to the configured vault drafts/staging path.",
    )
    init_parser.add_argument("--release", required=True)
    init_parser.add_argument("--motive", required=True)

    validate_parser = subparsers.add_parser("validate-release")
    validate_parser.add_argument("--release-root", required=True)

    args = parser.parse_args(argv)

    if args.command == "init-release":
        drafts_root = (
            Path(args.drafts_root).resolve()
            if args.drafts_root is not None
            else get_vault_staging_dir()
        )
        release_root = init_release(drafts_root, args.release, args.motive)
        print(release_root)
        return 0

    try:
        validate_payload_tree(Path(args.release_root).resolve())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
