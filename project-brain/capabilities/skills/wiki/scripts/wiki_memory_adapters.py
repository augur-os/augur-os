"""Cross-platform memory source adapters for the wiki scanner."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from skills.wiki.scripts.wiki_tier import normalize_tier, tier_for_surface, weight_for_tier


def _title_for(path: Path) -> str:
    if path.suffix.lower() in {".md", ".txt"}:
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                if stripped.startswith("# "):
                    return stripped[2:].strip()
        except OSError:
            pass
    return path.stem.replace("-", " ").replace("_", " ").title()


def _annotate(source: dict[str, Any], *, tier_override: str | None = None) -> dict[str, Any]:
    surface = str(source.get("source_surface") or "")
    tier = normalize_tier(tier_override, default=tier_for_surface(surface)) if tier_override else tier_for_surface(surface)
    return {**source, "tier": tier, "weight": weight_for_tier(tier)}


def _from_dir(
    *,
    root: Path,
    surface: str,
    hub: str,
    extra: dict[str, Any] | None = None,
    tier_override: str | None = None,
    extensions: Iterable[str] = (".md", ".txt", ".json", ".jsonl"),
) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    allowed = {ext.lower() for ext in extensions}
    out: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in allowed:
            continue
        source = {
            "path": str(path),
            "type": path.suffix.lstrip(".").lower(),
            "title": _title_for(path),
            "hub": hub,
            "format": path.suffix.lstrip(".").lower(),
            "source_surface": surface,
        }
        if extra:
            source.update(extra)
        out.append(_annotate(source, tier_override=tier_override))
    return out


def scan_client_memory(*, clients: dict[str, dict[str, Any]], enabled: bool = True) -> list[dict[str, Any]]:
    """Return configured AI-client memory/session files.

    Client-specific paths are data, not architecture. Each returned source uses
    the neutral ``client_memory`` surface and carries the concrete client name
    as metadata.
    """
    if not enabled:
        return []
    out: list[dict[str, Any]] = []
    for client, spec in sorted((clients or {}).items()):
        if not bool(spec.get("enabled", True)):
            continue
        raw_path = spec.get("path")
        if not raw_path:
            continue
        root = Path(str(raw_path)).expanduser()
        if not root.is_dir():
            continue
        globs = spec.get("globs") or ["**/*"]
        if isinstance(globs, str):
            globs = [globs]
        extensions = spec.get("extensions") or (".md", ".txt", ".json", ".jsonl")
        if isinstance(extensions, str):
            extensions = [extensions]
        allowed = {str(ext).lower() for ext in extensions}
        seen: set[Path] = set()
        for pattern in globs:
            for path in sorted(root.glob(str(pattern))):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in allowed:
                    continue
                resolved = path.resolve(strict=False)
                if resolved in seen:
                    continue
                seen.add(resolved)
                out.append(
                    _annotate(
                        {
                            "path": str(path),
                            "type": path.suffix.lstrip(".").lower(),
                            "title": _title_for(path),
                            "hub": str(spec.get("hub") or "memory"),
                            "format": path.suffix.lstrip(".").lower(),
                            "source_surface": "client_memory",
                            "client": str(client),
                        },
                        tier_override=str(spec.get("tier") or "critical"),
                    )
                )
    return out


def scan_codex_threads(*, threads_dir: Path, enabled: bool = True) -> list[dict[str, Any]]:
    """Return configured Codex thread/session files."""
    if not enabled:
        return []
    return _from_dir(root=threads_dir, surface="codex_threads", hub="memory")


def scan_gemini(*, path: Path | None, enabled: bool = True) -> list[dict[str, Any]]:
    """Return configured Gemini conversation/session files."""
    if not enabled or path is None:
        return []
    return _from_dir(root=path, surface="gemini", hub="memory")


def scan_copilot(*, path: Path | None, enabled: bool = True) -> list[dict[str, Any]]:
    """Return configured GitHub Copilot conversation/session files."""
    if not enabled or path is None:
        return []
    return _from_dir(root=path, surface="copilot", hub="memory")


def scan_external_clients(*, allowlist: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Return configured external client exports with a client discriminator."""
    out: list[dict[str, Any]] = []
    for name, spec in sorted((allowlist or {}).items()):
        if not bool(spec.get("enabled", True)):
            continue
        raw_path = spec.get("path")
        if not raw_path:
            continue
        out.extend(
            _from_dir(
                root=Path(str(raw_path)).expanduser(),
                surface="external_client",
                hub=str(spec.get("hub") or "memory"),
                extra={"client": str(name)},
                tier_override=str(spec.get("tier") or "high"),
            )
        )
    return out


def scan_episodic(*, loader: Callable[[], list[dict[str, Any]]] | None) -> list[dict[str, Any]]:
    """Return episodic-memory records supplied by an optional loader."""
    if loader is None:
        return []
    out: list[dict[str, Any]] = []
    for record in loader() or []:
        record_id = str(record.get("id") or "").strip()
        if not record_id:
            continue
        out.append(
            _annotate(
                {
                    "path": f"episodic://{record_id}",
                    "type": "episodic",
                    "title": str(record.get("title") or record_id).strip() or record_id,
                    "hub": "memory",
                    "format": "episodic",
                    "source_surface": "episodic",
                    "ts": record.get("ts"),
                }
            )
        )
    return out
