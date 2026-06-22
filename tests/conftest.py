"""
Root pytest conftest.py

Configures import paths for skills and provides src/lib test fixtures.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def pytest_configure(config):
    """Ignore stray console interrupts on Windows CI.

    On Windows the test process shares a console process group with the child
    servers/subprocesses tests spawn; a CTRL_C/CTRL_BREAK event one of them emits
    (or that the runner injects on churn) is delivered to pytest's main thread as
    a spurious KeyboardInterrupt and aborts an otherwise-green run at a
    non-deterministic point. CI is non-interactive, so there is no legitimate
    Ctrl+C to honor. This mirrors the production MCP bridge's
    `_ignore_interactive_interrupts` (SIG_IGN on SIGINT/SIGBREAK) — the reason
    the server itself is immune while the test harness was not.
    """
    if sys.platform != "win32":
        return

    # Use the Selector event loop on Windows. pytest-asyncio's default
    # ProactorEventLoop closes via an IOCP/self-pipe whose teardown at session
    # end emits a console event that kills the process (and shell) right at 100%,
    # before the summary prints — the root of the all-passed-but-exit-1 failure.
    # No test drives asyncio subprocesses (the only Proactor-only feature).
    try:
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:  # noqa: BLE001 - best effort
        pass

    import signal

    for _name in ("SIGINT", "SIGBREAK"):
        _sig = getattr(signal, _name, None)
        if _sig is None:
            continue
        try:
            signal.signal(_sig, signal.SIG_IGN)
        except (ValueError, OSError):  # not main thread / unsupported — best effort
            pass

    # Python's SIG_IGN only covers the interpreter's signal layer. A console
    # CTRL_C/CTRL_BREAK event (from a spawned child's process group, or runner
    # churn) can still hit the process at shutdown and set a non-zero exit even
    # when every test passed. SetConsoleCtrlHandler(NULL, TRUE) makes the whole
    # process ignore Ctrl+C at the OS level for its entire lifetime — the
    # definitive non-interactive-CI fix.
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleCtrlHandler(None, True)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - best effort; never block the test run
        pass


def pytest_sessionfinish(session, exitstatus):
    """Force a clean exit on an all-green Windows run.

    On Windows the process reliably runs every test to completion (the summary
    prints "N passed, 0 failed") but then exit-codes 1: a console CTRL event from
    a background thread / lingering child during interpreter shutdown (GC, thread
    joins, asyncio loop close) corrupts the exit status, and no signal/shell-level
    mitigation has stopped it. When the session itself had zero failures, flush
    output and os._exit(0) — skipping the problematic shutdown phase entirely.
    The reported summary is already written by the time this hook runs.
    """
    if sys.platform != "win32":
        return
    if getattr(session, "testsfailed", 0):
        return  # real failures: let pytest exit non-zero normally
    if int(exitstatus) not in (0,):
        return  # interrupted/usage/internal error: do not mask
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:  # noqa: BLE001
        pass
    os._exit(0)


# =============================================================================
# NO REAL INLINE RAG SYNC IN UNIT TESTS
# =============================================================================
@pytest.fixture(autouse=True)
def _no_real_inline_index_sync(request, monkeypatch):
    """Keep unit tests off the real index-staleness gate.

    `ensure_fresh_index` spawns a worker thread that runs a real `sync_categories`
    (subprocess indexing). On Windows those child processes share pytest's console
    process group, so a console Ctrl event one emits is delivered to pytest as a
    spurious KeyboardInterrupt that aborts an otherwise-green run (production is
    immune — the MCP bridge ignores SIGINT/SIGBREAK; pytest does not). It is also
    slow and side-effectful. Stub it everywhere except the tests that exercise the
    gate itself. (test_unified_search_fusion.py already stubs it locally.)
    """
    if "test_staleness" in request.node.nodeid:
        return
    try:
        from src.lib.index import staleness
    except Exception:
        return
    monkeypatch.setattr(
        staleness,
        "ensure_fresh_index",
        lambda *a, **k: {"stale": False, "synced": False, "warning": None},
        raising=False,
    )


# =============================================================================
# PATH SETUP
# =============================================================================

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _remove_direct_src_mcp_paths() -> None:
    def is_direct_src_mcp_path(path) -> bool:
        try:
            path_text = os.fspath(path)
        except TypeError:
            return False
        if not path_text:
            return False
        normalized = os.path.realpath(os.path.abspath(path_text))
        parts = Path(normalized).parts
        return len(parts) >= 2 and parts[-1] == "mcp" and parts[-2] == "src"

    sys.path = [path for path in sys.path if not is_direct_src_mcp_path(path)]


# Lock the repo-root ``scripts`` package before skill-local test bootstraps add
# their own ``.../scripts`` directories to ``sys.path`` during collection.
try:
    import scripts  # noqa: F401
except ImportError:
    pass

# Root tests import MCP source through the repo package path (`src.mcp.*`).
# Direct `src/mcp` path roots create a second module identity (`augur_*`) for
# the same files and make whole-suite mock.patch targets order-dependent.
_remove_direct_src_mcp_paths()

# Pre-import the pip ``mcp`` package BEFORE adding mcp-app-factory/scripts to
# sys.path. That directory contains its own ``mcp/`` package (the factory's MCP
# tooling), which would shadow the pip ``mcp`` package and break
# ``from mcp.types import ToolAnnotations`` in canonical MCP packages.
try:
    import mcp  # noqa: F401
    import mcp.types  # noqa: F401
except ImportError:
    pass  # mcp pip package not installed; affected tests will fail naturally

# Add mcp-app-factory scripts to path for skill_generation imports
# This allows tests to import skill_generation module directly
# Module moved from the legacy plugin layout to skills/ per ADR-426
plugin_factory_scripts = project_root / ".claude" / "skills" / "mcp-app-factory" / "scripts"
if plugin_factory_scripts.exists() and str(plugin_factory_scripts) not in sys.path:
    sys.path.insert(0, str(plugin_factory_scripts))


def import_plugin_module(bundle: str, skill: str, module_path: str):
    """
    Import a module from a canonical skill with hyphenated name.

    Args:
        bundle: Plugin bundle name (e.g., 'factory')
        skill: Skill name with hyphens (e.g., 'mcp-app-factory')
        module_path: Module path relative to skill (e.g., 'scripts.skill_generation')

    Returns:
        The imported module

    Example:
        skill_gen = import_plugin_module('factory', 'mcp-app-factory', 'scripts.skill_generation')
    """
    import importlib.util

    _unused_bundle = bundle
    skill_dir = project_root / "project-brain" / "capabilities" / "skills" / skill
    module_parts = module_path.split(".")
    module_file = skill_dir / "/".join(module_parts[:-1]) / f"{module_parts[-1]}.py"

    # Try as directory with __init__.py first
    if not module_file.exists():
        module_file = skill_dir / "/".join(module_parts) / "__init__.py"

    if not module_file.exists():
        raise ImportError(f"Cannot find module {module_path} in {skill_dir}")

    spec = importlib.util.spec_from_file_location(module_path, module_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for {module_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_path] = module
    spec.loader.exec_module(module)
    return module


# =============================================================================
# TEST ENVIRONMENT SETUP
# =============================================================================

# Ensure temp and data directories are writable in sandboxed environments
TEST_ROOT = project_root / "tests" / "test-data"
BOOTSTRAP_DATA_DIR = TEST_ROOT / "bootstrap-data"
TMP_ROOT = TEST_ROOT / "tmp"

for path in (BOOTSTRAP_DATA_DIR, TMP_ROOT):
    path.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("AUGUR_ROOT", str(BOOTSTRAP_DATA_DIR))
os.environ.setdefault("TMPDIR", str(TMP_ROOT))
os.environ.setdefault("TMP", str(TMP_ROOT))
os.environ.setdefault("TEMP", str(TMP_ROOT))


# Add all package roots to sys.path to allow imports during collection
def _setup_package_paths():
    plugins_dir = project_root / "plugins"
    if plugins_dir.exists():
        for package in plugins_dir.iterdir():
            if package.is_dir():
                src_dir = package / "src"
                candidate = src_dir if src_dir.exists() else package
                if str(candidate) not in sys.path:
                    sys.path.insert(0, str(candidate))


_setup_package_paths()
_remove_direct_src_mcp_paths()

# =============================================================================
# CORE FIXTURES
# =============================================================================


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root directory."""
    return project_root


