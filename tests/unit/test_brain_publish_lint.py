"""Brain publish-by-construction lint (ADR-814).

Continuously scans tracked files under project-brain/ for machine paths and
secret markers. Files that fail are not publishable; they must be fixed before
the commit can land. This keeps the brain tree release-safe at all times.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Source of FORBIDDEN_FILE_SUFFIXES — reuse to stay in sync.
# guard_public_release_tree is under scripts/, which may not be on sys.path in
# all test runners, so fall back to a local copy when the import fails.
try:
    import sys

    _SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    from guard_public_release_tree import FORBIDDEN_FILE_SUFFIXES  # type: ignore[import]
except Exception:  # noqa: BLE001
    # Copied from scripts/guard_public_release_tree.py; update both if the set changes.
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

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Files / directories exempted from the content scan (owner-private by design).
# These are removed entirely from product releases (see MVP_RELEASE_PRUNE_DIRS/FILES).
_EXEMPT_PREFIXES = (
    "project-brain/knowledge/memory/",
    "project-brain/MEMORY.md",
)
_EXEMPT_GLOB_PATTERNS = (".obsidian/",)

# Per-file scan exemptions with justification.
# Only for scanner/test code whose purpose is to detect these patterns — the
# file is explicitly testing that the relevant scanner works correctly, so the
# "bad" content appears as a string literal passed to a tmp_path fixture, not
# as an actual machine path.
_EXEMPT_FILES_WITH_REASON: dict[str, str] = {
    # Tests the standard_skill_contract scanner — writes fixture files
    # containing synthetic machine paths to tmp_path, verifies they are
    # flagged.  The paths are strings inside write_text() calls, never real.
    "project-brain/capabilities/skills/auto-skill-quality/augur/tests/test_standard_skill_contract.py": (
        "scanner test: writes synthetic machine-path fixtures to tmp_path"
    ),
    # Tests the security-scan daemon op — writes fixture files containing
    # synthetic sk-... key strings to tmp_path to verify the scanner flags
    # them.  The keys are clearly fake (sequential alphabet, random but short
    # test tokens) and do not constitute real credentials.
    "project-brain/capabilities/skills/daemon/augur/tests/test_security_scan.py": (
        "scanner test: writes synthetic sk-... fixture tokens to tmp_path"
    ),
}

# ── Content markers ─────────────────────────────────────────────────────────
#
# These are compiled regex patterns.  Each entry is (pattern, description).
#
# Design choices:
# * /Users/<word>/ — matches any macOS/Linux user dir with a real username
#   (at least 3 chars, not a well-known placeholder).
#   - Generic placeholder usernames (example, someone, you, x, u, test,
#     testuser, nobody, me, tester) are intentionally excluded because:
#     (a) they appear legitimately in documentation as illustrative paths,
#     (b) no actual owner information leaks from them,
#     (c) narrowing the check to these avoids false positives.
#   - The actual owner username (a real local username) was removed in the ADR-814
#     sanitization; this pattern would still catch it.
# * C:\Users\<word>\ — Windows path with an actual username (same logic).
# * PEM private key header — catches real key material, not scanner regexes.
# * Real credential values: sk-... prefix for OpenAI keys.
# * Real GitHub PATs: ghp_... and github_pat_... prefixes with real token
#   length.  The 'ghp_' string alone (without a long suffix) is excluded
#   because it appears in docs describing what the scanner detects.
#
_PLACEHOLDER_NAMES = {
    "example",
    "someone",
    "you",
    "x",
    "u",
    "test",
    "testuser",
    "nobody",
    "me",
    "tester",
    "intel",
    "gur",
    "...",
}

_CONTENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Real machine user paths — /Users/<username>/ where username is not a known placeholder
    (
        re.compile(
            r"/Users/(?!(?:" + "|".join(re.escape(n) for n in _PLACEHOLDER_NAMES) + r")[/\s'\"`)])([A-Za-z0-9_.-]{3,})/"
        ),
        "/Users/<username>/ machine path",
    ),
    # Windows machine user paths with an actual non-placeholder username
    (
        re.compile(
            r"C:\\Users\\(?!(?:" + "|".join(re.escape(n) for n in _PLACEHOLDER_NAMES) + r")\\)([A-Za-z0-9_.-]{3,})\\"
        ),
        r"C:\Users\<username>\ machine path",
    ),
    # PEM private key header — actual key material, not a scanner pattern string
    (
        re.compile(r"-----BEGIN\s+(?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
        "PEM private key block",
    ),
    # Real credential values (sk-... prefix is an OpenAI API key value)
    (
        re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
        "OpenAI API key value (sk-...)",
    ),
    # GitHub Personal Access Tokens — require a real token suffix length
    (
        re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
        "GitHub PAT (ghp_...)",
    ),
    (
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
        "GitHub fine-grained PAT (github_pat_...)",
    ),
]


def _is_exempt(rel_path: str) -> bool:
    for prefix in _EXEMPT_PREFIXES:
        if rel_path.startswith(prefix):
            return True
    for pattern in _EXEMPT_GLOB_PATTERNS:
        if pattern in rel_path:
            return True
    return False


def _tracked_brain_files() -> list[str]:
    """Return git-tracked paths under project-brain/ relative to PROJECT_ROOT."""
    result = subprocess.run(
        ["git", "ls-files", "project-brain/"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_no_forbidden_binary_suffixes_tracked_in_brain() -> None:
    """No binary/media files should be tracked under project-brain/."""
    violations: list[str] = []
    for rel in _tracked_brain_files():
        if _is_exempt(rel):
            continue
        suffix = Path(rel).suffix.lower()
        if suffix in FORBIDDEN_FILE_SUFFIXES:
            violations.append(rel)

    assert not violations, (
        "Binary/media files tracked under project-brain/ violate ADR-814 "
        "(publishable-by-construction):\n"
        + "\n".join(f"  {v}" for v in sorted(violations))
        + "\nRemove or gitignore these files."
    )


def test_no_machine_paths_or_secrets_in_brain_tree() -> None:
    """Text files under project-brain/ must not contain machine paths or secrets."""
    violations: list[tuple[str, str]] = []  # (rel_path, description)
    for rel in _tracked_brain_files():
        if _is_exempt(rel):
            continue
        if rel in _EXEMPT_FILES_WITH_REASON:
            continue
        path = PROJECT_ROOT / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 — unreadable file; skip content scan
            continue
        for pattern, description in _CONTENT_PATTERNS:
            if pattern.search(text):
                violations.append((rel, description))
                break  # one report per file is enough

    if violations:
        lines = [
            f"  {rel}  [{description}]  — violates ADR-814 publish-by-construction; "
            "personal/machine content belongs in Au-vault"
            for rel, description in sorted(violations)
        ]
        raise AssertionError(
            f"{len(violations)} file(s) under project-brain/ contain publish-blocking content:\n" + "\n".join(lines)
        )
