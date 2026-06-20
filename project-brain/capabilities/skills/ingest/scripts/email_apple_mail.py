from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Callable


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

from skills.ingest.scripts.email_adapters import EmailAttachment, EmailMessage


Runner = Callable[[str], str]


class AppleMailAdapter:
    def __init__(self, *, runner: Runner | None = None) -> None:
        self._runner = runner or _run_osascript

    def list_messages(self, *, mailbox: str, limit: int = 5) -> list[EmailMessage]:
        script = _list_messages_script(mailbox=mailbox, limit=limit)
        return parse_apple_mail_json(self._runner(script))


def parse_apple_mail_json(payload: str) -> list[EmailMessage]:
    data = json.loads(payload or "[]")
    if not isinstance(data, list):
        raise ValueError("Apple Mail returned non-list JSON")
    return [_message_from_dict(item) for item in data if isinstance(item, dict)]


def message_to_dict(message: EmailMessage) -> dict[str, object]:
    return {
        "message_id": message.message_id,
        "subject": message.subject,
        "sender": message.sender,
        "received_at": message.received_at,
        "body": message.body,
        "body_html": message.body_html,
        "recipients": message.recipients,
        "attachments": [
            {
                "filename": attachment.filename,
                "path": str(attachment.path),
                "content_type": attachment.content_type,
            }
            for attachment in message.attachments
        ],
    }


def _run_osascript(script: str) -> str:
    osascript = shutil.which("osascript")
    if not osascript:
        raise FileNotFoundError("Required executable not found in PATH: osascript")
    result = subprocess.run(
        [osascript, "-l", "JavaScript", "-e", script],
        capture_output=True,
        text=True,
        timeout=45,
        check=True,
    )  # nosec B603
    return result.stdout.strip()


def _list_messages_script(*, mailbox: str, limit: int) -> str:
    mailbox_json = json.dumps(mailbox or "inbox")
    limit = max(1, int(limit or 5))
    return f"""
const Mail = Application('Mail');
Mail.includeStandardAdditions = true;
const requestedMailbox = {mailbox_json};
const limit = {limit};

function lower(value) {{
  return String(value || '').toLowerCase();
}}

function isoDate(value) {{
  try {{
    return new Date(value).toISOString();
  }} catch (error) {{
    return String(value || '');
  }}
}}

function chooseMessages() {{
  if (lower(requestedMailbox) === 'inbox') {{
    return Mail.inbox.messages();
  }}
  const mailboxes = Mail.mailboxes.whose({{ name: requestedMailbox }})();
  if (mailboxes.length === 0) {{
    return [];
  }}
  return mailboxes[0].messages();
}}

const messages = chooseMessages();
const output = [];
for (let index = 0; index < messages.length && output.length < limit; index += 1) {{
  const message = messages[index];
  output.push({{
    id: String(message.messageId() || message.id()),
    subject: String(message.subject() || ''),
    sender: String(message.sender() || ''),
    receivedAt: isoDate(message.dateReceived()),
    body: String(message.content() || ''),
    attachments: [],
  }});
}}
JSON.stringify(output);
"""


def _message_from_dict(data: dict[str, object]) -> EmailMessage:
    raw_attachments = data.get("attachments", [])
    attachments = raw_attachments if isinstance(raw_attachments, list) else []
    return EmailMessage(
        message_id=str(data.get("message_id") or data.get("id") or ""),
        subject=str(data.get("subject") or ""),
        sender=str(data.get("sender") or ""),
        received_at=str(data.get("received_at") or data.get("receivedAt") or ""),
        body=str(data.get("body") or data.get("body_text") or ""),
        body_html=str(data.get("body_html") or ""),
        recipients=[
            str(item)
            for item in data.get("recipients", [])
            if isinstance(data.get("recipients"), list) and item
        ],
        attachments=[
            EmailAttachment(
                filename=str(
                    item.get("filename") or Path(str(item.get("path") or "")).name
                ),
                path=Path(str(item.get("path") or "")),
                content_type=str(item.get("content_type") or "application/octet-stream"),
            )
            for item in attachments
            if isinstance(item, dict)
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mailbox", default="inbox")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    messages = AppleMailAdapter().list_messages(mailbox=args.mailbox, limit=args.limit)
    if args.json:
        print(json.dumps([message_to_dict(message) for message in messages], indent=2))
    else:
        for message in messages:
            print(f"{message.received_at}\t{message.sender}\t{message.subject}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
