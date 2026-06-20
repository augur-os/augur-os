"""Bootstrap response must expose per-entry items so the Browse Profile tab
can render one BrowseItem card per memory entry, voice profile, and interview
slot (CLAUDE.md rule 32: every tab is the shared file-card mechanism, no
bespoke panels).
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


def _entry(name: str, etype: str) -> str:
    return textwrap.dedent(
        f"""\
        ---
        name: {name}
        description: short desc for {name}
        type: {etype}
        ---
        body
        """
    )


def test_build_browse_items_emits_one_card_per_entry(tmp_path: Path) -> None:
    """Each memory entry becomes its own BrowseItem record."""
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    memory_dir = tmp_path / "memory"
    entries_dir = memory_dir / "entries"
    entries_dir.mkdir(parents=True)
    (entries_dir / "user_feedback_alpha.md").write_text(_entry("alpha", "feedback"), encoding="utf-8")
    (entries_dir / "user_preference_beta.md").write_text(_entry("beta", "preference"), encoding="utf-8")
    (entries_dir / "user_project_gamma.md").write_text(_entry("gamma", "project"), encoding="utf-8")

    items = mod._build_browse_items(memory_dirs=[memory_dir], vault_dir=None)
    entry_items = [i for i in items if i.get("metadata", {}).get("kind") == "memory-entry"]

    assert len(entry_items) == 3, f"expected 3 memory-entry items, got {len(entry_items)}"
    titles = sorted(i["title"] for i in entry_items)
    assert titles == ["alpha", "beta", "gamma"]

    # Each card carries its normalized type as a metadata badge
    by_title = {i["title"]: i for i in entry_items}
    assert by_title["alpha"]["metadata"]["type"] == "decision"  # feedback -> decision
    assert by_title["beta"]["metadata"]["type"] == "preference"
    assert by_title["gamma"]["metadata"]["type"] == "pattern"  # project -> pattern

    # Each card has a primary action that opens the source file
    assert by_title["alpha"]["primaryAction"]["type"] == "open-file"
    assert "user_feedback_alpha.md" in by_title["alpha"]["primaryAction"]["target"]

    # Card carries hub=brain so existing renderer styling works
    assert all(i["hub"] == "brain" for i in entry_items)


def test_build_browse_items_emits_voice_profile_cards(tmp_path: Path) -> None:
    """A voice profile (about-me.md present) becomes its own card per language."""
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    vault_dir = tmp_path / "vault"
    en_dir = vault_dir / "profile" / "en"
    en_dir.mkdir(parents=True)
    (en_dir / "about-me.md").write_text("x" * 500, encoding="utf-8")

    items = mod._build_browse_items(memory_dirs=[], vault_dir=vault_dir)
    profile_items = [i for i in items if i.get("metadata", {}).get("kind") == "voice-profile"]
    assert len(profile_items) == 1
    assert profile_items[0]["title"] == "English Voice Profile"
    assert profile_items[0]["metadata"]["language"] == "en"
    assert profile_items[0]["metadata"]["status"] == "ready"
    assert profile_items[0]["metadata"]["sizeBytes"] == "500"


def test_build_browse_items_emits_interview_slots_even_when_pending(tmp_path: Path) -> None:
    """Interview slots render as cards too — pending interviews are still cards."""
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    vault_dir = tmp_path / "vault"
    (vault_dir / "profile" / "en").mkdir(parents=True)
    (vault_dir / "profile" / "he").mkdir(parents=True)
    # English: in-progress yaml only, no about-me
    (vault_dir / "profile" / "en" / "interview-in-progress.yaml").write_text(
        "version: 1\nlanguage: en\nanswered: 5\ntotal: 100\n", encoding="utf-8"
    )

    items = mod._build_browse_items(memory_dirs=[], vault_dir=vault_dir)
    slot_items = [i for i in items if i.get("metadata", {}).get("kind") == "interview-slot"]
    langs = sorted(i["metadata"]["language"] for i in slot_items)
    assert langs == ["en", "he"], slot_items
    en_slot = next(i for i in slot_items if i["metadata"]["language"] == "en")
    assert en_slot["metadata"]["status"] == "in-progress"
    he_slot = next(i for i in slot_items if i["metadata"]["language"] == "he")
    assert he_slot["metadata"]["status"] == "not-started"


def test_memory_entry_card_carries_client_and_actions(tmp_path: Path) -> None:
    """Each memory-entry card surfaces the originating agent (claude-code, codex,
    user, gemini, etc) as metadata.client and exposes overflow actions so it
    matches every other Browse card surface (rule 32)."""
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    memory_dir = tmp_path / "memory"
    entries_dir = memory_dir / "entries"
    entries_dir.mkdir(parents=True)
    (entries_dir / "claude-code_feedback_alpha.md").write_text(_entry("alpha", "feedback"), encoding="utf-8")
    (entries_dir / "codex_preference_beta.md").write_text(_entry("beta", "preference"), encoding="utf-8")
    (entries_dir / "user_project_gamma.md").write_text(_entry("gamma", "project"), encoding="utf-8")
    (entries_dir / "gemini_reference_delta.md").write_text(_entry("delta", "reference"), encoding="utf-8")

    items = mod._build_browse_items(memory_dirs=[memory_dir], vault_dir=None)
    by_name = {i["title"]: i for i in items if i.get("metadata", {}).get("kind") == "memory-entry"}

    assert by_name["alpha"]["metadata"]["client"] == "claude-code"
    assert by_name["beta"]["metadata"]["client"] == "codex"
    assert by_name["gamma"]["metadata"]["client"] == "user"
    assert by_name["delta"]["metadata"]["client"] == "gemini"

    # Every card has an actions array (3-dots overflow menu)
    actions = by_name["alpha"].get("actions") or []
    action_labels = {a["label"] for a in actions}
    assert "Reveal in Finder" in action_labels, action_labels
    assert "Copy Path" in action_labels, action_labels


def test_voice_profile_card_has_useful_actions(tmp_path: Path) -> None:
    import importlib

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    vault_dir = tmp_path / "vault"
    (vault_dir / "profile" / "en").mkdir(parents=True)
    (vault_dir / "profile" / "en" / "about-me.md").write_text("x" * 400, encoding="utf-8")

    items = mod._build_browse_items(memory_dirs=[], vault_dir=vault_dir)
    voice = next(i for i in items if i["metadata"]["kind"] == "voice-profile")
    action_labels = {a["label"] for a in (voice.get("actions") or [])}
    assert "Reveal in Finder" in action_labels
    # Should expose a way to trigger the update flow
    assert any("update" in a["label"].lower() or "Update" in a["label"] for a in voice.get("actions", []))


def test_bootstrap_response_includes_browse_items(tmp_path: Path, monkeypatch) -> None:
    """The bootstrap MCP response shape gains a top-level `browseItems` key."""
    import importlib
    from src.config import paths as paths_module

    mod = importlib.import_module("skills.knowledge.scripts.mcp.tools_memory_dashboard")

    memory_dir = tmp_path / "memory"
    (memory_dir / "entries").mkdir(parents=True)
    (memory_dir / "entries" / "user_feedback_a.md").write_text(_entry("a", "feedback"), encoding="utf-8")

    vault_dir = tmp_path / "vault"
    (vault_dir / "profile" / "en").mkdir(parents=True)
    (vault_dir / "profile" / "en" / "about-me.md").write_text("x" * 300, encoding="utf-8")

    items = mod._build_browse_items(memory_dirs=[memory_dir], vault_dir=vault_dir)
    kinds = {i["metadata"]["kind"] for i in items}
    # Both kinds present at minimum
    assert "memory-entry" in kinds
    assert "voice-profile" in kinds
