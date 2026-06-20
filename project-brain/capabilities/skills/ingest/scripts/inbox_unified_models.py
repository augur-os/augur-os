from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Literal


InboxFailureState = Literal[
    "pending_content",
    "needs_target",
    "needs_route",
    "needs_version_choice",
    "blocked_permission",
    "failed_extract",
    "failed_index",
]


@dataclass(frozen=True)
class InboxVaultTarget:
    id: str
    kind: str
    name: str
    vault_root: str
    docs_root: str
    default: bool = False
    writable: bool = True


@dataclass(frozen=True)
class InboxVaultCandidate:
    candidate_id: str
    kind: str
    name: str
    vault_root: str
    docs_root: str
    reason: str
    status: str = "unapproved"
    writable: bool = False


@dataclass(frozen=True)
class InboxSourceLane:
    id: str
    type: str
    name: str
    domain: str
    drop_root: str
    write_modes: list[str] = field(default_factory=list)
    default_target_vault: str = "personal"
    allowed_targets: list[str] = field(default_factory=lambda: ["personal"])
    enabled: bool = True
    health_state: str = "ready"
    health_error: str = ""


@dataclass(frozen=True)
class InboxPacket:
    packet_id: str
    source_id: str
    source_type: str
    capture_mode: str
    packet_dir: str
    title: str
    status: str
    target_vault: str = ""
    target_domain: str = "docs"
    original_filename: str = ""
    content_type: str = ""
    content_hash: str = ""
    conversation_hint: str = ""
    user_instruction: str = ""
    created_at: str = ""
    payload_paths: list[str] = field(default_factory=list)
    failure_state: InboxFailureState | None = None


@dataclass(frozen=True)
class InboxArchiveMove:
    relative_path: str
    reason: str
    artifact_group: str
    status: str = "planned"
    refusal_category: str = ""


@dataclass(frozen=True)
class InboxArchivePlan:
    auto_archive: list[InboxArchiveMove] = field(default_factory=list)
    ask: list[InboxArchiveMove] = field(default_factory=list)
    refused: list[InboxArchiveMove] = field(default_factory=list)


@dataclass(frozen=True)
class InboxRouteProposal:
    packet_id: str
    target_vault: str
    target_domain: str
    target_folder: str
    final_filename: str
    route_reason: str
    version_group: str
    status: str
    failure_state: InboxFailureState | None = None
    questions: list[str] = field(default_factory=list)
    archive_plan: InboxArchivePlan = field(default_factory=InboxArchivePlan)


@dataclass(frozen=True)
class InboxConsumeResult:
    packet_id: str
    status: str
    final_paths: list[str] = field(default_factory=list)
    sidecar_paths: list[str] = field(default_factory=list)
    archived_paths: list[str] = field(default_factory=list)
    refused_paths: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    index_refreshed: bool = False
    failure_state: InboxFailureState | None = None


@dataclass(frozen=True)
class UnifiedInboxRegistry:
    config_root: Path
    sources: list[InboxSourceLane]
    vaults: list[InboxVaultTarget]
    candidates: list[InboxVaultCandidate] = field(default_factory=list)

    def source_by_id(self, source_id: str) -> InboxSourceLane:
        for source in self.sources:
            if source.id == source_id:
                return source
        available = ", ".join(source.id for source in self.sources) or "none"
        raise KeyError(f"Inbox source lane not found: {source_id}. Available: {available}")

    def vault_by_id(self, vault_id: str) -> InboxVaultTarget:
        for vault in self.vaults:
            if vault.id == vault_id:
                return vault
        available = ", ".join(vault.id for vault in self.vaults) or "none"
        raise KeyError(f"Inbox vault target not found: {vault_id}. Available: {available}")


def to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    return value
