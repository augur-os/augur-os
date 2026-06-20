from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.lib.ingest.inbox_models import (
    InboxFileResult,
    InboxFolder,
    InboxFolderCounts,
    InboxInsight,
    InboxRunRecord,
    to_dict,
)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "folder"


class InboxStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.folders_path = self.root / "folders.json"
        self.runs_dir = self.root / "runs"

    def list_folders(self) -> list[InboxFolder]:
        data = self._read_json(self.folders_path, [])
        return [self._folder_from_dict(item) for item in data]

    def add_folder(self, name: str, path: Path | str) -> InboxFolder:
        folders = self.list_folders()
        folder = InboxFolder(
            id=self._unique_folder_id(_slug(name), folders),
            name=name,
            path=str(Path(path).expanduser().resolve(strict=False)),
        )
        folders.append(folder)
        self._write_json(self.folders_path, [to_dict(item) for item in folders])
        return folder

    def get_folder(self, folder_id: str) -> InboxFolder:
        for folder in self.list_folders():
            if folder.id == folder_id:
                return folder
        raise KeyError(f"Folder not found: {folder_id}")

    def update_folder_counts(
        self,
        folder_id: str,
        counts: InboxFolderCounts | dict[str, int],
    ) -> InboxFolder:
        folder_counts = counts if isinstance(counts, InboxFolderCounts) else InboxFolderCounts(**counts)
        folders = self.list_folders()
        updated: InboxFolder | None = None
        for folder in folders:
            if folder.id == folder_id:
                folder.counts = folder_counts
                updated = folder
                break
        if updated is None:
            raise KeyError(f"Folder not found: {folder_id}")
        self._write_json(self.folders_path, [to_dict(item) for item in folders])
        return updated

    def update_folder_state(
        self,
        folder_id: str,
        *,
        counts: InboxFolderCounts | dict[str, int] | None = None,
        last_scan_at: str | None = None,
        last_run_status: str | None = None,
    ) -> InboxFolder:
        folder_counts = (
            counts if isinstance(counts, InboxFolderCounts) or counts is None else InboxFolderCounts(**counts)
        )
        folders = self.list_folders()
        updated: InboxFolder | None = None
        for folder in folders:
            if folder.id != folder_id:
                continue
            if folder_counts is not None:
                folder.counts = folder_counts
            if last_scan_at is not None:
                folder.last_scan_at = last_scan_at
            if last_run_status is not None:
                folder.last_run_status = last_run_status
            updated = folder
            break
        if updated is None:
            raise KeyError(f"Folder not found: {folder_id}")
        self._write_json(self.folders_path, [to_dict(item) for item in folders])
        return updated

    def save_run(self, record: InboxRunRecord) -> InboxRunRecord:
        self._write_json(self._run_path(record.id), to_dict(record))
        return record

    def list_runs(
        self,
        folder_id: str | None = None,
        *,
        limit: int | None = None,
    ) -> list[InboxRunRecord]:
        if not self.runs_dir.exists():
            return []
        runs = []
        for path in self.runs_dir.glob("*.json"):
            try:
                runs.append(self._run_from_dict(self._read_json(path, {})))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
        if folder_id is not None:
            runs = [run for run in runs if run.folder_id == folder_id]
        runs = sorted(runs, key=lambda run: run.started_at, reverse=True)
        if limit is not None:
            return runs[: max(0, limit)]
        return runs

    def list_run_payloads(
        self,
        folder_id: str | None = None,
        *,
        limit: int | None = None,
        file_results_limit: int | None = None,
        include_file_results: bool = True,
    ) -> list[dict[str, Any]]:
        if not self.runs_dir.exists():
            return []
        candidates: list[tuple[str, Path]] = []
        for path in self.runs_dir.glob("*.json"):
            try:
                data = self._read_json(path, {})
                started_at = str(data["started_at"])
                run_folder_id = data["folder_id"]
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            if folder_id is not None and run_folder_id != folder_id:
                continue
            candidates.append((started_at, path))

        candidates.sort(key=lambda item: item[0], reverse=True)
        if limit is not None:
            candidates = candidates[: max(0, limit)]

        payloads: list[dict[str, Any]] = []
        for _, path in candidates:
            try:
                payload = self._read_json(path, {})
                if not include_file_results:
                    payload.pop("file_results", None)
                elif file_results_limit is not None:
                    payload["file_results"] = payload.get("file_results", [])[: max(0, file_results_limit)]
                normalized = to_dict(self._run_from_dict(payload))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            if not include_file_results:
                normalized.pop("file_results", None)
            payloads.append(normalized)
        return payloads

    def get_run(self, run_id: str) -> InboxRunRecord:
        path = self._run_path(run_id)
        if not path.exists():
            raise KeyError(f"Run not found: {run_id}")
        try:
            return self._run_from_dict(self._read_json(path, {}))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Corrupt inbox run record: {run_id}") from exc

    def _unique_folder_id(self, base_id: str, folders: list[InboxFolder]) -> str:
        existing_ids = {folder.id for folder in folders}
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

    def _folder_from_dict(self, data: dict[str, Any]) -> InboxFolder:
        counts = data.get("counts", {})
        return InboxFolder(
            id=data["id"],
            name=data["name"],
            path=data["path"],
            enabled=data.get("enabled", True),
            counts=(counts if isinstance(counts, InboxFolderCounts) else InboxFolderCounts(**counts)),
            last_scan_at=data.get("last_scan_at"),
            last_run_status=data.get("last_run_status"),
        )

    def _run_from_dict(self, data: dict[str, Any]) -> InboxRunRecord:
        file_results = []
        for item in data.get("file_results", []):
            if isinstance(item, InboxFileResult):
                file_results.append(item)
            else:
                item.setdefault("extracted_path", None)
                item.setdefault("escalation_reason", None)
                item.setdefault("cloud_provider", None)
                item.setdefault("cloud_model", None)
                item.setdefault("content_hash", None)
                file_results.append(InboxFileResult(**item))
        insights = [
            item if isinstance(item, InboxInsight) else InboxInsight(**item) for item in data.get("insights", [])
        ]
        return InboxRunRecord(
            id=data["id"],
            folder_id=data["folder_id"],
            started_at=data["started_at"],
            completed_at=data["completed_at"],
            status=data["status"],
            airplane_mode=data["airplane_mode"],
            files_seen=data.get("files_seen", 0),
            files_moved=data.get("files_moved", 0),
            files_indexed=data.get("files_indexed", 0),
            files_skipped=data.get("files_skipped", 0),
            files_failed=data.get("files_failed", 0),
            files_needing_review=data.get("files_needing_review", 0),
            cloud_calls=data.get("cloud_calls", 0),
            local_agent_calls=data.get("local_agent_calls", 0),
            wiki_update_marked=data.get("wiki_update_marked", False),
            file_results=file_results,
            insights=insights,
        )
