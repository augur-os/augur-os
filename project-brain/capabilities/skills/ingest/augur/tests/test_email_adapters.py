from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = next(
    (
        p
        for p in Path(__file__).resolve().parents
        if (p / "pyproject.toml").exists() and (p / ".git").exists()
    ),
    Path(__file__).resolve().parents[-1],
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.ingest.scripts.email_adapters import EmailAdapter, EmailMessage, StaticEmailAdapter


def test_static_email_adapter_lists_messages() -> None:
    message = EmailMessage(
        message_id="1",
        subject="Demo",
        sender="a@example.com",
        received_at="2026-05-29T10:00:00",
        body="Body",
        attachments=[],
    )
    adapter: EmailAdapter = StaticEmailAdapter([message])
    assert adapter.list_messages(mailbox="Augur") == [message]
