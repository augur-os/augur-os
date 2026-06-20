"""Tests for auto-test-webmcp scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "webmcp_ops.py"
_SPEC = importlib.util.spec_from_file_location("webmcp_ops_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-test-webmcp"


def test_d0_flags_missing_core_files(tmp_path: Path) -> None:
    """d0 flags when WebMCP core files are missing."""
    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert isinstance(result, ScanResult)
    missing_files = [i for i in result.issues if "Missing:" in i.get("detail", "")]
    assert len(missing_files) > 0


def test_d0_checks_block_registry(tmp_path: Path) -> None:
    """d0 checks the block registry exists and has entries."""
    # Create all required files so only registry is checked
    for f in [
        "apps/dashboard/lib/webmcp/types.ts",
        "apps/dashboard/lib/webmcp/polyfill.ts",
        "apps/dashboard/lib/webmcp/state-registry.ts",
        "apps/dashboard/lib/webmcp/WebMCPProvider.tsx",
        "apps/dashboard/lib/webmcp/useWebMCPReport.ts",
        "apps/dashboard/lib/webmcp/tools/errors.ts",
        "apps/dashboard/lib/webmcp/tools/blocks.ts",
        "apps/dashboard/lib/webmcp/tools/pages.ts",
        "apps/dashboard/lib/webmcp/tools/views.ts",
        "apps/dashboard/lib/webmcp/tools/navigation.ts",
        "apps/dashboard/lib/webmcp/tools/catalog.ts",
        "apps/dashboard/lib/webmcp/tools/forms.ts",
        "apps/dashboard/lib/webmcp/tools/agents.ts",
    ]:
        _write(tmp_path / f, "// stub")

    result = mod.scan(_ctx(tmp_path, difficulty=0))
    registry_issues = [i for i in result.issues if "registry" in i.get("detail", "").lower()]
    assert len(registry_issues) >= 1


def test_d1_detects_invalid_dispatch(tmp_path: Path) -> None:
    """d1 flags action YAML with invalid dispatch type."""
    _write(
        tmp_path / "project-brain" / "capabilities" / "skills" / "browse" / "augur" / "actions" / "test.yaml",
        yaml.dump({"id": "test", "dispatch": "invalid_mode"}),
    )
    issues = mod.check_d1_content(tmp_path)
    dispatch_issues = [i for i in issues if "invalid dispatch" in i.get("detail", "")]
    assert len(dispatch_issues) == 1


def test_find_skill_md_for_issue_uses_shared_vault(tmp_path: Path) -> None:
    skill_md = tmp_path / "project-brain" / "capabilities" / "skills" / "browse" / "SKILL.md"
    _write(skill_md, "---\nname: browse\n---\n")

    issue = {"detail": "Page browse:overview is missing WebMCP metadata"}

    assert mod._find_skill_md_for_issue(tmp_path, issue) == skill_md


def test_has_difficulty_spec() -> None:
    assert hasattr(mod, "DIFFICULTY_SPEC")
    assert isinstance(mod.DIFFICULTY_SPEC, dict)
    assert 0 in mod.DIFFICULTY_SPEC


# ── Block-registry regeneration honesty (failed regen must report failure) ──────

_REGISTRY_REL = "apps/dashboard/lib/blocks/generated-block-registry.ts"
_GEN_SCRIPT_REL = "src/scripts/generate_block_registry.py"


def _valid_registry_ts() -> str:
    """A registry with >=10 entries (mirrors d0's `':` entry-count heuristic)."""
    entries = "\n".join(f"  'block-{i}': {{ id: 'block-{i}' }}," for i in range(12))
    return "export const registry = {\n" + entries + "\n};\n"


def _regen_issue() -> dict:
    return {
        "category": "webmcp-registry",
        "detail": "Block registry not generated",
        "path": _REGISTRY_REL,
        "kind": "actionable",
        "root_cause_type": "generated_artifact",
        "fixability": "auto",
    }


def test_regen_reports_failure_when_generator_exits_nonzero(tmp_path: Path, monkeypatch) -> None:
    """Generator exits non-zero → action marked failed, NOT regenerated."""
    _write(tmp_path / _GEN_SCRIPT_REL, "# stub generator that 'fails'")

    class _FakeProc:
        returncode = 1
        stdout = ""
        stderr = "boom: missing node_modules"

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _FakeProc())

    action = mod._regenerate_block_registry(tmp_path)
    assert "regenerated" not in action
    assert action.get("failed") == "block-registry"


def test_regen_reports_failure_when_artifact_still_missing(tmp_path: Path, monkeypatch) -> None:
    """Generator exits 0 but registry file still absent → action marked failed."""
    _write(tmp_path / _GEN_SCRIPT_REL, "# stub generator that writes nothing")

    class _FakeProc:
        returncode = 0
        stdout = "done"
        stderr = ""

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _FakeProc())

    action = mod._regenerate_block_registry(tmp_path)
    assert "regenerated" not in action
    assert action.get("failed") == "block-registry"


def test_regen_reports_success_when_artifact_produced(tmp_path: Path, monkeypatch) -> None:
    """Generator exits 0 AND writes a non-trivial registry → action regenerated."""
    _write(tmp_path / _GEN_SCRIPT_REL, "# stub generator")
    registry_path = tmp_path / _REGISTRY_REL

    class _FakeProc:
        returncode = 0
        stdout = "done"
        stderr = ""

    def _fake_run(*a, **k):
        _write(registry_path, _valid_registry_ts())
        return _FakeProc()

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    action = mod._regenerate_block_registry(tmp_path)
    assert action.get("regenerated") == "block-registry"


def test_fix_reports_failure_when_regen_fails(tmp_path: Path, monkeypatch) -> None:
    """fix() must NOT claim success when the requested regeneration failed."""
    monkeypatch.setattr(
        mod,
        "_regenerate_block_registry",
        lambda root: {"failed": "block-registry", "reason": "generator failed"},
    )

    result = mod.fix(_ctx(tmp_path, difficulty=0), [_regen_issue()])
    assert isinstance(result, FixResult)
    assert result.success is False


def test_fix_reports_success_when_regen_succeeds(tmp_path: Path, monkeypatch) -> None:
    """fix() reports success when the regeneration actually produced the artifact."""
    monkeypatch.setattr(
        mod,
        "_regenerate_block_registry",
        lambda root: {"regenerated": "block-registry", "script": "stub"},
    )

    result = mod.fix(_ctx(tmp_path, difficulty=0), [_regen_issue()])
    assert isinstance(result, FixResult)
    assert result.success is True
