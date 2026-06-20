from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.guard_public_release_tree import PublicReleaseGuardError, guard_public_tree


ZERO_OIDS = {"0" * 40, "0" * 64}
MAX_REPORTED_VIOLATIONS = 80


@dataclass(frozen=True)
class PushUpdate:
    local_ref: str
    local_oid: str
    remote_ref: str
    remote_oid: str


def _is_public_mirror(remote_name: str, remote_url: str) -> bool:
    return remote_name == "augur-os" or "augur-os/augur-os" in remote_url


def _parse_updates(stdin: str) -> list[PushUpdate]:
    updates: list[PushUpdate] = []
    for line in stdin.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 4:
            raise ValueError(f"invalid pre-push line: {line}")
        updates.append(PushUpdate(*parts))
    return updates


def _git_archive(repo: Path, oid: str, output_root: Path) -> None:
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", oid],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if archive.returncode != 0:
        raise RuntimeError(archive.stderr.decode("utf-8", errors="replace").strip())

    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as tar:
        try:
            tar.extractall(output_root, filter="data")
        except TypeError:
            tar.extractall(output_root)


def _format_public_tree_error(exc: PublicReleaseGuardError) -> str:
    shown = [violation.format() for violation in exc.violations[:MAX_REPORTED_VIOLATIONS]]
    remaining = len(exc.violations) - len(shown)
    if remaining > 0:
        shown.append(f"... and {remaining} more public-release violation(s)")
    return "\n".join(shown)


def validate_public_updates(
    updates: list[PushUpdate],
    *,
    repo: Path,
    source_root: Path,
) -> list[str]:
    failures: list[str] = []
    for update in updates:
        if update.local_oid in ZERO_OIDS:
            failures.append(f"public mirror deletion is not allowed: {update.remote_ref}")
            continue

        with tempfile.TemporaryDirectory(prefix="augur-public-push.") as tmp:
            tree_root = Path(tmp)
            try:
                _git_archive(repo, update.local_oid, tree_root)
                guard_public_tree(tree_root, source_root=source_root)
            except PublicReleaseGuardError as exc:
                failures.append(
                    f"{update.local_ref} -> {update.remote_ref}\n{_format_public_tree_error(exc)}"
                )
            except RuntimeError as exc:
                failures.append(f"{update.local_ref} -> {update.remote_ref}\n{exc}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Guard pushes to the public augur-os mirror.")
    parser.add_argument("--remote-name", required=True)
    parser.add_argument("--remote-url", required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    stdin = sys.stdin.read()
    if not _is_public_mirror(args.remote_name, args.remote_url):
        return 0

    try:
        updates = _parse_updates(stdin)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    failures = validate_public_updates(
        updates,
        repo=args.repo.resolve(),
        source_root=args.source_root.resolve(),
    )
    if failures:
        print("BLOCKED: push to augur-os/augur-os contains a non-public tree.", file=sys.stderr)
        print("\n\n".join(failures), file=sys.stderr)
        return 1

    print(f"public push guard passed: {len(updates)} ref(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
