from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from src.lib.frontmatter_utils import write_frontmatter


@dataclass(frozen=True)
class PromotionPacketRequest:
    topic: str
    contributor: str
    synthesis: str
    source_paths: list[Path] = field(default_factory=list)
    source_brain_id: str | None = None
    target_brain_id: str | None = None
    source_root: Path | None = None
    proposed_actions: list[str] = field(default_factory=list)
    proposed_links: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    sensitivity: str = "internal"
    packet_date: date | None = None


@dataclass(frozen=True)
class PromotionPacket:
    path: Path
    manifest_path: Path
    synthesis_path: Path


def create_promotion_packet(project_brain_dir: Path, request: PromotionPacketRequest) -> PromotionPacket:
    topic = _require_text(request.topic, "topic")
    contributor = _require_text(request.contributor, "contributor")
    synthesis = _require_text(request.synthesis, "synthesis")
    packet_date = request.packet_date or date.today()

    packet_dir = _create_unique_packet_dir(
        project_brain_dir / "inbox" / "promotions",
        f"{packet_date.isoformat()}-{_slug(contributor)}-{_slug(topic)}",
    )

    manifest_path = packet_dir / "manifest.yaml"
    synthesis_path = packet_dir / "synthesis.md"
    proposed_actions_path = packet_dir / "proposed-actions.md"
    proposed_links_path = packet_dir / "proposed-links.md"
    sources_readme_path = packet_dir / "sources" / "README.md"
    sources_dir = packet_dir / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    source_paths = _validated_source_paths(request)

    write_frontmatter(
        synthesis_path,
        {
            "title": topic,
            "brain_scope": "project",
            "promotion_state": "packet",
            "contributor": contributor,
            "roles": list(request.roles),
            "domains": list(request.domains),
            "sensitivity": request.sensitivity,
        },
        synthesis,
    )
    write_frontmatter(
        proposed_actions_path,
        {
            "title": "Proposed Actions",
            "brain_scope": "project",
            "promotion_state": "packet",
        },
        _checkbox_body(request.proposed_actions),
    )
    write_frontmatter(
        proposed_links_path,
        {
            "title": "Proposed Links",
            "brain_scope": "project",
            "promotion_state": "packet",
        },
        _bullet_body(request.proposed_links),
    )
    write_frontmatter(
        sources_readme_path,
        {
            "title": "Promotion Packet Sources",
            "brain_scope": "project",
            "promotion_state": "packet",
        },
        (
            "Copied source files are stored in this directory and referenced "
            "from manifest.yaml with packet-relative paths, existence flags, "
            "and hash metadata. Missing or non-file sources are listed in the "
            "manifest by basename only."
        ),
    )

    manifest = {
        "schema_version": 1,
        "kind": (
            "brain-propagation-packet"
            if request.source_brain_id or request.target_brain_id
            else "project-brain-promotion-packet"
        ),
        "status": "packet",
        "topic": topic,
        "contributor": contributor,
        "date": packet_date.isoformat(),
        "sensitivity": request.sensitivity,
        "roles": list(request.roles),
        "domains": list(request.domains),
        "source_refs": [_source_ref(path, sources_dir) for path in source_paths],
        "outputs": {
            "synthesis": synthesis_path.name,
            "proposed_actions": proposed_actions_path.name,
            "proposed_links": proposed_links_path.name,
        },
    }
    if request.source_brain_id:
        manifest["source_brain_id"] = request.source_brain_id
    if request.target_brain_id:
        manifest["target_brain_id"] = request.target_brain_id
    manifest_path.write_text(
        yaml.dump(
            manifest,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )

    return PromotionPacket(
        path=packet_dir,
        manifest_path=manifest_path,
        synthesis_path=synthesis_path,
    )


def _require_text(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _validated_source_paths(request: PromotionPacketRequest) -> list[Path]:
    paths = [Path(path) for path in request.source_paths]
    if request.source_root is None:
        return paths
    source_root = Path(request.source_root).expanduser().resolve(strict=False)
    for source in paths:
        resolved = source.expanduser().resolve(strict=False)
        try:
            resolved.relative_to(source_root)
        except ValueError as exc:
            raise ValueError(f"source path is outside source brain: {source}") from exc
    return paths


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "packet"


def _create_unique_packet_dir(parent: Path, basename: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    for suffix in range(1, 10_000):
        candidate = parent / (basename if suffix == 1 else f"{basename}-{suffix}")
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise FileExistsError(f"could not create unique promotion packet for {basename}")


def _source_ref(path: Path, sources_dir: Path) -> dict[str, Any]:
    source = Path(path)
    source_name = _source_name(source)
    ref: dict[str, Any] = {
        "path": source_name,
        "source_name": source_name,
        "exists": source.exists(),
        "is_file": source.is_file(),
    }
    if source.is_file():
        copied_source = _copy_source(source, sources_dir)
        ref["path"] = copied_source.relative_to(sources_dir.parent).as_posix()
        ref["sha256"] = _sha256(copied_source)
    return ref


def _source_name(source: Path) -> str:
    return source.name or "packet"


def _copy_source(source: Path, sources_dir: Path) -> Path:
    destination = _unique_source_path(sources_dir, source.name)
    shutil.copyfile(source, destination)
    return destination


def _unique_source_path(sources_dir: Path, basename: str) -> Path:
    candidate_name = _sanitize_filename(basename)
    candidate = sources_dir / candidate_name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 10_000):
        candidate = sources_dir / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"could not create unique source file for {basename}")


def _sanitize_filename(basename: str) -> str:
    name = Path(basename).name
    suffix = Path(name).suffix.lower()
    stem = name[: -len(suffix)] if suffix else name
    sanitized_stem = _slug(stem)
    sanitized_suffix = re.sub(r"[^a-z0-9.]+", "-", suffix).strip("-")
    if sanitized_suffix and not sanitized_suffix.startswith("."):
        sanitized_suffix = f".{sanitized_suffix}"
    return f"{sanitized_stem}{sanitized_suffix}" or "packet"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checkbox_body(items: list[str]) -> str:
    return "\n".join(f"- [ ] {item}" for item in items)


def _bullet_body(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)
