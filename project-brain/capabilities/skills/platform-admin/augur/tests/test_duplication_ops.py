from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from src.lib.ops_protocol import OpsContext

_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "ops" / "duplication_ops.py"
)
_SPEC = importlib.util.spec_from_file_location("duplication_ops_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
duplication_ops = importlib.util.module_from_spec(_SPEC)
sys.modules["duplication_ops_under_test"] = duplication_ops
_SPEC.loader.exec_module(duplication_ops)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(project_root: Path, **kwargs) -> OpsContext:
    return OpsContext(project_root=project_root, **kwargs)


def test_scan_detects_exact_duplicate_auto_command_modules(tmp_path: Path):
    repo = tmp_path / "repo"
    code = (
        '"""docstring"""\n'
        "from __future__ import annotations\n\n"
        'name = "auto-code-review"\n'
        "def scan(ctx):\n    return None\n"
        "def fix(ctx, issues):\n    return None\n"
    )
    _write(
        repo / "plugins" / "dev" / "skills" / "devops" / "augur" / "augur.yaml",
        "commands:\n  - id: auto-code-review\n    protocol: scan-fix\n    callable: scripts/ops/code_review.py\n",
    )
    _write(
        repo / "plugins" / "dev" / "skills" / "devops" / "scripts" / "ops" / "code_review.py",
        code,
    )
    _write(
        repo / "plugins" / "adaptive" / "skills" / "auto-code-review" / "augur" / "augur.yaml",
        "commands:\n  - id: auto-code-review\n    protocol: scan-fix\n    callable: scripts/code_review.py\n",
    )
    _write(
        repo / "plugins" / "adaptive" / "skills" / "auto-code-review" / "scripts" / "code_review.py",
        code,
    )

    result = duplication_ops.scan(_ctx(repo, difficulty=1))

    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue["kind"] == "manual"
    assert issue["canonical"] == "project-brain/capabilities/skills/devops/scripts/ops/code_review.py"
    assert issue["safe_duplicates"] == []


def test_fix_rewrites_safe_adaptive_duplicate_as_wrapper(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    monkeypatch.setenv("AUGUR_STATE", str(state))
    code = (
        "from __future__ import annotations\n\n"
        'name = "auto-code-review"\n'
        "def scan(ctx):\n    return None\n"
        "def fix(ctx, issues):\n    return None\n"
    )
    canonical = repo / "plugins" / "dev" / "skills" / "devops" / "scripts" / "ops" / "code_review.py"
    duplicate = repo / "plugins" / "adaptive" / "skills" / "auto-code-review" / "scripts" / "code_review.py"
    _write(
        repo / "plugins" / "dev" / "skills" / "devops" / "augur" / "augur.yaml",
        "commands:\n  - id: auto-code-review\n    protocol: scan-fix\n    callable: scripts/ops/code_review.py\n",
    )
    _write(
        repo / "plugins" / "adaptive" / "skills" / "auto-code-review" / "augur" / "augur.yaml",
        "commands:\n  - id: auto-code-review\n    protocol: scan-fix\n    callable: scripts/code_review.py\n",
    )
    _write(
        repo / "plugins" / "adaptive" / "skills" / "auto-code-review" / "SKILL.md",
        "---\nname: auto-code-review\nx-augur-loop:\n  name: code-quality\n---\n",
    )
    _write(canonical, code)
    _write(duplicate, code)

    issue = duplication_ops.scan(
        _ctx(
            repo,
            difficulty=2,
            config={"max_groups": 10},
        )
    ).issues[0]
    result = duplication_ops.fix(_ctx(repo), [issue])

    assert result.success is True
    assert "project-brain/capabilities/skills/auto-code-review/scripts/code_review.py" in result.changes
    assert duplicate.exists() is False
    skill_md = (repo / "plugins" / "adaptive" / "skills" / "auto-code-review" / "SKILL.md")
    assert "x-augur-callable: project-brain/capabilities/skills/devops/scripts/ops/code_review.py" in skill_md.read_text(encoding="utf-8")
    report = json.loads((state / "reports" / "duplication-latest.json").read_text(encoding="utf-8"))
    assert report["fixed_groups"] == 1


def test_scan_marks_non_adaptive_duplicate_groups_manual(tmp_path: Path):
    repo = tmp_path / "repo"
    code = (
        "from __future__ import annotations\n\n"
        'name = "x"\n'
        "def scan(ctx):\n    return None\n"
        "def fix(ctx, issues):\n    return None\n"
    )
    _write(
        repo / "plugins" / "dev" / "skills" / "devops" / "augur" / "augur.yaml",
        "commands:\n  - id: a\n    protocol: scan-fix\n    callable: scripts/ops/a.py\n",
    )
    _write(repo / "plugins" / "dev" / "skills" / "devops" / "scripts" / "ops" / "a.py", code)
    _write(
        repo / "plugins" / "observability" / "skills" / "daemon" / "augur" / "augur.yaml",
        "contributions:\n  commands:\n    - id: b\n      protocol: scan-fix\n      callable: scripts/ops/b.py\n",
    )
    _write(repo / "plugins" / "observability" / "skills" / "daemon" / "scripts" / "ops" / "b.py", code)

    result = duplication_ops.scan(_ctx(repo, difficulty=1))

    assert len(result.issues) == 1
    assert result.issues[0]["kind"] == "manual"


def test_scan_includes_standalone_skill_scripts(tmp_path: Path):
    repo = tmp_path / "repo"
    code = (
        "from __future__ import annotations\n\n"
        'name = "auto-code-review"\n'
        "def scan(ctx):\n    return None\n"
        "def fix(ctx, issues):\n    return None\n"
    )
    _write(
        repo / "plugins" / "dev" / "skills" / "devops" / "augur" / "augur.yaml",
        "contributions:\n  commands:\n    - id: auto-code-review\n      protocol: scan-fix\n      callable: scripts/ops/code_review.py\n",
    )
    _write(
        repo / "plugins" / "dev" / "skills" / "devops" / "scripts" / "ops" / "code_review.py",
        code,
    )
    _write(
        repo / "plugins" / "adaptive" / "skills" / "auto-code-review" / "SKILL.md",
        "---\nname: auto-code-review\nx-augur-loop:\n  name: code-quality\n---\n",
    )
    _write(
        repo / "plugins" / "adaptive" / "skills" / "auto-code-review" / "scripts" / "code_review.py",
        code,
    )

    result = duplication_ops.scan(_ctx(repo, difficulty=1))

    assert len(result.issues) == 1
    assert result.issues[0]["safe_duplicates"] == [
        "project-brain/capabilities/skills/auto-code-review/scripts/code_review.py"
    ]


def test_scan_prefers_declared_skill_callable_over_helper_scripts(tmp_path: Path):
    repo = tmp_path / "repo"
    code = (
        "from __future__ import annotations\n\n"
        'name = "loop-evals"\n'
        "def scan(ctx):\n    return None\n"
        "def fix(ctx, issues):\n    return None\n"
    )
    helper = (
        "from __future__ import annotations\n\n"
        "def ensure_project_paths(current_file):\n    return current_file\n"
    )
    _write(
        repo / "plugins" / "dev" / "skills" / "evals" / "scripts" / "ops" / "eval_ops.py",
        code,
    )
    _write(
        repo / "plugins" / "dev" / "skills" / "evals" / "augur" / "augur.yaml",
        "commands:\n  - id: loop-evals\n    protocol: scan-fix\n    callable: scripts/ops/eval_ops.py\n",
    )
    _write(
        repo / "plugins" / "adaptive" / "skills" / "evals" / "SKILL.md",
        "---\nname: evals\nx-augur-callable: project-brain/capabilities/skills/evals/scripts/eval_ops.py\nx-augur-loop:\n  name: evals\n---\n",
    )
    _write(
        repo / "plugins" / "adaptive" / "skills" / "evals" / "scripts" / "bootstrap_paths.py",
        helper,
    )
    _write(
        repo / "plugins" / "adaptive" / "skills" / "evals" / "scripts" / "eval_ops.py",
        code,
    )

    result = duplication_ops.scan(_ctx(repo, difficulty=1))

    assert len(result.issues) == 1
    assert result.issues[0]["canonical"] == "project-brain/capabilities/skills/evals/scripts/ops/eval_ops.py"
    assert result.issues[0]["duplicates"] == [
        "project-brain/capabilities/skills/evals/scripts/eval_ops.py"
    ]


def test_scan_marks_ops_to_standalone_alias_duplicates_actionable(tmp_path: Path):
    repo = tmp_path / "repo"
    code = (
        "from __future__ import annotations\n\n"
        'name = "reindex-project"\n'
        "def scan(ctx):\n    return None\n"
        "def fix(ctx, issues):\n    return None\n"
    )
    _write(
        repo / "plugins" / "ai" / "skills" / "ai" / "augur" / "augur.yaml",
        "commands:\n  - id: reindex-project\n    protocol: scan-fix\n    callable: scripts/ops/project_index.py\n",
    )
    _write(
        repo / "plugins" / "ai" / "skills" / "ai" / "scripts" / "ops" / "project_index.py",
        code,
    )
    _write(
        repo / "plugins" / "ai" / "skills" / "reindex-project" / "SKILL.md",
        "---\nname: reindex-project\nx-augur-loop:\n  name: knowledge-enrichment\n---\n",
    )
    _write(
        repo / "plugins" / "ai" / "skills" / "reindex-project" / "scripts" / "project_index.py",
        code,
    )

    result = duplication_ops.scan(_ctx(repo, difficulty=1))

    assert len(result.issues) == 1
    assert result.issues[0]["kind"] == "actionable"
    assert result.issues[0]["safe_duplicates"] == [
        "project-brain/capabilities/skills/reindex-project/scripts/project_index.py"
    ]


def test_fix_migrates_existing_wrapper_to_skill_callable(monkeypatch, tmp_path: Path):
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    monkeypatch.setenv("AUGUR_STATE", str(state))
    canonical = repo / "project-brain" / "capabilities" / "skills" / "quality" / "scripts" / "ops" / "skill_standards_md.py"
    duplicate = repo / "plugins" / "adaptive" / "skills" / "auto-skill-md" / "scripts" / "skill_standards_md.py"
    _write(
        repo / "plugins" / "adaptive" / "skills" / "auto-skill-md" / "SKILL.md",
        "---\nname: auto-skill-md\nx-augur-loop:\n  name: skill-standards\n---\n",
    )
    _write(canonical, "from __future__ import annotations\n\ndef scan(ctx):\n    return None\n\ndef fix(ctx, issues):\n    return None\n")
    _write(
        duplicate,
        '"""Thin wrapper generated by auto-duplication.\n\n'
        "Canonical implementation: project-brain/capabilities/skills/quality/scripts/ops/skill_standards_md.py\n"
        '"""\n'
        "from __future__ import annotations\n\n"
        "from plugins.observability.skills.quality.scripts.ops.skill_standards_md import *  # noqa: F401,F403\n",
    )

    result = duplication_ops.scan(_ctx(repo, difficulty=1))
    assert len(result.issues) == 1

    fix_result = duplication_ops.fix(_ctx(repo), result.issues)

    assert fix_result.success is True
    assert duplicate.exists() is False
    assert "x-augur-callable: project-brain/capabilities/skills/quality/scripts/ops/skill_standards_md.py" in (
        repo / "plugins" / "adaptive" / "skills" / "auto-skill-md" / "SKILL.md"
    ).read_text(encoding="utf-8")


def test_scan_detects_near_duplicates_at_higher_difficulty(tmp_path: Path):
    repo = tmp_path / "repo"
    canonical_code = (
        "from __future__ import annotations\n\n"
        'name = "auto-code-review"\n'
        "def scan(ctx):\n"
        '    return {"issues": [], "summary": "ok"}\n'
        "def fix(ctx, issues):\n"
        "    return None\n"
    )
    near_duplicate_code = canonical_code.replace('"summary": "ok"', '"summary": "still ok"')
    _write(
        repo / "plugins" / "dev" / "skills" / "devops" / "augur" / "augur.yaml",
        "commands:\n  - id: auto-code-review\n    protocol: scan-fix\n    callable: scripts/ops/code_review.py\n",
    )
    _write(
        repo / "plugins" / "dev" / "skills" / "devops" / "scripts" / "ops" / "code_review.py",
        canonical_code,
    )
    _write(
        repo / "plugins" / "adaptive" / "skills" / "auto-code-review" / "SKILL.md",
        "---\nname: auto-code-review\nx-augur-loop:\n  name: code-quality\n---\n",
    )
    _write(
        repo / "plugins" / "adaptive" / "skills" / "auto-code-review" / "scripts" / "code_review.py",
        near_duplicate_code,
    )

    result = duplication_ops.scan(_ctx(repo, difficulty=2))

    assert len(result.issues) == 1
    assert result.issues[0]["kind"] == "manual"
    assert result.issues[0]["fixability"] == "root-extraction"
    assert result.issues[0]["extract_to"].endswith("scripts/ops/shared/code_review.py")
    assert result.issues[0]["common_line_count"] > 0
    assert result.issues[0]["common_lines"]
