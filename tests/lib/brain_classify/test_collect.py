from pathlib import Path

from src.lib.brain_classify.collect import collect_candidates


def test_collect_assigns_deterministic_high_confidence(tmp_path):
    vault_wiki = tmp_path / "Au-vault" / "wiki" / "concepts"
    vault_wiki.mkdir(parents=True)
    (vault_wiki / "daemon-loops.md").write_text(
        "The daemon in `src/` and `project-brain/capabilities/skills/daemon/`.", encoding="utf-8"
    )
    (vault_wiki / "recipes.md").write_text("Family recipes for `health/` meals. [[meal-ideas]]", encoding="utf-8")

    rows = collect_candidates(
        roots=[vault_wiki],
        project_root=tmp_path,
        vault_root=tmp_path / "Au-vault",
    )
    by_source = {Path(r.source).name: r for r in rows}
    assert by_source["daemon-loops.md"].verdict == "project"
    assert by_source["daemon-loops.md"].confidence == "high"
    # 'health/' + recipe → personal; stays in vault, but flagged as a row.
    assert by_source["recipes.md"].verdict in {"personal", "career", "venture"}


def test_ambiguous_files_marked_low_confidence(tmp_path):
    root = tmp_path / "Au-vault" / "_augur" / "memory" / "entries"
    root.mkdir(parents=True)
    (root / "vague.md").write_text("A general note with no artifact references.", encoding="utf-8")
    rows = collect_candidates(roots=[root], project_root=tmp_path, vault_root=tmp_path / "Au-vault")
    assert rows[0].confidence == "low"
