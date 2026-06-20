"""Deterministic route planning for /keep."""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from skills.ingest.scripts.note_type import detect_note_type_from_arg


URL_RE = re.compile(r"^https?://", re.IGNORECASE)
CLOUD_TERMS = {"google drive", "gdrive", "dropbox", "onedrive", "icloud"}
SAVE_OPTIONS_WITH_VALUES = {"--to", "--hub", "--slug", "--title", "--tags"}


@dataclass(frozen=True)
class KeepRoute:
    kind: str
    route: str
    original: str
    path: Path | None = None
    normalized_arg: str = ""
    warnings: list[str] = field(default_factory=list)
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "kind": self.kind,
            "route": self.route,
            "original": self.original,
            "normalized_arg": self.normalized_arg,
            "warnings": list(self.warnings),
            "requires_confirmation": self.requires_confirmation,
        }
        if self.path is not None:
            data["path"] = str(self.path)
        return data


def _tokens(arg: str) -> list[str]:
    try:
        return shlex.split(arg)
    except ValueError:
        return arg.split()


def _resolve_path(candidate: str, cwd: Path | None) -> Path:
    path = Path(candidate).expanduser()
    if not path.is_absolute() and cwd is not None:
        path = cwd / path
    return path


def _contains_cloud_request(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in CLOUD_TERMS)


def _save_source_path(parts: list[str]) -> str | None:
    index = 1
    while index < len(parts):
        token = parts[index]
        if token in SAVE_OPTIONS_WITH_VALUES:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token
    return None


def _local_route(candidate: Path, original: str, warnings: list[str]) -> KeepRoute:
    """Build a local-file / local-folder route for an existing path."""
    is_folder = detect_note_type_from_arg(str(candidate)) == "folder"
    return KeepRoute(
        kind="folder" if is_folder else "file",
        route="local-folder" if is_folder else "local-file",
        original=original,
        path=candidate,
        normalized_arg=str(candidate),
        warnings=warnings,
    )


def plan_keep_route(argument: str, *, cwd: str | Path | None = None) -> KeepRoute:
    original = argument
    arg = argument.strip()
    cwd_path = Path(cwd).expanduser().resolve() if cwd is not None else None
    warnings: list[str] = []

    if not arg:
        return KeepRoute(
            kind="interactive",
            route="interactive-picker",
            original=original,
            requires_confirmation=True,
        )

    if _contains_cloud_request(arg):
        warnings.append("cloud-route-not-selected")

    parts = _tokens(arg)
    save_mode = bool(parts and parts[0] in {"--save", "artifact"})
    if save_mode:
        source_path = _save_source_path(parts)
        if source_path is None:
            return KeepRoute(
                kind="artifact",
                route="generated-artifact",
                original=original,
                warnings=warnings + ["missing-artifact-path"],
                requires_confirmation=True,
            )
        candidate = _resolve_path(source_path, cwd_path)
        return KeepRoute(
            kind="artifact",
            route="generated-artifact",
            original=original,
            path=candidate if candidate.exists() else None,
            normalized_arg=str(candidate),
            warnings=warnings + ([] if candidate.exists() else ["artifact-path-not-found"]),
            requires_confirmation=not candidate.exists(),
        )

    if URL_RE.match(arg):
        return KeepRoute(kind="url", route="url-capture", original=original, normalized_arg=arg, warnings=warnings)

    # A keep argument may be a single filesystem path that contains spaces — common
    # from Claude Desktop and macOS ("Mobile Documents", "Claude Desktop Capture.md").
    # shlex would split such a path into many tokens and misroute it to "thought", so
    # resolve the whole argument as a path first and choose the local route directly.
    candidate = _resolve_path(arg, cwd_path)
    if candidate.exists():
        return _local_route(candidate, original, warnings)

    # A shell-quoted single path also resolves to one token (e.g. `"/x/my file.md"`),
    # which the whole-arg check above misses because of the literal quotes.
    if len(parts) == 1:
        quoted = _resolve_path(parts[0], cwd_path)
        if quoted.exists():
            return _local_route(quoted, original, warnings)

    return KeepRoute(kind="thought", route="thought", original=original, normalized_arg=arg, warnings=warnings)
