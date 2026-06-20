"""Tests for ui_quality loop orchestration."""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_ui_quality_importable():
    """Verify that ui_quality can be imported without errors."""
    mod = importlib.import_module("ui_quality")
    assert mod is not None


def test_fix_report_only_when_no_safe_changes(tmp_path, monkeypatch):
    """Finding issues without a safe rewrite should not mark the loop failed."""
    from src.lib.ops_protocol import OpsContext

    ui_quality = importlib.import_module("ui_quality")

    page_file = tmp_path / "apps" / "dashboard" / "features" / "pages" / "adaptive" / "page.tsx"
    page_file.parent.mkdir(parents=True)
    page_file.write_text("export default function Page() { return <button>Run</button>; }\n")

    monkeypatch.setattr(ui_quality, "get_runtime_dir", lambda: tmp_path / "runtime")
    monkeypatch.setattr(ui_quality, "_find_page_files", lambda _root: {"adaptive": page_file})

    class _Checks:
        @staticmethod
        def run_all_checks(content: str, page_path: str, difficulty: int):
            return {"dimension_scores": {"accessibility": 90}, "issues": [], "applicable": 1, "passing": 1}

    class _Scorer:
        @staticmethod
        def compute_page_score(_scores):
            return 90.0

        @staticmethod
        def load_registry(_path):
            return {"adaptive": {"score": 90.0, "issues": {"d0": 0, "d1": 0}}}

        @staticmethod
        def save_registry(_registry, _path):
            return None

        @staticmethod
        def priority_sort(_registry):
            return ["adaptive"]

    class _Fixers:
        @staticmethod
        def verify_build(_project_root, _verify_command):
            return True

        @staticmethod
        def safe_fix_page(**_kwargs):
            return {"action": "skipped", "reason": "no safe fix"}

    monkeypatch.setattr(
        ui_quality,
        "_import_sibling",
        lambda name: {"checks": _Checks, "scorer": _Scorer, "fixers": _Fixers}[name],
    )

    ctx = OpsContext(
        project_root=tmp_path,
        difficulty=2,
        dry_run=False,
        loop_config={},
        config={},
    )
    issues = [{"page_route": "adaptive", "detail": "cursor-pointer missing"}]

    result = ui_quality.fix(ctx, issues)

    assert result.success is True
    assert result.fix_type == "report"
    assert result.summary == "No fixes applied"


def test_visual_recommendations_use_shared_vault_ui_ux_skill(tmp_path, monkeypatch):
    """d3 visual escalation should resolve ui-ux-pro-max from project-brain."""
    from src.lib.ops_protocol import OpsContext

    ui_quality = importlib.import_module("ui_quality")
    page_file = tmp_path / "apps" / "dashboard" / "features" / "pages" / "adaptive" / "page.tsx"
    page_file.parent.mkdir(parents=True)
    page_file.write_text("export default function Page() { return <main />; }\n", encoding="utf-8")
    search_script = tmp_path / "project-brain" / "capabilities" / "skills" / "ui-ux-pro-max" / "scripts" / "search.py"
    search_script.parent.mkdir(parents=True)
    search_script.write_text("print('design')\n", encoding="utf-8")

    captured: dict[str, Path] = {}

    def fake_get_design_recommendations(_query: str, script: Path) -> str:
        captured["script"] = script
        return "design recommendations"

    fake_visual = types.SimpleNamespace(
        check_dashboard_available=lambda: True,
        screenshot_page=lambda *_args, **_kwargs: None,
        get_design_recommendations=fake_get_design_recommendations,
        build_llm_prompt=lambda **_kwargs: "prompt",
    )
    monkeypatch.setitem(sys.modules, "scripts.visual", fake_visual)
    monkeypatch.setattr(ui_quality, "get_runtime_dir", lambda: tmp_path / "runtime")
    monkeypatch.setattr(ui_quality, "_find_page_files", lambda _root: {"adaptive": page_file})

    class _Checks:
        @staticmethod
        def run_all_checks(content: str, page_path: str, difficulty: int):
            return {"dimension_scores": {"accessibility": 80}, "issues": [], "applicable": 1, "passing": 1}

    class _Scorer:
        @staticmethod
        def compute_page_score(_scores):
            return 80.0

        @staticmethod
        def load_registry(_path):
            return {"adaptive": {"score": 80.0, "dimension_scores": {"accessibility": 80}}}

        @staticmethod
        def save_registry(_registry, _path):
            return None

        @staticmethod
        def priority_sort(_registry):
            return ["adaptive"]

    class _Fixers:
        @staticmethod
        def verify_build(_project_root, _verify_command):
            return True

        @staticmethod
        def safe_fix_page(**_kwargs):
            return {"action": "skipped", "reason": "no safe fix"}

    monkeypatch.setattr(
        ui_quality,
        "_import_sibling",
        lambda name: {"checks": _Checks, "scorer": _Scorer, "fixers": _Fixers}[name],
    )

    result = ui_quality.fix(
        OpsContext(project_root=tmp_path, difficulty=3, dry_run=False, loop_config={}, config={}),
        [{"page_route": "adaptive", "detail": "needs visual review"}],
    )

    assert result.success is True
    assert captured["script"] == search_script
