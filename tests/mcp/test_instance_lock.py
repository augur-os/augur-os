"""Tests for MCP instance lock client-id resolution."""

from __future__ import annotations

from src.mcp.augur_shared import instance_lock  # noqa: E402


def test_resolve_lock_client_id_codex_uses_thread_id(monkeypatch):
    monkeypatch.setenv("CODEX_THREAD_ID", "019cba07-53c9-7152-97e9-c7e4d921e8c4")
    lock_id = instance_lock._resolve_lock_client_id(client_id="codex", transport="stdio", port=None)
    assert lock_id == "codex-019cba07-53c9-7152-97e9-c7e4d921e8c4"


def test_resolve_lock_client_id_codex_falls_back_to_process_pid(monkeypatch):
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setattr(instance_lock.os, "getpid", lambda: 54321)
    lock_id = instance_lock._resolve_lock_client_id(client_id="codex", transport="stdio", port=None)
    assert lock_id == "codex-pid54321"


def test_resolve_lock_client_id_non_stdio_passthrough():
    lock_id = instance_lock._resolve_lock_client_id(client_id="codex", transport="sse", port=None)
    assert lock_id == "codex"


def test_resolve_lock_client_id_auto_detect(monkeypatch):
    monkeypatch.setattr(instance_lock, "_detect_client_id", lambda: "cursor-123")
    lock_id = instance_lock._resolve_lock_client_id(client_id=None, transport="stdio", port=None)
    assert lock_id == "cursor-123"
