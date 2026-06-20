from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.skill_release import ensure_valid_release

PORTING_RELEASES = ("mvp", "r1", "r2", "r3", "r4")
STAGED_RELEASES = ("r1", "r2", "r3", "r4", "later")
_ALLOWED_TOP_LEVEL = {"skills", "pages", "manifest.md"}


@dataclass(frozen=True)
class ReleaseManifest:
    release: str
    motive: str
    skills: list[str]
    pages: list[str]
    prerequisites: list[str]


@dataclass(frozen=True)
class ReleasePayload:
    release_root: Path
    release: str
    manifest: ReleaseManifest
    skill_paths: list[Path]
    page_paths: list[Path]


def ensure_valid_staged_release(release: str) -> str:
    if release not in STAGED_RELEASES:
        raise ValueError(f"unsupported staged release: {release!r}")
    return release


def parse_release_manifest(manifest_path: Path) -> ReleaseManifest:
    metadata, _body = parse_frontmatter(manifest_path, include_sidecar_config=False)
    release = str(metadata.get("release") or "")
    if release in PORTING_RELEASES:
        ensure_valid_release(release)
    else:
        ensure_valid_staged_release(release)

    motive = str(metadata.get("motive") or "").strip()
    if not motive:
        raise ValueError("manifest motive is required")

    skills = [str(item) for item in metadata.get("skills") or []]
    pages = [str(item) for item in metadata.get("pages") or []]
    prerequisites = [str(item) for item in metadata.get("prerequisites") or []]
    return ReleaseManifest(
        release=release,
        motive=motive,
        skills=skills,
        pages=pages,
        prerequisites=prerequisites,
    )


def validate_payload_tree(release_root: Path) -> None:
    if not release_root.exists():
        raise FileNotFoundError(release_root)

    entries = {path.name for path in release_root.iterdir()}
    unexpected = sorted(entries - _ALLOWED_TOP_LEVEL)
    if unexpected:
        raise ValueError(f"unexpected files in payload root: {unexpected}")

    if not (release_root / "skills").exists():
        raise ValueError("payload is missing skills/")
    if not (release_root / "pages").exists():
        raise ValueError("payload is missing pages/")
    if not (release_root / "manifest.md").exists():
        raise ValueError("payload is missing manifest.md")


def build_release_payload(release_root: Path) -> ReleasePayload:
    validate_payload_tree(release_root)
    manifest = parse_release_manifest(release_root / "manifest.md")
    skill_paths = sorted(path for path in (release_root / "skills").iterdir() if path.is_dir())
    page_paths = sorted(
        path for path in (release_root / "pages").rglob("*") if path.is_file() and not path.name.startswith(".")
    )
    return ReleasePayload(
        release_root=release_root,
        release=manifest.release,
        manifest=manifest,
        skill_paths=skill_paths,
        page_paths=page_paths,
    )
