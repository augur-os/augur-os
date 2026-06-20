from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

import yaml

from skills.ingest.scripts import inbox_registry
from skills.ingest.scripts.inbox_unified_models import (
    InboxVaultCandidate,
    InboxVaultTarget,
    to_dict,
)


def _read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_candidates(candidates: list[InboxVaultCandidate]) -> None:
    registry = inbox_registry.load_inbox_registry()
    path = registry.config_root / "discovered.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"candidates": to_dict(candidates)}, sort_keys=False),
        encoding="utf-8",
    )


def _resolve_marker_root(marker: Path, marker_file: str) -> Path:
    root = marker
    for _ in Path(marker_file).parts:
        root = root.parent
    return root


def _resolve_marker_path(root: Path, raw_value: object, default: str) -> Path:
    value = Path(str(raw_value or default)).expanduser()
    if value.is_absolute():
        return value.resolve(strict=False)
    return (root / value).resolve(strict=False)


def _is_inside_project_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _candidate_from_marker(marker: Path, marker_file: str) -> InboxVaultCandidate | None:
    data = _read_yaml(marker)
    if not data:
        return None

    root = _resolve_marker_root(marker, marker_file)
    vault_root = _resolve_marker_path(root, data.get("vault_root"), "vault")
    docs_root = _resolve_marker_path(root, data.get("docs_root"), "docs")
    if not (
        _is_inside_project_root(vault_root, root)
        and _is_inside_project_root(docs_root, root)
    ):
        return None
    if not vault_root.exists() and not docs_root.exists():
        return None

    candidate_id = str(data.get("id") or root.name)
    kind = str(data.get("kind") or "project")
    name = str(data.get("name") or candidate_id.replace("-", " ").title())
    return InboxVaultCandidate(
        candidate_id=candidate_id,
        kind=kind,
        name=name,
        vault_root=str(vault_root),
        docs_root=str(docs_root),
        reason=f"found {marker_file} in {root}",
        status="unapproved",
        writable=False,
    )


def _candidate_depth(root: Path, marker: Path, marker_file: str) -> int | None:
    marker_root = _resolve_marker_root(marker, marker_file)
    try:
        relative_root = marker_root.relative_to(root)
    except ValueError:
        return None
    if str(relative_root) == ".":
        return 0
    return len(relative_root.parts)


def _iter_marker_paths(root: Path, marker_file: str, max_depth: int) -> Iterable[Path]:
    if not root.exists():
        return
    for marker in root.rglob(Path(marker_file).name):
        if not marker.is_file():
            continue
        try:
            marker.relative_to(root)
        except ValueError:
            continue
        if not _marker_matches(marker, marker_file):
            continue
        depth = _candidate_depth(root, marker, marker_file)
        if depth is None or depth > max_depth:
            continue
        yield marker


def _normalized_roots(roots: Iterable[Path | str]) -> list[Path]:
    unique: dict[str, Path] = {}
    for raw_root in roots:
        root = Path(raw_root).expanduser().resolve(strict=False)
        unique[str(root)] = root
    return list(unique.values())


def _marker_matches(path: Path, marker_file: str) -> bool:
    return path.parts[-len(Path(marker_file).parts):] == Path(marker_file).parts


def _configured_roots() -> list[Path]:
    config = inbox_registry.load_discovery_config()
    return _normalized_roots(config.get("approved_parent_roots", []))


def _registered_ids_and_roots() -> tuple[set[str], set[str], set[str]]:
    registry = inbox_registry.load_inbox_registry()
    ids = {vault.id for vault in registry.vaults}
    vault_roots = {
        str(Path(vault.vault_root).expanduser().resolve(strict=False))
        for vault in registry.vaults
    }
    docs_roots = {
        str(Path(vault.docs_root).expanduser().resolve(strict=False))
        for vault in registry.vaults
    }
    return ids, vault_roots, docs_roots


def _is_registered_candidate(
    candidate: InboxVaultCandidate,
    registered_ids: set[str],
    registered_vault_roots: set[str],
    registered_docs_roots: set[str],
) -> bool:
    return (
        candidate.candidate_id in registered_ids
        or candidate.vault_root in registered_vault_roots
        or candidate.docs_root in registered_docs_roots
    )


def _record_candidate(
    found: dict[str, InboxVaultCandidate],
    duplicate_ids: set[str],
    candidate: InboxVaultCandidate,
) -> None:
    if candidate.candidate_id in duplicate_ids:
        return
    existing = found.get(candidate.candidate_id)
    if existing is None:
        found[candidate.candidate_id] = candidate
        return
    if (
        existing.vault_root == candidate.vault_root
        and existing.docs_root == candidate.docs_root
    ):
        return
    duplicate_ids.add(candidate.candidate_id)
    found.pop(candidate.candidate_id, None)


def discover_vault_candidates(
    search_roots: Iterable[Path | str] | None = None,
    explicit_paths: Iterable[Path | str] | None = None,
) -> list[InboxVaultCandidate]:
    config = inbox_registry.load_discovery_config()
    marker_files = [
        str(item)
        for item in config.get("marker_files") or [".augur/vault.yaml"]
    ]
    max_depth = int(config.get("max_depth", 3))
    roots = _normalized_roots([*(search_roots or []), *_configured_roots()])
    registered_ids, registered_vault_roots, registered_docs_roots = _registered_ids_and_roots()

    found: dict[str, InboxVaultCandidate] = {}
    duplicate_ids: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for marker_file in marker_files:
            for marker in _iter_marker_paths(root, marker_file, max_depth):
                candidate = _candidate_from_marker(marker, marker_file)
                if candidate is None:
                    continue
                if _is_registered_candidate(
                    candidate,
                    registered_ids,
                    registered_vault_roots,
                    registered_docs_roots,
                ):
                    continue
                _record_candidate(found, duplicate_ids, candidate)

    for raw_path in explicit_paths or []:
        explicit = Path(raw_path).expanduser().resolve(strict=False)
        if explicit.is_file():
            marker_candidates = [
                (marker_file, explicit)
                for marker_file in marker_files
                if _marker_matches(explicit, marker_file)
            ]
        else:
            marker_candidates = [
                (marker_file, explicit / marker_file)
                for marker_file in marker_files
            ]
        for marker_file, marker in marker_candidates:
            if not marker.is_file():
                continue
            candidate = _candidate_from_marker(marker, marker_file)
            if candidate is None:
                continue
            if _is_registered_candidate(
                candidate,
                registered_ids,
                registered_vault_roots,
                registered_docs_roots,
            ):
                continue
            _record_candidate(found, duplicate_ids, candidate)

    candidates = sorted(found.values(), key=lambda item: item.candidate_id)
    _write_candidates(candidates)
    return candidates


def register_discovered_vault(candidate_id: str) -> InboxVaultTarget:
    registry = inbox_registry.load_inbox_registry()
    candidate = next(
        (item for item in registry.candidates if item.candidate_id == candidate_id),
        None,
    )
    if candidate is None:
        raise KeyError(f"Vault candidate not found: {candidate_id}")
    target = InboxVaultTarget(
        id=candidate.candidate_id,
        kind=candidate.kind,
        name=candidate.name,
        vault_root=candidate.vault_root,
        docs_root=candidate.docs_root,
        default=False,
        writable=True,
    )
    saved = inbox_registry.register_vault_target(target)
    remaining = [item for item in registry.candidates if item.candidate_id != candidate_id]
    _write_candidates(
        [replace(item, status="unapproved", writable=False) for item in remaining]
    )
    return saved
