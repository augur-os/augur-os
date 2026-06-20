"""Memory bootstrap must read memory/entries/*.md, not only MEMORY.md.

Mirrors the tools_reflect.py:243 entries-dir walk so the dashboard
surfaces the consolidated feedback/preference/project/reference files
that /ask retrieval already reads.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

SHARED_VAULT_ROOT = Path(__file__).resolve().parents[4]
if str(SHARED_VAULT_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_VAULT_ROOT))

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _entry(name: str, etype: str, body: str = "body line.\n") -> str:
    return textwrap.dedent(
        f"""\
        ---
        name: {name}
        description: short desc for {name}
        type: {etype}
        ---
        {body}
        """
    )


def test_parse_memory_entries_merges_entries_directory(tmp_path: Path) -> None:
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    memory_dir = tmp_path / "memory"
    entries_dir = memory_dir / "entries"
    entries_dir.mkdir(parents=True)
    (entries_dir / "claude-code_feedback_autonomous.md").write_text(
        _entry("Autonomous execution", "feedback"), encoding="utf-8"
    )
    (entries_dir / "claude-code_preference_terse.md").write_text(
        _entry("Terse responses", "preference"), encoding="utf-8"
    )
    (entries_dir / "claude-code_project_augur.md").write_text(
        _entry("Augur GTM", "project"), encoding="utf-8"
    )
    (entries_dir / "claude-code_reference_grafana.md").write_text(
        _entry("Grafana dashboard", "reference"), encoding="utf-8"
    )
    (memory_dir / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")

    entries = mod._parse_memory_entries_with_dir(memory_dir)
    types = sorted({e["type"] for e in entries})

    # _LEGACY_TYPE_MAP: feedback->decision, project->pattern, preference->preference,
    # reference->insight. Confirmed at tools_memory_dashboard.py:71-76.
    assert types == ["decision", "insight", "pattern", "preference"], types
    assert len(entries) == 4
    by_name = {e["name"]: e for e in entries}
    assert by_name["Autonomous execution"]["description"].startswith("short desc")
    assert by_name["Autonomous execution"]["type"] == "decision"
    assert by_name["Augur GTM"]["type"] == "pattern"
    assert by_name["Terse responses"]["type"] == "preference"
    assert by_name["Grafana dashboard"]["type"] == "insight"


def test_parse_memory_entries_handles_missing_entries_dir(tmp_path: Path) -> None:
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")

    entries = mod._parse_memory_entries_with_dir(memory_dir)
    assert entries == []


def test_build_stats_counts_entries_into_totals(tmp_path: Path) -> None:
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    memory_dir = tmp_path / "memory"
    entries_dir = memory_dir / "entries"
    entries_dir.mkdir(parents=True)
    for i in range(3):
        (entries_dir / f"claude-code_preference_p{i}.md").write_text(
            _entry(f"pref {i}", "preference"), encoding="utf-8"
        )
    (memory_dir / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")

    entries = mod._parse_memory_entries_with_dir(memory_dir)
    stats = mod._build_stats(entries, daily_logs=0, last_curated=None)
    assert stats["totalPreferences"] == 3


def test_parse_memory_entries_merges_multiple_memory_dirs(tmp_path: Path) -> None:
    """Vault + runtime memory dirs both have entries/ and MEMORY.md.

    Real prod call passes both get_memory_dir() and get_runtime_dir()/memory.
    Function must merge + dedupe across them.
    """
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    vault_dir = tmp_path / "vault" / "memory"
    runtime_dir = tmp_path / "runtime" / "memory"
    (vault_dir / "entries").mkdir(parents=True)
    (runtime_dir / "entries").mkdir(parents=True)

    (vault_dir / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    (runtime_dir / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")

    # vault entries
    (vault_dir / "entries" / "user_preference_terse.md").write_text(
        _entry("terse-prefs", "preference"), encoding="utf-8"
    )
    # runtime entries
    (runtime_dir / "entries" / "claude-code_feedback_autonomy.md").write_text(
        _entry("autonomy", "feedback"), encoding="utf-8"
    )
    (runtime_dir / "entries" / "claude-code_project_augur.md").write_text(
        _entry("augur-gtm", "project"), encoding="utf-8"
    )

    entries = mod._parse_memory_entries_with_dir(vault_dir, runtime_dir)
    assert len(entries) == 3
    types = sorted(e["type"] for e in entries)
    assert types == ["decision", "pattern", "preference"]


def test_parse_memory_entries_skips_unknown_or_empty_type(tmp_path: Path) -> None:
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    memory_dir = tmp_path / "memory"
    entries_dir = memory_dir / "entries"
    entries_dir.mkdir(parents=True)
    (entries_dir / "no-type.md").write_text(
        "---\nname: untyped\ndescription: x\n---\n", encoding="utf-8"
    )
    (entries_dir / "preference_ok.md").write_text(
        _entry("Real one", "preference"), encoding="utf-8"
    )

    entries = mod._parse_memory_entries_with_dir(memory_dir)
    assert [e["name"] for e in entries] == ["Real one"]
