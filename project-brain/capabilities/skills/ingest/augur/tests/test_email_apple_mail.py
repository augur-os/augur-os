from __future__ import annotations

import json
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

from skills.ingest.scripts.email_apple_mail import parse_apple_mail_json


def test_parse_apple_mail_json() -> None:
    payload = json.dumps(
        [
            {
                "id": "m1",
                "subject": "Investor Demo",
                "sender": "founder@example.com",
                "receivedAt": "2026-05-29T10:00:00",
                "body": "Deck attached",
                "attachments": [],
            }
        ]
    )

    messages = parse_apple_mail_json(payload)

    assert messages[0].message_id == "m1"
    assert messages[0].subject == "Investor Demo"
