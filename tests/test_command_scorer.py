from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _reset_command_scoring_caches():
    """Real-data command scoring reads through THREE process-wide caches, any of
    which a sibling test can poison with empty/tmp-root results (passes locally by
    ordering luck, fails in CI's full-suite order):
      1. skill_discovery._DISCOVERY_CACHE (30s) — a test that runs the real
         discover_all_skills against a tmp/empty skills dir caches 0 skills;
      2. command_scorer._CACHE (60s) — caches the scored-commands result;
      3. browse index command-enrichment cache — derived from the above.
    Invalidate the whole chain before+after so these tests always score the real
    repo regardless of prior test state."""
    import src.lib.command_scorer as command_scorer
    from src.plugins.skill_discovery import invalidate_discovery_cache
    from src.mcp.augur_framework.tools.infrastructure.browse import index_enrichment

    def _reset():
        invalidate_discovery_cache()
        command_scorer._CACHE = {}
        command_scorer._CACHE_TS = 0.0
        index_enrichment._command_enrichment_cache = {}
        index_enrichment._command_enrichment_ts = 0.0

    _reset()
    yield
    _reset()


def test_docs_score_rewards_rich_command_doc(tmp_path):
    from src.lib.command_scorer import score_docs

    rich = (
        "---\n"
        "description: " + ("word " * 25) + "\n"
        "---\n\n"
        "# /demo\n\n## Usage\n\n`/demo <arg>`\n\n## Examples\n\n```bash\n/demo x\n```\n"
    )
    thin = "---\ndescription: short one\n---\n\n# /demo\n"

    rich_score = score_docs(rich)
    thin_score = score_docs(thin)

    assert rich_score > thin_score
    assert rich_score >= 70
    assert thin_score < 40


def test_wiring_score_from_capability_exposure():
    from src.lib.command_scorer import score_wiring

    full = {"classification_status": "approved", "export_to": ["cli", "agents-md"]}
    missing = None
    unapproved = {"classification_status": "draft", "export_to": []}

    assert score_wiring(full, file_exists=True) == 100.0
    assert score_wiring(missing, file_exists=True) < 40.0
    assert score_wiring(unapproved, file_exists=True) < score_wiring(full, file_exists=True)


def test_overall_blends_docs_and_wiring_and_maps_tier():
    from src.lib.command_scorer import blend_score, score_to_tier

    # docs 60% + wiring 40%
    assert blend_score(90.0, 100.0) == 94.0
    assert blend_score(0.0, 0.0) == 0.0

    assert score_to_tier(94.0) == "A"
    assert score_to_tier(70.0) == "B"
    assert score_to_tier(50.0) == "C"
    assert score_to_tier(30.0) == "D"
    assert score_to_tier(10.0) == "F"


def test_kpi_status_from_aggregate(tmp_path):
    from src.lib.command_scorer import kpi_status_map

    reports = tmp_path / "_augur" / "evals" / "commands" / "reports"
    reports.mkdir(parents=True)
    (reports / "run-aggregate.json").write_text(
        json.dumps(
            {
                "by_command": {
                    "keep": {"total": 6, "pass": 6, "warn": 0, "fail": 0},
                    "ask": {"total": 4, "pass": 3, "warn": 0, "fail": 1},
                }
            }
        ),
        encoding="utf-8",
    )

    statuses = kpi_status_map(documents_dir=tmp_path)

    assert statuses["keep"] == "pass"
    assert statuses["ask"] == "fail"
    assert statuses.get("discover", "untested") == "untested"


def test_score_all_commands_real_data():
    from src.lib.command_scorer import score_all_commands

    result = score_all_commands()
    commands = result["commands"]
    assert len(commands) >= 7
    sample = commands[0]
    assert set(sample) >= {"id", "score", "tier", "dimensions", "kpiStatus"}
    assert 0.0 <= sample["score"] <= 100.0
    assert sample["tier"] in {"A", "B", "C", "D", "F"}
    assert set(sample["dimensions"]) == {"docs", "wiring"}


def test_browse_commands_include_quality_metadata(tmp_path, monkeypatch):
    from src.config import paths
    from src.lib.index._scanners_knowledge import index_commands
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    # Browse renders command cards from the on-disk RAG index. That index is
    # runtime state living under the cache dir — it exists on a developer machine
    # that has indexed before, but NOT in a clean CI checkout, so this test used
    # to pass locally and fail in CI with an empty command grid. Build a real
    # commands index from the repo's own skill command docs into a tmp rag dir
    # and point Browse at it, so the assertion is deterministic everywhere.
    rag_dir = tmp_path / "rag"
    indexed = index_commands(paths.get_project_root(), rag_dir)
    assert indexed > 0, "expected the repo's skill command docs to index"
    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: rag_dir / category)

    browse_index._populate_command_enrichment()
    result = json.loads(browse_index.browse_index_impl("commands", limit=20))
    scored = [item for item in result["items"] if item.get("metadata", {}).get("qualityTier")]

    assert scored
    metadata = scored[0]["metadata"]
    assert set(metadata) >= {"qualityTier", "qualityScore", "docsScore", "wiringScore", "kpiStatus"}
    assert metadata["qualityTier"] in {"A", "B", "C", "D", "F"}
