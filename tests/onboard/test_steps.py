import subprocess
from pathlib import Path

import src.lib.onboard.steps as s
from src.lib.onboard.result import OnboardContext


class _FakeRun:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, cwd=None, **kw):
        self.calls.append((cmd, cwd))
        return subprocess.CompletedProcess(cmd, 0, "", "")


def test_sync_deps_runs_pnpm_and_uv(monkeypatch, tmp_path: Path):
    fake = _FakeRun()
    monkeypatch.setattr(s.subprocess, "run", fake)
    r = s.sync_deps(OnboardContext(repo_root=tmp_path))
    assert r.status == "ok"
    joined = [" ".join(c[0]) for c in fake.calls]
    assert any("pnpm install" in j for j in joined)
    assert any("uv sync" in j for j in joined)


def test_sync_deps_fails_on_nonzero(monkeypatch, tmp_path: Path):
    def boom(cmd, cwd=None, **kw):
        return subprocess.CompletedProcess(cmd, 1, "", "pnpm exploded")

    monkeypatch.setattr(s.subprocess, "run", boom)
    r = s.sync_deps(OnboardContext(repo_root=tmp_path))
    assert r.status == "fail"
    assert "pnpm exploded" in r.message


def test_build_dashboard_uses_aug_dev_build(monkeypatch, tmp_path: Path):
    fake = _FakeRun()
    monkeypatch.setattr(s.subprocess, "run", fake)
    r = s.build_dashboard(OnboardContext(repo_root=tmp_path))
    assert r.status == "ok"
    assert any("aug" in c[0] and "dev" in c[0] and "build" in c[0] for c in fake.calls)


def test_wire_mcp_uses_aug_config_sync(monkeypatch, tmp_path: Path):
    fake = _FakeRun()
    monkeypatch.setattr(s.subprocess, "run", fake)
    r = s.wire_mcp(OnboardContext(repo_root=tmp_path))
    assert r.status == "ok"
    assert any("config" in c[0] and "sync" in c[0] for c in fake.calls)


def test_seed_creates_vault_scaffold_when_absent(monkeypatch, tmp_path: Path):
    vault = tmp_path / "vault"
    fake = _FakeRun()
    monkeypatch.setattr(s.subprocess, "run", fake)
    r = s.seed_brain_and_vault(OnboardContext(repo_root=tmp_path), vault_dir=vault)
    assert r.status == "ok"
    assert vault.is_dir()  # scaffold created
    assert any("init" in c[0] for c in fake.calls)  # aug init invoked


def test_seed_is_idempotent_when_vault_exists(monkeypatch, tmp_path: Path):
    # Fully-present vault (scaffold complete) plus user content -> no-op skip.
    vault = tmp_path / "vault"
    (vault / "inbox").mkdir(parents=True)
    (vault / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    (vault / "keep.md").write_text("user content", encoding="utf-8")
    fake = _FakeRun()
    monkeypatch.setattr(s.subprocess, "run", fake)
    r = s.seed_brain_and_vault(OnboardContext(repo_root=tmp_path), vault_dir=vault)
    assert r.status == "ok"
    assert (vault / "keep.md").read_text() == "user content"  # untouched
    assert "exists" in r.message.lower() or "skip" in r.message.lower()


def test_seed_self_heals_partial_vault(monkeypatch, tmp_path: Path):
    # Vault dir exists but the scaffold is incomplete (MEMORY.md missing).
    vault = tmp_path / "vault"
    vault.mkdir()
    fake = _FakeRun()
    monkeypatch.setattr(s.subprocess, "run", fake)
    r = s.seed_brain_and_vault(OnboardContext(repo_root=tmp_path), vault_dir=vault)
    assert r.status == "ok"
    assert (vault / "inbox").is_dir()  # healed
    assert (vault / "MEMORY.md").read_text() == "# Memory\n"  # healed


def test_seed_does_not_overwrite_existing_memory(monkeypatch, tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "inbox").mkdir(parents=True)
    (vault / "MEMORY.md").write_text("user memory content", encoding="utf-8")
    fake = _FakeRun()
    monkeypatch.setattr(s.subprocess, "run", fake)
    r = s.seed_brain_and_vault(OnboardContext(repo_root=tmp_path), vault_dir=vault)
    assert r.status == "ok"
    assert (vault / "MEMORY.md").read_text() == "user memory content"  # untouched
    assert "exists" in r.message.lower() or "skip" in r.message.lower()
