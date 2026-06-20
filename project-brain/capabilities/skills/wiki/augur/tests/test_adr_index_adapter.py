import json
from datetime import date, timedelta

import pytest

from src.config.paths import invalidate_project_cache
from skills.wiki.scripts.wiki_query_sources import AdrIndexAdapter


@pytest.fixture(autouse=True)
def _clear_path_cache():
    invalidate_project_cache()
    yield
    invalidate_project_cache()


def _seed_adrs(adr_dir, records: list[dict]) -> None:
    adr_dir.mkdir(parents=True, exist_ok=True)
    (adr_dir / "adrs-index.json").write_text(json.dumps(records), encoding="utf-8")


def test_adapter_kind():
    assert AdrIndexAdapter().kind == "adr_index"


def test_status_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_ROOT", str(tmp_path))
    (tmp_path / "project.yaml").write_text("name: Test\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _seed_adrs(
        tmp_path / "project-brain" / "decisions" / "adrs",
        [
            {
                "adr_number": "ADR-001",
                "title": "Accepted one",
                "status": "Accepted",
                "date": date.today().isoformat(),
                "decision_summary": "ok",
            },
            {
                "adr_number": "ADR-002",
                "title": "Proposed one",
                "status": "Proposed",
                "date": date.today().isoformat(),
                "decision_summary": "ok",
            },
        ],
    )

    result = AdrIndexAdapter().resolve({"kind": "adr_index", "status": ["Accepted"]}, budget_tokens=10_000)

    assert "ADR-001" in result.text
    assert "ADR-002" not in result.text


def test_recent_days_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_ROOT", str(tmp_path))
    (tmp_path / "project.yaml").write_text("name: Test\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    today = date.today()
    _seed_adrs(
        tmp_path / "project-brain" / "decisions" / "adrs",
        [
            {
                "adr_number": "ADR-001",
                "title": "Recent",
                "status": "Accepted",
                "date": today.isoformat(),
                "decision_summary": "ok",
            },
            {
                "adr_number": "ADR-002",
                "title": "Old",
                "status": "Accepted",
                "date": (today - timedelta(days=400)).isoformat(),
                "decision_summary": "ok",
            },
        ],
    )

    result = AdrIndexAdapter().resolve({"kind": "adr_index", "recent_days": 30}, budget_tokens=10_000)

    assert "ADR-001" in result.text
    assert "ADR-002" not in result.text


def test_empty_index(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_ROOT", str(tmp_path))
    (tmp_path / "project.yaml").write_text("name: Test\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _seed_adrs(tmp_path / "project-brain" / "decisions" / "adrs", [])

    result = AdrIndexAdapter().resolve({"kind": "adr_index"}, budget_tokens=10_000)

    assert result.text == ""
