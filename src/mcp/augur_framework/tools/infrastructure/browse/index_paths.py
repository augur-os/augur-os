"""Path identity and mtime helpers for the browse index modules."""

from pathlib import Path


def _path_mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _path_lstat_mtime_ns(path: Path) -> int:
    try:
        return path.lstat().st_mtime_ns
    except OSError:
        return 0


def _path_identity(path: Path) -> str:
    return str(Path(path).expanduser().resolve(strict=False))


def _path_lexical_identity(path: Path) -> str:
    return str(Path(path).expanduser().absolute())


def _has_symlink_between(root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True

    current = root
    for part in relative.parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False
