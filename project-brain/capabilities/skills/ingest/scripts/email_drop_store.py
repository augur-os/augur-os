from __future__ import annotations

import json
import re
from dataclasses import fields
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from skills.ingest.scripts.email_drop_models import (
    DEFAULT_EMAIL_DROP_FORMATS,
    EmailDropAttachment,
    EmailDropCounts,
    EmailDropPacket,
    EmailDropRunRecord,
    EmailDropSkipped,
    EmailDropSource,
    to_dict,
)


EMAIL_DROP_COUNT_FIELDS = {field.name for field in fields(EmailDropCounts)}
EMAIL_DROP_ATTACHMENT_FIELDS = {field.name for field in fields(EmailDropAttachment)}


def _counts_from_dict(data: dict[str, Any]) -> EmailDropCounts:
    return EmailDropCounts(
        **{key: value for key, value in data.items() if key in EMAIL_DROP_COUNT_FIELDS}
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "mail-drop"


class EmailDropStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.sources_path = self.root / "email_drop_sources.json"
        self.runs_dir = self.root / "email_drop_runs"

    def list_sources(self) -> list[EmailDropSource]:
        data = self._read_json(self.sources_path, [])
        return [self._source_from_dict(item) for item in data]

    def add_source(
        self,
        name: str,
        path: Path | str,
        *,
        formats: list[str] | None = None,
    ) -> EmailDropSource:
        sources = self.list_sources()
        source = EmailDropSource(
            id=self._unique_source_id(_slug(name), sources),
            name=name,
            path=str(path),
            formats=list(formats or DEFAULT_EMAIL_DROP_FORMATS),
        )
        sources.append(source)
        self._write_json(self.sources_path, [to_dict(item) for item in sources])
        return source

    def get_source(self, source_id: str) -> EmailDropSource:
        for source in self.list_sources():
            if source.id == source_id:
                return source
        raise KeyError(f"Email drop source not found: {source_id}")

    def update_source_counts(
        self,
        source_id: str,
        counts: EmailDropCounts | dict[str, int],
    ) -> EmailDropSource:
        source_counts = (
            counts
            if isinstance(counts, EmailDropCounts)
            else _counts_from_dict(counts)
        )
        sources = self.list_sources()
        updated: EmailDropSource | None = None
        for source in sources:
            if source.id == source_id:
                source.counts = source_counts
                updated = source
                break
        if updated is None:
            raise KeyError(f"Email drop source not found: {source_id}")
        self._write_json(self.sources_path, [to_dict(item) for item in sources])
        return updated

    def update_source_state(
        self,
        source_id: str,
        *,
        counts: EmailDropCounts | dict[str, int] | None = None,
        last_scan_at: str | None = None,
        last_consume_run_id: str | None = None,
        last_run_status: str | None = None,
        health_state: str | None = None,
        health_error: str | None = None,
    ) -> EmailDropSource:
        source_counts = (
            counts
            if isinstance(counts, EmailDropCounts) or counts is None
            else _counts_from_dict(counts)
        )
        sources = self.list_sources()
        updated: EmailDropSource | None = None
        for source in sources:
            if source.id != source_id:
                continue
            if source_counts is not None:
                source.counts = source_counts
            if last_scan_at is not None:
                source.last_scan_at = last_scan_at
            if last_consume_run_id is not None:
                source.last_consume_run_id = last_consume_run_id
            if last_run_status is not None:
                source.last_run_status = last_run_status
            if health_state is not None:
                source.health_state = health_state
            source.health_error = health_error
            updated = source
            break
        if updated is None:
            raise KeyError(f"Email drop source not found: {source_id}")
        self._write_json(self.sources_path, [to_dict(item) for item in sources])
        return updated

    def save_run(self, record: EmailDropRunRecord) -> EmailDropRunRecord:
        self._write_json(self._run_path(record.id), to_dict(record))
        return record

    def list_runs(
        self,
        source_id: str | None = None,
        *,
        limit: int | None = None,
    ) -> list[EmailDropRunRecord]:
        if not self.runs_dir.exists():
            return []
        runs = []
        for path in self.runs_dir.glob("*.json"):
            try:
                runs.append(self._run_from_dict(self._read_json(path, {})))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
        if source_id is not None:
            runs = [run for run in runs if run.source_id == source_id]
        runs = sorted(runs, key=lambda run: run.started_at, reverse=True)
        if limit is not None:
            return runs[: max(0, limit)]
        return runs

    def get_run(self, run_id: str) -> EmailDropRunRecord:
        path = self._run_path(run_id)
        if not path.exists():
            raise KeyError(f"Email drop run not found: {run_id}")
        try:
            return self._run_from_dict(self._read_json(path, {}))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Corrupt email drop run record: {run_id}") from exc

    def _unique_source_id(
        self,
        base_id: str,
        sources: list[EmailDropSource],
    ) -> str:
        existing_ids = {source.id for source in sources}
        if base_id not in existing_ids:
            return base_id
        suffix = 2
        while f"{base_id}-{suffix}" in existing_ids:
            suffix += 1
        return f"{base_id}-{suffix}"

    def _run_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{self._run_filename_stem(run_id)}.json"

    def _run_filename_stem(self, run_id: str) -> str:
        return sha256(run_id.encode("utf-8")).hexdigest()

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temp_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_path.replace(path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _source_from_dict(self, data: dict[str, Any]) -> EmailDropSource:
        counts = data.get("counts", {})
        return EmailDropSource(
            id=data["id"],
            name=data["name"],
            path=data["path"],
            type=data.get("type", "email_drop_folder"),
            enabled=data.get("enabled", True),
            formats=list(data.get("formats", DEFAULT_EMAIL_DROP_FORMATS)),
            batch_limit=data.get("batch_limit", 5),
            batch_order=data.get("batch_order", "newest_first"),
            after_success_action=data.get("after_success_action", "move_file"),
            after_success_target=data.get("after_success_target", "processed"),
            after_failure_action=data.get("after_failure_action", "leave_in_place"),
            after_failure_target=data.get("after_failure_target", "failed"),
            counts=(
                counts
                if isinstance(counts, EmailDropCounts)
                else _counts_from_dict(counts)
            ),
            last_scan_at=data.get("last_scan_at"),
            last_consume_run_id=data.get("last_consume_run_id"),
            last_run_status=data.get("last_run_status"),
            health_state=data.get("health_state", "unknown"),
            health_error=data.get("health_error"),
        )

    def _packet_from_dict(self, data: dict[str, Any]) -> EmailDropPacket:
        attachments = [
            item
            if isinstance(item, EmailDropAttachment)
            else EmailDropAttachment(
                **{
                    key: value
                    for key, value in item.items()
                    if key in EMAIL_DROP_ATTACHMENT_FIELDS
                }
            )
            for item in data.get("attachments", [])
        ]
        return EmailDropPacket(
            source_path=data["source_path"],
            artifact_type=data["artifact_type"],
            subject=data.get("subject"),
            from_address=data.get("from_address"),
            to_addresses=list(data.get("to_addresses", [])),
            cc_addresses=list(data.get("cc_addresses", [])),
            bcc_addresses=list(data.get("bcc_addresses", [])),
            date=data.get("date"),
            message_id=data.get("message_id"),
            body_text=data.get("body_text"),
            body_html=data.get("body_html"),
            links=list(data.get("links", [])),
            attachments=attachments,
            metadata_partial=data.get("metadata_partial", False),
            container_path=data.get("container_path"),
            contained_path=data.get("contained_path"),
            ordinal=data.get("ordinal", 0),
            status=data.get("status", "success"),
            error=data.get("error"),
        )

    def _skipped_from_dict(self, data: dict[str, Any]) -> EmailDropSkipped:
        return EmailDropSkipped(
            source_path=data["source_path"],
            reason=data["reason"],
            artifact_type=data.get("artifact_type"),
            container_path=data.get("container_path"),
            contained_path=data.get("contained_path"),
        )

    def _run_from_dict(self, data: dict[str, Any]) -> EmailDropRunRecord:
        packets = [
            item if isinstance(item, EmailDropPacket) else self._packet_from_dict(item)
            for item in data.get("packets", [])
        ]
        skipped = [
            item
            if isinstance(item, EmailDropSkipped)
            else self._skipped_from_dict(item)
            for item in data.get("skipped", [])
        ]
        return EmailDropRunRecord(
            id=data["id"],
            source_id=data["source_id"],
            started_at=data["started_at"],
            completed_at=data["completed_at"],
            status=data["status"],
            artifacts_seen=data.get("artifacts_seen", 0),
            files_moved=data.get("files_moved", 0),
            packets_created=data.get("packets_created", 0),
            archives_seen=data.get("archives_seen", 0),
            degraded_files_seen=data.get("degraded_files_seen", 0),
            files_skipped=data.get("files_skipped", 0),
            files_failed=data.get("files_failed", 0),
            attachments_seen=data.get("attachments_seen", 0),
            links_seen=data.get("links_seen", 0),
            wiki_update_marked=data.get("wiki_update_marked", False),
            packets=packets,
            skipped=skipped,
            errors=list(data.get("errors", [])),
        )
