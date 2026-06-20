from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


DEFAULT_EMAIL_DROP_FORMATS = [
    ".eml",
    ".msg",
    ".oft",
    ".mbox",
    ".pst",
    ".zip",
    ".tgz",
    ".tar",
    ".tar.gz",
    ".pdf",
    ".txt",
    ".html",
    ".htm",
    ".mht",
    ".mhtml",
]


@dataclass
class EmailDropCounts:
    pending_files: int = 0
    email_native: int = 0
    archives: int = 0
    degraded: int = 0
    unsupported: int = 0
    failed: int = 0
    contained_messages: int = 0
    attachments: int = 0
    article_links: int = 0


@dataclass
class EmailDropSource:
    id: str
    name: str
    path: str
    type: str = "email_drop_folder"
    enabled: bool = True
    formats: list[str] = field(
        default_factory=lambda: list(DEFAULT_EMAIL_DROP_FORMATS)
    )
    batch_limit: int = 5
    batch_order: str = "newest_first"
    after_success_action: str = "move_file"
    after_success_target: str = "processed"
    after_failure_action: str = "leave_in_place"
    after_failure_target: str = "failed"
    counts: EmailDropCounts = field(default_factory=EmailDropCounts)
    last_scan_at: str | None = None
    last_consume_run_id: str | None = None
    last_run_status: str | None = None
    health_state: str = "unknown"
    health_error: str | None = None


@dataclass
class EmailDropAttachment:
    filename: str
    content_type: str | None = None
    size: int = 0
    staged_path: str | None = None
    final_path: str | None = None


@dataclass
class EmailDropPacket:
    source_path: str
    artifact_type: str
    subject: str | None = None
    from_address: str | None = None
    to_addresses: list[str] = field(default_factory=list)
    cc_addresses: list[str] = field(default_factory=list)
    bcc_addresses: list[str] = field(default_factory=list)
    date: str | None = None
    message_id: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    links: list[str] = field(default_factory=list)
    attachments: list[EmailDropAttachment] = field(default_factory=list)
    metadata_partial: bool = False
    container_path: str | None = None
    contained_path: str | None = None
    ordinal: int = 0
    status: str = "success"
    error: str | None = None


@dataclass
class EmailDropSkipped:
    source_path: str
    reason: str
    artifact_type: str | None = None
    container_path: str | None = None
    contained_path: str | None = None


@dataclass
class EmailArtifactInfo:
    path: str
    category: str
    artifact_type: str
    supported: bool


@dataclass
class EmailArtifactParseResult:
    source_path: str
    artifact_type: str
    packets: list[EmailDropPacket] = field(default_factory=list)
    skipped: list[EmailDropSkipped] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class EmailDropRunRecord:
    id: str
    source_id: str
    started_at: str
    completed_at: str
    status: str
    artifacts_seen: int = 0
    files_moved: int = 0
    packets_created: int = 0
    archives_seen: int = 0
    degraded_files_seen: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    attachments_seen: int = 0
    links_seen: int = 0
    wiki_update_marked: bool = False
    packets: list[EmailDropPacket] = field(default_factory=list)
    skipped: list[EmailDropSkipped] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    return value
