"""Tests for the repo-root llms.txt / llms-full.txt generator (ADR-746).

Convention: this test file imports the module under test via
``importlib.util.spec_from_file_location`` rather than a dotted module path,
matching the project's `feedback_skill_test_convention` memory rule. Path
discovery walks up from this file so the tests stay portable across
worktrees and project-brain layouts.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType


# ---------------------------------------------------------------------------
# Module loading via importlib (no dotted module path)
# ---------------------------------------------------------------------------


def _load_llms_txt_module() -> ModuleType:
    """Load `llms_txt.py` directly from disk via importlib.

    Returns a cached module object. The test file lives at
    `<repo>/project-brain/capabilities/skills/ai/scripts/sync_agents/tests/test_llms_txt.py`
    so the module path is two directories up.
    """
    cache_key = "_augur_test_llms_txt_module"
    if cache_key in sys.modules:
        return sys.modules[cache_key]
    module_path = Path(__file__).resolve().parents[1] / "llms_txt.py"
    assert module_path.exists(), f"llms_txt.py not found at {module_path}"
    spec = importlib.util.spec_from_file_location(cache_key, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[cache_key] = module
    spec.loader.exec_module(module)
    return module


def _project_root() -> Path:
    """Walk up from this test file to find the Augur project root.

    The project root carries both `pyproject.toml` and a `project-brain/capabilities/skills`
    directory. We don't rely on `src.config.paths` here so the test stays
    light and re-usable inside tmp_path fixtures.
    """
    start = Path(__file__).resolve()
    for candidate in (start.parent, *start.parents):
        if (candidate / "pyproject.toml").exists() and (
            candidate / "project-brain" / "capabilities" / "skills"
        ).exists():
            return candidate
    raise RuntimeError(f"Could not find project root from {start}")


# ---------------------------------------------------------------------------
# Tmp-root scaffolding so the tests don't touch the live repo root
# ---------------------------------------------------------------------------


def _scaffold_minimal_project(tmp_root: Path) -> Path:
    """Materialize the minimum directory tree the generator needs.

    Copies the curated header templates, agent-topic markdown files, and the
    three inlined doc bodies from the live repo into ``tmp_root`` so the
    generator can run against an isolated tree.
    """
    src_root = _project_root()

    # Templates
    templates_src = src_root / "project-brain" / "capabilities" / "skills" / "ai" / "assets" / "templates"
    templates_dst = tmp_root / "project-brain" / "capabilities" / "skills" / "ai" / "assets" / "templates"
    templates_dst.mkdir(parents=True, exist_ok=True)
    for name in ("llms-txt-header.md", "llms-full-txt-header.md"):
        shutil.copy2(templates_src / name, templates_dst / name)

    # Agent topics
    topics_src = src_root / "docs" / "agent-topics"
    topics_dst = tmp_root / "docs" / "agent-topics"
    topics_dst.mkdir(parents=True, exist_ok=True)
    for md_path in topics_src.glob("*.md"):
        shutil.copy2(md_path, topics_dst / md_path.name)

    # Inlined load-bearing docs
    docs_dst = tmp_root / "docs"
    for name in ("architecture-overview.md", "what-is-augur.md"):
        shutil.copy2(src_root / "docs" / name, docs_dst / name)

    return tmp_root


# ---------------------------------------------------------------------------
# Composition tests (run against an isolated scaffolded tree)
# ---------------------------------------------------------------------------


def test_concise_includes_header(tmp_path: Path) -> None:
    """The concise variant must inline the hand-curated header paragraph."""
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    composed = mod.compose_llms_files(root)
    concise_path = root / mod.LLMS_TXT_NAME
    text = composed[concise_path]
    assert "# Augur — Local Second Brain for Your AI Clients" in text
    # Header phrase that uniquely identifies the concise template.
    assert "client-neutral pointer map" in text


def test_concise_enumerates_agent_topics(tmp_path: Path) -> None:
    """Every `docs/agent-topics/*.md` file must appear in the concise output."""
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    composed = mod.compose_llms_files(root)
    text = composed[root / mod.LLMS_TXT_NAME]

    for topic_path in (root / "docs" / "agent-topics").glob("*.md"):
        relative = topic_path.relative_to(root).as_posix()
        assert relative in text, f"missing topic pointer for {relative}"


def test_concise_lists_agent_rules_first(tmp_path: Path) -> None:
    """`agent-rules.md` is canonical and should head the agent-topics block."""
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    composed = mod.compose_llms_files(root)
    text = composed[root / mod.LLMS_TXT_NAME]

    topics_section = text.split("## Agent topics", 1)[1]
    first_entry_line = next(
        line for line in topics_section.splitlines() if line.startswith("- docs/")
    )
    assert "agent-rules.md" in first_entry_line


def test_full_inlines_agent_rules(tmp_path: Path) -> None:
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    composed = mod.compose_llms_files(root)
    full_text = composed[root / mod.LLMS_FULL_TXT_NAME]
    source_text = (root / "docs" / "agent-topics" / "agent-rules.md").read_text(
        encoding="utf-8"
    )
    assert "## Inlined: docs/agent-topics/agent-rules.md" in full_text
    # Compare on a stable substring to dodge trailing-newline differences.
    assert source_text.rstrip("\n") in full_text


def test_full_inlines_architecture_overview(tmp_path: Path) -> None:
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    composed = mod.compose_llms_files(root)
    full_text = composed[root / mod.LLMS_FULL_TXT_NAME]
    source_text = (root / "docs" / "architecture-overview.md").read_text(encoding="utf-8")
    assert "## Inlined: docs/architecture-overview.md" in full_text
    assert source_text.rstrip("\n") in full_text


def test_full_inlines_what_is_augur(tmp_path: Path) -> None:
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    composed = mod.compose_llms_files(root)
    full_text = composed[root / mod.LLMS_FULL_TXT_NAME]
    source_text = (root / "docs" / "what-is-augur.md").read_text(encoding="utf-8")
    assert "## Inlined: docs/what-is-augur.md" in full_text
    assert source_text.rstrip("\n") in full_text


def test_full_carries_concise_pointer_index(tmp_path: Path) -> None:
    """The full file embeds the concise pointer index verbatim (minus H1)."""
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    composed = mod.compose_llms_files(root)
    concise_text = composed[root / mod.LLMS_TXT_NAME]
    full_text = composed[root / mod.LLMS_FULL_TXT_NAME]
    # Pull a section header that only exists in the concise pointer body.
    assert "## Entry points" in concise_text
    assert "## Entry points" in full_text
    assert "## References" in full_text


def test_stable_output(tmp_path: Path) -> None:
    """Two consecutive generations produce byte-identical output."""
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    first = mod.compose_llms_files(root)
    second = mod.compose_llms_files(root)
    assert first == second
    # Also exercise the write path twice and verify on-disk bytes match.
    paths_a = mod.generate_llms_files(root)
    bytes_a = [p.read_bytes() for p in paths_a]
    paths_b = mod.generate_llms_files(root)
    bytes_b = [p.read_bytes() for p in paths_b]
    assert bytes_a == bytes_b


def test_size_sanity_concise(tmp_path: Path) -> None:
    """Concise variant should stay within its budget (spec acceptance criterion)."""
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    composed = mod.compose_llms_files(root)
    text = composed[root / mod.LLMS_TXT_NAME]
    size = len(text.encode("utf-8"))
    assert size <= mod.LLMS_TXT_MAX_BYTES, f"llms.txt exceeded budget: {size} bytes"


def test_size_sanity_full(tmp_path: Path) -> None:
    """Full variant stays within budget — a guaranteed invariant of the
    budget-aware composer, not a tripwire that fails when docs grow (ADR-746)."""
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    composed = mod.compose_llms_files(root)
    text = composed[root / mod.LLMS_FULL_TXT_NAME]
    size = len(text.encode("utf-8"))
    assert size <= mod.LLMS_FULL_TXT_MAX_BYTES, f"llms-full.txt exceeded budget: {size} bytes"


def test_full_stays_bounded_and_points_to_truncated_sources(
    tmp_path: Path, monkeypatch
) -> None:
    """When the inlined docs exceed the budget, the composer truncates gracefully
    with a pointer to the complete file and never exceeds the ceiling."""
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    # Force a budget far below the curated docs' total so truncation must engage.
    monkeypatch.setattr(mod, "LLMS_FULL_TXT_MAX_BYTES", 12 * 1024)

    text = mod.compose_llms_files(root)[root / mod.LLMS_FULL_TXT_NAME]

    assert len(text.encode("utf-8")) <= 12 * 1024  # bounded by construction
    assert "## Entry points" in text  # pointer index preserved
    assert "read the complete file at" in text  # graceful truncation pointer


def test_full_truncation_closes_open_code_fence(tmp_path: Path, monkeypatch) -> None:
    """A body truncated mid code-block gets a balanced closing fence."""
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    monkeypatch.setattr(mod, "LLMS_FULL_TXT_MAX_BYTES", 12 * 1024)

    text = mod.compose_llms_files(root)[root / mod.LLMS_FULL_TXT_NAME]

    # Balanced fences: every opening ``` has a matching closing ```.
    fence_lines = [ln for ln in text.splitlines() if ln.lstrip().startswith("```")]
    assert len(fence_lines) % 2 == 0


def test_missing_header_template_raises(tmp_path: Path) -> None:
    """If a header template is missing, generation must fail loudly."""
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    # Remove one template to provoke the failure.
    target = (
        root
        / "project-brain"
        / "capabilities"
        / "skills"
        / "ai"
        / "assets"
        / "templates"
        / mod.CONCISE_HEADER_NAME
    )
    target.unlink()
    import pytest

    with pytest.raises(FileNotFoundError):
        mod.compose_llms_files(root)


def test_drift_detection(tmp_path: Path) -> None:
    """`llms_files_drift` reports stale files and clears after regeneration."""
    mod = _load_llms_txt_module()
    root = _scaffold_minimal_project(tmp_path)
    mod.generate_llms_files(root)
    assert mod.llms_files_drift(root) == []

    # Mutate the concise file on disk; drift must flag it.
    concise_path = root / mod.LLMS_TXT_NAME
    contents = concise_path.read_text(encoding="utf-8")
    mutated = "\n".join(
        line for line in contents.splitlines() if not line.startswith("- README.md")
    )
    concise_path.write_text(mutated, encoding="utf-8")
    drift = mod.llms_files_drift(root)
    assert concise_path in drift

    # Regenerate; drift clears.
    mod.generate_llms_files(root)
    assert mod.llms_files_drift(root) == []


# ---------------------------------------------------------------------------
# End-to-end test against the live `sync_agents check` CLI
# ---------------------------------------------------------------------------


def test_check_mode_detects_drift_on_live_repo() -> None:
    """Mutating the live llms.txt makes `sync_agents check` exit non-zero.

    This test exercises the CLI wired into modes.check_mode and is the only
    test that touches the actual repo root. It restores the file before
    returning, regardless of outcome.
    """
    mod = _load_llms_txt_module()
    project_root = _project_root()
    concise_path, _ = mod.llms_txt_paths(project_root)

    # Ensure the file is generated and clean before we mutate it.
    mod.generate_llms_files(project_root)
    assert mod.llms_files_drift(project_root) == []

    original = concise_path.read_text(encoding="utf-8")
    try:
        # Drop a known marker line; the regenerated body restores it.
        mutated = "\n".join(
            line for line in original.splitlines() if not line.startswith("- README.md")
        )
        concise_path.write_text(mutated, encoding="utf-8")

        scripts_dir = (
            project_root / "project-brain" / "capabilities" / "skills" / "ai" / "scripts"
        ).resolve()
        os_mod = __import__("os")
        env = {
            **os_mod.environ,
            "PYTHONPATH": os_mod.pathsep.join((str(scripts_dir), str(project_root))),
        }
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "sync_agents",
                "check",
            ],
            cwd=str(project_root),
            env=env,
            capture_output=True,
            text=True,
        )
        # check_mode logs to stderr; combined output mentions llms.txt drift.
        combined = (completed.stdout or "") + (completed.stderr or "")
        assert completed.returncode != 0, (
            "Expected sync_agents check to flag drift; got rc=0.\n" + combined
        )
        assert "llms.txt" in combined, combined
    finally:
        concise_path.write_text(original, encoding="utf-8")
