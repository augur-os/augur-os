"""Voice-profile state helpers for vault/profile/<language>/.

The interview itself is run by the active AI client. This module owns the
small durable files that make that flow resumable and visible to the dashboard.
"""
from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter

SCHEMA_VERSION = 1
DEFAULT_TOTAL = 100
SUPPORTED_LANGUAGES = ("en", "he")
Language = Literal["en", "he"]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_language(language: str | None) -> Language:
    normalized = (language or "").strip().lower()
    if normalized not in SUPPORTED_LANGUAGES:
        raise ValueError("language must be 'en' or 'he'")
    return normalized  # type: ignore[return-value]


def profile_dir(vault_dir: Path, language: str) -> Path:
    return vault_dir / "profile" / normalize_language(language)


def state_path(vault_dir: Path, language: str) -> Path:
    return profile_dir(vault_dir, language) / "interview-in-progress.yaml"


def about_me_path(vault_dir: Path, language: str) -> Path:
    return profile_dir(vault_dir, language) / "about-me.md"


def archive_dir(vault_dir: Path, language: str) -> Path:
    return profile_dir(vault_dir, language) / "archive"


@dataclass(frozen=True)
class QAPair:
    n: int
    category: str
    q: str
    a: str
    asked_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InterviewState:
    version: int = SCHEMA_VERSION
    language: Language = "en"
    total: int = DEFAULT_TOTAL
    answered: int = 0
    started_at: str = ""
    last_answered_at: str = ""
    mode: str = "full"
    qa_pairs: list[QAPair] = field(default_factory=list)

    @classmethod
    def fresh(cls, *, language: str = "en", mode: str = "full", total: int = DEFAULT_TOTAL) -> "InterviewState":
        now = _iso_now()
        return cls(
            version=SCHEMA_VERSION,
            language=normalize_language(language),
            total=total,
            answered=0,
            started_at=now,
            last_answered_at=now,
            mode=mode,
            qa_pairs=[],
        )

    @property
    def is_complete(self) -> bool:
        return self.answered >= self.total

    @property
    def percentage(self) -> int:
        if self.total <= 0:
            return 0
        return max(0, min(100, round((self.answered / self.total) * 100)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "language": self.language,
            "total": self.total,
            "answered": self.answered,
            "started_at": self.started_at,
            "last_answered_at": self.last_answered_at,
            "mode": self.mode,
            "qa_pairs": [qa.to_dict() for qa in self.qa_pairs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InterviewState":
        pairs: list[QAPair] = []
        for raw in data.get("qa_pairs") or []:
            if not isinstance(raw, dict):
                continue
            pairs.append(
                QAPair(
                    n=int(raw.get("n", len(pairs) + 1)),
                    category=str(raw.get("category", "")),
                    q=str(raw.get("q", "")),
                    a=str(raw.get("a", "")),
                    asked_at=str(raw.get("asked_at", "")),
                )
            )
        language = normalize_language(str(data.get("language") or "en"))
        answered = int(data.get("answered", len(pairs)))
        return cls(
            version=int(data.get("version", SCHEMA_VERSION)),
            language=language,
            total=int(data.get("total", DEFAULT_TOTAL)),
            answered=answered,
            started_at=str(data.get("started_at", "")),
            last_answered_at=str(data.get("last_answered_at", "")),
            mode=str(data.get("mode", "full")),
            qa_pairs=pairs,
        )


def load_state(path: Path) -> InterviewState | None:
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"Voice profile state must be a mapping: {path}")
    return InterviewState.from_dict(raw)


def save_state(path: Path, state: InterviewState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(state.to_dict(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def append_answer(
    state: InterviewState,
    *,
    category: str,
    question: str,
    answer: str,
    asked_at: str | None = None,
) -> InterviewState:
    qa_pairs = list(state.qa_pairs)
    qa_pairs.append(
        QAPair(
            n=len(qa_pairs) + 1,
            category=category,
            q=question,
            a=answer,
            asked_at=asked_at or _iso_now(),
        )
    )
    return InterviewState(
        version=state.version,
        language=state.language,
        total=state.total,
        answered=len(qa_pairs),
        started_at=state.started_at,
        last_answered_at=qa_pairs[-1].asked_at,
        mode=state.mode,
        qa_pairs=qa_pairs,
    )


def archive_state(state_file: Path, target_archive_dir: Path, *, run_date_iso: str | None = None) -> Path | None:
    if not state_file.exists():
        return None
    date_part = run_date_iso or datetime.now(timezone.utc).date().isoformat()
    target_archive_dir.mkdir(parents=True, exist_ok=True)
    target = target_archive_dir / f"interview-{date_part}.yaml"
    suffix = 2
    while target.exists():
        target = target_archive_dir / f"interview-{date_part}-{suffix}.yaml"
        suffix += 1
    shutil.move(str(state_file), str(target))
    return target


def get_about_me_age_days(path: Path) -> int | None:
    if not path.exists():
        return None
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    delta = datetime.now(timezone.utc) - modified
    return max(0, int(delta.total_seconds() // 86400))


def _split_markdown_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---"):
        return {}, content
    marker = content.find("\n---", 4)
    if marker == -1:
        return {}, content
    raw_meta = content[4:marker]
    body = content[marker + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    try:
        meta = yaml.safe_load(raw_meta)
    except yaml.YAMLError:
        return {}, content
    return meta if isinstance(meta, dict) else {}, body


def write_about_me(path: Path, content: str, *, language: str) -> None:
    lang = normalize_language(language)
    incoming_meta, body = _split_markdown_frontmatter(content)
    existing_meta: dict[str, Any] = {}
    if path.exists():
        existing_meta, _ = parse_frontmatter(path, include_sidecar_config=False)

    metadata = dict(existing_meta)
    metadata.update(incoming_meta)
    metadata.update(
        {
            "title": metadata.get("title") or f"Voice Profile ({lang.upper()})",
            "language": lang,
            "_hub": "brain",
            "_content_kind": "voice-profile",
            "_updated": _iso_now(),
        }
    )
    write_vault_frontmatter(path, metadata, body.rstrip() + "\n")
