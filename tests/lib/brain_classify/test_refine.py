from src.lib.brain_classify.manifest import ManifestRow
from src.lib.brain_classify.refine import refine_rows


def test_refine_only_touches_non_high_rows_and_applies_verdict(tmp_path):
    f = tmp_path / "thesis.md"
    f.write_text("The compounding gateway is Augur's product story for Guriqo.", encoding="utf-8")

    rows = [
        ManifestRow(source=str(f), verdict="personal", target="t", confidence="low", rationale="x"),
        ManifestRow(source=str(f), verdict="project", target="t", confidence="high", rationale="locked"),
    ]

    def fake_classify(path, body, evidence_signals, current):
        return {
            "verdict": "venture",
            "confidence": "high",
            "rationale": "Augur/Guriqo product thesis",
            "target": "Au-vault/venture/thesis.md",
        }

    out = refine_rows(rows, classify_fn=fake_classify, root=tmp_path.parent)
    assert out[0].verdict == "venture"
    assert out[0].target == "Au-vault/venture/thesis.md"
    assert out[1].rationale == "locked"  # high-confidence row untouched
