"""Shared test bootstrap for daemon adaptive modules."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Pre-import the pip ``mcp`` package before adding skill-local script dirs to
# sys.path, since some skill scripts contain their own ``mcp`` subpackage that
# would shadow the SDK. Mirrors the root tests/conftest.py + ai skill conftest.
try:
    import mcp  # noqa: F401
    import mcp.types  # noqa: F401
    import mcp.server.fastmcp  # noqa: F401
except ImportError:
    pass

# Repo root for src.* imports.
_REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DAEMON_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(DAEMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(DAEMON_SCRIPTS_DIR))


def _force_load_daemon_module(bare_name: str) -> None:
    """Pre-load daemon's version of a generic-named module and register it under
    its bare name in sys.modules. Without this, an earlier test in the sweep that
    loaded ai's same-named module (e.g. ai/scripts/bootstrap_paths.py) leaves
    sys.modules['bootstrap_paths'] pointing at ai's version — and any subsequent
    daemon test that does `from bootstrap_paths import <daemon_only_symbol>`
    fails with ImportError. See feedback-sys-modules-namespacing-discipline memory.
    """
    path = DAEMON_SCRIPTS_DIR / f"{bare_name}.py"
    if not path.is_file():
        return
    spec = importlib.util.spec_from_file_location(bare_name, path)
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[bare_name] = module
    spec.loader.exec_module(module)


# Generic-named modules that exist in MULTIPLE skills — force-load daemon's
# versions so bare-name imports in daemon tests find daemon's symbols, not
# another skill's. ai + daemon both have bootstrap_paths.py and runtime_paths.py.
# cleanup_processes.py exists in BOTH daemon and platform-admin: daemon's is a
# superset (adds kill_process_group), and continuous_executor.py puts
# platform-admin/scripts on sys.path, so without this pre-load a daemon-dir
# sweep that collects test_continuous_executor first poisons
# sys.modules['cleanup_processes'] with platform-admin's version, breaking
# scoped_restart's `import cleanup_processes` (no attribute kill_process_group).
for _generic in ("bootstrap_paths", "runtime_paths", "cleanup_processes"):
    _force_load_daemon_module(_generic)
