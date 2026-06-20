from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "project-brain"
    / "capabilities"
    / "skills"
    / "platform-admin"
    / "scripts"
    / "harness_closeout.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("harness_closeout_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_harness_closeout_script_prints_json_report(monkeypatch, tmp_path: Path, capsys) -> None:
    from src.lib.brain_closeout import CloseoutReport

    module = _load_script()
    fake_report = CloseoutReport(
        all_ok=True,
        generated_at="2026-05-25T18:00:00Z",
        sections={
            "tiers": {"items": [{"tier": "global", "brain_id": "augur-core", "root": "/repo/project-brain"}]},
            "harness": {"all_ok": True, "codex": {"ok": True, "missing": []}},
            "parity": {"ok": True, "added": [], "dropped": []},
            "orphan_refs": {"ok": True, "count": 0, "refs": []},
            "memory_round_trip": {"ok": True, "entry_count": 2, "sample_entries": ["one"]},
        },
    )

    monkeypatch.setattr(module, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(module, "get_client_skill_dirs", lambda: {"codex-local": tmp_path / ".codex" / "skills"})
    monkeypatch.setattr(module, "resolve_active_stack", lambda *, cwd=None: object())
    monkeypatch.setattr(module, "enabled_clients_from_dirs", lambda _dirs: ("codex",))
    monkeypatch.setattr(module, "project_tier_skill_names", lambda _stack: {"ai"})
    monkeypatch.setattr(module, "default_memory_targets", lambda _root, _clients: {"codex": tmp_path / "memory.md"})
    monkeypatch.setattr(module, "scan_orphan_references", lambda _roots, _paths: [])
    monkeypatch.setattr(module, "verify_family_closeout", lambda *args, **kwargs: fake_report)

    exit_code = module.main(["--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["all_ok"] is True
    assert payload["sections"]["harness"]["codex"]["ok"] is True


def test_harness_closeout_script_returns_nonzero_when_report_is_red(monkeypatch, tmp_path: Path, capsys) -> None:
    from src.lib.brain_closeout import CloseoutReport

    module = _load_script()
    fake_report = CloseoutReport(
        all_ok=False,
        generated_at="2026-05-25T18:00:00Z",
        sections={
            "tiers": {"items": []},
            "harness": {"all_ok": False, "codex": {"ok": False, "missing": ["ai"]}},
            "parity": {"ok": True, "added": [], "dropped": []},
            "orphan_refs": {"ok": True, "count": 0, "refs": []},
            "memory_round_trip": {"ok": True, "entry_count": 1, "sample_entries": ["one"]},
        },
    )

    monkeypatch.setattr(module, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(module, "get_client_skill_dirs", lambda: {"codex-local": tmp_path / ".codex" / "skills"})
    monkeypatch.setattr(module, "resolve_active_stack", lambda *, cwd=None: object())
    monkeypatch.setattr(module, "enabled_clients_from_dirs", lambda _dirs: ("codex",))
    monkeypatch.setattr(module, "project_tier_skill_names", lambda _stack: {"ai"})
    monkeypatch.setattr(module, "default_memory_targets", lambda _root, _clients: {"codex": tmp_path / "memory.md"})
    monkeypatch.setattr(module, "scan_orphan_references", lambda _roots, _paths: [])
    monkeypatch.setattr(module, "verify_family_closeout", lambda *args, **kwargs: fake_report)

    exit_code = module.main([])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "Harness Layering Closeout" in output
    assert "all_ok: false" in output
    assert "codex: FAIL" in output
