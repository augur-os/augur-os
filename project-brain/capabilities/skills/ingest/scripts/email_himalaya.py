from __future__ import annotations

import json
import subprocess  # nosec B404
from collections.abc import Mapping
from typing import Any

from skills.ingest.scripts.email_adapters import EmailMessage


def _sender_from(raw: Mapping[str, Any]) -> str:
    sender = raw.get("sender") or raw.get("from") or ""
    if isinstance(sender, Mapping):
        return str(
            sender.get("addr") or sender.get("address") or sender.get("name") or ""
        )
    return str(sender)


def parse_himalaya_envelope(raw_output: bytes) -> list[EmailMessage]:
    data = json.loads(raw_output.decode("utf-8") or "[]")
    if not isinstance(data, list):
        return []

    messages: list[EmailMessage] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        raw_message_id = item.get("id", item.get("message_id"))
        message_id = str(raw_message_id) if raw_message_id is not None else ""
        if not message_id:
            continue

        messages.append(
            EmailMessage(
                message_id=message_id,
                subject=str(item.get("subject") or ""),
                sender=_sender_from(item),
                received_at=str(item.get("received_at") or item.get("date") or ""),
            )
        )
    return messages


class HimalayaEmailAdapter:
    def __init__(self, *, binary: str = "himalaya", timeout_seconds: float = 45) -> None:
        self.binary = binary
        self.timeout_seconds = timeout_seconds

    def list_messages(self, *, mailbox: str, limit: int = 5) -> list[EmailMessage]:
        result = subprocess.run(
            [
                self.binary,
                "envelope",
                "list",
                "--folder",
                mailbox,
                "--page-size",
                str(limit),
                "--output",
                "json",
            ],
            check=True,
            capture_output=True,
            timeout=self.timeout_seconds,
        )  # nosec B603
        return parse_himalaya_envelope(result.stdout)
