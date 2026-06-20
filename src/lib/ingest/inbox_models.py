from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


@dataclass
class InboxFolderCounts:
    new_files: int = 0
    document_candidates: int = 0
    trash_candidates: int = 0
    failed: int = 0


@dataclass
class InboxFolder:
    id: str
    name: str
    path: str
    enabled: bool = True
    counts: InboxFolderCounts = field(default_factory=InboxFolderCounts)
    last_scan_at: str | None = None
    last_run_status: str | None = None


@dataclass
class InboxFileResult:
    source_path: str
    final_path: str
    source_card_path: str
    content_type: str
    extraction_method: str
    hardware_backend: str
    confidence: str
    route: str
    renamed_to: str
    rag_indexed: bool
    status: str
    document_kind: str | None = None
    route_reason: str | None = None
    extracted_path: str | None = None
    local_agent_used: bool = False
    cloud_used: bool = False
    escalation_reason: str | None = None
    cloud_provider: str | None = None
    cloud_model: str | None = None
    content_hash: str | None = None
    review_reason: str | None = None
    error: str | None = None


@dataclass
class InboxInsight:
    title: str
    summary: str
    sources: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    impact_score: float = 0.5


@dataclass
class InboxRunRecord:
    id: str
    folder_id: str
    started_at: str
    completed_at: str
    status: str
    airplane_mode: bool
    files_seen: int = 0
    files_moved: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    files_needing_review: int = 0
    cloud_calls: int = 0
    local_agent_calls: int = 0
    wiki_update_marked: bool = False
    file_results: list[InboxFileResult] = field(default_factory=list)
    insights: list[InboxInsight] = field(default_factory=list)


def to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    return value
