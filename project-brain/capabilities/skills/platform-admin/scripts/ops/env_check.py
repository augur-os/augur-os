"""auto-env-check: Validate environment variable usage against documentation.

Scans source files for env var references and checks whether each variable
is documented in .env.example, .env.local.example, or .env files.

Difficulty gates:
  - d0: TypeScript in apps/dashboard/ only
  - d1+: also Python in src/ and skills/
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
import re
from pathlib import Path

from src.config.paths import get_project_brain_skills_dir
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    make_issue,
    report_only_fix,
)

name = "auto-env-check"

DIFFICULTY_SPEC = {
    0: "Dashboard TypeScript env var usage only",
    1: "Also scan Python files in src/ and skills/",
    2: "Same as d1 (full coverage)",
    3: "Same as d1 (full coverage)",
    4: "Same as d1 (full coverage)",
}

# ---------------------------------------------------------------------------
# Env var extraction patterns
# ---------------------------------------------------------------------------

# TypeScript: process.env.SOME_VAR or process.env['SOME_VAR'] or process.env["SOME_VAR"]
_TS_PROCESS_ENV_DOT = re.compile(r"process\.env\.([A-Z_][A-Z0-9_]*)")
_TS_PROCESS_ENV_BRACKET = re.compile(r"""process\.env\[['"]([A-Z_][A-Z0-9_]*)['"]\]""")

# Python: os.environ["VAR"], os.environ.get("VAR"), os.getenv("VAR")
_PY_ENVIRON_BRACKET = re.compile(r"""os\.environ\[['"]([A-Z_][A-Z0-9_]*)['"]\]""")
_PY_ENVIRON_GET = re.compile(r"""os\.environ\.get\(\s*['"]([A-Z_][A-Z0-9_]*)['"]""")
_PY_GETENV = re.compile(r"""os\.getenv\(\s*['"]([A-Z_][A-Z0-9_]*)['"]""")

# Well-known env vars that are always expected — never flag as undocumented.
# Categories: builtins, OS/platform, networking, Python, external APIs,
# CI, SMTP, credentials, framework internals, IDE client detection.
_BUILTIN_VARS: set[str] = {
    # Node.js / Next.js builtins
    "CI",
    "HOME",
    "HOSTNAME",
    "NODE_ENV",
    "PATH",
    "PORT",
    "PWD",
    "SHELL",
    "TERM",
    "TZ",
    "USER",
    "VERCEL",
    "VERCEL_ENV",
    "VERCEL_URL",
    "NEXT_RUNTIME",
    "NEXT_PUBLIC_VERCEL_URL",
    "__NEXT_PRIVATE_PREBUNDLED_REACT",
    "TURBOPACK",
    # Regex placeholder — matched from this file's own docstring (line 41)
    "VAR",
    # OS / platform (Windows)
    "APPDATA",
    "LOCALAPPDATA",
    "PATHEXT",
    "PROGRAMFILES",
    "USERNAME",
    "USERDOMAIN",
    "USERPROFILE",
    # Networking / proxy
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    # Python ecosystem
    "PIP_TRUSTED_HOST",
    "PYTHONIOENCODING",
    "PYTHONUTF8",
    "VIRTUAL_ENV",
    # External API keys / tokens
    "ANTHROPIC_API_KEY",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "OPENAI_API_KEY",
    # CI (GitHub Actions)
    "GITHUB_ACTIONS",
    "GITHUB_OUTPUT",
    "GITHUB_SHA",
    # SMTP / alerting
    "ALERT_EMAIL",
    "SMTP_HOST",
    "SMTP_PORT",
    # Credentials (should never appear in docs)
    "INBOX_EMAIL_PASSWORD",
    # Internal framework
    "CHAIN_CONTEXT",
    "EDITOR",
    "INIT_CWD",
    "JEST_WORKER_ID",
    "MCP_PORT",
    "PYTHONPATH",
    "PYTEST_CURRENT_TEST",
    # Slack
    "SLACK_WEBHOOK_URL",
    "VISUAL",
    # IDE client detection (set by external tools, not users)
    "AUGUR_CLAUDE_PLUGIN_CACHE",
    "AUGUR_CORE",
    "AUGUR_MCP_CLIENT_ID",
    "AUGUR_REPO",
    "AUGUR_RUNTIME",
    "AUGUR_RUNTIME_DIR",
    "AUGUR_STATE",
    "CLAUDE_DESKTOP",
    "CLAUDE_PLUGINS_CACHE",
    "CODEIUM_SESSION",
    "CODEX_HOME",
    "CODEX_THREAD_ID",
    "CURSOR_CONFIG_DIR",
    "CURSOR_SESSION_ID",
    "WINDSURF_SESSION_ID",
    # Common platform path overrides and local build/test toggles
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
    "MOUNT_WARN_ONLY",
    "SKIP_TYPE_CHECK",
}


def _collect_ts_files(directories: list[Path]) -> list[Path]:
    """Collect TypeScript files, excluding node_modules and build output."""
    files: list[Path] = []
    for d in directories:
        if not d.is_dir():
            continue
        for ext in ("*.ts", "*.tsx"):
            files.extend(d.rglob(ext))
    return [
        f for f in files
        if "node_modules" not in f.parts
        and ".next" not in f.parts
        and "__tests__" not in f.parts
        and not f.name.endswith(".d.ts")
    ]


def _collect_py_files(directories: list[Path]) -> list[Path]:
    """Collect Python files, excluding caches and venvs."""
    files: list[Path] = []
    for d in directories:
        if not d.is_dir():
            continue
        files.extend(d.rglob("*.py"))
    return [
        f for f in files
        if "__pycache__" not in f.parts
        and ".venv" not in f.parts
        and "node_modules" not in f.parts
        and "tests" not in f.parts
    ]


def _extract_env_vars_ts(content: str) -> set[str]:
    """Extract env var names from TypeScript content."""
    vars_found: set[str] = set()
    vars_found.update(_TS_PROCESS_ENV_DOT.findall(content))
    vars_found.update(_TS_PROCESS_ENV_BRACKET.findall(content))
    return vars_found


def _extract_env_vars_py(content: str) -> set[str]:
    """Extract env var names from Python content."""
    vars_found: set[str] = set()
    vars_found.update(_PY_ENVIRON_BRACKET.findall(content))
    vars_found.update(_PY_ENVIRON_GET.findall(content))
    vars_found.update(_PY_GETENV.findall(content))
    return vars_found


def _load_documented_vars(project_root: Path) -> set[str]:
    """Load env var names from .env example/documentation files."""
    documented: set[str] = set()
    env_files = [
        project_root / ".env.example",
        project_root / ".env.local.example",
        project_root / ".env",
        project_root / "apps" / "dashboard" / ".env.example",
        project_root / "apps" / "dashboard" / ".env.local.example",
        project_root / "apps" / "dashboard" / ".env",
        project_root / "apps" / "dashboard" / ".env.local",
    ]

    # Also search for any .env* files at project root
    for env_file in project_root.glob(".env*"):
        if env_file.is_file() and env_file not in env_files:
            env_files.append(env_file)

    env_line_re = re.compile(r"^([A-Z_][A-Z0-9_]*)\s*=", re.MULTILINE)

    for env_file in env_files:
        if not env_file.is_file():
            continue
        try:
            content = env_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        documented.update(env_line_re.findall(content))

    return documented


def _shorten_path(full_path: Path, project_root: Path) -> str:
    """Convert absolute path to relative for display."""
    try:
        return str(full_path.relative_to(project_root.resolve()))
    except ValueError:
        return str(full_path)


# ---------------------------------------------------------------------------
# Scan / Fix
# ---------------------------------------------------------------------------

def scan(ctx: OpsContext) -> ScanResult:
    """Check for undocumented environment variable references."""
    root = ctx.project_root
    documented_vars = _load_documented_vars(root)
    all_builtins = _BUILTIN_VARS | documented_vars

    # Track which vars are referenced and where
    var_locations: dict[str, list[str]] = {}  # var_name -> [file_paths]
    items_scanned = 0

    # --- TypeScript ---
    ts_dirs = [root / "apps" / "dashboard"]
    ts_files = _collect_ts_files(ts_dirs)
    items_scanned += len(ts_files)

    for ts_file in ts_files:
        try:
            content = ts_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        env_vars = _extract_env_vars_ts(content)
        rel_path = _shorten_path(ts_file, root)
        for var in env_vars:
            if var not in all_builtins:
                var_locations.setdefault(var, []).append(rel_path)

    # --- Python (difficulty >= 1) ---
    if ctx.difficulty >= 1:
        py_dirs = [
            root / "src",
            get_project_brain_skills_dir(root),
        ]
        py_files = _collect_py_files(py_dirs)
        items_scanned += len(py_files)

        for py_file in py_files:
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            env_vars = _extract_env_vars_py(content)
            rel_path = _shorten_path(py_file, root)
            for var in env_vars:
                if var not in all_builtins:
                    var_locations.setdefault(var, []).append(rel_path)

    # Build issues
    issues: list[dict] = []
    for var_name in sorted(var_locations):
        locations = var_locations[var_name]
        # Deduplicate and limit file list for readability
        unique_files = sorted(set(locations))
        file_list = ", ".join(unique_files[:5])
        if len(unique_files) > 5:
            file_list += f" (+{len(unique_files) - 5} more)"

        issues.append(
            make_issue(
                category="env-check",
                detail=f"Undocumented env var {var_name} used in: {file_list}",
                path=unique_files[0],
                kind="actionable",
                root_cause_type="manual_debt",
                fixability="easy",
                var_name=var_name,
                locations=unique_files,
                count=len(unique_files),
            )
        )

    if not issues:
        return ScanResult(
            issues=[],
            summary=f"All env vars documented ({items_scanned} files scanned, {len(documented_vars)} vars documented)",
            severity="info",
            items_scanned=items_scanned,
        )

    total_refs = sum(i.get("count", 0) for i in issues)
    return ScanResult(
        issues=issues,
        summary=f"Found {len(issues)} undocumented env var(s) across {total_refs} reference(s)",
        severity="warning",
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Report undocumented env vars (manual documentation required)."""
    return report_only_fix(ctx, "env_check.json", issues, noun="undocumented env var")
