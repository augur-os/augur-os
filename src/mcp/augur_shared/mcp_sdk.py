"""MCP SDK pinning, metrics, and tool interceptor — shared cross-server utilities.

Extracted from the legacy monolith server and plugin tools in Track 3a PR 1.
After Track 3a, both augur-core and augur-framework depend on this module
(via the augur_shared package); the legacy augur_mcp namespace is retired
in PR 7.

Symbols hosted:
- `_pin_mcp_sdk_package()`: ensures the installed MCP SDK is loaded before
  any skill-local `scripts/mcp` package shadows it.
- `metrics`: global `MetricsTracker` instance used by every MCP tool.
- `mcp_tool_interceptor`: lazy accessor for the decorator that wraps every
  tool with a correlation ID, structured logging, and a thread-pool dispatch
  shim so blocking subprocess/file calls don't stall the asyncio event loop.

The `metrics` and `mcp_tool_interceptor` symbols are re-exported as module
attributes via `__getattr__` so callers see them as plain attributes
(`from src.mcp.augur_shared.mcp_sdk import metrics`) while the underlying
binding stays late-resolved.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from src.config.paths import get_managed_skill_source_dirs

# ---------------------------------------------------------------------------
# SDK pinning (canonical home, moved from plugin_tools.py)
# ---------------------------------------------------------------------------


def _is_managed_skill_import_path(path_entry: str) -> bool:
    if not path_entry:
        return False
    try:
        candidate = Path(path_entry).resolve()
    except (OSError, RuntimeError):
        return False

    for skills_root in get_managed_skill_source_dirs():
        try:
            relative = candidate.relative_to(skills_root.resolve())
        except (OSError, ValueError):
            continue
        parts = relative.parts
        if len(parts) == 1:
            return True
        if len(parts) >= 2 and parts[1] == "scripts":
            return True
    return False


def _module_is_managed_skill_import(name: str) -> bool:
    module = sys.modules.get(name)
    if module is None:
        return False
    module_file = getattr(module, "__file__", None)
    return isinstance(module_file, str) and _is_managed_skill_import_path(module_file)


def _pin_mcp_sdk_package() -> None:
    """Load the real MCP SDK before skill-local ``scripts/mcp`` packages.

    Several skill MCP entrypoints add their local ``scripts`` directory to
    ``sys.path`` for historical imports. Those directories also contain an
    ``mcp`` package for the skill entrypoint, so a later ``import mcp.types``
    can accidentally resolve to a skill package instead of the installed MCP
    SDK. Importing the SDK first pins it in ``sys.modules``.
    """
    if _module_is_managed_skill_import("mcp"):
        for module_name in list(sys.modules):
            if module_name == "mcp" or module_name.startswith("mcp."):
                sys.modules.pop(module_name, None)

    original_sys_path = list(sys.path)
    sys.path = [path_entry for path_entry in original_sys_path if not _is_managed_skill_import_path(path_entry)]
    try:
        import mcp  # noqa: F401
        import mcp.types  # noqa: F401
    except ImportError:
        # Skill packages may not be installed yet during early init.
        pass
    finally:
        sys.path = original_sys_path


_pin_mcp_sdk_package()


# ---------------------------------------------------------------------------
# Canonical metrics + mcp_tool_interceptor definitions.
# ---------------------------------------------------------------------------

# These imports must follow _pin_mcp_sdk_package() above so the real MCP SDK is
# pinned in sys.modules before any transitive skill-local mcp package can shadow it.
import asyncio  # noqa: E402
import functools  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

from src.mcp.augur_shared.config import get_config  # noqa: E402
from src.mcp.augur_shared.logging import get_entity_logger  # noqa: E402
from src.mcp.augur_shared.server_cache import MetricsTracker  # noqa: E402

try:
    from src.mcp.augur_shared.annotations import generate_correlation_id, set_correlation_id
except ImportError:  # annotations module variant

    def generate_correlation_id() -> str:
        import uuid

        return str(uuid.uuid4())

    def set_correlation_id(_corr_id: str) -> None:
        return None


_logger = get_entity_logger("mcp.shared.sdk", log_level="INFO")
_config = get_config()

# Global metrics singleton — used by every MCP tool registered in any server
# (augur-core, augur-framework, or per-bundle vault servers).
metrics = MetricsTracker(_config.metrics_file)


# Thread pool for blocking tool handlers (subprocess.run, file I/O, osascript,
# CLI bridges). Without dispatch to a worker thread, a single blocking tool
# stalls the asyncio event loop and serializes concurrent tool calls.
#
# Sizing: a single dashboard page fans out 10-15 data-card tool calls at once,
# and the user's button actions are *additional* concurrent calls on top. With
# a fixed cap of 8 the button request queued behind the page's cards and timed
# out, surfacing as failed buttons + the "MCP server unreachable" banner. Almost
# all tools are I/O-bound (CLIs, file/RAG/HTTP) so the GIL is released during
# their blocking calls and oversubscription yields real concurrency. Scale with
# CPU and allow an explicit override.
def _tool_pool_max_workers() -> int:
    raw = os.environ.get("AUGUR_MCP_TOOL_WORKERS", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return min(48, max(32, (os.cpu_count() or 4) * 4))


_tool_thread_pool = ThreadPoolExecutor(max_workers=_tool_pool_max_workers(), thread_name_prefix="mcp-tool")


def _run_tool_in_thread(coro: Any, corr_id: str) -> Any:
    """Execute a tool coroutine in a worker thread with its own event loop."""
    set_correlation_id(corr_id)
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Eval-harness capture observer (ADR-742) — opt-in, off by default.
#
# The eval skill registers a lightweight observer the interceptor consults
# AFTER a tool returns successfully. The import is guarded so a missing or
# broken eval skill yields a no-op observer and never breaks tool
# registration; the observer itself is wrapped in try/except inside the eval
# skill and never raises into the tool path.
# ---------------------------------------------------------------------------


def _noop_capture_observer(*_args: Any, **_kwargs: Any) -> None:
    """Fallback observer when the eval skill is unavailable — does nothing."""
    return None


def _load_capture_observer() -> Any:
    """Import the eval skill's capture observer; fall back to a no-op."""
    try:
        import importlib.util as _il

        from src.config.paths import get_project_brain_skills_dir, get_project_root

        capture_path = get_project_brain_skills_dir(get_project_root()) / "evals" / "scripts" / "capture.py"
        if not capture_path.is_file():
            return _noop_capture_observer
        spec = _il.spec_from_file_location("_augur_evals_capture", capture_path)
        if spec is None or spec.loader is None:
            return _noop_capture_observer
        module = _il.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module.register_capture_observer()
    except Exception as exc:  # noqa: BLE001 - never break tool registration
        _logger.warning("eval capture observer unavailable (no-op): %s", exc)
        return _noop_capture_observer


