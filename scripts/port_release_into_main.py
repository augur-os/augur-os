#!/usr/bin/env python3
"""Port a staged release from vault drafts/staging into the main tree."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_project_brain_skills_dir, get_vault_staging_dir
from src.lib.porting_payload import build_release_payload


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def port_release_payload(
    repo_root: Path,
    release: str,
    *,
    release_root: Path | None = None,
    consume: bool = False,
):
    release_root = release_root or (get_vault_staging_dir() / release)
    payload = build_release_payload(release_root)

    if payload.release != release:
        raise ValueError(
            f"requested release {release!r} does not match manifest release {payload.release!r}"
        )

    for skill_dir in payload.skill_paths:
        target = get_project_brain_skills_dir(repo_root) / skill_dir.name
        target.parent.mkdir(parents=True, exist_ok=True)
        _copy_tree(skill_dir, target)

    for page_file in payload.page_paths:
        target = repo_root / page_file.relative_to(release_root / "pages")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(page_file, target)

    if consume:
        shutil.rmtree(release_root)

    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Port a staged release from vault drafts/staging into the main tree."
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--release", required=True)
    parser.add_argument(
        "--release-root",
        default=None,
        help="Explicit release root; defaults to RELEASE under the configured vault drafts/staging path.",
    )
    parser.add_argument("--consume", action="store_true")
    args = parser.parse_args(argv)

    payload = port_release_payload(
        repo_root=Path(args.repo_root).resolve(),
        release=args.release,
        release_root=Path(args.release_root).resolve() if args.release_root else None,
        consume=args.consume,
    )
    print(payload.release_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
