from __future__ import annotations

import argparse
import fnmatch
import getpass
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_public_release_tree import DOCS_ONLY_ALLOWLIST, DOCS_ONLY_DIR_ALLOWLIST
from src.lib.partition_integrity import load_policy, resolve_scope, scan_partition

FORBIDDEN_PATH_PATTERNS = [
    ".claude/**",
    ".codex/**",
    ".cursor/**",
    ".gemini/**",
    ".github/**",
    "apps/**",
    "config/**",
    "packages/**",
    "plugins/**",
    "project-brain/**",
    "scripts/**",
    "shared-vault/**",
    "src/**",
    "tests/**",
    "docs/security/**",
]

FORBIDDEN_FILE_SUFFIXES = {
    ".7z",
    ".avif",
    ".docx",
    ".gif",
    ".gz",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".pptx",
    ".tar",
    ".tgz",
    ".wav",
    ".webp",
    ".zip",
}

FORBIDDEN_FILE_NAMES = {".DS_Store"}

FORBIDDEN_CONTENT_MARKERS = [
    "PRIVATE KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "github_pat_",
    "ghp_",
    "sk-abcdefghijklmnopqrstuvwxyz",
]


@dataclass(frozen=True)
class PublicReleaseViolation:
    reason: str
    path: str
    detail: str | None = None

    def format(self) -> str:
        if self.reason == "forbidden content marker" and self.detail:
            return f"{self.reason} {self.detail}: {self.path}"
        if self.detail:
            return f"{self.reason}: {self.path} ({self.detail})"
        return f"{self.reason}: {self.path}"


class PublicReleaseGuardError(RuntimeError):
    def __init__(self, violations: list[PublicReleaseViolation]) -> None:
        self.violations = violations
        super().__init__("\n".join(violation.format() for violation in violations))


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _path_is_forbidden(rel_path: str) -> bool:
    return any(fnmatch.fnmatchcase(rel_path, pattern) for pattern in FORBIDDEN_PATH_PATTERNS)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def machine_path_markers() -> list[str]:
    """Machine-specific strings that must never reach a public release tree.

    The building user's absolute home directory and bare username. This catches
    leaked working-tree dirt — e.g. ``project-brain/BRAIN.yaml`` mutated locally
    to ``root: /Users/<name>/...`` — which the partition scan does not inspect.
    A generic ``/Users/*`` / ``/home/*`` match is deliberately avoided: the tree
    legitimately carries placeholder fixtures (``/Users/example``, ``/home/user``,
    Home Assistant ``/home/skills`` entity ids), so only the *actual* builder's
    home/username is treated as a leak.
    """
    markers: list[str] = []
    # The builder's absolute home directory is ALWAYS a valid marker: it is a full
    # path, so it cannot false-positive on common words/identifiers. (This is what
    # the worktree-leak guard tests rely on.)
    try:
        home = str(Path.home())
        # Skip degenerate roots like "/" or "\" that would match everything.
        if len(home.strip("/\\")) >= 2:
            markers.append(home)
    except (RuntimeError, OSError):
        pass
    # The BARE username is only a safe marker when it's distinctive. Short or
    # generic/shared accounts (me, ci, runner, ubuntu, github, ...) recur as
    # common substrings (e.g. "runner" in "workflow_runner" or "test runners"),
    # so exclude them — otherwise the guard false-positives across the whole tree
    # when it runs in CI (where the build user is "runner"). The configured
    # AUGUR_PRIVATE_MARKER_REGEX still catches real private markers regardless.
    generic_users = {
        "runner",
        "runneradmin",
        "ubuntu",
        "admin",
        "administrator",
        "user",
        "users",
        "github",
        "vsts",
        "circleci",
        "build",
        "vagrant",
        "docker",
    }
    try:
        user = getpass.getuser()
        if len(user) >= 5 and user.lower() not in generic_users and user not in markers:
            markers.append(user)
    except Exception:
        pass
    return markers


def _content_leak_violations(
    rel_path: str,
    text: str,
    *,
    marker_re: re.Pattern[str] | None,
    marker_pattern: str | None,
    machine_markers: list[str],
    include_secret_markers: bool,
) -> list[PublicReleaseViolation]:
    """Content-safety checks for one text file: configured private markers and
    machine-specific paths always; the ``FORBIDDEN_CONTENT_MARKERS`` env-var-name
    list only when ``include_secret_markers`` is set.

    The marker list is calibrated for the tiny docs_only allowlist; it false-
    positives on the full code tree, where ``OPENAI_API_KEY`` / ``PRIVATE KEY``
    legitimately appear as env-var names and detection patterns. So full scope
    relies on the partition scan plus the configured ``AUGUR_PRIVATE_MARKER_REGEX``
    and the machine-path check, not the env-var-name markers.
    """
    out: list[PublicReleaseViolation] = []
    if include_secret_markers:
        for marker in FORBIDDEN_CONTENT_MARKERS:
            if marker in text:
                out.append(PublicReleaseViolation("forbidden content marker", rel_path, repr(marker)))
    if marker_re is not None and marker_re.search(text):
        out.append(PublicReleaseViolation("forbidden content marker", rel_path, repr(marker_pattern)))
    for machine_marker in machine_markers:
        if machine_marker in text:
            out.append(PublicReleaseViolation("machine-specific path", rel_path, repr(machine_marker)))
    return out


