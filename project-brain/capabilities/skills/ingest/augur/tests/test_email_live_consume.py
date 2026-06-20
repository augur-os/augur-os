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

from skills.ingest.scripts.email_adapters import EmailMessage, StaticEmailAdapter
from skills.ingest.scripts.email_live_consume import collect_email_packets


def test_collect_email_packets_from_adapter() -> None:
    adapter = StaticEmailAdapter(
        [
            EmailMessage(
                message_id="m1",
                subject="Deck",
                sender="founder@example.com",
                received_at="2026-05-29T10:00:00",
                body="Updated deck",
                attachments=[],
            )
        ]
    )

    packets = collect_email_packets(adapter, mailbox="Augur")

    assert packets[0]["source_id"] == "m1"
    assert packets[0]["title"] == "Deck"
    assert packets[0]["kind"] == "email"
