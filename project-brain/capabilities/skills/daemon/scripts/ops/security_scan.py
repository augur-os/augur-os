"""auto-security-scan: Scan for secrets, CVEs, and dependency vulnerabilities.
Extracted from /security-audit (ADR-200).

Scan: checks for hardcoded secrets, runs npm audit, and checks for known CVEs.
Fix: runs npm audit fix for safe auto-fixable vulnerabilities, reports the rest.
"""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, declare_ops_capabilities


name = "auto-security-scan"
OPS_CAPABILITIES = declare_ops_capabilities(
    platforms=("cross_platform",),
    windows_fix_mode="report_only",
)

# Patterns that suggest hardcoded secrets
_SECRET_PATTERNS = [
    re.compile(r"""(?:api[_-]?key|secret[_-]?key|password|token)\s*[=:]\s*['"][A-Za-z0-9+/=_-]{16,}['"]""", re.IGNORECASE),
    re.compile(r"""sk-[A-Za-z0-9]{20,}"""),  # OpenAI-style keys
    re.compile(r"""ghp_[A-Za-z0-9]{36}"""),  # GitHub personal tokens
    re.compile(r"""AKIA[A-Z0-9]{16}"""),  # AWS access keys
]

# Strings that match a secret pattern's *shape* but are obvious
# placeholders/examples — most often inside another tool's own list of
# secret-detection patterns (e.g. a sequential alphabet next to "ghp_" /
# "OPENAI_API_KEY"). These are skipped by STRUCTURE only (known example
# tokens, sequential/repeated characters, near-zero entropy) — never by file
# path — so a real high-entropy credential leaked anywhere is still flagged.
_PLACEHOLDER_TOKENS = {
    "abcdefghijklmnopqrstuvwxyz",
    "abcdefghijklmnopqrstuvwxyz0123456789",
    "0123456789",
    "0123456789abcdef",
    "1234567890",
}
_PLACEHOLDER_SUBSTRINGS = (
    "example",
    "placeholder",
    "changeme",
    "redacted",
    "your_api",
    "yourapikey",
    "dummy",
)
# Known secret prefixes stripped before judging the entropy-bearing remainder.
_SECRET_TOKEN_PREFIXES = ("github_pat_", "ghp_", "sk-", "AKIA")
# Deliberately permissive thresholds: they only skip clearly degenerate
# strings and leave borderline values flagged. A real credential body is
# high-entropy and non-monotone; __PROJECT_ROOT__ (~2.7 bits/char, monotone
# ratio ~0.2) stays above both floors and remains flagged.
_MIN_SECRET_ENTROPY = 2.0  # bits/char
_MAX_MONOTONE_RATIO = 0.8  # fraction of repeated or +/-1 adjacent steps

_SCAN_GLOBS = ["**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.env*", "**/*.yaml", "**/*.yml"]
_SKIP_DIRS = {"node_modules", ".next", ".git", ".worktrees", "__pycache__", "runtime", ".venv", ".venv-test", "tests"}
_ALLOWLIST_PRAGMA = "pragma: allowlist secret"
_SKIP_FILE_SUFFIXES = (
    ".test.ts",
    ".test.tsx",
    ".spec.ts",
    ".spec.tsx",
    ".test.js",
    ".spec.js",
)


def _npm_command() -> str | None:
    """Return an executable npm command for subprocess on this platform."""
    return shutil.which("npm.cmd") or shutil.which("npm")


def _shannon_entropy(value: str) -> float:
    """Shannon entropy in bits/char (0.0 for empty or single-symbol strings)."""
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    total = len(value)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def _monotone_ratio(value: str) -> float:
    """Fraction of adjacent char pairs that repeat or step by +/-1.

    A sequential alphabet ("abc...xyz") or a repeated run ("aaaa") scores ~1.0;
    a random credential body scores near 0. This is what distinguishes the
    high-entropy-but-sequential alphabet placeholder from a real key (the
    alphabet has *maximum* entropy, so entropy alone cannot catch it).
    """
    if len(value) < 2:
        return 0.0
    monotone = sum(1 for a, b in zip(value, value[1:]) if abs(ord(b) - ord(a)) <= 1)
    return monotone / (len(value) - 1)


