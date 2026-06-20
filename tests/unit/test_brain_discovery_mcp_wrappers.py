from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.lib.ai_artifact_inventory import AiArtifactInventory, AiArtifactRecord
from src.lib.brain_active_context import (
    ActiveBrainFolderContextResult,
)
from src.lib.brain_registry import clear_cache
from src.mcp.augur_core.tools.core import brain_discovery


def _artifact(index: int) -> AiArtifactRecord:
    return AiArtifactRecord(
        id=f"artifact-{index}",
        project_brain_id="preview-repo",
        project_root="/tmp/repo",
        artifact_type="instruction",
        client="codex",
        vendor="openai",
        source_path=f"/tmp/repo/AGENTS-{index}.md",
        relative_path=f"AGENTS-{index}.md",
        title=f"Artifact {index}",
        classification="source",
        confidence=0.9,
        warnings=["low_confidence"] if index == 0 else [],
        discovered_at="2026-06-05T00:00:00+00:00",
        freshness="current",
        provenance={"kind": "test"},
    )


@pytest.mark.asyncio
async def test_brain_folder_scan_reports_totals_and_limits_returned_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifacts = [_artifact(index) for index in range(55)]

    def fake_scan_ai_artifacts(*, project_root: Path, project_brain_id: str):
        return AiArtifactInventory(
            schema_version=1,
            project_brain_id=project_brain_id,
            project_root=str(project_root),
            generated_at="2026-06-05T00:00:00+00:00",
            artifacts=artifacts,
            warnings=["scan-warning"],
        )

    monkeypatch.setattr(
        "src.lib.ai_artifact_inventory.scan_ai_artifacts",
        fake_scan_ai_artifacts,
    )

    payload = json.loads(await brain_discovery.brain_folder_scan_impl(str(tmp_path)))

    assert payload["success"] is True
    assert payload["writes_metadata"] is False
    assert payload["inventory_count"] == 55
    assert payload["inventory_warning_count"] == 2
    assert len(payload["artifacts"]) == 50
    assert payload["artifacts"][0]["id"] == "artifact-0"


@pytest.mark.asyncio
async def test_brain_folder_scan_returns_json_for_path_normalization_failure() -> None:
    payload = json.loads(await brain_discovery.brain_folder_scan_impl("bad\x00path"))

    assert payload["success"] is False
    assert payload["error"]
    assert payload["project_root"] == "bad\x00path"


@pytest.mark.asyncio
async def test_brain_init_returns_launch_summary_and_activates_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Existing instructions\n", encoding="utf-8")
    registry_path = tmp_path / "registry.yaml"
    active_context_path = tmp_path / "active-context.json"
    clear_cache()
    monkeypatch.setattr(
        "src.lib.brain_init.get_brain_registry_path",
        lambda: registry_path,
    )
    monkeypatch.setattr(
        "src.config.paths.get_brain_registry_path",
        lambda: registry_path,
    )
    monkeypatch.setattr(
        "src.lib.brain_active_context.default_active_context_path",
        lambda: active_context_path,
    )

    payload = json.loads(await brain_discovery.brain_init_impl(str(project), run_sync=False))

    assert payload["success"] is True
    assert payload["launch_journey"]["success_moment"] == "inventory_proof"
    assert payload["launch_journey"]["write_boundary"]["inventory_only"] is True
    assert payload["launch_journey"]["browse"]["active_context"]["brain_id"] == payload["brain_id"]
    assert payload["launch_context"]["success"] is True
    assert payload["launch_context"]["context"]["brain_id"] == payload["brain_id"]


@pytest.mark.asyncio
async def test_brain_init_returns_json_when_launch_context_activation_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Existing instructions\n", encoding="utf-8")
    registry_path = tmp_path / "registry.yaml"
    clear_cache()
    monkeypatch.setattr(
        "src.lib.brain_init.get_brain_registry_path",
        lambda: registry_path,
    )
    monkeypatch.setattr(
        "src.config.paths.get_brain_registry_path",
        lambda: registry_path,
    )

    def fail_activation(*args, **kwargs):
        raise OSError("runtime state unavailable")

    monkeypatch.setattr(
        "src.lib.onboarding_journey.activate_project_launch_context",
        fail_activation,
    )

    payload = json.loads(await brain_discovery.brain_init_impl(str(project), run_sync=False))

    assert payload["success"] is True
    assert payload["brain_id"].startswith("project-")
    assert payload["inventory_count"] >= 1
    assert payload["launch_journey"]["success_moment"] == "inventory_proof"
    assert payload["launch_context"]["success"] is False
    assert payload["launch_context"]["context"] is None
    assert payload["launch_context"]["repaired"] is False
    assert payload["launch_context"]["error"] == "runtime state unavailable"


@dataclass(frozen=True)
class _StrictContext:
    scope: str
    label: str
    brain_id: str | None = None

    @property
    def __dict__(self):  # type: ignore[override]
        raise AssertionError("wrapper must use dataclasses.asdict")


@pytest.mark.asyncio
async def test_brain_active_context_serializes_stable_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_get_active_context(*, cwd: Path, project_root: Path):
        return SimpleNamespace(
            success=True,
            context=_StrictContext(scope="all", label="All Brains"),
            options=[{"id": "all", "scope": "all"}],
            repaired=False,
            error=None,
        )

    monkeypatch.setattr("src.config.paths.get_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "src.lib.brain_active_context.get_active_brain_folder_context",
        fake_get_active_context,
    )

    payload = json.loads(await brain_discovery.brain_active_context_impl())

    assert set(payload) == {"success", "context", "options", "repaired", "error"}
    assert payload["context"] == {"scope": "all", "label": "All Brains", "brain_id": None}
    assert payload["options"] == [{"id": "all", "scope": "all"}]


@pytest.mark.asyncio
async def test_brain_set_active_context_serializes_stable_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    requested_values: list[dict[str, str]] = []

    def fake_set_active_context(requested: dict[str, str], *, cwd: Path, project_root: Path):
        requested_values.append(requested)
        return ActiveBrainFolderContextResult(
            success=True,
            context=_StrictContext(
                scope="brain",
                label="Demo",
                brain_id="project-demo",
            ),
            options=[{"id": "project-demo", "scope": "brain"}],
            repaired=False,
            error=None,
        )

    monkeypatch.setattr("src.config.paths.get_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "src.lib.brain_active_context.set_active_brain_folder_context",
        fake_set_active_context,
    )

    payload = json.loads(
        await brain_discovery.brain_set_active_context_impl(
            scope="brain",
            brain_id="project-demo",
        )
    )

    assert requested_values == [{"scope": "brain", "brain_id": "project-demo"}]
    assert set(payload) == {"success", "context", "options", "repaired", "error"}
    assert payload["context"]["scope"] == "brain"
    assert payload["context"]["brain_id"] == "project-demo"
    assert payload["options"] == [{"id": "project-demo", "scope": "brain"}]
