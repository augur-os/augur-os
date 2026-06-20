"""Partition-integrity scanner for the public augur-os release.

Proves the public partition (the code repo) carries no private content, so
`release_scope: full` can publish the whole tree. Replaces the docs_only
exclusion allowlist with a positive integrity check. See
docs/superpowers/specs/2026-06-16-public-soft-launch-readiness-design.md.

The scanner walks the WHOLE repo root minus a denylist of top-level/internal
directories (exclude_dirs) and glob exclusions (exclude_globs). This is a privacy
gate, so it errs toward over-reporting: a false "clean" is the dangerous failure.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.config.paths import get_project_root

_POLICY_REL = Path("config/system/partition_policy.yaml")
_SCOPE_REL = Path("config/system/release_scope.yaml")
_MARKER_ENV = "AUGUR_PRIVATE_MARKER_REGEX"

# Known-binary suffixes whose contents are NOT scanned for markers/secrets. Every
# other non-excluded file IS content-scanned (a denylist, not an allowlist), so a
# gate cannot miss private text hiding in an unusual text suffix (.sql, .tf, ...).
_BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".gz",
    ".7z",
    ".webp",
    ".avif",
    ".mp3",
    ".mp4",
    ".mov",
    ".wav",
    ".woff",
    ".woff2",
    ".ttf",
    ".ico",
    ".so",
    ".dylib",
    ".bin",
}

# The canonical AWS documentation example access-key id. AWS publishes it as the
# placeholder used throughout their own docs; it is never a real credential, so a
# `secret` match on this exact literal is suppressed everywhere (not just under
# secret_allow_globs).
_AWS_EXAMPLE_TOKEN = "AKIAIOSFODNN7EXAMPLE"

# Filename tails that mark a committed, secret-free public template (e.g.
# `.env.example`). A forbidden_names match on a file ending in one of these is
# suppressed so standard public templates don't hold the gate permanently red.
_TEMPLATE_TAILS = (".example", ".sample", ".template")


def load_policy(policy_path: Path | None = None) -> dict:
    """Load and normalize the partition policy."""
    path = policy_path or (get_project_root() / _POLICY_REL)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        "private_paths": list(data.get("private_paths") or []),
        # Lowercased for case-insensitive matching (server.KEY must be caught).
        "forbidden_suffixes": {s.lower() for s in (data.get("forbidden_suffixes") or [])},
        # Exact/dotfile filenames that must never be published (.env, .env.local).
        "forbidden_names": {n.lower() for n in (data.get("forbidden_names") or [])},
        "secret_patterns": list(data.get("secret_patterns") or []),
        # Repo-relative globs where secret-pattern matches are KNOWN example/fixture
        # tokens and must NOT produce a `secret` finding. Applies ONLY to the
        # `secret` kind — marker / private-path / forbidden checks are never relaxed.
        "secret_allow_globs": list(data.get("secret_allow_globs") or []),
        # Top-level / internal directory names never scanned (denylist model).
        "exclude_dirs": set(data.get("exclude_dirs") or []),
        "exclude_globs": list(data.get("exclude_globs") or []),
    }


@dataclass(frozen=True)
class Finding:
    # "private-path" | "forbidden-suffix" | "forbidden-name" | "marker" | "secret" | "symlink"
    kind: str
    path: str  # repo-relative POSIX path
    line: int | None  # 1-based line for content findings, else None
    detail: str


def _excluded(rel_posix: str, exclude_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel_posix, pat) for pat in exclude_globs)


def _tracked_files(root: Path) -> set[str] | None:
    """Return the set of repo-relative POSIX paths git tracks under ``root``.

    Only git-tracked files can ever reach the public partition (the release guard
    archives the pushed commit, which carries only tracked files), so gitignored /
    untracked local artifacts (build caches, dev symlinks, log markers) are not in
    scope. Returns None when ``root`` is not inside a git work tree or git is
    unavailable — the caller then falls back to the full filesystem walk, which is
    correct for an archived release tree (no ``.git``, already tracked-only).

    Also returns None when ``root`` is a SUBDIR of a work tree rather than its
    toplevel: `git ls-files` from a subdir lists only paths under that subdir
    (often an empty set), which would otherwise skip every file and report a
    dangerous false "clean". Trusting the tracked-set requires root == toplevel.
    """
    try:
        toplevel = (
            subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                capture_output=True,
                check=True,
            )
            .stdout.decode("utf-8", "surrogateescape")
            .strip()
        )
        if not toplevel or Path(toplevel).resolve() != root.resolve():
            return None
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return {rel for rel in out.decode("utf-8", "surrogateescape").split("\0") if rel}


def _iter_entries(root: Path, policy: dict):
    """Yield (path, rel_posix, is_symlink) for every file or symlink in the repo,
    skipping exclude_dirs (by path part) and exclude_globs.

    Symlinks are yielded (and flagged) but never followed — a symlink pointing at
    the private vault must surface as a finding, not silently hide its contents.

    When ``root`` is inside a git work tree, only git-tracked files are considered
    (gitignored / untracked artifacts never get published); exclude_dirs /
    exclude_globs are still applied on top. When ``root`` is not a git repo (an
    archived release tree), the full walk runs unchanged.
    """
    exclude_dirs = policy["exclude_dirs"]
    exclude_globs = policy["exclude_globs"]
    tracked = _tracked_files(root)
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        parts = p.relative_to(root).parts
        if any(part in exclude_dirs for part in parts):
            continue
        if _excluded(rel, exclude_globs):
            continue
        # In a git work tree, scan only tracked paths (a tracked symlink is in this
        # set; an untracked symlink is not, so it is skipped).
        if tracked is not None and rel not in tracked:
            continue
        is_symlink = p.is_symlink()
        if is_symlink:
            yield p, rel, True
            continue
        if p.is_file():
            yield p, rel, False


def public_release_files(root: Path, policy: dict | None = None) -> list[str]:
    """Sorted repo-relative POSIX paths that ship in a ``full``-scope public
    release: every git-tracked regular file under ``root`` minus the partition
    policy's ``exclude_dirs`` / ``exclude_globs``.

    This is exactly the file set :func:`scan_partition` inspects — both iterate
    :func:`_iter_entries` — so the published tree equals the scanned tree.
    Symlinks are excluded (a publishable tree carries none; the scanner reports
    any unfollowed symlink as a finding).
    """
    policy = policy or load_policy()
    return sorted(rel for _path, rel, is_symlink in _iter_entries(root, policy) if not is_symlink)


def scan_partition(
    root: Path | None = None,
    policy: dict | None = None,
    marker_regex: str | None = None,
) -> list[Finding]:
    """Scan the public partition; return all private-content findings."""
    root = root or get_project_root()
    policy = policy or load_policy()
    if marker_regex is None:
        marker_regex = os.environ.get(_MARKER_ENV) or None

    marker_re = re.compile(marker_regex) if marker_regex else None
    secret_res = [re.compile(p) for p in policy["secret_patterns"]]
    private_globs = policy["private_paths"]
    forbidden = policy["forbidden_suffixes"]
    forbidden_names = policy["forbidden_names"]
    secret_allow_globs = policy.get("secret_allow_globs") or []

    findings: list[Finding] = []
    for p, rel, is_symlink in _iter_entries(root, policy):
        if is_symlink:
            findings.append(Finding("symlink", rel, None, "symlink in public partition (not followed)"))
            continue
        if any(fnmatch.fnmatch(rel, g) for g in private_globs):
            findings.append(Finding("private-path", rel, None, "file lives in a private-partition path"))
            continue
        name = p.name.lower()
        suffix = p.suffix.lower()
        if suffix in forbidden:
            findings.append(Finding("forbidden-suffix", rel, None, f"forbidden suffix {p.suffix}"))
            continue
        # Dotfiles like `.env` have an empty suffix, so also match the full name and
        # the dotted name-prefix (.env.local) against forbidden_names. A `.` boundary
        # is required after the entry so `.environment` does NOT match `.env`, and
        # committed public templates (`.env.example`, `.env.mcp.example`) are exempt.
        if not name.endswith(_TEMPLATE_TAILS):
            bad_name = next(
                (n for n in forbidden_names if name == n or name.startswith(n + ".")),
                None,
            )
            if bad_name is not None:
                findings.append(Finding("forbidden-name", rel, None, f"forbidden name {bad_name}"))
                continue
        if (marker_re or secret_res) and suffix not in _BINARY_SUFFIXES:
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            # `secret` findings are suppressed for files under secret_allow_globs
            # (documented example/fixture tokens). The marker check is NEVER relaxed.
            secret_allowed = any(fnmatch.fnmatch(rel, g) for g in secret_allow_globs)
            for i, line in enumerate(text.splitlines(), 1):
                if marker_re and marker_re.search(line):
                    findings.append(Finding("marker", rel, i, "private marker match"))
                if secret_allowed:
                    continue
                for sre in secret_res:
                    m = sre.search(line)
                    if not m:
                        continue
                    # The canonical AWS docs example token is never a real key.
                    if m.group(0) == _AWS_EXAMPLE_TOKEN:
                        continue
                    findings.append(Finding("secret", rel, i, "secret-like token"))
    return findings


def resolve_scope(scope_path: Path | None = None) -> str:
    """Return the configured release scope (default 'docs_only')."""
    path = scope_path or (get_project_root() / _SCOPE_REL)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return str(data.get("scope", "docs_only"))
