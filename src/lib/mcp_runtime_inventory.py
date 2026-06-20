"""Live Augur MCP process inventory for Browse observability."""

from __future__ import annotations

import shlex
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class AugurMcpProcess:
    pid: int
    ppid: int
    server_id: str
    client_id: str
    bundle: str
    command: str


def _module_index(args: list[str], module_name: str) -> int:
    for index, arg in enumerate(args[:-1]):
        if arg == "-m" and args[index + 1] == module_name:
            return index
    return -1


def _client_id_from_args(args: list[str]) -> str:
    for index, arg in enumerate(args):
        if arg == "--client-id" and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith("--client-id="):
            return arg.split("=", 1)[1]
    return ""


def _parse_process_line(line: str) -> AugurMcpProcess | None:
    parts = line.strip().split(None, 2)
    if len(parts) < 3:
        return None
    try:
        pid = int(parts[0])
        ppid = int(parts[1])
    except ValueError:
        return None

    command = parts[2].strip()
    try:
        args = shlex.split(command)
    except ValueError:
        return None

    if _module_index(args, "augur_core") >= 0:
        return AugurMcpProcess(
            pid=pid,
            ppid=ppid,
            server_id="augur-core",
            client_id=_client_id_from_args(args),
            bundle="",
            command=command,
        )

    if _module_index(args, "augur_framework") >= 0:
        return AugurMcpProcess(
            pid=pid,
            ppid=ppid,
            server_id="augur-framework",
            client_id=_client_id_from_args(args),
            bundle="",
            command=command,
        )

    bundle_index = _module_index(args, "augur_shared.bundle_server")
    if bundle_index >= 0 and bundle_index + 2 < len(args):
        bundle = args[bundle_index + 2].strip()
        if not bundle or bundle.startswith("-"):
            return None
        return AugurMcpProcess(
            pid=pid,
            ppid=ppid,
            server_id=f"augur-{bundle}",
            client_id=_client_id_from_args(args),
            bundle=bundle,
            command=command,
        )

    return None


def parse_augur_mcp_processes(ps_output: str) -> list[AugurMcpProcess]:
    """Parse `ps -axo pid=,ppid=,command=` output into Augur MCP processes."""
    processes: list[AugurMcpProcess] = []
    for line in ps_output.splitlines():
        process = _parse_process_line(line)
        if process is not None:
            processes.append(process)
    return processes


def collect_augur_mcp_processes() -> list[AugurMcpProcess]:
    """Collect live Augur MCP processes from the local process table."""
    try:
        ps_output = subprocess.check_output(
            ["ps", "-axo", "pid=,ppid=,command="],
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_augur_mcp_processes(ps_output)


def _join_unique(values: Iterable[str]) -> str:
    return ",".join(dict.fromkeys(value for value in values if value))


def _runtime_fields(
    processes: list[AugurMcpProcess],
    *,
    configured: bool,
) -> dict[str, object]:
    status = "configured-running" if configured else "stale-running"
    if configured and not processes:
        status = "configured-stopped"

    return {
        "runtime_status": status,
        "runtime_pids": ",".join(str(process.pid) for process in processes),
        "running_clients": _join_unique(process.client_id for process in processes),
        "runtime_process_count": len(processes),
        "runtime_commands": " | ".join(process.command for process in processes),
        "stale_runtime": not configured,
    }


def enrich_mcp_server_entries_with_runtime(
    entries: list[dict],
    *,
    ps_output: str | None = None,
) -> list[dict]:
    """Add live runtime metadata to configured MCP server Browse entries.

    Running Augur MCP processes with no configured server row are returned as
    synthetic `stale-runtime` rows so Browse can surface process-resident drift.
    """
    processes = parse_augur_mcp_processes(ps_output) if ps_output is not None else collect_augur_mcp_processes()
    running_by_server: dict[str, list[AugurMcpProcess]] = defaultdict(list)
    for process in processes:
        running_by_server[process.server_id].append(process)

    configured_ids = {str(entry.get("id") or "").strip() for entry in entries}
    enriched: list[dict] = []
    for entry in entries:
        server_id = str(entry.get("id") or "").strip()
        server_processes = running_by_server.get(server_id, [])
        updated = dict(entry)
        updated.update(_runtime_fields(server_processes, configured=True))
        enriched.append(updated)

    for server_id in sorted(set(running_by_server) - configured_ids):
        server_processes = running_by_server[server_id]
        bundle = _join_unique(process.bundle for process in server_processes)
        stale_entry = {
            "id": server_id,
            "title": f"{server_id} (stale runtime)",
            "name": server_id,
            "description": ("Running Augur MCP process not declared in " "config/system/mcp_servers.yaml"),
            "category": "mcp-servers",
            "tier": "runtime",
            "command": "",
            "args": "",
            "bundle": bundle,
            "bundle_path": "",
            "source_path": "",
            "status": "stale-runtime",
        }
        stale_entry.update(_runtime_fields(server_processes, configured=False))
        enriched.append(stale_entry)

    return enriched
