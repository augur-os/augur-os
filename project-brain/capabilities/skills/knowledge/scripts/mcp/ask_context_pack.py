"""Static live-memory context pack for /ask retrieval."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import subprocess
from typing import Iterable


SUMMARY_FILENAMES = (
    "MEMORY.md",
    "memory/MEMORY.md",
    "digest-hot.md",
    "memory/digest-hot.md",
)

CURRENT_FOCUS_TERMS = {
    "now",
    "currently",
    "latest",
    "today",
}
CURRENT_FOCUS_PHRASES = (" working on ", " current focus ", " focused on ")
CLIENT_MEMORY_FAMILIES = {"codex_memory", "agent_global_memories"}
GENERIC_QUERY_TERMS = {
    "what",
    "about",
    "this",
    "that",
    "these",
    "those",
    "thing",
    "things",
    "it",
    "its",
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "onto",
    "over",
    "under",
    "why",
    "how",
    "when",
    "where",
    "who",
    "which",
    "should",
    "could",
    "would",
    "does",
    "did",
    "not",
    "working",
    "work",
    "current",
    "currently",
    "latest",
    "today",
    "focus",
    "focused",
    "now",
    "are",
    "was",
    "were",
    "been",
    "being",
    "has",
    "have",
    "had",
    "can",
    "will",
    "might",
    "must",
    "shall",
    "know",
    "want",
    "need",
    "tell",
    "give",
    "show",
    "list",
}

STRUCTURED_SEARCH_COMMANDS = {
    "search",
    "status",
    "reindex",
    "cleanup",
    "purge",
}

WIKI_META_PAGE_NAMES = {"index.md", "overview.md"}
WIKI_META_SOURCE_PRIORITY = 0.6

# Extracted document chunks have index-build mtimes, not content dates; score
# them with neutral freshness so a rebuild never outranks genuinely fresh notes.
DOCUMENT_CHUNK_FRESHNESS = 0.45


@dataclass(frozen=True)
class SourceRoot:
    family: str
    root: Path
    label: str
    current_focus_eligible: bool
    summary_names: tuple[str, ...] = SUMMARY_FILENAMES


@dataclass(frozen=True)
class SourceCandidate:
    family: str
    path: Path | None
    path_label: str
    text: str
    updated_at: str | None
    freshness: float
    score: float
    reasons: tuple[str, ...] = field(default_factory=tuple)
    match_terms: tuple[str, ...] = field(default_factory=tuple)
    current_focus_eligible: bool = False
    stale: bool = False

    def quality_source(self) -> dict[str, object]:
        return {
            "text": self.text,
            "source_family": self.family,
            "path_label": self.path_label,
            "updated_at": self.updated_at,
            "freshness": self.freshness,
            "stale": self.stale,
            "score": self.score,
            "reasons": list(self.reasons),
            "match_terms": list(self.match_terms),
        }


@dataclass(frozen=True)
class ContextPack:
    intent: str
    candidates: tuple[SourceCandidate, ...]
    source_basis: tuple[str, ...]
    warnings: tuple[str, ...]

    def quality_sources(self) -> list[dict[str, object]]:
        return [candidate.quality_source() for candidate in self.candidates if candidate.text]


def _home_dir() -> Path:
    return Path(os.environ.get("HOME") or Path.home()).expanduser()


def _codex_memory_root() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "memories"
    return _home_dir() / ".codex" / "memories"


def _configured_global_memory_roots() -> list[Path]:
    raw = os.environ.get("AUGUR_ASK_MEMORY_ROOTS", "")
    roots: list[Path] = []
    for item in raw.split(os.pathsep):
        if item.strip():
            roots.append(Path(item).expanduser())
    return roots


def discover_source_roots(
    *,
    vault_dir: Path,
    wiki_dir: Path,
    vault_memory_dir: Path,
    runtime_dir: Path,
    project_root: Path,
) -> list[SourceRoot]:
    runtime_memory_dir = runtime_dir / "memory"
    if not runtime_memory_dir.exists():
        runtime_memory_dir = runtime_dir
    candidates = [
        SourceRoot("augur_wiki", wiki_dir, "Augur wiki", True),
        # Only the vault-root index; memory/* summaries belong to augur_vault_memory.
        SourceRoot("personal_vault", vault_dir, "Personal vault", False, ("MEMORY.md",)),
        SourceRoot("augur_vault_memory", vault_memory_dir, "Au-vault memory", True),
        SourceRoot(
            "augur_runtime_memory",
            runtime_memory_dir,
            "Augur runtime memory",
            True,
        ),
        SourceRoot("codex_memory", _codex_memory_root(), "Codex memory", True),
        SourceRoot("repo_evidence", project_root, "Augur repo", True, ()),
    ]
    for index, root in enumerate(_configured_global_memory_roots(), start=1):
        candidates.append(
            SourceRoot(
                "agent_global_memories",
                root,
                f"Agent global memory {index}",
                True,
            )
        )
    return [root for root in candidates if root.root.exists()]


def _looks_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return b"\x00" in handle.read(2048)
    except OSError:
        return True


def read_bounded_file(path: Path, max_chars: int = 4000) -> str:
    marker = "\n\n[...]\n\n"
    if not path.is_file() or _looks_binary(path):
        return ""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            initial = handle.read(max_chars + 1)
    except OSError:
        return ""
    if len(initial) <= max_chars:
        return initial
    if max_chars <= len(marker):
        return initial[:max_chars]

    content_chars = max_chars - len(marker)
    head_len = content_chars // 2
    tail_len = content_chars - head_len
    head = initial[:head_len]
    tail = ""
    try:
        with path.open("rb") as handle:
            tail_window = max(tail_len * 4, tail_len)
            handle.seek(0, os.SEEK_END)
            file_size = handle.tell()
            handle.seek(max(0, file_size - tail_window))
            tail = handle.read(tail_window).decode("utf-8", errors="ignore")[-tail_len:]
    except OSError:
        return head
    return head + marker + tail


def iter_summary_files(root: SourceRoot, *, max_files: int = 12) -> Iterable[Path]:
    yielded: list[Path] = []
    for name in root.summary_names:
        path = root.root / name
        if path.is_file():
            yielded.append(path)
    if root.family == "augur_wiki":
        active = root.root / "active-projects.md"
        if active.is_file() and active not in yielded:
            yielded.insert(0, active)
        latest_pages = sorted(
            (path for path in root.root.glob("*.md") if path.is_file()),
            key=lambda path: (-_safe_mtime(path), str(path)),
        )[:max_files]
        for path in latest_pages:
            if path not in yielded:
                yielded.append(path)
    if root.family == "codex_memory":
        rollout_dir = root.root / "rollout_summaries"
        if rollout_dir.is_dir():
            latest = sorted(
                (path for path in rollout_dir.iterdir() if path.suffix == ".md"),
                key=lambda path: (-_safe_mtime(path), str(path)),
            )[:5]
            yielded.extend(latest)
    seen: set[Path] = set()
    for path in yielded:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        yield path
        if len(seen) >= max_files:
            break


def iso_mtime(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return None


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def classify_query_intent(query: str) -> str:
    lowered = query.lower().strip()
    tokens = re.findall(r"[a-z0-9_-]+", lowered)
    command_tokens = tokens[1:] if tokens[:1] == ["ask"] else tokens
    if command_tokens and command_tokens[0] in STRUCTURED_SEARCH_COMMANDS:
        return "structured_search"
    compact = f" {' '.join(tokens)} "
    if " not working " in compact:
        return "reflective"
    token_set = set(command_tokens)
    if (
        any(phrase in compact for phrase in CURRENT_FOCUS_PHRASES)
        or token_set.intersection(CURRENT_FOCUS_TERMS)
    ):
        return "current_focus"
    return "reflective"


def _normalise_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().strip("'\"").strip()
    cleaned = cleaned.replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
        cleaned = f"{cleaned}T00:00:00+00:00"
    elif " " in cleaned and "T" not in cleaned:
        date_part, time_part = cleaned.split(" ", 1)
        cleaned = f"{date_part}T{time_part}"
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _parse_frontmatter_updated(text: str) -> str | None:
    normalised_text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalised_text.startswith("---\n"):
        return None
    end = normalised_text.find("\n---", 4)
    if end == -1:
        return None
    frontmatter = normalised_text[4:end]
    for key in ("updated_at", "_updated", "modified", "updated", "captured_at", "date"):
        match = re.search(rf"^{key}:\s*([^#\n]+)", frontmatter, re.MULTILINE)
        if match:
            timestamp = _normalise_timestamp(match.group(1))
            if timestamp:
                return timestamp
    return None


def _parse_embedded_updated(text: str) -> str | None:
    pattern = (
        r"\b(?:updated|updated_at|captured_at|modified)\s*[:=]\s*"
        r"['\"]?(\d{4}-\d{2}-\d{2}(?:[T ][0-9:.+-]+(?:Z|[+-]\d{2}:?\d{2})?)?)"
    )
    match = re.search(pattern, text)
    if not match:
        return None
    return _normalise_timestamp(match.group(1))


def _parse_date(value: str | None) -> datetime | None:
    normalised = _normalise_timestamp(value)
    if not normalised:
        return None
    try:
        return datetime.fromisoformat(normalised)
    except ValueError:
        return None


def _current_day(current_date: str) -> datetime:
    parsed = _parse_date(current_date)
    if parsed is None:
        return datetime.now(timezone.utc)
    return parsed


def _is_stale(updated_at: str | None, *, current_date: str, stale_after_days: int = 14) -> bool:
    parsed = _parse_date(updated_at)
    if parsed is None:
        return False
    today = _current_day(current_date)
    return (today.date() - parsed.date()).days > stale_after_days


def _lexical_terms(text: str) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]+", text.lower()):
        if len(word) <= 2 or word in seen:
            continue
        seen.add(word)
        terms.append(word)
    return tuple(terms)


def _query_terms(query: str) -> tuple[str, ...]:
    terms = list(_lexical_terms(query))
    while terms and (terms[0] == "ask" or terms[0] in STRUCTURED_SEARCH_COMMANDS):
        terms.pop(0)
    return tuple(terms)


def _match_terms(query: str, text: str) -> tuple[str, ...]:
    content_terms = _content_query_terms(query)
    if not content_terms:
        return ()
    text_terms = set(_lexical_terms(text))
    return tuple(term for term in content_terms if term in text_terms)


def _keyword_score(query: str, text: str) -> float:
    content_terms = _content_query_terms(query)
    if not content_terms:
        return 0.0
    return len(_match_terms(query, text)) / len(content_terms)


def _freshness_score(updated_at: str | None, *, current_date: str) -> float:
    parsed = _parse_date(updated_at)
    if parsed is None:
        return 0.2
    today = _current_day(current_date)
    age_days = max((today.date() - parsed.date()).days, 0)
    if age_days <= 1:
        return 1.0
    if age_days <= 7:
        return 0.8
    if age_days <= 30:
        return 0.45
    return 0.1


def _source_priority(family: str, intent: str) -> float:
    if intent == "current_focus":
        return {
            "repo_evidence": 1.1,
            "codex_memory": 1.0,
            "agent_global_memories": 0.95,
            "augur_runtime_memory": 0.9,
            "personal_vault": 0.85,
            "augur_vault_memory": 0.8,
            "augur_wiki": 0.5,
        }.get(family, 0.4)
    return {
        "augur_wiki": 1.2,
        "personal_vault": 0.95,
        "augur_vault_memory": 0.75,
        "augur_runtime_memory": 0.65,
        "codex_memory": 0.55,
        "agent_global_memories": 0.5,
        "repo_evidence": 0.4,
    }.get(family, 0.4)


def _is_wiki_meta_page(path: Path, text: str) -> bool:
    """Structural wiki pages (index/overview/query rollups) — never topical answers."""
    if path.name in WIKI_META_PAGE_NAMES:
        return True
    normalised = text.replace("\r\n", "\n")
    if not normalised.startswith("---\n"):
        return False
    end = normalised.find("\n---", 4)
    if end == -1:
        return False
    return bool(re.search(r"^_page_type:\s*query\s*$", normalised[4:end], re.MULTILINE))


def _source_quality(path: Path, root: SourceRoot) -> float:
    try:
        relative = path.relative_to(root.root).as_posix()
    except ValueError:
        relative = path.name
    if relative in root.summary_names or path.name in {"active-projects.md", "MEMORY.md", "digest-hot.md"}:
        return 0.15
    if root.family == "augur_wiki" and path.suffix == ".md":
        return 0.08
    return 0.03


def _candidate_for_file(
    root: SourceRoot,
    path: Path,
    query: str,
    *,
    intent: str,
    current_date: str,
) -> SourceCandidate | None:
    text = read_bounded_file(path)
    if not text.strip():
        return None
    updated_at = _parse_frontmatter_updated(text) or _parse_embedded_updated(text) or iso_mtime(path)
    freshness = _freshness_score(updated_at, current_date=current_date)
    stale = _is_stale(updated_at, current_date=current_date)
    source = _source_priority(root.family, intent)
    if root.family == "augur_wiki" and _is_wiki_meta_page(path, text):
        source = min(source, WIKI_META_SOURCE_PRIORITY)
    match_terms = _match_terms(query, text)
    lexical = _keyword_score(query, text)
    quality = _source_quality(path, root)
    stale_penalty = 0.35 if stale and intent == "current_focus" else 0.0
    score = source + freshness + lexical + quality - stale_penalty
    reasons = (
        f"source={source:.2f}",
        f"freshness={freshness:.2f}",
        f"lexical={lexical:.2f}",
        f"quality={quality:.2f}",
        f"match_terms={','.join(match_terms) if match_terms else 'none'}",
    )
    return SourceCandidate(
        family=root.family,
        path=path,
        path_label=f"{root.label}: {path.name}",
        text=text,
        updated_at=updated_at,
        freshness=freshness,
        score=score,
        reasons=reasons,
        match_terms=match_terms,
        current_focus_eligible=root.current_focus_eligible,
        stale=stale,
    )


def _repo_candidate(project_root: Path, query: str, *, intent: str, current_date: str) -> SourceCandidate | None:
    if intent != "current_focus" or not (project_root / ".git").exists():
        return None
    reference_day = (_parse_date(current_date) or datetime(1970, 1, 1, tzinfo=timezone.utc)).astimezone(
        timezone.utc
    )
    since = (reference_day - timedelta(days=2)).isoformat()
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--oneline", "--no-merges", "-n", "20"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    text = result.stdout.strip()
    if not text:
        return None
    updated_at = reference_day.isoformat()
    freshness = 1.0
    match_terms = _match_terms(query, text)
    lexical = _keyword_score(query, text)
    score = _source_priority("repo_evidence", intent) + freshness + lexical
    return SourceCandidate(
        family="repo_evidence",
        path=project_root,
        path_label="Augur repo: recent commits",
        text=text,
        updated_at=updated_at,
        freshness=freshness,
        score=score,
        reasons=(
            "recent-git-log",
            "freshness=1.00",
            f"lexical={lexical:.2f}",
            f"match_terms={','.join(match_terms) if match_terms else 'none'}",
        ),
        match_terms=match_terms,
        current_focus_eligible=True,
    )


def candidate_for_search_hit(
    hit: dict,
    *,
    vault_dir: Path,
    wiki_dir: Path,
    query: str,
    intent: str,
    rag_dir: Path | None = None,
    current_date: str | None = None,
) -> SourceCandidate | None:
    """Convert a hybrid-search hit into a scored candidate (family by location).

    Relative BM25 chunk paths resolve against ``rag_dir``; extracted personal
    document chunks (``chunks/documents/...``) join the personal_vault family.
    """
    file_path = hit.get("file", "")
    if not file_path:
        return None
    path = Path(file_path)
    if not path.is_absolute() and rag_dir is not None:
        candidate_path = rag_dir / path
        if candidate_path.is_file():
            path = candidate_path
    try:
        resolved = path.resolve()
    except OSError:
        return None
    today = current_date or datetime.now(timezone.utc).date().isoformat()
    family, label, root_dir = "personal_vault", "Personal vault", vault_dir
    document_source = ""
    try:
        resolved.relative_to(wiki_dir.resolve())
        family, label, root_dir = "augur_wiki", "Augur wiki", wiki_dir
    except (ValueError, OSError):
        try:
            resolved.relative_to(vault_dir.resolve())
        except (ValueError, OSError):
            if rag_dir is None:
                return None
            try:
                resolved.relative_to((rag_dir / "chunks" / "documents").resolve())
            except (ValueError, OSError):
                return None
            label, root_dir = "Personal documents", rag_dir
            document_source = str(hit.get("source", "") or "")
    root = SourceRoot(family, root_dir, label, False)
    candidate = _candidate_for_file(root, path, query, intent=intent, current_date=today)
    if candidate is not None and document_source:
        candidate = replace(
            candidate,
            path_label=f"{label}: {document_source}",
            updated_at=None,
            freshness=DOCUMENT_CHUNK_FRESHNESS,
            score=candidate.score - candidate.freshness + DOCUMENT_CHUNK_FRESHNESS,
            stale=False,
        )
    return candidate


def source_basis_for(candidates: list[SourceCandidate]) -> tuple[str, ...]:
    """Public provenance line builder for an already-ranked candidate list."""
    return _source_basis(candidates)


def _source_basis(candidates: list[SourceCandidate]) -> tuple[str, ...]:
    basis: list[str] = []
    for candidate in candidates[:5]:
        if not candidate.updated_at:
            basis.append(candidate.path_label)
            continue
        stale = " (stale)" if candidate.stale else ""
        basis.append(f"{candidate.path_label} updated {candidate.updated_at[:10]}{stale}")
    return tuple(basis)


def _updated_sort_value(updated_at: str | None) -> float:
    parsed = _parse_date(updated_at)
    if parsed is None:
        return float("-inf")
    return parsed.timestamp()


def _relevance_sort_values(candidate: SourceCandidate, intent: str, query: str) -> tuple[float, int]:
    if intent not in {"structured_search", "reflective"}:
        return (0.0, 0)
    content_terms = _content_query_terms(query)
    if not content_terms:
        return (0.0, 0)
    match_count = len(candidate.match_terms)
    return (match_count / len(content_terms), match_count)


def candidate_sort_key(
    candidate: SourceCandidate, intent: str, query: str
) -> tuple[float, int, float, float, float, str, str]:
    relevance_coverage, relevance_count = _relevance_sort_values(candidate, intent, query)
    return (
        -relevance_coverage,
        -relevance_count,
        -candidate.score,
        -candidate.freshness,
        -_updated_sort_value(candidate.updated_at),
        candidate.family,
        candidate.path_label,
    )


def sort_candidates(
    candidates: list[SourceCandidate], intent: str, query: str
) -> list[SourceCandidate]:
    return sorted(candidates, key=lambda c: candidate_sort_key(c, intent, query))


def _content_query_terms(query: str) -> tuple[str, ...]:
    return tuple(term for term in _query_terms(query) if term not in GENERIC_QUERY_TERMS)


def _content_match_terms(candidate: SourceCandidate) -> tuple[str, ...]:
    return tuple(term for term in candidate.match_terms if term not in GENERIC_QUERY_TERMS)


EXPANSION_STOP_WORDS = {
    "what",
    "working",
    "current",
    "currently",
    "latest",
    "today",
    "focus",
    "now",
    "this",
    "that",
    "with",
    "from",
    "about",
    "work",
    "fresh",
    "thread",
    "updated",
    "rollout",
    "path",
    "users",
    "projects",
    "augur",
    "codex",
    "sessions",
    "session",
    "payload",
    "meta",
    "jsonl",
    "branch",
    "main",
    "built",
    "validated",
    "cleanup",
    "status",
    "source",
    "basis",
    "event",
    "report",
    "generated",
    "passed",
    "warnings",
    "outcome",
    "partial",
    "preference",
    "signals",
    "steps",
    "verified",
    "repo",
}

def _is_expansion_noise_line(line: str) -> bool:
    lowered = line.strip().lower()
    return not lowered


def _contains_path_shape(value: str) -> bool:
    stripped = value.strip().strip("`'\"()").strip()
    lowered = stripped.lower()
    if re.search(r"(?:[A-Za-z]:\\|\\\\)", stripped):
        return True
    if lowered.startswith(("~/", "/", "./", "../")) and stripped.count("/") >= 2:
        return True
    if re.search(r"\b(?:project-brain|src|apps|docs|config|plugins)(?:/|\\)", lowered):
        return True
    if re.search(r"(?:/|\\)[^/\\\s]+(?:/|\\)[^/\\\s]+", stripped):
        return True
    if re.search(r"(?:/|\\)[^/\\\s]+\.[A-Za-z0-9]{2,5}\b", stripped):
        return True
    return False


def _mask_enclosed_path_spans(line: str) -> str:
    span_pattern = re.compile(
        r"`[^`\r\n]*(?:/|\\)[^`\r\n]*`"
        r"|'[^'\r\n]*(?:/|\\)[^'\r\n]*'"
        r"|\"[^\"\r\n]*(?:/|\\)[^\"\r\n]*\""
        r"|\([^()\r\n]*(?:/|\\)[^()\r\n]*\)"
    )
    return span_pattern.sub(lambda match: " " if _contains_path_shape(match.group(0)) else match.group(0), line)


def _strip_expansion_noise_tokens(line: str) -> str:
    cleaned = re.sub(r"\b[a-z][a-z0-9+.-]*://\S+", " ", line, flags=re.IGNORECASE)
    cleaned = _mask_enclosed_path_spans(cleaned)
    cleaned = re.sub(
        r"(?<![A-Za-z0-9])~?/Library/Application Support/"
        r"(?:[^\s`'\"(),.;:]+/)*"
        r"(?:[^\s`'\"(),.;:]+(?:\s+[^\s`'\"(),.;:]+)*\.[A-Za-z0-9]{2,5}|[^\s`'\"(),.;:]+)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?<![A-Za-z0-9])[A-Za-z]:\\"
        r"(?:[^\s\\`'\"(),.;:]+\\)*(?:Application Support\\)?(?:[^\s\\`'\"(),.;:]+\\)*"
        r"(?:[^\s\\`'\"(),.;:]+(?:\s+[^\s\\`'\"(),.;:]+)*\.[A-Za-z0-9]{2,5}|[^\s\\`'\"(),.;:]+)",
        " ",
        cleaned,
    )
    cleaned = re.sub(
        r"(?<![A-Za-z0-9_-])(?:\.{1,2}/)?"
        r"(?:project-brain|src|apps|docs|config|plugins)(?:/[^\s`'\"(),.;:]+)+",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?<![A-Za-z0-9_-])(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+(?:\.[A-Za-z0-9]{2,5})?",
        " ",
        cleaned,
    )
    cleaned = re.sub(
        r"(?<![A-Za-z0-9])[`'\"(]*~?/(?:[^\s`'\"()]+/)+[^\s`'\"(),.;:]+[`'\"),.;:]*",
        " ",
        cleaned,
    )
    cleaned = re.sub(
        r"(?<![A-Za-z0-9])[`'\"(]*[A-Za-z]:\\[^\s`'\"()]+[`'\"),.;:]*",
        " ",
        cleaned,
    )
    cleaned = re.sub(
        r"(?<![A-Za-z0-9])[`'\"(]*\\\\[^\s`'\"()]+[`'\"),.;:]*",
        " ",
        cleaned,
    )
    cleaned = re.sub(
        r"\b(?:updated_at|updated|captured_at|modified|rollout_path|thread_id|session_meta|source_basis)\b\s*[:=]?",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\S+\.jsonl\b", " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def _expansion_terms(text: str) -> Iterable[str]:
    for line in text.splitlines():
        if _is_expansion_noise_line(line):
            continue
        for term in re.findall(r"[A-Za-z]{4,}", _strip_expansion_noise_tokens(line)):
            lowered = term.lower()
            if lowered in EXPANSION_STOP_WORDS:
                continue
            yield term


def build_context_pack(
    query: str,
    *,
    vault_dir: Path,
    wiki_dir: Path,
    vault_memory_dir: Path,
    runtime_dir: Path,
    project_root: Path,
    current_date: str | None = None,
    max_candidates: int = 12,
) -> ContextPack:
    today = current_date or datetime.now(timezone.utc).date().isoformat()
    intent = classify_query_intent(query)
    roots = discover_source_roots(
        vault_dir=vault_dir,
        wiki_dir=wiki_dir,
        vault_memory_dir=vault_memory_dir,
        runtime_dir=runtime_dir,
        project_root=project_root,
    )
    candidates: list[SourceCandidate] = []
    for root in roots:
        if root.family == "repo_evidence":
            repo = _repo_candidate(root.root, query, intent=intent, current_date=today)
            if repo is not None:
                candidates.append(repo)
            continue
        for path in iter_summary_files(root):
            candidate = _candidate_for_file(root, path, query, intent=intent, current_date=today)
            if candidate is not None:
                candidates.append(candidate)

    candidates = sort_candidates(candidates, intent, query)
    kept = candidates[:max_candidates]
    warnings: list[str] = []
    if kept and kept[0].stale:
        warnings.append("stale-primary-source")
    if kept and any(candidate.stale for candidate in kept):
        warnings.append("stale-source-present")
    if intent == "current_focus" and not any(not candidate.stale for candidate in kept):
        warnings.append("no-fresh-sources")
    if intent == "current_focus" and not any(
        candidate.family in CLIENT_MEMORY_FAMILIES for candidate in kept
    ):
        warnings.append("client-memory-unavailable")
    if (
        intent == "reflective"
        and kept
        and not _content_query_terms(query)
        and not any(_content_match_terms(candidate) for candidate in kept)
    ):
        warnings.append("generic-query-low-signal")
    return ContextPack(
        intent=intent,
        candidates=tuple(kept),
        source_basis=_source_basis(kept),
        warnings=tuple(warnings),
    )


def expanded_search_query(query: str, pack: ContextPack, *, max_terms: int = 8) -> str:
    if pack.intent != "current_focus":
        return query
    terms: list[str] = []
    seen: set[str] = set()
    for candidate in pack.candidates[:4]:
        for term in _expansion_terms(candidate.text):
            lowered = term.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            terms.append(term)
            if len(terms) >= max_terms:
                break
        if len(terms) >= max_terms:
            break
    if not terms:
        return query
    return " ".join([query, *terms])
