from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from skills.ingest.scripts.thought_cards import write_thought_card
from src.lib.frontmatter_utils import parse_frontmatter

import importlib.util
import sys

_MOD_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "inbox_triage.py"
)
_spec = importlib.util.spec_from_file_location("inbox_triage_under_test", _MOD_PATH)
inbox_triage = importlib.util.module_from_spec(_spec)
sys.modules["inbox_triage_under_test"] = inbox_triage
_spec.loader.exec_module(inbox_triage)


def _domains_vault(tmp_path: Path) -> Path:
    (tmp_path / "BRAIN.yaml").write_text("layout: domains\n", encoding="utf-8")
    return tmp_path


def test_list_inbox_cards_returns_metadata(tmp_path):
    vault = _domains_vault(tmp_path)
    write_thought_card(
        vault_dir=vault,
        body="Meta moved 7000 engineers to AI teams and morale broke.",
        title="Meta AI reorg morale crisis",
        captured_at=datetime.now(UTC) - timedelta(days=3),
    )
    cards = inbox_triage.list_inbox_cards(vault)
    assert len(cards) == 1
    card = cards[0]
    assert card["title"] == "Meta AI reorg morale crisis"
    assert card["note_type"] == "thought"
    assert "Meta moved" in card["excerpt"]
    assert card["age_days"] >= 3
    assert card["path"].endswith(".md")


def test_list_inbox_cards_empty_when_no_inbox(tmp_path):
    vault = _domains_vault(tmp_path)
    assert inbox_triage.list_inbox_cards(vault) == []


def test_list_inbox_cards_handles_naive_captured_at(tmp_path):
    # Older cards may carry a timezone-naive captured_at; age computation must
    # not crash subtracting from an aware now() (real-vault regression).
    vault = _domains_vault(tmp_path)
    inbox = vault / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "old-card.md").write_text(
        "---\ntitle: Old card\nx-augur-note-type: thought\n"
        "captured_at: '2026-05-16T15:49:00'\n---\nbody text\n",
        encoding="utf-8",
    )
    cards = inbox_triage.list_inbox_cards(vault)
    assert len(cards) == 1
    assert cards[0]["age_days"] >= 0


def _make_card(vault: Path, title: str, body: str) -> Path:
    return write_thought_card(vault_dir=vault, body=body, title=title)


def test_file_card_moves_into_existing_domain(tmp_path):
    vault = _domains_vault(tmp_path)
    (vault / "venture").mkdir()
    card = _make_card(vault, "Augur pitch notes", "Notes about the venture pitch.")
    result = inbox_triage.file_card(
        vault_dir=vault,
        card_path=card,
        target_rel="venture",
        reason="Venture pitch material.",
        refresh_index=False,
    )
    assert result["success"] is True
    new_path = Path(result["new_path"])
    assert new_path.parent == vault / "venture"
    assert not card.exists()
    meta, _ = parse_frontmatter(new_path)
    assert meta["filed_to"] == "venture"
    assert meta["filed_by"] == "inbox-triage"
    assert meta["filed_reason"] == "Venture pitch material."
    assert result["created_folder"] is False


def test_file_card_creates_new_domain_and_flags_it(tmp_path):
    vault = _domains_vault(tmp_path)
    card = _make_card(vault, "Reading list", "A book I want to read.")
    result = inbox_triage.file_card(
        vault_dir=vault,
        card_path=card,
        target_rel="reading/queue",
        reason="Recurring reading-list theme.",
        refresh_index=False,
    )
    assert result["success"] is True
    assert result["created_folder"] is True
    assert (vault / "reading" / "queue").is_dir()
    meta, _ = parse_frontmatter(Path(result["new_path"]))
    assert meta["filed_created_folder"] is True


def test_file_card_rejects_target_outside_vault(tmp_path):
    vault = _domains_vault(tmp_path)
    card = _make_card(vault, "Escape", "body")
    result = inbox_triage.file_card(
        vault_dir=vault, card_path=card, target_rel="../evil",
        reason="x", refresh_index=False,
    )
    assert result["success"] is False
    assert "outside vault" in result["error"]
    assert card.exists()  # untouched


def test_file_card_rejects_machine_target(tmp_path):
    vault = _domains_vault(tmp_path)
    card = _make_card(vault, "Machine", "body")
    result = inbox_triage.file_card(
        vault_dir=vault, card_path=card, target_rel="_augur/config",
        reason="x", refresh_index=False,
    )
    assert result["success"] is False
    assert "machine" in result["error"].lower()
    assert card.exists()


def test_file_card_unique_name_on_collision(tmp_path):
    vault = _domains_vault(tmp_path)
    finance = vault / "finance"
    finance.mkdir()
    # Pre-seed a file that the incoming card's slug will collide with, so
    # file_card's own unique-naming (not the inbox's) is exercised.
    existing = finance / "tax.md"
    existing.write_text("pre-existing finance note\n", encoding="utf-8")
    card = _make_card(vault, "Tax", "incoming tax note")
    result = inbox_triage.file_card(vault_dir=vault, card_path=card,
                                    target_rel="finance", reason="x", refresh_index=False)
    assert result["success"] is True
    new_path = Path(result["new_path"])
    assert new_path.name != "tax.md"  # did not overwrite the existing file
    assert new_path.exists()
    assert existing.read_text(encoding="utf-8") == "pre-existing finance note\n"


def test_file_card_refreshes_prompts_for_prompt_cards(tmp_path, monkeypatch):
    vault = _domains_vault(tmp_path)
    (vault / "profile").mkdir()
    inbox = vault / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "card.md").write_text(
        "---\nid: card\nx-augur-note-type: prompt\nx-augur-prompt-triggerable: true\n---\nBody {{x}}\n",
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_refresh(*, paths=None, categories=None, vault_dir=None, documents_dir=None):
        cats = set(categories or set())
        for _p in (paths or []):
            cats |= {"vault", "prompts"}
        seen["categories"] = cats
        return {}

    monkeypatch.setattr(inbox_triage, "refresh_browse_after_write", fake_refresh, raising=False)

    result = inbox_triage.file_card(
        vault_dir=vault, card_path=inbox / "card.md",
        target_rel="profile", reason="x", refresh_index=True,
    )
    assert result["success"] is True
    assert seen["categories"] == {"vault", "prompts"}
