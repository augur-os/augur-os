"""Entry search/match/scope/journey filtering helpers for Browse."""

from datetime import datetime
from pathlib import Path

from .index_common import _ARCHIVE_SEARCH_METADATA_KEYS, _as_string_list


def _entry_search_values(entry: dict) -> list[object]:
    return [
        entry.get("id", ""),
        entry.get("name", ""),
        entry.get("title", ""),
        entry.get("description", ""),
        entry.get("source", ""),
        entry.get("ownership", ""),
        entry.get("skill_client", ""),
        entry.get("skill_origin", ""),
        " ".join(_as_string_list(entry.get("client_sources"))),
        " ".join(_as_string_list(entry.get("skill_clients"))),
        *[entry.get(key, "") for key in _ARCHIVE_SEARCH_METADATA_KEYS],
    ]


def _entry_matches_search(entry: dict, search_lower: str) -> bool:
    searchable_values = _entry_search_values(entry)
    return any(search_lower in str(value).lower() for value in searchable_values if value)


def _entry_search_score(entry: dict, search_lower: str) -> int:
    score = 0
    for value in _entry_search_values(entry):
        text = str(value).strip().lower()
        if not text:
            continue
        if text == search_lower:
            score = max(score, 3)
        elif text.startswith(search_lower):
            score = max(score, 2)
        elif search_lower in text:
            score = max(score, 1)
    return score


def _entry_timestamp(entry: dict) -> float:
    for key in ("modified", "indexed_at", "created"):
        raw_value = str(entry.get(key) or "").strip()
        if not raw_value:
            continue
        try:
            return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
    return 0.0


def _entry_search_sort_key(entry: dict, search_lower: str) -> tuple[int, float, str]:
    label = str(entry.get("title") or entry.get("name") or entry.get("id") or "").lower()
    return (-_entry_search_score(entry, search_lower), -_entry_timestamp(entry), label)


def _entry_matches_scope(entry: dict, scope: str | None) -> bool:
    if not scope:
        return True
    normalized = scope.strip().lower()
    if normalized == "packet":
        return str(entry.get("promotion_state") or "").strip().lower() == "packet"
    if normalized in {"shared", "private"}:
        if str(entry.get("promotion_state") or "").strip().lower() == "packet":
            return False
        return str(entry.get("vault_scope") or "").strip().lower() == normalized
    return True


def _entry_matches_vault_journey(entry: dict, category_dir: Path, root: str) -> bool:
    journey = str(entry.get("journey_category") or "").strip()
    if journey:
        return journey == root

    index_path = entry.get("_index_path")
    if index_path:
        try:
            relative = Path(str(index_path)).relative_to(category_dir)
            return relative.parts[0] == root
        except (ValueError, IndexError):
            pass

    source_path = str(entry.get("source_path") or "")
    if not source_path:
        return False
    parts = Path(source_path).parts
    if not parts:
        return False
    if Path(source_path).is_absolute():
        try:
            vault_index = parts.index("Au-vault")
        except ValueError:
            return False
        return len(parts) > vault_index + 1 and parts[vault_index + 1] == root
    return parts[0] == root


def _latest_indexed_at(entries: list[dict]) -> str | None:
    latest: str | None = None
    for entry in entries:
        entry_ts = entry.get("indexed_at")
        if entry_ts and (latest is None or str(entry_ts) > latest):
            latest = str(entry_ts)
    return latest
