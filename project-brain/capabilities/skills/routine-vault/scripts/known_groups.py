"""Match files against cached .augur-lifecycle.yaml known_groups entries."""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any

VERSION_TOKEN_RE = re.compile(r"[Vv](\d+)(?:-(\d+))?")


@dataclass(frozen=True)
class MatchResult:
    moves_by_group: dict[str, list[str]] = field(default_factory=dict)
    no_touch: set[str] = field(default_factory=set)
    unmatched_files: list[dict[str, Any]] = field(default_factory=list)


def _version_sort_key(name: str) -> tuple[int, int]:
    match = VERSION_TOKEN_RE.search(name)
    if match is None:
        return (-1, -1)
    major = int(match.group(1))
    minor = int(match.group(2)) if match.group(2) is not None else 0
    return (major, minor)


def match_known_groups(files: list[dict[str, Any]], groups: list[Any]) -> MatchResult:
    """Resolve cached groups against scan files.

    The matcher is deliberately pure: it receives scan file dicts plus parsed
    KnownGroup values and returns the moves/no-touch/unmatched partitions.
    """
    moves_by_group: dict[str, list[str]] = {}
    no_touch: set[str] = set()
    consumed_paths: set[str] = set()

    for group in groups:
        if group.canonical_strategy == "highest_version":
            matched = [f for f in files if fnmatch.fnmatch(f["name"], group.pattern)]
            if not matched:
                continue
            ordered = sorted(matched, key=lambda f: (_version_sort_key(f["name"]), f["mtime_iso"]))
            archive = ordered[:-1]
            moves_by_group[group.name] = [f["relative_path"] for f in archive]
            consumed_paths.update(f["relative_path"] for f in matched)

        elif group.canonical_strategy == "explicit":
            member_set = set(group.members)
            matched = [f for f in files if f["name"] in member_set]
            if not matched:
                continue
            archive = [f for f in matched if f["name"] != group.canonical]
            moves_by_group[group.name] = [f["relative_path"] for f in archive]
            consumed_paths.update(f["relative_path"] for f in matched)

        elif group.canonical_strategy == "not_a_group":
            member_set = set(group.members)
            matched = [f for f in files if f["name"] in member_set]
            if not matched:
                continue
            no_touch.update(f["relative_path"] for f in matched)
            consumed_paths.update(f["relative_path"] for f in matched)

    unmatched = [f for f in files if f["relative_path"] not in consumed_paths]
    return MatchResult(
        moves_by_group=moves_by_group,
        no_touch=no_touch,
        unmatched_files=unmatched,
    )
