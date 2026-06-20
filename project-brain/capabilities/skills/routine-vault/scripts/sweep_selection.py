"""Typed Browse sweep selection validation and persistence."""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from src.config.paths import get_documents_dir, get_project_root, get_runtime_dir, get_vault_dir

SweepTargetKind = Literal["docs", "source-cards", "vault-notes", "pages-artifacts", "pages-live"]
ArchiveMode = Literal["docs-archive", "git-aware"]
SourceTab = Literal["sources", "notes", "pages"]

DOCS_ARCHIVE_KINDS = {"docs", "pages-artifacts"}
GIT_AWARE_KINDS = {"source-cards", "vault-notes", "pages-live"}
VALID_SOURCE_TABS = {"sources", "notes", "pages"}
KIND_ROOTS = {
    "docs": ("documents",),
    "source-cards": ("project", "vault"),
    "pages-artifacts": ("documents",),
    "vault-notes": ("vault",),
    "pages-live": ("project", "vault"),
}
SOURCE_TAB_KINDS = {
    "sources": {"docs", "source-cards"},
    "notes": {"vault-notes"},
    "pages": {"pages-artifacts", "pages-live"},
}
SELECTION_ID_RE = re.compile(r"^browse-sweep-\d{8}-\d{6}-[0-9a-f]{8}$")


@dataclass(frozen=True)
class ValidatedTarget:
    kind: str
    source_path: str
    source_id: str
    archive_mode: str
    source_tab: str
    title: str
    relative_path: str
    root_key: str
    repository_root: str | None
    metadata: dict[str, str]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _selection_dir() -> Path:
    path = get_runtime_dir() / "routine-vault" / "selections"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _allowed_roots() -> dict[str, Path]:
    return {
        "project": get_project_root().resolve(),
        "documents": get_documents_dir().resolve(),
        "vault": get_vault_dir().resolve(),
    }


def _string_metadata(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(val) for key, val in value.items() if val is not None}


def _matching_roots(path: Path) -> list[tuple[str, Path]]:
    resolved = path.resolve()
    matches: list[tuple[str, Path]] = []
    for key, root in _allowed_roots().items():
        try:
            resolved.relative_to(root)
            matches.append((key, root))
        except ValueError:
            continue
    return sorted(matches, key=lambda item: len(item[1].parts), reverse=True)


def _expected_archive_mode(kind: str) -> str | None:
    if kind in DOCS_ARCHIVE_KINDS:
        return "docs-archive"
    if kind in GIT_AWARE_KINDS:
        return "git-aware"
    return None


def _artifact_sidecar_path(html_path: Path) -> Path:
    return html_path.with_suffix("").with_suffix(".meta.yaml")


def _is_live_page_source(root_key: str, relative_path: Path) -> bool:
    parts = relative_path.parts
    if root_key == "vault":
        if parts[:1] == ("skills",) and len(parts) == 3:
            return parts[2] == "SKILL.md"
        if parts[:1] == ("skills",) and len(parts) == 5:
            return (
                parts[2] == "augur"
                and parts[3] == "pages"
                and relative_path.suffix.lower() in {".yaml", ".yml"}
            )
        return False

    if parts[:3] == ("project-brain", "capabilities", "skills") and len(parts) == 5:
        return parts[4] == "SKILL.md"
    if parts[:3] == ("project-brain", "capabilities", "skills") and len(parts) == 7:
        return (
            parts[4] == "augur"
            and parts[5] == "pages"
            and relative_path.suffix.lower() in {".yaml", ".yml"}
        )
    if parts[:3] == ("apps", "dashboard", "app"):
        return len(parts) >= 4 and parts[-1] == "page.tsx"
    if parts[:4] == ("apps", "dashboard", "features", "pages"):
        return len(parts) >= 5 and parts[-1] == "page.tsx"
    return False


def _matches_kind_subpath(
    kind: str,
    root_key: str,
    resolved: Path,
    relative_path: Path,
) -> bool:
    parts = relative_path.parts
    if kind == "source-cards":
        if root_key == "vault":
            return len(parts) > 1 and parts[0] == "sources"
        if root_key == "project":
            return len(parts) > 2 and parts[:2] == ("project-brain", "sources")
        return False
    if kind == "vault-notes":
        return len(parts) > 1 and parts[0] == "notes"
    if kind == "pages-artifacts":
        if resolved.suffix.lower() not in {".html", ".htm"}:
            return False
        return _artifact_sidecar_path(resolved).is_file()
    if kind == "pages-live":
        return _is_live_page_source(root_key, relative_path)
    return True


def _has_symlinked_parent(path: Path) -> bool:
    return any(parent.is_symlink() for parent in path.parents)


