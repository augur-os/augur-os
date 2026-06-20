"""Tests for demo-vault artifact cleanup (demo_ready._purge_demo_vault_artifacts).

A demo run leaves three linked artifacts per file (source card in notes/, routed copy
via final_path, extracted text via extracted_path). `reset` must purge all of them
without touching genuine user notes.
"""
from __future__ import annotations

from pathlib import Path

from skills.demo.scripts.demo_ready import _purge_demo_vault_artifacts


def test_purge_removes_demo_artifacts_and_keeps_real(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    notes = vault / "notes"
    extracted = vault / "sources" / "extracted"
    finance = vault / "finance"
    for d in (notes, extracted, finance):
        d.mkdir(parents=True)

    final = finance / "demo-invoice.txt"
    final.write_text("invoice")
    ext = extracted / "demo-invoice.extracted.md"
    ext.write_text("invoice text")
    (notes / "demo-invoice.md").write_text(
        "---\n"
        "original_path: /Users/x/Desktop/Augur Demo Inbox/demo-invoice.txt\n"
        f"final_path: {final}\n"
        f"extracted_path: {ext}\n"
        "---\nbody\n"
    )

    # A demo card from a DIFFERENT demo desktop folder must also be caught
    # (criterion is the original filename, not the folder name).
    (notes / "demo-meeting.md").write_text(
        "---\n"
        "original_path: /Users/x/Desktop/Augur Workflow Example Inbox/demo-meeting.mp3\n"
        "---\nbody\n"
    )

    # A genuine note (non-demo origin) MUST survive.
    real = notes / "real-meeting.md"
    real.write_text("---\noriginal_path: /Users/x/Desktop/real.txt\n---\nbody\n")

    out = _purge_demo_vault_artifacts(vault)

    assert out == {"cards": 2, "final": 1, "extracted": 1}
    assert not (notes / "demo-invoice.md").exists()
    assert not (notes / "demo-meeting.md").exists()
    assert not final.exists()
    assert not ext.exists()
    assert real.exists(), "genuine note must not be purged"


def test_purge_is_noop_without_notes_dir(tmp_path: Path) -> None:
    assert _purge_demo_vault_artifacts(tmp_path / "missing") == {
        "cards": 0,
        "final": 0,
        "extracted": 0,
    }
