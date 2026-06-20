from __future__ import annotations

from pathlib import Path


def test_calibration_scores_text_file_without_cloud(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from skills.demo.scripts import ai_pc_demo_calibration

    sample = tmp_path / "invoice.txt"
    sample.write_text("Invoice 100\nAmount 20\n", encoding="utf-8")
    monkeypatch.setattr(
        ai_pc_demo_calibration,
        "get_extraction_policy",
        lambda: {
            "airplane_mode_enabled": True,
            "cloud_escalation_allowed": False,
            "local_agent_escalation_allowed": True,
        },
    )

    result = ai_pc_demo_calibration.score_file(sample)

    assert result["path"] == str(sample)
    assert result["cloud_allowed"] is False
    assert result["text_present"] is True
    assert result["score"] >= 1
