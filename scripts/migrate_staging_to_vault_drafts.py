#!/usr/bin/env python3
"""Move repo staging payloads into the vault drafts/staging tree."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.paths import get_project_root, get_vault_skills_dir, get_vault_staging_dir

RUNTIME_BLOCKER_PROMOTIONS: tuple[tuple[str, str], ...] = (
    ("apple", "vault"),
    ("lifestyle", "vault"),
    ("plugin-pack", "repo"),
)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_signature(root: Path) -> tuple[tuple[str, str, int | None, str | None], ...]:
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise NotADirectoryError(root)

    entries: list[tuple[str, str, int | None, str | None]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            entries.append(("dir", relative, None, None))
            continue
        stat = path.stat()
        entries.append(("file", relative, stat.st_size, _hash_file(path)))
    return tuple(entries)


def _assert_tree_matches_signature(
    root: Path, signature: tuple[tuple[str, str, int | None, str | None], ...], *, label: str
) -> None:
    if _tree_signature(root) != signature:
        raise ValueError(
            f"{label} replace verification failed for target: {root}"
        )


def _is_residue_file(path: Path) -> bool:
    return path.name == ".DS_Store" or path.suffix == ".pyc"


def _has_payload_files(root: Path) -> bool:
    return any(path.is_file() and not _is_residue_file(path) for path in root.rglob("*"))


def _backup_path(target: Path) -> Path:
    return target.parent / f".{target.name}.migrate-backup"


def copy_repo_staging_to_vault_drafts(
    *, replace: bool = False
) -> tuple[Path, Path, str]:
    project_root = get_project_root()
    source = project_root / "staging"
    target = get_vault_staging_dir()

    if not source.exists():
        if target.exists():
            return source, target, "already_migrated"
        raise FileNotFoundError(f"Repo staging directory does not exist: {source}")

    if target.exists() and not _has_payload_files(source):
        shutil.rmtree(source)
        return source, target, "already_migrated"

    source_signature = _tree_signature(source)
    if target.exists():
        if not replace:
            raise FileExistsError(f"Vault staging already exists: {target}")
        backup = _backup_path(target)
        if backup.exists():
            raise FileExistsError(f"Backup path already exists: {backup}")
        shutil.move(str(target), str(backup))
        try:
            shutil.copytree(source, target)
            _assert_tree_matches_signature(target, source_signature, label="Vault staging")
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            shutil.move(str(backup), str(target))
            raise
        shutil.rmtree(backup)
        shutil.rmtree(source)
        return source, target, "copied"

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    _assert_tree_matches_signature(target, source_signature, label="Vault staging")
    shutil.rmtree(source)
    return source, target, "copied"


def _target_root_for_destination(destination: str) -> Path:
    if destination == "vault":
        return get_vault_skills_dir()
    if destination == "repo":
        return get_project_root() / "project-brain" / "capabilities" / "skills"
    raise ValueError(f"Unknown destination: {destination}")


def promote_active_skill(skill_name: str, *, destination: str, replace: bool = False) -> Path:
    staging_root = get_vault_staging_dir()
    matches = sorted(staging_root.glob(f"*/skills/{skill_name}"))
    target_root = _target_root_for_destination(destination)
    if matches and len(matches) != 1:
        raise ValueError(f"Expected exactly one draft match for {skill_name}, found {len(matches)}")

    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / skill_name
    source = matches[0] if matches else None
    if target.exists():
        if not matches:
            return target
        if not replace:
            raise FileExistsError(f"Active skill target already exists: {target}")
        assert source is not None
        source_signature = _tree_signature(source)
        backup = _backup_path(target)
        if backup.exists():
            raise FileExistsError(f"Backup path already exists: {backup}")
        shutil.move(str(target), str(backup))
        try:
            shutil.move(str(source), str(target))
            _assert_tree_matches_signature(target, source_signature, label=f"{skill_name} promotion")
        except Exception:
            if target.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(source))
            shutil.move(str(backup), str(target))
            raise
        shutil.rmtree(backup)
        return target

    if len(matches) != 1:
        raise ValueError(f"Expected exactly one draft match for {skill_name}, found {len(matches)}")

    assert source is not None
    source_signature = _tree_signature(source)
    shutil.move(str(source), str(target))
    _assert_tree_matches_signature(target, source_signature, label=f"{skill_name} promotion")
    return target


def promote_skill_set(promotions: list[tuple[str, str]], *, replace: bool = False) -> list[Path]:
    return [
        promote_active_skill(skill_name, destination=destination, replace=replace)
        for skill_name, destination in promotions
    ]


def promote_runtime_blockers(*, replace: bool = False) -> list[Path]:
    return promote_skill_set(list(RUNTIME_BLOCKER_PROMOTIONS), replace=replace)


def _parse_promotion_spec(spec: str) -> tuple[str, str]:
    skill_name, separator, destination = spec.partition(":")
    if not separator or destination not in {"repo", "vault"} or not skill_name:
        raise argparse.ArgumentTypeError(
            f"Invalid promotion {spec!r}; expected SKILL:repo or SKILL:vault"
        )
    return skill_name, destination


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Move repo staging payloads into the vault drafts/staging tree."
    )
    subparsers = parser.add_subparsers(dest="command")

    copy_parser = subparsers.add_parser("copy")
    copy_parser.add_argument("--replace", action="store_true")

    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("--replace", action="store_true")
    promote_parser.add_argument("promotions", nargs="+", type=_parse_promotion_spec)

    blockers_parser = subparsers.add_parser("promote-runtime-blockers")
    blockers_parser.add_argument("--replace", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "copy"):
        source, target, status = copy_repo_staging_to_vault_drafts(
            replace=getattr(args, "replace", False)
        )
        print(source)
        print(target)
        print(status)
        return 0

    if args.command == "promote":
        for target in promote_skill_set(list(args.promotions), replace=args.replace):
            print(target)
        return 0

    if args.command == "promote-runtime-blockers":
        for target in promote_runtime_blockers(replace=args.replace):
            print(target)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
