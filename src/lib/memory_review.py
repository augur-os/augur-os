"""Memory review product — the reviewed promotion path into canonical brain memory (ADR-772, Task 5).

Client-native memory (what an AI client writes to its own store) is *input*, not
canonical state. Per ADR-772, raw client memory is no longer auto-promoted into a
brain's ``memory/entries/``; instead candidate facts are surfaced in a review
queue and the user or agent must explicitly **approve** a candidate before it is
written as a canonical memory entry. This module is the core engine behind the
``memory-review-*`` MCP tools and the ``/brain/memory-review`` dashboard surface.

Design mirrors :mod:`src.lib.brain_discovery`:

- The engine is **pure with respect to AI clients** — it never imports a
  skill-tree module. It cannot discover client-native memory itself; the MCP
  wrapper injects discovered ``Candidate`` records (just as the discovery wrapper
  injects per-client projection status). Everything else — staging agent
  observations, recording rejections, classifying status, and writing the
  approved entry to the brain's canonical entries dir — lives here.
- The write destination is resolved through ADR-771's
  :func:`src.lib.brain_write_routing.resolve_write_target`, so approved entries
  always land in the active brain's ``memory_dir/entries`` (today
  ``<personal-root>/memory/entries``; once ADR-770 migrates personal content,
  ``<root>/knowledge/memory/entries`` — same code, no path hardcoding).

Two persistence layers live under ``<runtime>/memory_review/<brain_id>/``:

- ``submitted.jsonl`` — agent/``/ask``-submitted candidates that have no
  client-native source file and must persist until approved or rejected.
- ``rejected.json`` — fingerprints the reviewer rejected, so a rejected
  candidate never resurfaces from live client discovery.

The pending queue itself is *derived* (client candidates are pulled live, not
copied into runtime), honoring the spec rule that Augur must not copy raw client
memory into runtime folders.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from src.lib.brain_write_routing import BrainWriteTarget, resolve_write_target

# Memory entry types recognized in canonical brain entries (matches the
# frontmatter ``type:`` field used by existing entries and the Browse Profile
# tab card mechanism).
_KNOWN_KINDS = {"feedback", "project", "preference", "reference", "user", "insight", "decision"}
_DEFAULT_KIND = "insight"

_FILENAME_SAFE = re.compile(r"[^a-z0-9]+")


# ---------------------------------------------------------------------------
# Candidate model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    """One reviewable memory fact awaiting promotion into canonical brain memory.

    ``id`` is a stable fingerprint of (client, name, description) so the same
    candidate keeps its identity across queue rebuilds — that is what lets a
    rejection stick and a promotion be detected.
    """

    id: str
    source: str  # "client:<client>" | "agent" | "ask" | "log"
    client: str  # originating client/agent ("claude-code", "agent", ...)
    kind: str  # canonical entry type (feedback/project/preference/insight/...)
    name: str
    description: str
    body: str
    target_filename: str  # canonical entry filename if promoted
    origin: str = ""  # source path or human label
    created: str = ""

    def to_public(self, *, status: str) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "client": self.client,
            "kind": self.kind,
            "name": self.name,
            "description": self.description,
            "body": self.body,
            "target_filename": self.target_filename,
            "origin": self.origin,
            "created": self.created,
            "status": status,
        }


def normalize_kind(kind: str | None) -> str:
    value = (kind or "").strip().lower()
    return value if value in _KNOWN_KINDS else _DEFAULT_KIND


def candidate_fingerprint(client: str, name: str, description: str) -> str:
    """Stable short id for a candidate keyed on client + name + description."""
    basis = " | ".join(part.strip().lower() for part in (client or "", name or "", description or ""))
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    return f"mc_{digest[:16]}"


def _slugify(text: str, *, fallback: str = "entry") -> str:
    slug = _FILENAME_SAFE.sub("_", (text or "").strip().lower()).strip("_")
    return slug or fallback


def make_candidate(
    *,
    client: str,
    name: str,
    description: str,
    body: str,
    kind: str | None = None,
    source: str | None = None,
    origin: str = "",
    created: str = "",
    target_filename: str | None = None,
) -> Candidate:
    """Build a :class:`Candidate` with a derived id and canonical filename."""
    client_id = (client or "user").strip() or "user"
    fingerprint = candidate_fingerprint(client_id, name, description)
    if not target_filename:
        target_filename = f"{client_id}_{_slugify(name)}.md"
    return Candidate(
        id=fingerprint,
        source=source or f"client:{client_id}",
        client=client_id,
        kind=normalize_kind(kind),
        name=name.strip() or fingerprint,
        description=description.strip(),
        body=body,
        target_filename=target_filename,
        origin=origin,
        created=created or _now(),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Persistence store (runtime, per brain)
# ---------------------------------------------------------------------------


class MemoryReviewStore:
    """Per-brain runtime persistence for submitted candidates + rejections."""

    def __init__(self, brain_id: str, *, root: Optional[Path] = None) -> None:
        self.brain_id = brain_id
        base = root if root is not None else _runtime_root()
        self.dir = base / brain_id
        self.submitted_path = self.dir / "submitted.jsonl"
        self.rejected_path = self.dir / "rejected.json"

    # -- submitted candidates ------------------------------------------------

    def list_submitted(self) -> list[Candidate]:
        if not self.submitted_path.is_file():
            return []
        out: list[Candidate] = []
        for line in self.submitted_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.append(_candidate_from_dict(data))
        return out

    def add_submitted(self, candidate: Candidate) -> None:
        existing = {c.id: c for c in self.list_submitted()}
        existing[candidate.id] = candidate
        self._write_submitted(existing.values())

    def remove_submitted(self, candidate_id: str) -> bool:
        existing = self.list_submitted()
        kept = [c for c in existing if c.id != candidate_id]
        if len(kept) == len(existing):
            return False
        self._write_submitted(kept)
        return True

    def _write_submitted(self, candidates: Iterable[Candidate]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(asdict(c), ensure_ascii=False) for c in candidates]
        self.submitted_path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")

    # -- rejections ----------------------------------------------------------

    def load_rejected(self) -> dict[str, dict[str, Any]]:
        if not self.rejected_path.is_file():
            return {}
        try:
            data = json.loads(self.rejected_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def is_rejected(self, candidate_id: str) -> bool:
        return candidate_id in self.load_rejected()

    def add_rejected(self, candidate_id: str, *, reason: str = "", name: str = "") -> None:
        rejected = self.load_rejected()
        rejected[candidate_id] = {
            "reason": reason,
            "name": name,
            "rejected_at": _now(),
        }
        self.dir.mkdir(parents=True, exist_ok=True)
        self.rejected_path.write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8")

    def remove_rejected(self, candidate_id: str) -> bool:
        rejected = self.load_rejected()
        if candidate_id not in rejected:
            return False
        del rejected[candidate_id]
        self.dir.mkdir(parents=True, exist_ok=True)
        self.rejected_path.write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8")
        return True


def _candidate_from_dict(data: dict[str, Any]) -> Candidate:
    return Candidate(
        id=str(data.get("id", "")),
        source=str(data.get("source", "agent")),
        client=str(data.get("client", "user")),
        kind=normalize_kind(data.get("kind")),
        name=str(data.get("name", "")),
        description=str(data.get("description", "")),
        body=str(data.get("body", "")),
        target_filename=str(data.get("target_filename", "")),
        origin=str(data.get("origin", "")),
        created=str(data.get("created", "")),
    )


def _runtime_root() -> Path:
    from src.config.paths import get_runtime_dir

    return get_runtime_dir() / "memory_review"


# ---------------------------------------------------------------------------
# Status classification + queue
# ---------------------------------------------------------------------------


def _existing_entry_fingerprints(entries_dir: Path) -> tuple[set[str], set[str]]:
    """Return (existing filenames, existing fingerprints) for promoted entries.

    A candidate counts as already promoted if its target filename exists OR an
    existing entry's frontmatter (client, name, description) fingerprints to the
    same id. The latter catches entries written under the legacy auto-assembler
    naming before the candidate id scheme existed.
    """
    filenames: set[str] = set()
    fingerprints: set[str] = set()
    if not entries_dir.is_dir():
        return filenames, fingerprints
    for path in sorted(entries_dir.glob("*.md")):
        filenames.add(path.name)
        meta = _read_entry_frontmatter(path)
        if meta is None:
            continue
        client = _client_from_filename(path.stem)
        name = str(meta.get("name") or path.stem)
        description = str(meta.get("description") or "")
        fingerprints.add(candidate_fingerprint(client, name, description))
    return filenames, fingerprints


def _read_entry_frontmatter(path: Path) -> Optional[dict[str, Any]]:
    try:
        from src.lib.frontmatter_utils import parse_frontmatter

        meta, _body = parse_frontmatter(path, include_sidecar_config=False)
        return meta
    except Exception:  # noqa: BLE001 — a malformed entry never breaks the queue
        return None


_KNOWN_CLIENT_PREFIXES = {"claude-code", "codex", "gemini", "copilot", "cursor", "user", "augur", "agent"}


def _client_from_filename(stem: str) -> str:
    if "_" not in stem:
        return "user"
    prefix = stem.split("_", 1)[0]
    return prefix if prefix in _KNOWN_CLIENT_PREFIXES else "user"


def classify(
    candidate: Candidate,
    *,
    existing_filenames: set[str],
    existing_fingerprints: set[str],
    rejected_ids: set[str],
) -> str:
    if candidate.id in rejected_ids:
        return "rejected"
    if candidate.target_filename in existing_filenames or candidate.id in existing_fingerprints:
        return "promoted"
    return "pending"


def build_queue(
    *,
    target: BrainWriteTarget,
    client_candidates: Iterable[Candidate],
    store: Optional[MemoryReviewStore] = None,
    include_resolved: bool = False,
) -> dict[str, Any]:
    """Assemble the review queue snapshot for one brain.

    Merges injected client-native candidates with persisted agent submissions,
    dedupes by id (submitted wins, so an agent can override a client summary),
    and classifies each as pending / promoted / rejected.
    """
    store = store or MemoryReviewStore(target.brain.id)
    entries_dir = target.memory_dir / "entries"
    existing_filenames, existing_fingerprints = _existing_entry_fingerprints(entries_dir)
    rejected = store.load_rejected()
    rejected_ids = set(rejected.keys())

    merged: dict[str, Candidate] = {}
    for cand in client_candidates:
        merged[cand.id] = cand
    for cand in store.list_submitted():
        merged[cand.id] = cand  # submitted overrides a same-id client candidate

    pending: list[dict[str, Any]] = []
    promoted: list[dict[str, Any]] = []
    rejected_out: list[dict[str, Any]] = []
    seen_rejected: set[str] = set()
    for cand in merged.values():
        status = classify(
            cand,
            existing_filenames=existing_filenames,
            existing_fingerprints=existing_fingerprints,
            rejected_ids=rejected_ids,
        )
        record = cand.to_public(status=status)
        if status == "pending":
            pending.append(record)
        elif status == "promoted":
            promoted.append(record)
        else:
            rejected_out.append(record)
            seen_rejected.add(cand.id)

    # Rejections persist even when their candidate is no longer live (e.g. an
    # agent submission that was rejected and removed from staging). Surface the
    # full rejection set so the count is honest and a rejection can be undone.
    for rid, meta in rejected.items():
        if rid in seen_rejected:
            continue
        rejected_out.append(
            {
                "id": rid,
                "name": str(meta.get("name", "")),
                "reason": str(meta.get("reason", "")),
                "rejected_at": str(meta.get("rejected_at", "")),
                "status": "rejected",
            }
        )

    pending.sort(key=lambda r: (r["client"], r["name"].lower()))

    snapshot: dict[str, Any] = {
        "success": True,
        "generated_at": _now(),
        "brain": target.summary(),
        "writable": target.mode != "packet",
        "entries_dir": str(entries_dir),
        "counts": {
            "pending": len(pending),
            "promoted": len(promoted),
            "rejected": len(rejected_out),
        },
        "pending": pending,
    }
    if include_resolved:
        snapshot["promoted"] = promoted
        snapshot["rejected"] = rejected_out
    return snapshot


# ---------------------------------------------------------------------------
# Promotion (approve), reject, submit
# ---------------------------------------------------------------------------


def _packet_guard(target: BrainWriteTarget) -> Optional[dict[str, Any]]:
    if target.mode == "packet":
        return {
            "success": False,
            "error": f"brain {target.brain.id} requires packet-based writes; " "memory review cannot write directly",
            "brain": target.summary(),
            "packet_root": str(target.packet_root) if target.packet_root else None,
        }
    return None


def write_entry(*, target: BrainWriteTarget, candidate: Candidate) -> Path:
    """Write an approved candidate as a canonical brain memory entry.

    Destination: ``target.memory_dir/entries/<target_filename>`` (ADR-771
    resolver). The frontmatter matches the existing entry schema; a provenance
    comment is placed after the closing frontmatter marker (CLAUDE.md rule 17).
    """
    from src.lib.frontmatter_utils import write_frontmatter

    entries_dir = target.memory_dir / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    dest = entries_dir / candidate.target_filename

    metadata = {
        "name": candidate.name,
        "description": candidate.description,
        "type": candidate.kind,
        "source": candidate.source,
        "source_client": candidate.client,
        "source_created_at": candidate.created,
        "reviewed_at": _now(),
    }
    provenance = f"<!-- PROMOTED via memory review from {candidate.client} -->"
    body = candidate.body.strip()
    body = f"{provenance}\n\n{body}\n" if body else f"{provenance}\n"
    write_frontmatter(dest, metadata, body)
    return dest


def approve(
    *,
    target: BrainWriteTarget,
    candidate: Candidate,
    store: Optional[MemoryReviewStore] = None,
) -> dict[str, Any]:
    guard = _packet_guard(target)
    if guard is not None:
        return guard
    store = store or MemoryReviewStore(target.brain.id)
    dest = write_entry(target=target, candidate=candidate)
    store.remove_submitted(candidate.id)
    store.remove_rejected(candidate.id)
    return {
        "success": True,
        "approved": candidate.id,
        "path": str(dest),
        "brain": target.summary(),
        "name": candidate.name,
    }


def reject(
    *,
    target: BrainWriteTarget,
    candidate_id: str,
    store: Optional[MemoryReviewStore] = None,
    reason: str = "",
    name: str = "",
) -> dict[str, Any]:
    store = store or MemoryReviewStore(target.brain.id)
    store.add_rejected(candidate_id, reason=reason, name=name)
    store.remove_submitted(candidate_id)
    return {
        "success": True,
        "rejected": candidate_id,
        "brain": target.summary(),
    }


def submit(
    *,
    target: BrainWriteTarget,
    name: str,
    description: str,
    body: str,
    kind: str | None = None,
    client: str = "agent",
    source: str = "agent",
    store: Optional[MemoryReviewStore] = None,
) -> dict[str, Any]:
    """Stage an agent-curated observation as a pending review candidate."""
    if not name.strip():
        return {"success": False, "error": "candidate name is required"}
    store = store or MemoryReviewStore(target.brain.id)
    candidate = make_candidate(
        client=client,
        name=name,
        description=description,
        body=body,
        kind=kind,
        source=source,
        origin="agent submission",
    )
    store.remove_rejected(candidate.id)  # an explicit resubmit clears a prior rejection
    store.add_submitted(candidate)
    return {
        "success": True,
        "submitted": candidate.id,
        "candidate": candidate.to_public(status="pending"),
        "brain": target.summary(),
    }


# ---------------------------------------------------------------------------
# Convenience: resolve target + queue from cwd/explicit brain
# ---------------------------------------------------------------------------


def resolve_target(
    *,
    explicit_brain: str | None = None,
    cwd: Path | None = None,
    registry_path: Path | None = None,
) -> BrainWriteTarget:
    return resolve_write_target(
        explicit_brain=explicit_brain,
        cwd=cwd,
        registry_path=registry_path,
    )
