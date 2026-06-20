from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    path: Path
    content_type: str = "application/octet-stream"


@dataclass(frozen=True)
class EmailMessage:
    message_id: str
    subject: str
    sender: str
    received_at: str
    body: str = ""
    body_html: str = ""
    recipients: list[str] = field(default_factory=list)
    attachments: list[EmailAttachment] = field(default_factory=list)


class EmailAdapter(Protocol):
    def list_messages(self, *, mailbox: str, limit: int = 5) -> list[EmailMessage]:
        ...


class StaticEmailAdapter:
    def __init__(self, messages: list[EmailMessage]) -> None:
        self._messages = messages

    def list_messages(self, *, mailbox: str, limit: int = 5) -> list[EmailMessage]:
        del mailbox
        return self._messages[:limit]
