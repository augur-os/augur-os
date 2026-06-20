"""Deterministic scan dispatch for the ADR-755 routine orchestrator."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.lib.ops_protocol import OpsContext, SessionContext


class ScanCommand:
    """Small test-friendly command wrapper for scan dispatch."""

    def __init__(
        self,
        *,
        name: str,
        module: Any,
        loop_name: str,
        config: dict[str, Any],
        tier: int = 0,
    ) -> None:
        self.name = name
        self.module = module
        self.loop_name = loop_name
        self.config = config
        self.tier = tier


def scan_loop(
    loop_name: str,
    *,
    project_root: Path | str | None = None,
    commands: Iterable[Any] | Mapping[str, Any] | None = None,
    session: SessionContext | None = None,
    difficulty: int = 0,
    loop_config: dict[str, Any] | None = None,
    shared_snapshot: dict[str, Any] | None = None,
    client: str | None = None,
) -> list[dict[str, Any]]:
    """Run scan() for every command in ``loop_name`` and return flat findings.

    Production callers omit ``commands`` so discovery goes through
    ``adaptive.discovery.discover_auto_commands``. Tests can pass loaded fixture
    modules or entry-like objects directly.
    """
    root = Path(project_root) if project_root is not None else _find_project_root()
    entries = _resolve_commands(loop_name, root, commands)
    findings: list[dict[str, Any]] = []

    for entry in entries:
        ctx = OpsContext(
            project_root=root,
            difficulty=difficulty,
            dry_run=True,
            config=dict(entry.config),
            loop_config=dict(loop_config or {}),
            shared_snapshot=dict(shared_snapshot or {}),
            session=session or SessionContext(),
            client=client,
        )
        try:
            scan_result = entry.module.scan(ctx)
        except Exception as exc:  # noqa: BLE001 - scan crashes are reported as findings.
            findings.append(_scan_error_finding(entry, loop_name, exc))
            continue

        for issue in _scan_issues(scan_result):
            finding = dict(issue) if isinstance(issue, dict) else {"detail": str(issue)}
            finding["auto_command"] = entry.name
            finding["loop"] = loop_name
            findings.append(finding)

    return findings


def discover_loop_commands(loop_name: str, project_root: Path | str | None = None) -> list[ScanCommand]:
    """Discover production auto-commands for one loop via adaptive discovery."""
    root = Path(project_root) if project_root is not None else _find_project_root()
    discovery = _load_adaptive_discovery()
    registry = discovery.discover_auto_commands(root)
    grouped = discovery.group_by_loop(registry)
    return [
        _coerce_command_entry(entry, loop_name=loop_name)
        for entry in grouped.get(loop_name, [])
    ]


def _resolve_commands(
    loop_name: str,
    project_root: Path,
    commands: Iterable[Any] | Mapping[str, Any] | None,
) -> list[ScanCommand]:
    if commands is None:
        return discover_loop_commands(loop_name, project_root)

    raw_commands: Iterable[Any]
    if isinstance(commands, Mapping):
        raw_commands = [
            command if _looks_like_entry(command) else _mapping_entry(name, command, loop_name)
            for name, command in commands.items()
        ]
    else:
        raw_commands = commands

    entries = [_coerce_command_entry(command, loop_name=loop_name) for command in raw_commands]
    return [entry for entry in entries if entry.loop_name == loop_name]


def _coerce_command_entry(command: Any, *, loop_name: str) -> ScanCommand:
    if _looks_like_entry(command):
        module = command.module
        name = str(getattr(command, "name", "") or getattr(module, "name", ""))
        entry_loop = str(getattr(command, "loop_name", "") or loop_name)
        config = getattr(command, "config", {}) or {}
        tier = int(getattr(command, "tier", 0) or 0)
        return ScanCommand(
            name=name,
            module=module,
            loop_name=entry_loop,
            config=dict(config),
            tier=tier,
        )

    name = str(getattr(command, "name", "") or getattr(command, "__name__", "auto-command"))
    return ScanCommand(name=name, module=command, loop_name=loop_name, config={})


def _mapping_entry(name: str, module: Any, loop_name: str) -> ScanCommand:
    return ScanCommand(name=str(name), module=module, loop_name=loop_name, config={})


def _looks_like_entry(command: Any) -> bool:
    return hasattr(command, "module") and callable(getattr(command.module, "scan", None))


def _scan_issues(scan_result: Any) -> list[Any]:
    if scan_result is None:
        return []
    if isinstance(scan_result, list):
        return scan_result
    if isinstance(scan_result, dict):
        issues = scan_result.get("issues", [])
    else:
        issues = getattr(scan_result, "issues", [])
    if issues is None:
        return []
    return list(issues)


def _scan_error_finding(entry: ScanCommand, loop_name: str, exc: Exception) -> dict[str, Any]:
    return {
        "kind": "scan-error",
        "band": "mechanical",
        "finding_band": "mechanical",
        "error_message": str(exc),
        "auto_command": entry.name,
        "loop": loop_name,
    }


def _load_adaptive_discovery() -> Any:
    scripts_dir = Path(__file__).resolve().parents[1]
    discovery_path = scripts_dir / "adaptive" / "discovery.py"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    spec = importlib.util.spec_from_file_location("adaptive.discovery", discovery_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load adaptive discovery from {discovery_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in (current.parent, *current.parents):
        if (parent / "src").is_dir() and (parent / "config").is_dir():
            return parent
    return Path.cwd()