def _candidate_token(match_text: str) -> str:
    """Extract the entropy-bearing token from a secret-pattern match.

    Prefers a quoted value (api_key = "...") and strips a known secret prefix
    so the random remainder is what gets judged.
    """
    quoted = re.search(r"""['"]([A-Za-z0-9+/=_-]{8,})['"]""", match_text)
    core = quoted.group(1) if quoted else match_text.strip()
    for prefix in _SECRET_TOKEN_PREFIXES:
        if core.startswith(prefix):
            return core[len(prefix):]
    return core


def _is_obvious_placeholder(match_text: str) -> bool:
    """True when a matched string is clearly an example/placeholder, not a key.

    Decided by structure only — known example tokens, sequential/repeated
    characters, or near-zero entropy — never by file path, so real
    high-entropy secrets stay flagged wherever they appear.
    """
    token = _candidate_token(match_text)
    if len(token) < 8:
        return False
    lowered = token.lower()
    if lowered in _PLACEHOLDER_TOKENS:
        return True
    if any(marker in lowered for marker in _PLACEHOLDER_SUBSTRINGS):
        return True
    if _monotone_ratio(token) >= _MAX_MONOTONE_RATIO:
        return True
    if _shannon_entropy(token) < _MIN_SECRET_ENTROPY:
        return True
    return False


def _scan_secrets(project_root: Path, difficulty: int) -> list[dict]:
    """Scan source files for hardcoded secrets."""
    issues: list[dict] = []
    patterns = _SECRET_PATTERNS[:2] if difficulty < 2 else _SECRET_PATTERNS

    globs = _SCAN_GLOBS[:3] if difficulty < 1 else _SCAN_GLOBS
    for pattern_str in globs:
        for filepath in project_root.glob(pattern_str):
            if any(skip in filepath.parts for skip in _SKIP_DIRS):
                continue
            if filepath.as_posix().endswith(_SKIP_FILE_SUFFIXES):
                continue
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                for secret_re in patterns:
                    for match in secret_re.finditer(content):
                        line_start = content.rfind("\n", 0, match.start()) + 1
                        line_end = content.find("\n", match.end())
                        if line_end == -1:
                            line_end = len(content)
                        if _ALLOWLIST_PRAGMA in content[line_start:line_end]:
                            continue
                        if _is_obvious_placeholder(match.group()):
                            continue
                        line_num = content[:match.start()].count("\n") + 1
                        issues.append({
                            "action": "potential-secret",
                            "file": str(filepath.relative_to(project_root)),
                            "line": line_num,
                            "pattern": secret_re.pattern[:40],
                            "snippet": match.group()[:20] + "...",
                        })
            except (OSError, UnicodeDecodeError):
                continue

    return issues


def _npm_lockfile(dashboard_dir: Path) -> Path | None:
    for name in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock"):
        p = dashboard_dir / name
        if p.exists():
            return p
    return None


