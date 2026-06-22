"""Internal path/template helpers for config adapters.

Resolves manifest template variables (e.g. ``${AUGUR_ROOT}``) and
``cwd_required`` at sync time so adapters write fully-resolved absolute
values to user-tier client configs.
"""

from __future__ import annotations

import os
import string
from pathlib import Path

from src.cli_config.manifest import ServerEntry
from src.config.paths import get_project_root, get_vault_dir


def resolve_entry(entry: ServerEntry) -> ServerEntry:
    """Expand template variables and resolve interpreter path in a server entry.

    Substitutes ``${AUGUR_ROOT}`` with the absolute path to the current
    Augur checkout and ``${AUGUR_VAULT}`` with the configured vault root
    (so vault-tier bundle paths follow a relocated vault instead of a baked
    ``~/Projects/Au-vault`` literal). If ``command == "python"``, resolves to
    the project venv interpreter when present; otherwise leaves it as the bare
    ``python`` to fall back on the user's PATH.

    Returns a new ``ServerEntry`` with expanded values; does not mutate.
    """
    # Forward slashes: these land in JSON/TOML client configs. Native Windows
    # backslashes are invalid JSON escapes ("\U", "\t" ...) and break posix path
    # assertions; "/" is valid JSON and a legal path separator on Windows.
    augur_root = get_project_root().as_posix()
    substitutions = {"AUGUR_ROOT": augur_root, "AUGUR_VAULT": get_vault_dir().as_posix()}

    def expand(s: str) -> str:
        return string.Template(s).safe_substitute(substitutions)

    # Resolve `python` -> project venv interpreter if present.
    command = entry.command
    if command == "python":
        if os.name == "nt":
            venv_python = Path(augur_root) / ".venv" / "Scripts" / "python.exe"
        else:
            venv_python = Path(augur_root) / ".venv" / "bin" / "python3"
        if venv_python.exists():
            command = venv_python.as_posix()

    return ServerEntry(
        id=entry.id,
        description=entry.description,
        command=command,
        args=[expand(a) for a in entry.args],
        cwd_required=entry.cwd_required,
        env={
            "AUGUR_ROOT": augur_root,
            **{k: expand(v) for k, v in entry.env.items()},
        },
        bundle=entry.bundle,
        bundle_path=expand(entry.bundle_path) if entry.bundle_path else None,
        per_client_args={client: [expand(a) for a in args] for client, args in entry.per_client_args.items()},
        platforms=list(entry.platforms),
        startup_timeout_sec=entry.startup_timeout_sec,
        scope=entry.scope,
    )


def render_entry_dict(entry: ServerEntry, client: str | None = None) -> dict:
    """Render a resolved ``ServerEntry`` into a client-config dict.

    When ``client`` is provided and the entry has ``per_client_args[client]``
    defined, those args are appended to the base args.

    Includes ``cwd`` field when ``cwd_required=True``. Includes ``env``
    only when non-empty.
    """
    resolved = resolve_entry(entry)

    args = list(resolved.args)
    if client and client in resolved.per_client_args:
        args.extend(resolved.per_client_args[client])

    out: dict = {"command": resolved.command, "args": args}
    if resolved.cwd_required:
        out["cwd"] = str(get_project_root())
    if resolved.env:
        out["env"] = dict(resolved.env)
    return out
