from __future__ import annotations

import importlib.util
from pathlib import Path


ADAPTERS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wiki_memory_adapters.py"
SPEC = importlib.util.spec_from_file_location("wiki_memory_adapters_under_test", ADAPTERS_PATH)
assert SPEC and SPEC.loader
adapters = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapters)


def test_scan_client_memory_handles_multiple_configured_clients(tmp_path: Path) -> None:
    memory_dir = tmp_path / ".claude" / "projects" / "-Users-test-Project" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    (memory_dir / "feedback_x.md").write_text("# Feedback\n", encoding="utf-8")
    codex_day = tmp_path / ".codex" / "sessions" / "2026" / "05" / "13"
    codex_day.mkdir(parents=True)
    (codex_day / "rollout.jsonl").write_text('{"role": "user"}\n', encoding="utf-8")
    gemini_dir = tmp_path / ".gemini" / "conversations"
    gemini_dir.mkdir(parents=True)
    (gemini_dir / "session.json").write_text("{}", encoding="utf-8")

    sources = adapters.scan_client_memory(
        clients={
            "claude": {
                "path": str(tmp_path / ".claude"),
                "globs": ["projects/*/memory/*.md"],
                "tier": "critical",
            },
            "codex": {
                "path": str(tmp_path / ".codex" / "sessions"),
                "tier": "critical",
            },
            "gemini": {
                "path": str(gemini_dir),
                "tier": "high",
            },
            "missing": {
                "path": str(tmp_path / "missing"),
                "tier": "high",
            },
        }
    )

    by_name = {Path(source["path"]).name: source for source in sources}
    assert sorted(by_name) == ["MEMORY.md", "feedback_x.md", "rollout.jsonl", "session.json"]
    assert all(source["source_surface"] == "client_memory" for source in sources)
    assert by_name["MEMORY.md"]["client"] == "claude"
    assert by_name["rollout.jsonl"]["client"] == "codex"
    assert by_name["session.json"]["client"] == "gemini"
    assert by_name["MEMORY.md"]["tier"] == "critical"
    assert by_name["rollout.jsonl"]["weight"] == 3.0
    assert by_name["session.json"]["tier"] == "high"


def test_scan_codex_threads_respects_session_tree_and_disabled_flag(tmp_path: Path) -> None:
    threads_dir = tmp_path / "sessions"
    session_day = threads_dir / "2026" / "05" / "13"
    session_day.mkdir(parents=True)
    (session_day / "rollout.jsonl").write_text('{"role": "user"}\n', encoding="utf-8")
    (threads_dir / "thread2.md").write_text("# Thread 2\n", encoding="utf-8")

    sources = adapters.scan_codex_threads(threads_dir=threads_dir)

    assert len(sources) == 2
    assert sorted(Path(source["path"]).name for source in sources) == ["rollout.jsonl", "thread2.md"]
    assert all(source["source_surface"] == "codex_threads" for source in sources)
    assert all(source["tier"] == "critical" for source in sources)
    assert adapters.scan_codex_threads(threads_dir=threads_dir, enabled=False) == []


def test_scan_gemini_copilot_and_external_clients(tmp_path: Path) -> None:
    gemini_dir = tmp_path / "gemini"
    copilot_dir = tmp_path / "copilot"
    chatgpt_dir = tmp_path / "chatgpt"
    for directory in (gemini_dir, copilot_dir, chatgpt_dir):
        directory.mkdir()
    (gemini_dir / "session.json").write_text("{}", encoding="utf-8")
    (copilot_dir / "log.md").write_text("# Copilot\n", encoding="utf-8")
    (chatgpt_dir / "export.md").write_text("# ChatGPT\n", encoding="utf-8")

    gemini = adapters.scan_gemini(path=gemini_dir)
    copilot = adapters.scan_copilot(path=copilot_dir)
    external = adapters.scan_external_clients(
        allowlist={
            "chatgpt": {"path": str(chatgpt_dir), "tier": "high"},
            "missing": {"path": str(tmp_path / "missing"), "tier": "high"},
        }
    )

    assert gemini[0]["source_surface"] == "gemini"
    assert gemini[0]["tier"] == "high"
    assert copilot[0]["source_surface"] == "copilot"
    assert copilot[0]["tier"] == "high"
    assert external[0]["source_surface"] == "external_client"
    assert external[0]["client"] == "chatgpt"
    assert external[0]["tier"] == "high"


def test_scan_episodic_via_loader() -> None:
    records = [
        {"id": "abc", "title": "Past convo", "ts": "2026-05-01T10:00:00Z"},
        {"id": "def", "title": "Other convo", "ts": "2026-05-09T10:00:00Z"},
    ]

    sources = adapters.scan_episodic(loader=lambda: records)

    assert [source["path"] for source in sources] == ["episodic://abc", "episodic://def"]
    assert all(source["source_surface"] == "episodic" for source in sources)
    assert all(source["tier"] == "critical" for source in sources)
    assert adapters.scan_episodic(loader=None) == []