@pytest.fixture
def plugins_dir(repo_root: Path) -> Path:
    """Return the canonical shared skills directory."""
    return repo_root / "project-brain" / "capabilities" / "skills"


@pytest.fixture
def all_skill_dirs(plugins_dir: Path) -> list[Path]:
    """Return all skill directories in project-brain/capabilities/skills/."""
    return [d for d in plugins_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]


@pytest.fixture
def src_lib_dir(repo_root: Path) -> Path:
    """Return the src/lib directory."""
    return repo_root / "src/lib"


@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory):
    """
    Create temporary data directory for tests.
    Returns: Path to temporary augur directory
    """
    data_dir = tmp_path_factory.mktemp("augur")
    return data_dir


@pytest.fixture(scope="session")
def test_project_root(repo_root):
    """Alias for repo_root to support legacy tests."""
    return repo_root


# =============================================================================
# LOGGING FIXTURES
# =============================================================================


@pytest.fixture
def test_logger():
    """Get test logger with correlation ID."""
    try:
        from src.logging import (
            generate_correlation_id,
            get_entity_logger,
            set_correlation_id,
        )

        logger = get_entity_logger("tests", log_level="DEBUG")
        corr_id = generate_correlation_id()
        set_correlation_id(corr_id)
        return logger
    except ImportError:
        return logging.getLogger("tests")