def _validate_target(
    raw: dict[str, Any],
    source_tab: str,
) -> tuple[ValidatedTarget | None, dict[str, Any] | None]:
    kind = str(raw.get("kind") or "")
    archive_mode = str(raw.get("archive_mode") or "")
    source_path = str(raw.get("source_path") or "")
    source_id = str(raw.get("source_id") or "")
    title = str(raw.get("title") or source_id or source_path)

    expected_mode = _expected_archive_mode(kind)
    if expected_mode is None:
        return None, {
            "source_id": source_id,
            "source_path": source_path,
            "refusal_category": "unsupported_kind",
        }
    if archive_mode != expected_mode:
        return None, {
            "source_id": source_id,
            "source_path": source_path,
            "refusal_category": "archive_mode_mismatch",
        }

    raw_path = Path(source_path)
    if not source_path or not raw_path.is_absolute():
        return None, {
            "source_id": source_id,
            "source_path": source_path,
            "refusal_category": "invalid_source_path",
        }

    path = raw_path.expanduser()
    if path.is_symlink() or _has_symlinked_parent(path):
        return None, {
            "source_id": source_id,
            "source_path": source_path,
            "refusal_category": "symlink",
        }
    if not path.exists():
        return None, {
            "source_id": source_id,
            "source_path": source_path,
            "refusal_category": "source_missing",
        }
    if not path.is_file():
        return None, {
            "source_id": source_id,
            "source_path": source_path,
            "refusal_category": "not_file",
        }

    if kind not in SOURCE_TAB_KINDS[source_tab]:
        return None, {
            "source_id": source_id,
            "source_path": source_path,
            "refusal_category": "source_tab_kind_mismatch",
        }

    root_matches = _matching_roots(path)
    if not root_matches:
        return None, {
            "source_id": source_id,
            "source_path": source_path,
            "refusal_category": "outside_allowed_roots",
        }

    expected_root_keys = KIND_ROOTS[kind]
    root_key, root_path = root_matches[0]
    if root_key not in expected_root_keys:
        return None, {
            "source_id": source_id,
            "source_path": source_path,
            "refusal_category": "root_kind_mismatch",
        }

    resolved = path.resolve()
    relative_path_obj = resolved.relative_to(root_path)
    if not _matches_kind_subpath(kind, root_key, resolved, relative_path_obj):
        return None, {
            "source_id": source_id,
            "source_path": source_path,
            "refusal_category": "kind_path_mismatch",
        }

    relative_path = relative_path_obj.as_posix()
    repository_root = str(root_path) if archive_mode == "git-aware" else None
    return (
        ValidatedTarget(
            kind=kind,
            source_path=str(resolved),
            source_id=source_id,
            archive_mode=archive_mode,
            source_tab=source_tab,
            title=title,
            relative_path=relative_path,
            root_key=root_key,
            repository_root=repository_root,
            metadata=_string_metadata(raw.get("metadata")),
        ),
        None,
    )


def create_selection(
    *,
    source_tab: str,
    filter_summary: dict[str, Any] | None,
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    if source_tab not in VALID_SOURCE_TABS:
        return {
            "success": False,
            "error": f"unsupported source_tab: {source_tab}",
            "target_count": 0,
            "refusal_count": 0,
            "refusals": [],
        }

    selection_id = (
        f"browse-sweep-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-"
        f"{uuid.uuid4().hex[:8]}"
    )
    valid: list[ValidatedTarget] = []
    refusals: list[dict[str, Any]] = []

    for raw in targets:
        if not isinstance(raw, dict):
            refusals.append(
                {
                    "source_id": "",
                    "source_path": "",
                    "refusal_category": "malformed_target",
                }
            )
            continue
        target, refusal = _validate_target(raw, source_tab)
        if target is not None:
            valid.append(target)
        if refusal is not None:
            refusals.append(refusal)

    payload = {
        "selection_id": selection_id,
        "created_at": _now_iso(),
        "source_tab": source_tab,
        "filter_summary": filter_summary or {},
        "targets": [asdict(target) for target in valid],
        "refusals": refusals,
    }
    path = _selection_dir() / f"{selection_id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "success": True,
        "selection_id": selection_id,
        "selection_path": str(path),
        "target_count": len(valid),
        "refusal_count": len(refusals),
        "refusals": refusals,
    }


def read_selection(selection_id: str) -> dict[str, Any]:
    if not SELECTION_ID_RE.fullmatch(selection_id):
        raise ValueError(f"invalid selection id: {selection_id}")
    path = _selection_dir() / f"{selection_id}.json"
    if not path.is_file():
        raise ValueError(f"selection not found: {selection_id}")
    return json.loads(path.read_text(encoding="utf-8"))