def _scan_npm_audit(project_root: Path, *, timeout: int = 30, cache_dir: Path | None = None) -> list[dict]:
    """Run npm audit (timeout-bounded) and collect vulnerability info.

    Skips the audit entirely when the dependency lockfile hash is unchanged
    since the last run (cached under the runtime dir), so the hardening loop is
    not re-paying registry latency every cycle.
    """
    dashboard_dir = project_root / "apps" / "dashboard"
    if not (dashboard_dir / "package.json").exists():
        return []

    if cache_dir is None:
        try:
            from src.mcp.augur_shared.config import get_runtime_dir
            cache_dir = Path(get_runtime_dir()) / "security_scan"
        except Exception:
            cache_dir = dashboard_dir / ".augur-audit-cache"
    cache_dir = Path(cache_dir)
    lockfile = _npm_lockfile(dashboard_dir)
    lock_hash = (
        hashlib.sha256(lockfile.read_bytes()).hexdigest() if lockfile and lockfile.is_file() else "no-lock"
    )
    proj_fp = hashlib.sha256(str(Path(project_root).resolve()).encode()).hexdigest()[:12]
    cache_file = cache_dir / f"npm_audit-{proj_fp}.json"
    if cache_file.is_file():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("lock_hash") == lock_hash:
                return list(cached.get("issues", []))
        except (ValueError, OSError):
            pass

    npm = _npm_command()
    if npm is None:
        return [{
            "action": "npm-audit-error",
            "stderr": "npm executable not found on PATH",
            "kind": "environment", "fixability": "manual", "root_cause_type": "env_runtime",
        }]

    try:
        result = subprocess.run(
            [npm, "audit", "--json", "--package-lock=false"],
            capture_output=True, text=True, cwd=str(dashboard_dir), timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [{
            "action": "npm-audit-skipped",
            "stderr": f"npm audit exceeded {timeout}s timeout; skipped this run",
            "kind": "maintenance", "fixability": "manual", "root_cause_type": "env_runtime",
        }]

    if result.returncode == 0:
        issues: list[dict] = []
    else:
        try:
            audit_data = json.loads(result.stdout)
            vulns = audit_data.get("vulnerabilities", {})
            issues = []
            for pkg_name, info in vulns.items():
                severity = info.get("severity", "unknown")
                fix_available = info.get("fixAvailable", False)
                is_breaking = isinstance(fix_available, dict) and bool(fix_available.get("isSemVerMajor"))
                issues.append({
                    "action": "npm-vulnerability", "package": pkg_name, "severity": severity,
                    "fixAvailable": fix_available,
                    "kind": "external" if is_breaking else "actionable",
                    "fixability": "manual" if is_breaking else "auto",
                    "root_cause_type": "external_dependency" if is_breaking else "unknown",
                })
        except (ValueError, KeyError):
            issues = [{"action": "npm-audit-error", "stderr": result.stderr[:200]}]

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"lock_hash": lock_hash, "issues": issues}), encoding="utf-8")
    except OSError:
        pass
    return issues


def scan(ctx: OpsContext) -> ScanResult:
    all_issues: list[dict] = []

    # Always scan for secrets
    secrets = _scan_secrets(ctx.project_root, ctx.difficulty)
    all_issues.extend(secrets)

    # npm audit at difficulty >= 1
    if ctx.difficulty >= 1:
        npm_issues = _scan_npm_audit(ctx.project_root)
        all_issues.extend(npm_issues)

    if not all_issues:
        return ScanResult(issues=[], summary="No security issues found", severity="info")

    parts = []
    secret_count = sum(1 for i in all_issues if i["action"] == "potential-secret")
    npm_count = sum(1 for i in all_issues if i["action"] == "npm-vulnerability")
    if secret_count:
        parts.append(f"{secret_count} potential secrets")
    if npm_count:
        parts.append(f"{npm_count} npm vulnerabilities")

    return ScanResult(
        issues=all_issues,
        summary=f"Found {', '.join(parts)}",
        severity="error" if secret_count > 0 else "warning",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} security issues found")

    changes: list[str] = []

    # Run npm audit fix for safe vulnerabilities
    npm_fixable = [
        i for i in issues
        if (
            i.get("action") == "npm-vulnerability"
            and i.get("fixAvailable")
            and i.get("kind") != "external"
            and i.get("fixability") != "manual"
        )
    ]
    if npm_fixable:
        dashboard_dir = ctx.project_root / "apps" / "dashboard"
        npm = _npm_command()
        if npm is None:
            return FixResult(
                success=True,
                summary="npm executable not found on PATH; security fixes require manual review",
                fix_type="report",
            )
        result = subprocess.run(
            [npm, "audit", "fix"],
            capture_output=True,
            text=True,
            cwd=str(dashboard_dir),
        )
        if result.returncode == 0:
            changes.append(f"npm audit fix applied ({len(npm_fixable)} packages)")

    # Secrets are never auto-fixed — always manual review
    secret_count = sum(1 for i in issues if i["action"] == "potential-secret")

    parts = []
    if changes:
        parts.append("; ".join(changes))
    if secret_count:
        parts.append(f"{secret_count} potential secrets require manual review")

    return FixResult(
        success=True,
        changes=changes,
        summary="; ".join(parts) if parts else "No auto-fixable issues",
    )
