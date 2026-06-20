from src.lib.brain_classify.manifest import (
    ManifestRow,
    write_manifest,
    read_manifest,
    validate_manifest,
)


def test_roundtrip_preserves_rows(tmp_path):
    rows = [
        ManifestRow(
            source="Au-vault/wiki/concepts/daemon-loops.md",
            verdict="project",
            target="project-brain/knowledge/wiki/concepts/daemon-loops.md",
            confidence="high",
            rationale="src/ + daemon refs",
        ),
        ManifestRow(
            source="project-brain/knowledge/memory/entries/resume-tailor-skill.md",
            verdict="personal",
            target="Au-vault/_augur/memory/entries/resume-tailor-skill.md",
            confidence="high",
            rationale="Au-vault skill refs",
        ),
    ]
    p = tmp_path / "manifest.yaml"
    write_manifest(p, rows)
    back = read_manifest(p)
    assert [r.source for r in back] == [r.source for r in rows]
    assert back[1].verdict == "personal"


def test_validate_flags_bad_verdict_and_missing_target(tmp_path):
    rows = [
        ManifestRow(source="a.md", verdict="bogus", target="x", confidence="high", rationale=""),
        ManifestRow(source="b.md", verdict="project", target="", confidence="low", rationale=""),
    ]
    errors = validate_manifest(rows)
    assert any("verdict" in e for e in errors)
    assert any("target" in e for e in errors)


def test_low_confidence_and_cross_brain_sort_first(tmp_path):
    from src.lib.brain_classify.manifest import sort_for_review

    rows = [
        ManifestRow(source="hi.md", verdict="project", target="t", confidence="high", rationale=""),
        ManifestRow(source="lo.md", verdict="personal", target="t", confidence="low", rationale=""),
    ]
    ordered = sort_for_review(rows)
    assert ordered[0].source == "lo.md"
