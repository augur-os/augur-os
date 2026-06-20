from __future__ import annotations

import importlib
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

mod = importlib.import_module("skills.ingest.scripts.email_himalaya")
HimalayaEmailAdapter = mod.HimalayaEmailAdapter
parse_himalaya_envelope = mod.parse_himalaya_envelope


def test_parse_himalaya_envelope_json() -> None:
    messages = parse_himalaya_envelope(
        b"""[
          {"id": 7, "subject": "Demo", "from": {"addr": "a@example.com"}, "date": "2026-05-29T09:00:00Z"},
          {"id": "8", "subject": "Followup", "sender": "b@example.com", "received_at": "2026-05-29T10:00:00Z"}
        ]"""
    )

    assert [message.message_id for message in messages] == ["7", "8"]
    assert messages[0].subject == "Demo"
    assert messages[0].sender == "a@example.com"


def test_adapter_builds_bounded_json_command(monkeypatch) -> None:
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))

        class Result:
            stdout = b"[]"

        return Result()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    adapter = HimalayaEmailAdapter(binary="himalaya")
    assert adapter.list_messages(mailbox="INBOX", limit=3) == []

    assert calls == [
        (
            [
                "himalaya",
                "envelope",
                "list",
                "--folder",
                "INBOX",
                "--page-size",
                "3",
                "--output",
                "json",
            ],
            {"check": True, "capture_output": True, "timeout": 45},
        )
    ]