def scan_content_safety(root: Path) -> list[PublicReleaseViolation]:
    """Walk every text file under ``root`` for content leaks that must be blocked
    in *any* scope — machine-specific paths and the configured private-marker
    regex. The full-scope partition scan checks file *placement*, not *content*,
    so this is what catches working-tree dirt like the BRAIN.yaml absolute-path
    leak. The env-var-name secret markers are intentionally excluded here (they
    false-positive on real source); they remain a docs_only allowlist check."""
    root = root.resolve()
    marker_pattern = os.environ.get("AUGUR_PRIVATE_MARKER_REGEX") or None
    marker_re = re.compile(marker_pattern) if marker_pattern else None
    machine_markers = machine_path_markers()

    violations: list[PublicReleaseViolation] = []
    for file_path in sorted(path for path in root.rglob("*") if path.is_file()):
        text = _read_text(file_path)
        if text is None:
            continue
        violations.extend(
            _content_leak_violations(
                _relative_path(file_path, root),
                text,
                marker_re=marker_re,
                marker_pattern=marker_pattern,
                machine_markers=machine_markers,
                include_secret_markers=False,
            )
        )
    return violations


def docs_only_allowed_paths(source_root: Path) -> set[str]:
    source_root = source_root.resolve()
    allowed_paths = set(DOCS_ONLY_ALLOWLIST)
    for rel_dir in DOCS_ONLY_DIR_ALLOWLIST:
        source_dir = source_root / rel_dir
        if not source_dir.is_dir():
            continue
        for file_path in sorted(path for path in source_dir.rglob("*") if path.is_file()):
            allowed_paths.add(file_path.relative_to(source_root).as_posix())
    return allowed_paths


def collect_public_tree_violations(
    root: Path,
    *,
    allowed_paths: set[str] | None = None,
) -> list[PublicReleaseViolation]:
    root = root.resolve()
    if not root.is_dir():
        return [PublicReleaseViolation("missing public tree", root.as_posix())]

    marker_pattern = os.environ.get("AUGUR_PRIVATE_MARKER_REGEX") or None
    marker_re = re.compile(marker_pattern) if marker_pattern else None
    machine_markers = machine_path_markers()

    violations: list[PublicReleaseViolation] = []
    actual_paths: set[str] = set()
    for file_path in sorted(path for path in root.rglob("*") if path.is_file()):
        rel_path = _relative_path(file_path, root)
        actual_paths.add(rel_path)

        if _path_is_forbidden(rel_path):
            violations.append(PublicReleaseViolation("forbidden path", rel_path))

        if file_path.name in FORBIDDEN_FILE_NAMES:
            violations.append(PublicReleaseViolation("forbidden file name", rel_path))

        if file_path.suffix.lower() in FORBIDDEN_FILE_SUFFIXES:
            violations.append(PublicReleaseViolation("forbidden file type", rel_path))

        text = _read_text(file_path)
        if text is None:
            violations.append(PublicReleaseViolation("non-text file", rel_path))
            continue

        violations.extend(
            _content_leak_violations(
                rel_path,
                text,
                marker_re=marker_re,
                marker_pattern=marker_pattern,
                machine_markers=machine_markers,
                include_secret_markers=True,
            )
        )

    if allowed_paths is not None:
        for rel_path in sorted(actual_paths - allowed_paths):
            violations.append(PublicReleaseViolation("unexpected public file", rel_path))
        for rel_path in sorted(allowed_paths - actual_paths):
            violations.append(PublicReleaseViolation("missing allowlisted file", rel_path))

    return violations


def guard_public_tree(
    root: Path,
    *,
    source_root: Path | None = None,
    allowed_paths: set[str] | None = None,
) -> list[PublicReleaseViolation]:
    src = source_root or Path.cwd()
    scope_cfg = os.environ.get("AUGUR_RELEASE_SCOPE_CONFIG")
    scope = resolve_scope(Path(scope_cfg) if scope_cfg else src / "config/system/release_scope.yaml")
    if scope == "full" and allowed_paths is None:
        policy = load_policy(src / "config/system/partition_policy.yaml")
        findings = scan_partition(root=root, policy=policy)
        violations = [
            PublicReleaseViolation(f"partition: {f.kind}", f.path, f"line {f.line}" if f.line else None)
            for f in findings
        ]
        # The partition scan checks file *placement*; it does not inspect content
        # for secrets, private markers, or machine-specific paths (the BRAIN.yaml
        # absolute-path leak in v1.12.0). Run the shared content-safety scan too.
        violations += scan_content_safety(root)
        if violations:
            raise PublicReleaseGuardError(violations)
        return violations
    # docs_only (default): existing allowlist behavior
    if allowed_paths is None:
        allowed_paths = docs_only_allowed_paths(source_root or Path.cwd())
    violations = collect_public_tree_violations(root, allowed_paths=allowed_paths)
    if violations:
        raise PublicReleaseGuardError(violations)
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Block unsafe files from public release trees.")
    parser.add_argument("--root", type=Path, required=True, help="Generated public release tree")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path.cwd(),
        help="Private source checkout used to resolve public allowlists",
    )
    args = parser.parse_args()

    try:
        guard_public_tree(args.root, source_root=args.source_root)
    except PublicReleaseGuardError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"public release guard passed: {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
