"""Detect (and repair) AI-client MCP configs that point at paths that no longer exist.

Root-cause class this closes: an Augur-managed root moves (e.g. the 2026-06-13
documents migration ``~/Projects/Au-docs`` → ``~/Documents``) and an external,
client-owned MCP config keeps pointing at the old path. The client's MCP server
then crash-loops on startup (the secure-filesystem server stats every allowed
directory and exits on ENOENT), and Augur's own MCP health audit — which only
ever inspected Augur's *own* dashboard↔tool wiring — never saw it. The breakage
stayed silent for days.

This module discovers each client's MCP config, extracts the directories a
server is told to use (server ``cwd`` plus directory-typed DXT ``userConfig``
values), checks they exist, and — for *user-owned* configs — auto-repairs a
dangling path when the path-migration redirect map yields an unambiguous
successor that actually exists. Auto-generated configs (project ``.mcp.json``)
are flagged for ``aug config sync`` rather than hand-edited.

Consumed by the ``auto-mcp-health-audit`` routine.
"""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from src.config.paths import get_client_runtime_dir, get_project_root
from src.lib.path_migrations import load_migrations, resolve_successor


@dataclass(frozen=True)
class ConfigSource:
    """A discovered client MCP config file."""

    client: str
    path: Path
    fmt: str  # "json" | "toml"
    kind: str  # "mcp-config" | "dxt-extension"
    generated: bool  # True => Augur-generated; repair via sync, never hand-edit


@dataclass
class PathRef:
    """A filesystem path referenced inside a config, with where it came from."""

    raw: str  # as authored in the file (may use ~)
    expanded: str  # absolute, expanded
    location: str  # human label, e.g. 'mcpServers.Filesystem.cwd'


@dataclass
class Finding:
    """A dangling path found in a client config."""

    client: str
    config_path: str
    location: str
    raw: str
    expanded: str
    generated: bool
    successor: str | None = None  # expanded successor path, if repairable

    @property
    def repairable(self) -> bool:
        return bool(self.successor) and not self.generated

    @property
    def detail(self) -> str:
        base = f"{self.client}: {self.location} -> {self.raw} (missing)"
        if self.generated:
            return base + " [generated config; run `aug config sync`]"
        if self.successor:
            return base + f" [auto-repair -> {self.successor}]"
        return base + " [no known successor; manual]"


# ── path-shape heuristics ────────────────────────────────────────────────────


def _expand(value: str) -> str:
    return os.path.abspath(os.path.expanduser(os.path.expandvars(str(value))))


def _looks_like_path(value: object) -> bool:
    """True for strings that are filesystem paths (not tokens, ids, modules)."""
    if not isinstance(value, str) or not value:
        return False
    return value.startswith(("/", "~", "$"))


def _collapse_home(path_abs: str) -> str:
    """Re-express an absolute path using ``~`` when it lives under HOME."""
    home = os.path.expanduser("~")
    if path_abs == home:
        return "~"
    if path_abs.startswith(home + os.sep):
        return "~" + path_abs[len(home) :]
    return path_abs


def _raw_like(original_raw: str, successor_abs: str) -> str:
    """Format the successor the same way the original was authored (~ or absolute)."""
    if original_raw.startswith("~"):
        return _collapse_home(successor_abs)
    return successor_abs


# ── extraction (pure: text -> path refs) ──────────────────────────────────────


def _refs_from_mcp_servers(servers: object, prefix: str) -> list[PathRef]:
    """Pull server ``cwd`` directory refs from an ``mcpServers``/``mcp_servers`` map."""
    refs: list[PathRef] = []
    if not isinstance(servers, dict):
        return refs
    for name, conf in servers.items():
        if not isinstance(conf, dict):
            continue
        cwd = conf.get("cwd")
        if _looks_like_path(cwd):
            refs.append(PathRef(raw=cwd, expanded=_expand(cwd), location=f"{prefix}.{name}.cwd"))
    return refs


def extract_path_refs(source: ConfigSource, text: str) -> list[PathRef]:
    """Extract directory path references from a config file's text."""
    try:
        if source.fmt == "toml":
            data = tomllib.loads(text)
        else:
            data = json.loads(text)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, ValueError):
        return []

    if not isinstance(data, dict):
        return []

    if source.kind == "dxt-extension":
        refs: list[PathRef] = []
        user_config = data.get("userConfig", {})
        if isinstance(user_config, dict):
            for key, value in user_config.items():
                values = value if isinstance(value, list) else [value]
                for item in values:
                    if _looks_like_path(item):
                        refs.append(
                            PathRef(
                                raw=item,
                                expanded=_expand(item),
                                location=f"userConfig.{key}",
                            )
                        )
        return refs

    # mcp-config (json or toml)
    refs = _refs_from_mcp_servers(data.get("mcpServers"), "mcpServers")
    refs += _refs_from_mcp_servers(data.get("mcp_servers"), "mcp_servers")
    return refs


# ── audit + repair ────────────────────────────────────────────────────────────


