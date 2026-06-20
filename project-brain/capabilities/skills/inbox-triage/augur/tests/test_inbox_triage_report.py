import importlib.util
import sys
from pathlib import Path

_MOD = Path(__file__).resolve().parents[2] / "scripts" / "inbox_triage_report.py"
_spec = importlib.util.spec_from_file_location("inbox_triage_report_under_test", _MOD)
report = importlib.util.module_from_spec(_spec)
sys.modules["inbox_triage_report_under_test"] = report
_spec.loader.exec_module(report)


def test_render_report_lists_moves_and_created_folders():
    entries = [
        {"title": "Meta AI reorg", "filed_to": "general", "reason": "No domain fit.",
         "created_folder": False},
        {"title": "Reading list", "filed_to": "reading/queue",
         "reason": "Recurring theme.", "created_folder": True},
    ]
    text = report.render_report("2026-06-13", entries, left_in_inbox=[])
    assert "2026-06-13" in text
    assert "Meta AI reorg" in text
    assert "general" in text
    assert "reading/queue" in text
    assert "created folder" in text.lower()
    assert "2 card" in text  # count line


def test_render_report_zero_cards_is_explicit():
    text = report.render_report("2026-06-13", [], left_in_inbox=[])
    assert "0 card" in text


def test_write_report_creates_dated_file(tmp_path):
    out = report.write_report(tmp_path, "2026-06-13", [], left_in_inbox=[])
    p = Path(out)
    assert p.exists()
    assert p.name == "2026-06-13.md"
    assert p.parent.name == "inbox-triage"
