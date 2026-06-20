from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = next(
    (
        path
        for path in Path(__file__).resolve().parents
        if (path / "pyproject.toml").exists() and (path / ".git").exists()
    ),
    Path(__file__).resolve().parents[-1],
)
CAPABILITIES_ROOT = PROJECT_ROOT / "project-brain" / "capabilities"
if str(CAPABILITIES_ROOT) not in sys.path:
    sys.path.insert(0, str(CAPABILITIES_ROOT))

from skills.ingest.scripts.email_adapters import EmailAdapter


def collect_email_packets(
    adapter: EmailAdapter,
    *,
    mailbox: str,
    limit: int = 5,
) -> list[dict[str, object]]:
    packets: list[dict[str, object]] = []
    for message in adapter.list_messages(mailbox=mailbox, limit=limit):
        packets.append(
            {
                "kind": "email",
                "source": "apple_mail",
                "source_id": message.message_id,
                "title": message.subject,
                "sender": message.sender,
                "received_at": message.received_at,
                "body": message.body,
                "attachments": [
                    {
                        "filename": attachment.filename,
                        "path": str(attachment.path),
                        "content_type": attachment.content_type,
                    }
                    for attachment in message.attachments
                ],
            }
        )
    return packets