_capture_observer = _load_capture_observer()


# --- Structured invocation log (ADR-804) — always-on, local, truncated, never raises.
# One JSON line per tool call carrying the inputs (args) and output (result), so the
# skill optimizer's "replay real runs" has real cases to validate edits against.
_INVOCATION_LOG_DISABLED = False
_INVOCATION_ARG_CAP = 2000
_INVOCATION_RESULT_CAP = 4000
_INVOCATION_LOG_MAX_BYTES = 8_000_000


def _truncate_str(value: Any, cap: int) -> str:
    try:
        s = value if isinstance(value, str) else json.dumps(value, default=str)
    except Exception:
        s = str(value)
    return s if len(s) <= cap else s[:cap] + "…[truncated]"


def _safe_args(kwargs: dict) -> dict:
    """Keep args as a dict (replay needs structured inputs); truncate oversized strings."""
    out: dict = {}
    for key, value in (kwargs or {}).items():
        if key in ("self", "ctx", "context"):
            continue
        if isinstance(value, str) and len(value) > _INVOCATION_ARG_CAP:
            out[key] = value[:_INVOCATION_ARG_CAP] + "…[truncated]"
        else:
            out[key] = value
    return out


def _record_invocation(tool_name: str, kwargs: dict, result: Any, duration_ms: int) -> None:
    """Append a {ts, tool, args, result} JSON line for optimizer replay (ADR-804)."""
    global _INVOCATION_LOG_DISABLED
    if _INVOCATION_LOG_DISABLED:
        return
    try:
        import time as _time

        from src.config.paths import get_logs_dir

        path = Path(get_logs_dir()) / "mcp_invocations.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > _INVOCATION_LOG_MAX_BYTES:
            tail = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-20000:]
            path.write_text("\n".join(tail) + "\n", encoding="utf-8")
        rec = {
            "ts": _time.time(),
            "tool": tool_name,
            "args": _safe_args(kwargs),
            "result": _truncate_str(result, _INVOCATION_RESULT_CAP),
            "duration_ms": duration_ms,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(rec, default=str) + "\n")
    except Exception:
        _INVOCATION_LOG_DISABLED = True  # stop trying; never affect the live tool path


def mcp_tool_interceptor(func: Any) -> Any:
    """Decorator: add correlation IDs + dispatch tools to a thread pool.

    Uses functools.wraps + __wrapped__ to preserve the original signature
    so the MCP SDK's Pydantic validation continues to work.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        corr_id = generate_correlation_id()
        set_correlation_id(corr_id)
        tool_name = func.__name__
        _logger.info(f"Tool invoked: {tool_name}", extra={"correlation_id": corr_id})
        _started_ns = time.monotonic_ns()
        try:
            loop = asyncio.get_running_loop()
            coro = func(*args, **kwargs)
            result = await loop.run_in_executor(
                _tool_thread_pool,
                functools.partial(_run_tool_in_thread, coro, corr_id),
            )
            _logger.info(f"Tool completed: {tool_name}", extra={"correlation_id": corr_id})
            # Eval-harness capture (ADR-742) — opt-in, off by default. The
            # observer is a no-op unless contributor mode + consent are set;
            # it is wrapped in try/except inside the eval skill and never
            # raises. The extra guard here keeps capture from ever affecting
            # the live tool result.
            _duration_ms = int((time.monotonic_ns() - _started_ns) / 1_000_000)
            try:
                _capture_observer(tool_name, args, kwargs, result, _duration_ms)
            except Exception as _capture_exc:  # noqa: BLE001
                _logger.warning(
                    f"eval capture observer raised (swallowed): {_capture_exc}",
                    extra={"correlation_id": corr_id},
                )
            # Structured invocation log (ADR-804) — always-on replay source; never raises.
            _record_invocation(tool_name, kwargs, result, _duration_ms)
            return result
        except Exception as e:
            _logger.error(
                f"Tool failed: {tool_name} | {type(e).__name__}: {e}",
                extra={"correlation_id": corr_id, "error": str(e)},
                exc_info=True,
            )
            raise

    wrapper.__wrapped__ = func
    return wrapper


__all__ = [
    "_pin_mcp_sdk_package",
    "metrics",
    "mcp_tool_interceptor",
]