@pytest.fixture
def sample_correlation_id():
    """Generate sample correlation ID for testing."""
    try:
        from src.logging import generate_correlation_id

        return generate_correlation_id()
    except ImportError:
        import uuid

        return str(uuid.uuid4())[:8]


@pytest.fixture
def capture_logs(caplog):
    """Capture logs for assertions."""
    caplog.set_level(logging.INFO)
    return caplog


# =============================================================================
# ENVIRONMENT FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def setup_test_environment(test_data_dir, monkeypatch):
    """
    Setup test environment for all tests.
    Auto-applied to every test to ensure isolation.
    """
    _remove_direct_src_mcp_paths()
    monkeypatch.setenv("AUGUR_ROOT", str(test_data_dir))
    monkeypatch.setenv("AUGUR_TEST_MODE", "true")
    (test_data_dir / "runtime" / "logs").mkdir(parents=True, exist_ok=True)
    (test_data_dir / "runtime" / "cache").mkdir(parents=True, exist_ok=True)
    try:
        from src.mcp.augur_shared.config import reset_config

        if reset_config:
            reset_config()
    except Exception:
        pass
    _remove_direct_src_mcp_paths()
    yield
    _remove_direct_src_mcp_paths()


# =============================================================================
# MCP MOCK FIXTURES
# =============================================================================


@pytest.fixture
def mock_mcp_server():
    """Mock MCP server for integration tests."""
    server = MagicMock()
    server.call_tool = MagicMock(return_value={"status": "success", "data": {}})
    server.list_tools = MagicMock(return_value=["list-skills", "get-skill", "skill-action"])
    return server


@pytest.fixture
def mock_skill_execution():
    """Mock skill execution for testing."""

    async def execute(**kwargs):
        return {
            "status": "completed",
            "output": "Test output",
            "artifacts": [],
        }

    return execute


@pytest.fixture
def mock_skill_registry():
    """Mock skill registry for testing."""
    registry = MagicMock()
    registry.list_skills = MagicMock(
        return_value=[
            {
                "id": "careers",
                "name": "Career Consultant",
                "enabled": True,
                "actions": ["sync_jobs", "apply_job"],
            },
            {
                "id": "developer",
                "name": "Developer",
                "enabled": True,
                "actions": ["implement_feature", "fix_bug"],
            },
        ]
    )
    return registry


@pytest.fixture
def mock_skill_config():
    """Provide a consistent mock skill config for MCP generator tests."""
    return {
        "slug": "virtual-doctor",
        "pillars": {
            "capture": {"relevance": 0.8},
            "recall": {"relevance": 1.0},
        },
        "rag_project_id": "virtual-doctor",
        "domain": "medical",
    }