def audit_source(source: ConfigSource, migrations: list[dict[str, str]] | None = None) -> list[Finding]:
    """Return dangling-path findings for one config source."""
    try:
        text = source.path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    findings: list[Finding] = []
    for ref in extract_path_refs(source, text):
        if Path(ref.expanded).exists():
            continue
        successor = None if source.generated else resolve_successor(ref.expanded, migrations)
        findings.append(
            Finding(
                client=source.client,
                config_path=str(source.path),
                location=ref.location,
                raw=ref.raw,
                expanded=ref.expanded,
                generated=source.generated,
                successor=str(successor) if successor else None,
            )
        )
    return findings


def repair_source(source: ConfigSource, findings: list[Finding]) -> list[dict[str, str]]:
    """Rewrite repairable dangling paths in-place via targeted text replacement.

    Text replacement (not parse-and-redump) preserves the file's formatting and
    every unrelated key — only the dangling path token changes.
    """
    repairable = [f for f in findings if f.repairable and f.config_path == str(source.path)]
    if not repairable:
        return []
    try:
        text = source.path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    applied: list[dict[str, str]] = []
    new_text = text
    for f in repairable:
        new_raw = _raw_like(f.raw, f.successor or "")
        if f.raw not in new_text or new_raw == f.raw:
            continue
        new_text = new_text.replace(f.raw, new_raw)
        applied.append({"client": f.client, "location": f.location, "old": f.raw, "new": new_raw})

    if applied and new_text != text:
        source.path.write_text(new_text, encoding="utf-8")
    return applied


# ── discovery (real client config locations) ──────────────────────────────────


def discover_sources() -> list[ConfigSource]:
    """Locate the client MCP configs that exist on this machine.

    Each entry is best-effort: a path helper that raises (unsupported client on
    this platform) is skipped rather than aborting the whole audit.
    """
    sources: list[ConfigSource] = []

    def _add(client: str, path: Path, fmt: str, kind: str, generated: bool) -> None:
        if path.is_file():
            sources.append(ConfigSource(client, path, fmt, kind, generated))

    # Claude Desktop: user-owned mcpServers + DXT extension settings.
    try:
        cd_root = get_client_runtime_dir("claude-desktop")
        _add("claude-desktop", cd_root / "claude_desktop_config.json", "json", "mcp-config", False)
        ext_dir = cd_root / "Claude Extensions Settings"
        if ext_dir.is_dir():
            for ext_json in sorted(ext_dir.glob("*.json")):
                _add("claude-desktop-extension", ext_json, "json", "dxt-extension", False)
    except (ValueError, OSError):
        pass

    # Project .mcp.json — auto-generated from config/system/mcp_servers.yaml.
    try:
        _add("client-mcp", get_project_root() / ".mcp.json", "json", "mcp-config", True)
    except (ValueError, OSError):
        pass

    # Codex CLI (TOML) and Gemini CLI (JSON) — user-owned.
    _add("codex", Path.home() / ".codex" / "config.toml", "toml", "mcp-config", False)
    _add("gemini", Path.home() / ".gemini" / "settings.json", "json", "mcp-config", False)

    return sources


@dataclass
class AuditOutcome:
    findings: list[Finding] = field(default_factory=list)
    sources_scanned: int = 0


def audit_all(migrations: list[dict[str, str]] | None = None) -> AuditOutcome:
    """Audit every discovered client config; returns all dangling-path findings."""
    migrations = load_migrations() if migrations is None else migrations
    outcome = AuditOutcome()
    for source in discover_sources():
        outcome.sources_scanned += 1
        outcome.findings.extend(audit_source(source, migrations))
    return outcome


def repair_all(findings: list[Finding]) -> list[dict[str, str]]:
    """Apply repairs for repairable findings, grouped by their owning config file."""
    by_path: dict[str, list[Finding]] = {}
    for f in findings:
        by_path.setdefault(f.config_path, []).append(f)

    applied: list[dict[str, str]] = []
    for config_path, group in by_path.items():
        repairable = [f for f in group if f.repairable]
        if not repairable:
            continue
        first = repairable[0]
        source = ConfigSource(
            client=first.client,
            path=Path(config_path),
            fmt="toml" if config_path.endswith(".toml") else "json",
            kind="dxt-extension" if "Extensions Settings" in config_path else "mcp-config",
            generated=False,
        )
        applied.extend(repair_source(source, group))
    return applied


def reconcile_and_repair() -> dict[str, object]:
    """One-shot migration hook: record moved roots, then detect + repair.

    Sequence: ``reconcile_migrations()`` auto-records any canonical root that
    moved since the last run, ``audit_all()`` re-reads the (now-updated) redirect
    map and finds dangling client paths, and ``repair_all()`` heals the
    user-owned ones. This is the hands-off path so a root move needs no manual
    redirect-map entry. Surfaced via ``aug config reconcile-paths`` and run at
    the head of the ``auto-mcp-health-audit`` routine.
    """
    from src.lib.path_migrations import reconcile_migrations

    recorded = reconcile_migrations()
    outcome = audit_all()
    applied = repair_all(outcome.findings)
    return {
        "recorded": recorded,
        "sources_scanned": outcome.sources_scanned,
        "findings": [f.detail for f in outcome.findings],
        "repaired": applied,
    }
