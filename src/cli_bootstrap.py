"""
Augur CLI bootstrap — resolve AUGUR_ROOT and configure sys.path.

Three resolution modes:
1. Active cwd checkout/worktree
2. AUGUR_ROOT env var (explicit override outside a checkout)
3. Repo checkout (editable install — __file__ relative)
4. ~/.augur/ auto-setup (pip install without repo)
"""

import os
import sys
from pathlib import Path


def _is_repo_checkout(candidate: Path) -> bool:
    """Check if candidate looks like a full Augur repo checkout."""
    # Post Track 3a + dismantle: augur_mcp/ was retired; augur_shared/ is the
    # new shared package guaranteed to exist in any repo checkout.
    return (candidate / "src" / "mcp" / "augur_shared").is_dir()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def _project_root_from_cwd() -> Path | None:
    """Resolve the active checkout from cwd, including git worktrees."""
    try:
        current = Path.cwd().resolve()
    except OSError:
        return None

    for candidate in (current, *current.parents):
        if _is_repo_checkout(candidate):
            return candidate
    return None


def _get_user_dir() -> Path:
    """Return ~/.augur/ path. Does not create directories (lazy)."""
    return Path.home() / ".augur"


def _ensure_user_dir() -> Path:
    """Create ~/.augur/ with minimal structure for standalone install."""
    user_dir = _get_user_dir()
    for subdir in ("config", "state", "state/sessions", "plugins"):
        (user_dir / subdir).mkdir(parents=True, exist_ok=True)
    return user_dir


def resolve_project_root() -> Path:
    """Resolve AUGUR_ROOT using the three-tier strategy.

    Does NOT create directories — callers that need runtime dirs
    should call _ensure_user_dir() when actually needed.
    """
    # 1. Active checkout/worktree. This prevents a global pipx `aug` entrypoint
    # from pulling main-checkout state while the user is inside a worktree.
    cwd_root = _project_root_from_cwd()

    # 2. Explicit env var, unless cwd is a different checkout.
    if "AUGUR_ROOT" in os.environ:
        env_root = Path(os.environ["AUGUR_ROOT"]).resolve()
        if cwd_root is not None and cwd_root != env_root:
            return cwd_root
        return env_root

    if cwd_root is not None:
        return cwd_root

    # 3. Repo checkout (editable install)
    repo_candidate = Path(__file__).resolve().parent.parent
    if _is_repo_checkout(repo_candidate):
        return repo_candidate

    # 4. Standalone pip install — return ~/.augur/ without creating dirs
    return _get_user_dir()


def _is_bootstrap_path(entry: str, project_root: Path) -> bool:
    """Return True for current or stale Augur paths that should be re-ordered."""
    if not entry:
        return False
    try:
        path = Path(entry).resolve()
    except (OSError, RuntimeError):
        return False

    src_dir = project_root / "src"
    package_src = project_root / "src" / "mcp"
    if path in {project_root.resolve(), src_dir.resolve(), package_src.resolve()}:
        return True
    if path.name == "mcp" and (path / "augur_shared").is_dir():
        return True
    return _is_repo_checkout(path)


def _update_loaded_src_package(project_root: Path) -> None:
    """Point an already-imported ``src`` package at the active checkout."""
    src_pkg = sys.modules.get("src")
    if src_pkg is None or not hasattr(src_pkg, "__path__"):
        return

    src_dir = project_root / "src"
    src_init = src_dir / "__init__.py"
    if not src_init.exists():
        return
    src_pkg.__path__ = [str(src_dir)]  # type: ignore[attr-defined]
    src_pkg.__file__ = str(src_init)  # type: ignore[attr-defined]


def _purge_stale_src_submodules(project_root: Path) -> None:
    """Drop already-imported src.* modules that came from another checkout."""
    keep = {"src.cli", "src.cli_bootstrap"}
    for name, module in list(sys.modules.items()):
        if not name.startswith("src.") or name in keep:
            continue
        module_file = getattr(module, "__file__", None)
        if not module_file:
            continue
        try:
            module_path = Path(module_file)
        except TypeError:
            continue
        if not _is_relative_to(module_path, project_root):
            sys.modules.pop(name, None)


def configure_sys_path(project_root: Path) -> None:
    """Set up sys.path for augur_mcp and src.* imports."""
    package_src = project_root / "src" / "mcp"

    # Remove stale Augur checkout paths, plus src/ because it shadows stdlib
    # modules such as logging. Then put the active checkout first.
    sys.path = [p for p in sys.path if not _is_bootstrap_path(p, project_root)]
    sys.path.insert(0, str(package_src))
    sys.path.insert(0, str(project_root))
    _update_loaded_src_package(project_root)
    _purge_stale_src_submodules(project_root)


def should_reexec_cli_from_project_root(project_root: Path, cli_file: str | Path) -> bool:
    """Return True when a console script imported ``src.cli`` from another checkout."""
    if not _is_repo_checkout(project_root):
        return False
    if not _is_relative_to(Path(cli_file), project_root):
        return True
    return not _is_current_project_python(project_root)


def _project_python_candidates(project_root: Path) -> tuple[Path, ...]:
    return (
        project_root / ".venv" / "bin" / "python3",
        project_root / ".venv" / "bin" / "python",
        project_root / ".venv" / "Scripts" / "python.exe",
    )


def _project_python(project_root: Path) -> str:
    candidates = _project_python_candidates(project_root)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _is_current_project_python(project_root: Path) -> bool:
    candidates = [candidate for candidate in _project_python_candidates(project_root) if candidate.exists()]
    if not candidates:
        return True
    try:
        executable = Path(sys.executable).resolve()
    except (OSError, RuntimeError):
        return False
    for candidate in candidates:
        try:
            if executable == candidate.resolve():
                return True
        except (OSError, RuntimeError):
            continue
    return False


def _prepend_pythonpath(project_root: Path, existing: str | None) -> str:
    canonical = [
        str(project_root / "project-brain" / "capabilities"),
        str(project_root),
        str(project_root / "src" / "mcp"),
    ]
    kept: list[str] = []
    for entry in (existing or "").split(os.pathsep):
        if not entry or entry in canonical:
            continue
        try:
            entry_path = Path(entry).resolve()
        except (OSError, RuntimeError):
            kept.append(entry)
            continue
        if _is_repo_checkout(entry_path) or entry_path.name in {"mcp", "capabilities"}:
            continue
        kept.append(entry)
    return os.pathsep.join([*canonical, *kept])


def reexec_cli_from_project_root_if_needed(project_root: Path, cli_file: str | Path) -> None:
    """Re-exec a globally installed ``aug`` entrypoint through the active checkout."""
    if os.environ.get("AUGUR_CLI_REEXECED") == "1":
        return
    if not should_reexec_cli_from_project_root(project_root, cli_file):
        return

    env = os.environ.copy()
    env["AUGUR_ROOT"] = str(project_root)
    env["AUGUR_CORE"] = str(project_root)
    env["AUGUR_REPO"] = str(project_root)
    env["AUGUR_CLI_REEXECED"] = "1"
    env["PYTHONPATH"] = _prepend_pythonpath(project_root, env.get("PYTHONPATH"))

    os.chdir(project_root)
    python = _project_python(project_root)
    os.execvpe(python, [python, "-m", "src.cli", *sys.argv[1:]], env)


def bootstrap() -> Path:
    """Full bootstrap: resolve root, configure paths. Returns project root."""
    project_root = resolve_project_root()
    configure_sys_path(project_root)
    return project_root
