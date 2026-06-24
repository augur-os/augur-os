"""Client runner renders the loop prompt from its resolved discover_path."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_DIR = _REPO_ROOT / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "routine_orchestrator"

if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_client_runner_renders_prompt_from_discover_path(tmp_path: Path):
    model = _load("loop_model")
    runner_mod = _load("loop_runner")
    prompt = tmp_path / "dream.md"
    prompt.write_text("# Dream\n\nRun the cycle.\n", encoding="utf-8")
    loop = model.parse_standard_loop(
        {"id": "dream", "skill": "dream", "automation": {"trigger": "manual", "runner": "auto", "discover": "dream.md"}},
        skill_name="dream",
        skill_root=tmp_path,
    )
    result = runner_mod.ClaudeRunner().run(loop)
    assert result["loop_id"] == "dream"
    assert result["runner"] == "claude"
    assert result["render_prompt"].startswith("# Dream")


def test_client_runner_omits_render_prompt_when_no_file(tmp_path: Path):
    model = _load("loop_model")
    runner_mod = _load("loop_runner")
    loop = model.parse_standard_loop(
        {"id": "x", "skill": "s", "automation": {"trigger": "manual", "runner": "auto"}},
        skill_name="s",
    )
    # no discover → falls through to orchestrator; inject a stub so we don't hit the real one
    stub_result = {"loop_id": "x", "ran": True}
    result = runner_mod.ClaudeRunner(orchestrate=lambda name, **kw: stub_result).run(loop)
    assert "render_prompt" not in result
    assert result["loop_id"] == "x"


def test_client_runner_runs_orchestrator_for_non_md_loop(tmp_path: Path):
    model = _load("loop_model")
    runner_mod = _load("loop_runner")
    py = tmp_path / "orchestrator.py"
    py.write_text("# not a prompt\n", encoding="utf-8")
    loop = model.parse_standard_loop(
        {"id": "testing", "skill": "rc", "loop_name": "testing",
         "automation": {"trigger": "nightly", "runner": "auto", "discover": "orchestrator.py"}},
        skill_name="rc", skill_root=tmp_path,
    )
    calls = []
    runner = runner_mod.ClaudeRunner(orchestrate=lambda name, **kw: calls.append((name, kw)) or {"ran": name})
    result = runner.run(loop, session="s")
    assert result == {"ran": "testing"}
    assert calls == [("testing", {"session": "s"})]
    assert "render_prompt" not in result


def test_client_runner_renders_md_even_with_loop_name(tmp_path: Path):
    model = _load("loop_model")
    runner_mod = _load("loop_runner")
    md = tmp_path / "dream.md"
    md.write_text("# Dream\n", encoding="utf-8")
    loop = model.parse_standard_loop(
        {"id": "dream", "skill": "dream",
         "automation": {"trigger": "manual", "runner": "auto", "discover": "dream.md"}},
        skill_name="dream", skill_root=tmp_path,
    )
    # orchestrate must NOT be called for a .md prompt loop
    runner = runner_mod.ClaudeRunner(orchestrate=lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not orchestrate")))
    result = runner.run(loop)
    assert result["render_prompt"].startswith("# Dream")
