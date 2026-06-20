# Wiki Report Agent-Step Contract — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/wiki report` a deterministic end-to-end flow with a defined agent-step contract — so any AI client (Claude Code, Codex, Gemini CLI, Cursor, Copilot) can produce a high-quality Second Brain Intelligence Report HTML + sidecar landing at the ADR-723-canonical location.

**Architecture:** Single `wiki_report_contract.py` module owns the contract (schema + validator). `wiki-report-data` MCP tool returns the schema alongside raw data. `wiki-report-generate` MCP tool validates input on entry and writes both HTML and a YAML sidecar at `get_documents_dir()/brain/artifacts/`. The renderer template wraps every optional section in `{% if %}` so missing-but-allowed sections degrade silently while missing-required sections produce a structured `agent_step_required` error. No skeleton fallback. No server-side LLM for this flow.

**Tech Stack:** Python 3.11+, Jinja2 (renderer), pytest (tests), YAML (sidecar). All changes inside `shared-vault/skills/ingest/` and `shared-vault/skills/rag/` plus `tests/unit/`.

**Spec:** `docs/superpowers/specs/2026-05-11-wiki-report-agent-step-contract-design.md`

---

## Boundary rules (apply to every task)

- **No server-side LLM call for this flow.** Augur is the harness; the agent step is the user's AI client.
- **No skeleton fallback.** If required fields are missing, fail loud with the structured error. Do not write HTML.
- **Output path is `get_documents_dir()/brain/artifacts/<slug>.html`** (per ADR-723 §4). Filename slug: `second-brain-report-<YYYY-MM-DD>`. Sidecar: same path with `.meta.yaml` suffix.
- **Wiki-only scope.** Do not generalize to a reusable "agent-step framework."
- **PDF generation is downstream of HTML.** Existing `render_pdf` reads the same dict; no changes to PDF logic in this PR.
- **`shared-vault/skills/ingest/assets/seeds/wiki-schema/` and `assets/templates/report.html.j2` must exist** (restored in commit `3b376ba74` on 2026-05-11). Any fresh clone needs them; if they're missing, restore from that commit before running tests.

After each commit, run: `pytest tests/unit/test_wiki_report_contract.py tests/unit/test_wiki_report_e2e.py -v` (only the e2e once that file exists). Each task lists its specific verification command.

---

## Task 1: Contract module — `wiki_report_contract.py`

**Files:**
- Create: `shared-vault/skills/ingest/scripts/wiki_report_contract.py`

This module is the single source of truth for the agent-step contract. Both MCP tools (`wiki-report-data`, `wiki-report-generate`) import from it; tests import from it.

- [ ] **Step 1: Create the contract module with schema + validator**

Write to `shared-vault/skills/ingest/scripts/wiki_report_contract.py`:

```python
"""Wiki report agent-step contract.

Single source of truth for the rich-dict shape that the agent step must produce.
The contract has three surfaces:
  1. SYNTHESIS_SCHEMA (this module) — returned by wiki-report-data
  2. /wiki report action docs — narrative contract for the agent
  3. validate_rich_dict (this module) — runtime validation in wiki-report-generate

Designed so the validator is testable in isolation, without MCP plumbing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Schema version. Bump on breaking contract changes.
SCHEMA_VERSION = 1

# JSON-shape description of what the agent step must produce.
SYNTHESIS_SCHEMA: dict[str, Any] = {
    "version": SCHEMA_VERSION,
    "required": [
        {"path": "synthesis", "type": "string", "min_len": 100, "max_len": 400},
        {"path": "hub_sections[*].summary", "type": "string", "min_len": 60, "max_len": 200},
    ],
    "optional": [
        {"path": "who_you_are.what_you_do", "type": "string"},
        {"path": "who_you_are.how_you_think", "type": "string"},
        {"path": "expertise[*]", "shape": {
            "domain": "string",
            "level": "enum:Expert|Advanced|Intermediate|Building|Beginner",
            "percentage": "int:0-100",
            "color": "hex",
        }},
        {"path": "patterns[*]", "shape": {
            "title": "string",
            "description": "string",
        }},
        {"path": "blind_spots[*]", "shape": {
            "title": "string",
            "description": "string",
            "severity": "enum:low|medium|high",
        }},
    ],
    "passed_through": [
        {"path": "stats", "from": "raw_data.stats"},
        {"path": "portfolio", "from": "raw_data.portfolio"},
    ],
}

# Allowed severity values for blind_spots
ALLOWED_SEVERITIES = frozenset({"low", "medium", "high"})

# Length bounds for synthesis
SYNTHESIS_MIN_LEN = 100
SYNTHESIS_MAX_LEN = 400

# Length bounds for hub_sections[*].summary
HUB_SUMMARY_MIN_LEN = 60
HUB_SUMMARY_MAX_LEN = 200


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a rich dict.

    success: True iff missing_required is empty.
    missing_required: list of dotted paths to fields that failed (missing or
        wrong-shaped). Empty when validation passes.
    """
    success: bool
    missing_required: list[str] = field(default_factory=list)


def validate_rich_dict(report: dict[str, Any]) -> ValidationResult:
    """Validate the rich dict for wiki-report-generate.

    Collects every failing required field; does not short-circuit on first
    failure. Missing optional fields produce success.
    """
    missing: list[str] = []

    # synthesis: required string, bounded length
    synthesis = report.get("synthesis")
    if not isinstance(synthesis, str) or not (SYNTHESIS_MIN_LEN <= len(synthesis) <= SYNTHESIS_MAX_LEN):
        missing.append("synthesis")

    # hub_sections: required non-empty list
    hub_sections = report.get("hub_sections")
    if not isinstance(hub_sections, list) or not hub_sections:
        missing.append("hub_sections")
    else:
        for i, hub in enumerate(hub_sections):
            if not isinstance(hub, dict):
                missing.append(f"hub_sections[{i}]")
                continue
            summary = hub.get("summary")
            if not isinstance(summary, str) or not (HUB_SUMMARY_MIN_LEN <= len(summary) <= HUB_SUMMARY_MAX_LEN):
                missing.append(f"hub_sections[{i}].summary")

    # blind_spots[i].severity: if blind_spots present, severity must be in enum
    blind_spots = report.get("blind_spots")
    if isinstance(blind_spots, list):
        for i, spot in enumerate(blind_spots):
            if not isinstance(spot, dict):
                continue
            severity = spot.get("severity")
            if severity is not None and severity not in ALLOWED_SEVERITIES:
                missing.append(f"blind_spots[{i}].severity")

    # expertise[i].percentage: if expertise present, percentage must be int 0-100
    expertise = report.get("expertise")
    if isinstance(expertise, list):
        for i, item in enumerate(expertise):
            if not isinstance(item, dict):
                continue
            pct = item.get("percentage")
            if pct is not None and not (isinstance(pct, int) and 0 <= pct <= 100):
                missing.append(f"expertise[{i}].percentage")

    return ValidationResult(success=len(missing) == 0, missing_required=missing)


def hub_sections_skeleton(hubs: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive the hub_sections list-of-dicts skeleton from the aggregator's hubs dict.

    Returned entries have name + source_count filled in; summary/icon/color
    are left for the agent to populate. Sorted by source_count descending so
    the agent sees the most-prominent hubs first.
    """
    return [
        {
            "name": name,
            "source_count": hub_meta.get("source_count", 0),
        }
        for name, hub_meta in sorted(
            hubs.items(),
            key=lambda x: -x[1].get("source_count", 0) if isinstance(x[1], dict) else 0,
        )
    ]
```

- [ ] **Step 2: Verify the module imports cleanly**

Run:
```bash
python3 -c "
import sys
sys.path.insert(0, 'shared-vault')
from skills.ingest.scripts.wiki_report_contract import (
    SYNTHESIS_SCHEMA, SCHEMA_VERSION, ALLOWED_SEVERITIES,
    validate_rich_dict, hub_sections_skeleton, ValidationResult,
)
print('OK — schema version:', SCHEMA_VERSION)
print('Allowed severities:', sorted(ALLOWED_SEVERITIES))
"
```
Expected:
```
OK — schema version: 1
Allowed severities: ['high', 'low', 'medium']
```

- [ ] **Step 3: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_report_contract.py
git commit -m "$(cat <<'EOF'
feat(wiki): wiki_report_contract module — schema + validator

Single source of truth for the rich-dict shape the agent step must
produce. Three surfaces (per ADR spec):
  - SYNTHESIS_SCHEMA constant (returned by wiki-report-data)
  - /wiki report command docs (added in a later task)
  - validate_rich_dict() function (used by wiki-report-generate)

Tiered required: synthesis + hub_sections[*].summary required;
who_you_are / expertise / patterns / blind_spots optional. Validator
collects all failures (no short-circuit) so the structured error can
list every missing field in one shot.

Also exports hub_sections_skeleton() helper that derives the list-of-
dicts skeleton from the aggregator's hubs dict — bridges the existing
shape divergence between wiki-report-data and wiki-report-generate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Unit tests for the validator

**Files:**
- Create: `tests/unit/test_wiki_report_contract.py`

- [ ] **Step 1: Write the tests**

Write to `tests/unit/test_wiki_report_contract.py`:

```python
"""Unit tests for the wiki report agent-step contract."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the shared-vault skill modules importable
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "shared-vault"))

from skills.ingest.scripts.wiki_report_contract import (  # noqa: E402
    SCHEMA_VERSION,
    SYNTHESIS_SCHEMA,
    ALLOWED_SEVERITIES,
    HUB_SUMMARY_MIN_LEN,
    HUB_SUMMARY_MAX_LEN,
    SYNTHESIS_MIN_LEN,
    SYNTHESIS_MAX_LEN,
    validate_rich_dict,
    hub_sections_skeleton,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_valid() -> dict:
    """Smallest dict that passes validation: synthesis + one hub_section.summary."""
    return {
        "synthesis": "A " + "x" * (SYNTHESIS_MIN_LEN - 1),  # exactly SYNTHESIS_MIN_LEN chars
        "hub_sections": [
            {
                "name": "brain",
                "source_count": 136,
                "summary": "B" + "y" * (HUB_SUMMARY_MIN_LEN - 1),  # exactly HUB_SUMMARY_MIN_LEN chars
            },
        ],
    }


# ---------------------------------------------------------------------------
# Schema metadata tests
# ---------------------------------------------------------------------------

def test_schema_version_is_one():
    assert SYNTHESIS_SCHEMA["version"] == 1
    assert SCHEMA_VERSION == 1


def test_schema_lists_required_and_optional_paths():
    required_paths = [item["path"] for item in SYNTHESIS_SCHEMA["required"]]
    assert "synthesis" in required_paths
    assert "hub_sections[*].summary" in required_paths

    optional_paths = [item["path"] for item in SYNTHESIS_SCHEMA["optional"]]
    assert "who_you_are.what_you_do" in optional_paths
    assert "who_you_are.how_you_think" in optional_paths
    assert "expertise[*]" in optional_paths
    assert "patterns[*]" in optional_paths
    assert "blind_spots[*]" in optional_paths


def test_allowed_severities_is_frozenset_of_three():
    assert ALLOWED_SEVERITIES == frozenset({"low", "medium", "high"})


# ---------------------------------------------------------------------------
# validate_rich_dict — happy paths
# ---------------------------------------------------------------------------

def test_minimal_valid_dict_passes():
    result = validate_rich_dict(_minimal_valid())
    assert result.success
    assert result.missing_required == []


def test_all_optional_fields_present_and_valid_passes():
    d = _minimal_valid()
    d["who_you_are"] = {
        "what_you_do": "Building Augur — local-first AI infrastructure.",
        "how_you_think": "Decision-first; every architectural move gets an ADR.",
    }
    d["expertise"] = [
        {"domain": "Cross-Client AI Harness", "level": "Expert", "percentage": 95, "color": "#6366f1"},
    ]
    d["patterns"] = [
        {"title": "Discipline beats velocity", "description": "100% quality-passing wiki pages."},
    ]
    d["blind_spots"] = [
        {"title": "Life hub thin", "description": "Only 8 pages — work dominates.", "severity": "medium"},
    ]
    result = validate_rich_dict(d)
    assert result.success
    assert result.missing_required == []


# ---------------------------------------------------------------------------
# validate_rich_dict — synthesis failures
# ---------------------------------------------------------------------------

def test_missing_synthesis_fails():
    d = _minimal_valid()
    del d["synthesis"]
    result = validate_rich_dict(d)
    assert not result.success
    assert "synthesis" in result.missing_required


def test_synthesis_too_short_fails():
    d = _minimal_valid()
    d["synthesis"] = "x" * (SYNTHESIS_MIN_LEN - 1)
    result = validate_rich_dict(d)
    assert not result.success
    assert "synthesis" in result.missing_required


def test_synthesis_too_long_fails():
    d = _minimal_valid()
    d["synthesis"] = "x" * (SYNTHESIS_MAX_LEN + 1)
    result = validate_rich_dict(d)
    assert not result.success
    assert "synthesis" in result.missing_required


def test_synthesis_wrong_type_fails():
    d = _minimal_valid()
    d["synthesis"] = 42  # not a string
    result = validate_rich_dict(d)
    assert not result.success
    assert "synthesis" in result.missing_required


# ---------------------------------------------------------------------------
# validate_rich_dict — hub_sections failures
# ---------------------------------------------------------------------------

def test_missing_hub_sections_fails():
    d = _minimal_valid()
    del d["hub_sections"]
    result = validate_rich_dict(d)
    assert not result.success
    assert "hub_sections" in result.missing_required


def test_empty_hub_sections_fails():
    d = _minimal_valid()
    d["hub_sections"] = []
    result = validate_rich_dict(d)
    assert not result.success
    assert "hub_sections" in result.missing_required


def test_hub_section_missing_summary_fails():
    d = _minimal_valid()
    d["hub_sections"] = [{"name": "brain", "source_count": 136}]
    result = validate_rich_dict(d)
    assert not result.success
    assert "hub_sections[0].summary" in result.missing_required


def test_hub_section_summary_too_short_fails():
    d = _minimal_valid()
    d["hub_sections"][0]["summary"] = "x" * (HUB_SUMMARY_MIN_LEN - 1)
    result = validate_rich_dict(d)
    assert not result.success
    assert "hub_sections[0].summary" in result.missing_required


def test_hub_section_summary_too_long_fails():
    d = _minimal_valid()
    d["hub_sections"][0]["summary"] = "x" * (HUB_SUMMARY_MAX_LEN + 1)
    result = validate_rich_dict(d)
    assert not result.success
    assert "hub_sections[0].summary" in result.missing_required


def test_hub_section_at_index_not_a_dict_fails():
    d = _minimal_valid()
    d["hub_sections"] = ["not a dict"]
    result = validate_rich_dict(d)
    assert not result.success
    assert "hub_sections[0]" in result.missing_required


# ---------------------------------------------------------------------------
# validate_rich_dict — optional-field shape failures
# ---------------------------------------------------------------------------

def test_bad_severity_fails():
    d = _minimal_valid()
    d["blind_spots"] = [
        {"title": "x", "description": "y", "severity": "critical"},  # not in enum
    ]
    result = validate_rich_dict(d)
    assert not result.success
    assert "blind_spots[0].severity" in result.missing_required


def test_bad_percentage_above_100_fails():
    d = _minimal_valid()
    d["expertise"] = [
        {"domain": "AI", "level": "Expert", "percentage": 150, "color": "#fff"},
    ]
    result = validate_rich_dict(d)
    assert not result.success
    assert "expertise[0].percentage" in result.missing_required


def test_bad_percentage_negative_fails():
    d = _minimal_valid()
    d["expertise"] = [
        {"domain": "AI", "level": "Expert", "percentage": -5, "color": "#fff"},
    ]
    result = validate_rich_dict(d)
    assert not result.success
    assert "expertise[0].percentage" in result.missing_required


# ---------------------------------------------------------------------------
# validate_rich_dict — multi-failure collection
# ---------------------------------------------------------------------------

def test_multiple_failures_collected_not_short_circuit():
    """Validator collects every failure, not just the first."""
    d = {
        "synthesis": "short",  # too short
        "hub_sections": [
            {"name": "brain"},  # missing summary
            {"name": "career", "summary": "x" * 30},  # summary too short
        ],
    }
    result = validate_rich_dict(d)
    assert not result.success
    assert "synthesis" in result.missing_required
    assert "hub_sections[0].summary" in result.missing_required
    assert "hub_sections[1].summary" in result.missing_required
    assert len(result.missing_required) == 3


# ---------------------------------------------------------------------------
# hub_sections_skeleton
# ---------------------------------------------------------------------------

def test_hub_sections_skeleton_sorts_by_source_count_desc():
    hubs = {
        "general": {"source_count": 16},
        "brain":   {"source_count": 136},
        "career":  {"source_count": 119},
    }
    result = hub_sections_skeleton(hubs)
    assert [h["name"] for h in result] == ["brain", "career", "general"]
    assert [h["source_count"] for h in result] == [136, 119, 16]
    # No editorial fields filled in — agent's job
    for h in result:
        assert "summary" not in h
        assert "icon" not in h
        assert "color" not in h


def test_hub_sections_skeleton_handles_missing_source_count():
    hubs = {"empty_hub": {}}
    result = hub_sections_skeleton(hubs)
    assert result == [{"name": "empty_hub", "source_count": 0}]


def test_hub_sections_skeleton_handles_empty_input():
    assert hub_sections_skeleton({}) == []
```

- [ ] **Step 2: Run the tests — verify all pass**

Run:
```bash
pytest tests/unit/test_wiki_report_contract.py -v
```
Expected: all tests pass (count: ~21).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_wiki_report_contract.py
git commit -m "$(cat <<'EOF'
test(wiki): contract validator unit tests

Covers:
  - Schema metadata (version, required/optional paths, severities)
  - Validator happy paths (minimal valid, all-fields-valid)
  - synthesis failures (missing, too short, too long, wrong type)
  - hub_sections failures (missing, empty list, missing summary,
    summary too short/long, non-dict entry)
  - optional-field shape failures (bad severity, bad percentage)
  - Multi-failure collection (no short-circuit on first failure)
  - hub_sections_skeleton helper (sorting, missing keys, empty input)

Total: ~21 test cases.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `wiki-report-data` MCP tool — add synthesis_schema + hub_sections skeleton

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py` lines 810-855 (the `wiki_report_data` function)

- [ ] **Step 1: Read the current implementation**

Run:
```bash
sed -n '810,855p' shared-vault/skills/ingest/scripts/mcp/wiki_tools.py
```
Confirm the function returns `{"success": True, **result}` where result has keys `stats`, `hubs`, `pages`, `connections`, `consolidation`, `portfolio`.

- [ ] **Step 2: Add the schema import + skeleton derivation**

Use Edit on `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`. Find:

```python
            result = {
                "stats": data.stats,
                "hubs": data.hubs,
                "pages": data.pages,
                "connections": data.connections,
                "consolidation": getattr(data, "consolidation", []),
                "portfolio": data.portfolio,
            }
            return json.dumps({"success": True, **result}, indent=2, default=str)
```

Replace with:

```python
            from skills.ingest.scripts.wiki_report_contract import SYNTHESIS_SCHEMA, hub_sections_skeleton
            result = {
                "stats": data.stats,
                "hubs": data.hubs,
                "hub_sections": hub_sections_skeleton(data.hubs),
                "pages": data.pages,
                "connections": data.connections,
                "consolidation": getattr(data, "consolidation", []),
                "portfolio": data.portfolio,
                "synthesis_schema": SYNTHESIS_SCHEMA,
            }
            return json.dumps({"success": True, **result}, indent=2, default=str)
```

(Imports inside the function are fine here — the rest of `wiki_report_data` follows the same pattern.)

- [ ] **Step 3: Verify the modified function imports cleanly + returns the new fields**

Run:
```bash
python3 << 'PY'
import sys, json
sys.path.insert(0, '.')
sys.path.insert(0, 'shared-vault')
from src.config.paths import get_documents_dir, get_runtime_dir, get_vault_dir, get_compiled_wiki_dir
from skills.ingest.scripts.wiki_report import aggregate_report_data
from skills.ingest.scripts.wiki_report_contract import SYNTHESIS_SCHEMA, hub_sections_skeleton

# Re-create what wiki-report-data does
data = aggregate_report_data(
    wiki_dir=get_compiled_wiki_dir(),
    runtime_wiki_dir=get_runtime_dir() / "wiki",
    portfolio_dir=get_vault_dir() / "portfolio",
    vault_dir=get_vault_dir(),
    documents_dir=get_documents_dir(),
    hub=None,
)
out = {
    "stats": data.stats,
    "hubs": data.hubs,
    "hub_sections": hub_sections_skeleton(data.hubs),
    "portfolio": data.portfolio,
    "synthesis_schema": SYNTHESIS_SCHEMA,
}
assert "synthesis_schema" in out
assert out["synthesis_schema"]["version"] == 1
assert isinstance(out["hub_sections"], list)
assert all("name" in h and "source_count" in h for h in out["hub_sections"])
print(f"OK — schema_version={out['synthesis_schema']['version']}, hubs={len(out['hub_sections'])}")
PY
```
Expected: `OK — schema_version=1, hubs=7` (or whatever the current hub count is).

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/wiki_tools.py
git commit -m "$(cat <<'EOF'
feat(wiki): wiki-report-data returns synthesis_schema + hub_sections skeleton

wiki-report-data now includes two new top-level fields in its response:

  - synthesis_schema: the machine-readable contract from
    wiki_report_contract.SYNTHESIS_SCHEMA. The agent reads this to
    know what fields it must produce in the rich dict.

  - hub_sections: a list-of-dicts skeleton derived from the raw hubs
    dict, sorted by source_count descending. Each entry has name +
    source_count filled in; summary/icon/color are left for the agent
    to populate. This closes the existing shape divergence with
    wiki-report-generate which expected a list, not a dict.

The raw "hubs" dict is preserved for backward compatibility — both
shapes coexist in the response.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `wiki-report-generate` — refactor body into sync helper + add validation

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py` lines 923-985 (the `wiki_report_generate` function)

Refactoring the body out lets us unit-test it without the `@mcp.tool` decorator.

- [ ] **Step 1: Read current implementation to map what gets extracted**

Run:
```bash
sed -n '923,985p' shared-vault/skills/ingest/scripts/mcp/wiki_tools.py
```

Note: the async MCP tool body is the candidate for extraction into a sync helper.

- [ ] **Step 2: Refactor — extract helper + add validation**

Use Edit on `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`. Find the entire `wiki_report_generate` function body (the part inside the `async def`):

```python
    @mcp.tool(name="wiki-report-generate", annotations=tool_annotations({"title": "Wiki Report Generate", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def wiki_report_generate(report_json: str = "", style: str = "demo", output_dir: str = "") -> str:
        """Generate Second Brain Report as PDF + HTML from structured report data."""
        metrics.track_tool("wiki_report_generate", skill="ingest")
        try:
            from skills.ingest.scripts.wiki_report_charts import (
                render_hub_distribution,
                render_knowledge_graph,
                render_radar_chart,
            )
            from skills.ingest.scripts.wiki_report_render import render_html, render_pdf
            from skills.ingest.scripts.wiki_report import ReportData
            from src.config.paths import get_documents_dir, get_runtime_dir
            from datetime import date

            report = json.loads(report_json)
```

Replace through to the end of `try` body (just before the `except Exception as exc:` line) with:

```python
    @mcp.tool(name="wiki-report-generate", annotations=tool_annotations({"title": "Wiki Report Generate", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def wiki_report_generate(report_json: str = "", style: str = "demo", output_dir: str = "") -> str:
        """Generate Second Brain Report as PDF + HTML from a validated rich dict.

        Validates input against wiki_report_contract.SYNTHESIS_SCHEMA. Returns a
        structured agent_step_required error if required fields are missing —
        no skeleton fallback per CLAUDE.md rule 1.
        """
        metrics.track_tool("wiki_report_generate", skill="ingest")
        try:
            from skills.ingest.scripts.wiki_report_contract import validate_rich_dict
            report = json.loads(report_json) if report_json else {}

            # Validate against the agent-step contract
            validation = validate_rich_dict(report)
            if not validation.success:
                return json.dumps({
                    "success": False,
                    "error": "agent_step_required",
                    "missing_required": validation.missing_required,
                    "contract_path": "shared-vault/skills/rag/commands/wiki.md#report-action",
                    "hint": "Run /wiki report from inside Claude Code, Codex, Gemini CLI, Cursor, or Copilot. The agent layer is required for editorial synthesis.",
                }, indent=2)

            # Hand off to the sync helper (extractable, testable)
            return _generate_report_html(report, output_dir=output_dir)
```

Keep the `except Exception as exc:` block as it is.

- [ ] **Step 3: Add the `_generate_report_html` sync helper**

In the same file, BEFORE the `register_wiki_tools` function (or in a clearly-marked module-scope helper section near other private helpers), add:

```python
def _generate_report_html(report: dict, output_dir: str = "") -> str:
    """Render rich-dict report to HTML + PDF + sidecar.

    Pre-condition: validate_rich_dict(report).success is True.
    Output path: get_documents_dir()/brain/artifacts/second-brain-report-<YYYY-MM-DD>.html
    Sidecar:     same path + ".meta.yaml" per ADR-723.
    """
    from skills.ingest.scripts.wiki_report_charts import (
        render_hub_distribution,
        render_knowledge_graph,
        render_radar_chart,
    )
    from skills.ingest.scripts.wiki_report_render import render_html, render_pdf
    from skills.ingest.scripts.wiki_report import ReportData
    from src.config.paths import get_documents_dir, get_runtime_dir
    from datetime import date

    # Build a lightweight ReportData for chart rendering — avoids re-scanning wiki pages
    data = ReportData(
        stats=report.get("stats", {}),
        hubs={
            h["name"]: {
                "page_count": 0,
                "source_count": h.get("source_count", 0),
                "word_count": 0,
                "tags": [],
            }
            for h in report.get("hub_sections", [])
            if "name" in h
        },
        pages=[],
        connections=[],
        portfolio=report.get("portfolio", {}),
    )

    # Render charts to runtime asset dir
    chart_dir = get_runtime_dir() / "wiki" / "report-assets"
    chart_dir.mkdir(parents=True, exist_ok=True)
    report["charts"] = {
        "radar":        str(render_radar_chart(data, output_dir=chart_dir)),
        "graph":        str(render_knowledge_graph(data, output_dir=chart_dir)),
        "distribution": str(render_hub_distribution(data, output_dir=chart_dir)),
    }

    # Output path — ADR-723 alignment
    out = Path(output_dir) if output_dir else (get_documents_dir() / "brain" / "artifacts")
    out.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    slug = f"second-brain-report-{today}"

    template_dir = _skill_root / "assets" / "templates"
    html_path = render_html(report, output_path=out / f"{slug}.html", template_dir=template_dir)
    pdf_path = render_pdf(report, output_path=out / f"{slug}.pdf")

    # Sidecar (per ADR-723) is written in Task 5.

    return json.dumps({
        "success": True,
        "pdf_path": str(pdf_path),
        "html_path": str(html_path),
    }, indent=2)
```

(The `_skill_root` symbol already exists in `wiki_tools.py` — see how the original `wiki_report_generate` references `template_dir = _skill_root / "assets" / "templates"`.)

- [ ] **Step 4: Sanity check the file still parses**

Run:
```bash
python3 -c "
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'shared-vault')
from skills.ingest.scripts.mcp import wiki_tools
print('OK — wiki_tools imports cleanly')
"
```
Expected: `OK — wiki_tools imports cleanly`.

- [ ] **Step 5: Verify the validator path with a synthetic invalid dict**

Run:
```bash
python3 << 'PY'
import sys, json
sys.path.insert(0, 'shared-vault')
from skills.ingest.scripts.wiki_report_contract import validate_rich_dict

# Empty dict → should produce agent_step_required-style failures
result = validate_rich_dict({})
print(f"Valid? {result.success}")
print(f"Missing: {result.missing_required}")
assert not result.success
assert "synthesis" in result.missing_required
assert "hub_sections" in result.missing_required
print("OK — validation rejects empty dict")
PY
```
Expected: validation rejects with `synthesis` and `hub_sections` in `missing_required`.

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/wiki_tools.py
git commit -m "$(cat <<'EOF'
feat(wiki): wiki-report-generate validates rich dict + helper extraction

- Extract HTML/PDF rendering logic into _generate_report_html() module-
  scope helper. Makes the rendering pipeline directly callable from
  tests, without the @mcp.tool decorator wrapper.

- wiki-report-generate now validates input against the contract
  (validate_rich_dict from wiki_report_contract). On failure it returns
  the structured agent_step_required error pointing at the slash-
  command docs and naming every missing field — no HTML/PDF is
  written. CLAUDE.md rule 1: fail loud, no degraded fallback.

- Output path moves from get_documents_dir()/reports/ to
  get_documents_dir()/brain/artifacts/ per ADR-723. The hub directory
  ("brain") plus artifacts/ subdir matches the ADR-723 canonical layout.

Sidecar writing (the .meta.yaml file required by ADR-723) lands in a
follow-on task in this same series.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Sidecar generation (ADR-723 alignment)

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py` — `_generate_report_html` (added in Task 4)

- [ ] **Step 1: Add sidecar writing inside `_generate_report_html`**

Use Edit. Find inside `_generate_report_html`:

```python
    html_path = render_html(report, output_path=out / f"{slug}.html", template_dir=template_dir)
    pdf_path = render_pdf(report, output_path=out / f"{slug}.pdf")

    # Sidecar (per ADR-723) is written in Task 5.

    return json.dumps({
        "success": True,
        "pdf_path": str(pdf_path),
        "html_path": str(html_path),
    }, indent=2)
```

Replace with:

```python
    html_path = render_html(report, output_path=out / f"{slug}.html", template_dir=template_dir)
    pdf_path = render_pdf(report, output_path=out / f"{slug}.pdf")

    # Sidecar per ADR-723 — lives next to the HTML
    sidecar_path = _write_report_sidecar(
        html_path=html_path,
        slug=slug,
        stats=report.get("stats", {}),
        today=today,
    )

    return json.dumps({
        "success": True,
        "pdf_path": str(pdf_path),
        "html_path": str(html_path),
        "sidecar_path": str(sidecar_path),
    }, indent=2)
```

- [ ] **Step 2: Add the `_write_report_sidecar` helper above `_generate_report_html`**

Use Edit. Insert immediately above the `def _generate_report_html(report: dict, ...)` line:

```python
def _write_report_sidecar(*, html_path: Path, slug: str, stats: dict, today: str) -> Path:
    """Write the ADR-723 sidecar .meta.yaml next to the HTML report.

    The sidecar describes the artifact (slug, title, hub, source, tags,
    created_at) so the ADR-723 Browse pages ViewMode can index it.
    """
    from datetime import datetime, timezone

    sidecar_path = html_path.with_suffix(html_path.suffix + ".meta.yaml")
    n_pages = stats.get("total_pages", stats.get("pages", 0))
    n_hubs = stats.get("total_hubs", stats.get("hubs", 0))
    n_sources = stats.get("total_sources", stats.get("sources", 0))
    n_words = stats.get("total_words", stats.get("words", 0))
    n_cross = stats.get("total_cross_refs", stats.get("cross_refs", 0))

    sidecar_yaml = f"""---
slug: {slug}
title: "Second Brain Intelligence Report — {today}"
kind: generated
hub: brain
source:
  type: agent-synthesized
  origin: "Augur wiki snapshot — {n_pages} pages across {n_hubs} hubs, {n_sources} sources, {n_words} words, {n_cross} cross-references"
  generator: "shared-vault/skills/ingest/scripts/mcp/wiki_tools.py + agent-step synthesis per /wiki report"
tags: [wiki, report, second-brain]
created_at: {datetime.now(timezone.utc).isoformat()}
notes: ""
---
"""
    sidecar_path.write_text(sidecar_yaml, encoding="utf-8")
    return sidecar_path
```

Also add the import at the top of the function-region (if `Path` and `datetime` aren't already imported at module scope, the in-function `from ... import` covers it).

- [ ] **Step 3: Verify the sidecar writer can be called standalone**

Run:
```bash
python3 << 'PY'
import sys, tempfile
from pathlib import Path
sys.path.insert(0, 'shared-vault')

# Import the helper from wiki_tools (need to import the module first; the
# helper is at module scope alongside register_wiki_tools).
from skills.ingest.scripts.mcp.wiki_tools import _write_report_sidecar

with tempfile.TemporaryDirectory() as td:
    html_path = Path(td) / "test.html"
    html_path.write_text("<html></html>")
    sidecar = _write_report_sidecar(
        html_path=html_path,
        slug="test-slug",
        stats={"total_pages": 74, "total_hubs": 7, "total_sources": 400, "total_words": 34286, "total_cross_refs": 422},
        today="2026-05-11",
    )
    assert sidecar.exists()
    body = sidecar.read_text()
    assert "slug: test-slug" in body
    assert "kind: generated" in body
    assert "hub: brain" in body
    assert "74 pages across 7 hubs" in body
    print("OK — sidecar written with expected fields")
PY
```
Expected: `OK — sidecar written with expected fields`.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/wiki_tools.py
git commit -m "$(cat <<'EOF'
feat(wiki): _write_report_sidecar — ADR-723 sidecar generation

After rendering HTML + PDF, _generate_report_html now writes a
<slug>.html.meta.yaml sidecar next to the HTML, per ADR-723's artifact
schema (slug, title, kind, hub, source, tags, created_at).

The sidecar exists so ADR-723's Browse pages ViewMode will discover
this artifact automatically once that ADR is implemented. No coupling
to ADR-723 implementation here — the sidecar conforms to the schema
without depending on the page-pipeline runtime.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Template guards — wrap optional sections in `{% if %}`

**Files:**
- Modify: `shared-vault/skills/ingest/assets/templates/report.html.j2`

- [ ] **Step 1: Identify which sections need guards**

Run:
```bash
grep -n "{% for item in report.expertise %}\|{% for pattern in report.patterns %}\|{% for spot in report.blind_spots %}" shared-vault/skills/ingest/assets/templates/report.html.j2
```
Expected: 3 line numbers. Each loop renders nothing when its source list is empty, but the surrounding section/card title still renders. We add a guard so the entire surrounding section is omitted when the list is empty or missing.

- [ ] **Step 2: Guard the Expertise Stack card**

Use Edit. Find:

```
      <!-- Right: expertise stack -->
      <div class="card">
        <div class="card-title">Expertise Stack</div>
        {% for item in report.expertise %}
```

Replace with:

```
      <!-- Right: expertise stack -->
      {% if report.expertise %}
      <div class="card">
        <div class="card-title">Expertise Stack</div>
        {% for item in report.expertise %}
```

Then find the closing `{% endfor %}` immediately following the expertise loop (it'll be just before the `</div>` that closes the expertise card). After that `{% endfor %}`, the existing structure has `</div>` closing the card. Add `{% endif %}` AFTER that closing `</div>`:

```
        {% endfor %}
      </div>
      {% endif %}
```

- [ ] **Step 3: Guard the Patterns column**

Use Edit. Find:

```
      <!-- Patterns -->
      <div>
        <div class="col-title">Patterns Your AI Noticed</div>
        {% for pattern in report.patterns %}
```

Replace with:

```
      <!-- Patterns -->
      {% if report.patterns %}
      <div>
        <div class="col-title">Patterns Your AI Noticed</div>
        {% for pattern in report.patterns %}
```

Find the closing `{% endfor %}` for that loop, then the `</div>` closing the patterns column. Add `{% endif %}` AFTER that `</div>`.

- [ ] **Step 4: Guard the Blind Spots column**

Use Edit. Find:

```
      <!-- Blind Spots -->
      <div>
        <div class="col-title">Blind Spots &amp; Gaps</div>
        {% for spot in report.blind_spots %}
```

Replace with:

```
      <!-- Blind Spots -->
      {% if report.blind_spots %}
      <div>
        <div class="col-title">Blind Spots &amp; Gaps</div>
        {% for spot in report.blind_spots %}
```

Find the closing `{% endfor %}` for that loop, then the `</div>` closing the blind-spots column. Add `{% endif %}` AFTER that `</div>`.

- [ ] **Step 5: Verify the template still parses with Jinja2**

Run:
```bash
python3 << 'PY'
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader("shared-vault/skills/ingest/assets/templates"),
    autoescape=select_autoescape(["html"]),
)
template = env.get_template("report.html.j2")

# Render with minimal-but-valid input — optional sections omitted
minimal_report = {
    "title": "Test", "name": "Tester", "date": "2026-05-11",
    "synthesis": "x" * 200,
    "stats": {"pages": 74, "hubs": 7, "sources": 400, "words": "34,286", "cross_refs": 422},
    "hub_sections": [{"name": "brain", "source_count": 136, "summary": "y" * 100, "icon": "🧠", "color": "#8b5cf6"}],
    "charts": {"radar": "", "graph": "", "distribution": ""},
    "portfolio": {},
}
html = template.render(report=minimal_report)
# Optional sections must NOT appear in output
assert "Expertise Stack" not in html, "expertise card leaked when expertise absent"
assert "Patterns Your AI Noticed" not in html, "patterns column leaked when patterns absent"
assert "Blind Spots" not in html, "blind_spots column leaked when blind_spots absent"
# Required sections MUST appear
assert "Who You Are" in html  # section header, no body — header is unconditional
assert "What Your Brain Contains" in html
print("OK — optional sections correctly hidden when absent")
PY
```
Expected: `OK — optional sections correctly hidden when absent`.

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/ingest/assets/templates/report.html.j2
git commit -m "$(cat <<'EOF'
fix(wiki): template guards on optional report sections

Wrapped three optional sections in {% if %} so they're omitted when
the agent step doesn't supply them (per the tiered-required contract
in wiki_report_contract.SYNTHESIS_SCHEMA):

  - Expertise Stack card (right column of Who-You-Are)
  - Patterns Your AI Noticed (left column of Patterns & Blind Spots)
  - Blind Spots & Gaps (right column of Patterns & Blind Spots)

Renderer test confirms the section chrome no longer leaks when the
optional list is empty or absent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `/wiki report` action documentation

**Files:**
- Modify: `shared-vault/skills/rag/commands/wiki.md`

- [ ] **Step 1: Read current command structure**

Run:
```bash
cat shared-vault/skills/rag/commands/wiki.md
```
Note: the actions list is in section 2, and the action-to-MCP mapping is in section 3.

- [ ] **Step 2: Add `report` to the actions list**

Use Edit. Find:

```
   - `reset` — run a safe clean-slate reset that purges generated wiki pages and compiler state, rebuilds source indexes, reindexes wiki pages, lints, then prepares a bounded concept extraction batch by default
```

Replace with:

```
   - `reset` — run a safe clean-slate reset that purges generated wiki pages and compiler state, rebuilds source indexes, reindexes wiki pages, lints, then prepares a bounded concept extraction batch by default
   - `report` — generate a Second Brain Intelligence Report (HTML + PDF + sidecar artifact)
```

- [ ] **Step 3: Add the action-to-MCP mapping**

Use Edit. Find:

```
   - `reset` -> `wiki-reset`
```

Replace with:

```
   - `reset` -> `wiki-reset`
   - `report` -> three-step agent flow (see ## /wiki report section below)
```

- [ ] **Step 4: Append the `/wiki report` deep-dive section to the end of the file**

Read the current end of the file:
```bash
tail -20 shared-vault/skills/rag/commands/wiki.md
```

Append (use Edit, replace the last line with itself + the new section, or use Write if the file is short):

```markdown

## /wiki report

Generate a Second Brain Intelligence Report from your compiled wiki. The flow is **three steps executed by the AI client agent** (per `docs/superpowers/specs/2026-05-11-wiki-report-agent-step-contract-design.md`):

### Step 1 — Call `wiki-report-data` MCP tool

Read the returned `raw_data` (stats, hubs, hub_sections skeleton, portfolio) and `synthesis_schema`. The schema names every required and optional field the agent must produce.

### Step 2 — Synthesize the editorial fields

The agent reads `raw_data` and produces a **rich dict** combining raw passed-through fields with synthesized editorial content. Required fields:

- `synthesis` — 1-2 sentence cover paragraph (100-400 chars) that captures what the brain reveals: dominant themes, quality posture, overall shape.
- `hub_sections[*].summary` — one-line description per hub (60-200 chars) explaining what content lives there, drawn from each hub's tags and source-count distribution.

Optional fields (rendered when present, skipped when absent):

- `who_you_are.what_you_do` — 2-4 sentence narrative of what the user is building/doing.
- `who_you_are.how_you_think` — 2-4 sentence narrative of cognitive patterns.
- `expertise` — ranked list of `{domain, level, percentage, color}`. Level enum: `Expert | Advanced | Intermediate | Building | Beginner`.
- `patterns` — list of `{title, description}` patterns the agent notices.
- `blind_spots` — list of `{title, description, severity}` gaps. Severity enum: `low | medium | high`.

### Step 3 — Call `wiki-report-generate(rich_dict)` MCP tool

Pass the rich dict (synthesized fields + passed-through stats + portfolio). The MCP tool validates input on entry and:

- **On success**: writes `get_documents_dir()/brain/artifacts/second-brain-report-<YYYY-MM-DD>.html`, the PDF alongside it, and a `.meta.yaml` sidecar per ADR-723. Returns paths.
- **On failure**: returns a structured error `{success: false, error: "agent_step_required", missing_required: [...], contract_path, hint}`. No HTML is written.

### Synthesis examples

**synthesis (cover paragraph):**

> "A 74-page wiki anchored in AI infrastructure (adaptive loops, command surfaces, brain control plane) with strong career positioning in AI-transformation leadership. 422 cross-references across 74 pages, 5.7 outgoing links per page on average — densely connected. 100% quality-passing, zero stale or orphan content."

**hub_sections[*].summary (per-hub one-liner):**

| Hub | Example summary |
|---|---|
| `brain` | "Control plane for advisor analytics, agent-learning compounding pipeline, architecture review, and observability work." |
| `career` | "AI-transformation and platform-engineering leadership positioning, career advancement strategy, content-operations playbooks." |
| `studio` | "Content idea capture, publishing workflows, brand/campaign/collateral work, agent-learning compounding pipeline." |

**patterns (4-ish suggested):**

| Title | Description shape |
|---|---|
| "Discipline beats velocity" | Reference quality_gate stats; e.g. "{N} pages with 100% quality-passing, zero stale, zero orphan, zero draft pages — disciplined maintenance cadence." |
| "Knowledge compounds at the cross-ref level" | Reference cross_ref + avg_outgoing_links stats. |
| "Founder context dominates capture" | Reference top hubs by content. |
| "Heavy ingest, deliberate compounding" | Reference source-to-page ratio. |

**blind_spots (4-ish suggested, with severity calibrated to gap size):**

| Title | Severity guidance |
|---|---|
| "Life hub underrepresented" | `medium` if life is one of the smallest hubs by page count. |
| "Brain hub: high ingest, lower compounding" | `medium` if source-to-page ratio is much higher than other hubs. |
| "General hub is a catch-all" | `low` if general has < 5 pages. |
| "Cluster pipeline idle" | `low` if cluster_ready_pages > 0 but merge_candidates is small. |

### Failure mode — no agent layer present

If the agent step is skipped (e.g., calling `wiki-report-generate` from a script or daemon without an AI client doing the synthesis), the tool returns:

```json
{
  "success": false,
  "error": "agent_step_required",
  "missing_required": ["synthesis", "hub_sections[0].summary", ...],
  "contract_path": "shared-vault/skills/rag/commands/wiki.md#wiki-report",
  "hint": "Run /wiki report from inside Claude Code, Codex, Gemini CLI, Cursor, or Copilot. The agent layer is required for editorial synthesis."
}
```

No skeleton HTML is written. The CLI/daemon path is intentionally not supported — invoke from an AI client.
```

- [ ] **Step 5: Verify the command file still grep-clean for the new action**

Run:
```bash
grep -n "report" shared-vault/skills/rag/commands/wiki.md | head -10
```
Expected: see entries for the new `report` action.

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/rag/commands/wiki.md
git commit -m "$(cat <<'EOF'
docs(wiki): /wiki report action — 3-step agent flow + synthesis examples

The /wiki report action documents the agent-step contract for AI
clients. Three steps:
  1. agent calls wiki-report-data → gets raw_data + synthesis_schema
  2. agent synthesizes editorial fields per the schema
  3. agent calls wiki-report-generate(rich_dict) → HTML + PDF + sidecar

Section includes example synthesis output for each editorial field
(synthesis, hub summaries, patterns, blind spots) so any client
(Claude Code, Codex, Gemini, Cursor, Copilot) can produce consistent
output without external context.

Failure mode (no agent present) explicitly documented: structured
agent_step_required error, no skeleton HTML.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: End-to-end test — mock rich dict → render → DOM assertions

**Files:**
- Create: `tests/unit/test_wiki_report_e2e.py`

- [ ] **Step 1: Write the e2e test**

Write to `tests/unit/test_wiki_report_e2e.py`:

```python
"""End-to-end test for the wiki report agent-step pipeline.

Skips the LIVE aggregator (which depends on a populated wiki) and skips
the MCP plumbing (which requires an MCP server). Tests _generate_report_html
directly with a hand-built rich dict, then asserts on the resulting HTML.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

# Make the shared-vault skill modules importable
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "shared-vault"))


def _rich_dict() -> dict:
    """A complete, valid rich dict — all required + all optional fields."""
    return {
        "title": "What Your AI Knows About You",
        "name": "Test User",
        "date": "May 11, 2026",
        "synthesis": (
            "A 74-page wiki anchored in AI infrastructure with strong career positioning. "
            "422 cross-references across 74 pages — densely connected. 100% quality-passing."
        ),
        "stats": {
            "pages": 74, "hubs": 7, "sources": 400, "words": "34,286", "cross_refs": 422,
        },
        "hub_sections": [
            {
                "name": "brain", "source_count": 136,
                "summary": "Control plane for advisor analytics, agent-learning compounding pipeline, and observability work.",
                "icon": "🧠", "color": "#8b5cf6",
            },
            {
                "name": "career", "source_count": 119,
                "summary": "AI-transformation leadership positioning, career advancement strategy, content operations.",
                "icon": "📈", "color": "#10b981",
            },
        ],
        "who_you_are": {
            "what_you_do": "Building Augur — local-first AI infrastructure that personalizes AI clients.",
            "how_you_think": "Decision-first; every architectural move gets an ADR. Loop-driven.",
        },
        "expertise": [
            {"domain": "Cross-Client AI Harness", "level": "Expert", "percentage": 95, "color": "#6366f1"},
            {"domain": "ADR-Driven Architecture", "level": "Expert", "percentage": 92, "color": "#8b5cf6"},
        ],
        "patterns": [
            {"title": "Discipline beats velocity", "description": "100% quality-passing across all pages."},
            {"title": "Cross-ref compounding", "description": "5.7 outgoing links per page — densely connected."},
        ],
        "blind_spots": [
            {"title": "Life hub thin", "description": "Only 8 pages — work dominates.", "severity": "medium"},
            {"title": "General hub catch-all", "description": "2 pages, 877 words.", "severity": "low"},
        ],
        "portfolio": {"profile": "", "logo": "", "cover": "", "hub_images": {}},
    }


def _read_html(text_or_path):
    if isinstance(text_or_path, Path):
        return text_or_path.read_text(encoding="utf-8")
    return text_or_path


def _strip_html(html: str) -> str:
    """Strip HTML tags, return visible text for token-level assertions."""
    text = re.sub(r"<style.*?</style>", "", html, flags=re.DOTALL)
    text = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def test_validator_rejects_empty_dict():
    """Top-level integration: invalid input → agent_step_required error."""
    from skills.ingest.scripts.wiki_report_contract import validate_rich_dict
    result = validate_rich_dict({})
    assert not result.success
    assert "synthesis" in result.missing_required
    assert "hub_sections" in result.missing_required


def test_full_rich_dict_renders_all_sections():
    """A complete rich dict should produce HTML containing every section's content."""
    from skills.ingest.scripts.mcp.wiki_tools import _generate_report_html

    with tempfile.TemporaryDirectory() as td:
        result_json = _generate_report_html(_rich_dict(), output_dir=td)
        result = json.loads(result_json)
        assert result["success"], f"render failed: {result}"

        html_path = Path(result["html_path"])
        assert html_path.exists()
        html = html_path.read_text(encoding="utf-8")
        text = _strip_html(html)

        # Cover content
        assert "What Your AI Knows About You" in text
        assert "Test User" in text
        assert "May 11, 2026" in text
        assert "A 74-page wiki anchored" in text  # synthesis paragraph

        # Stats bar
        assert "74" in text  # pages
        assert "7" in text   # hubs
        assert "400" in text # sources

        # Who You Are
        assert "Building Augur" in text
        assert "Decision-first" in text

        # Expertise stack
        assert "Cross-Client AI Harness" in text
        assert "Expert" in text

        # Hub sections
        assert "brain" in text
        assert "Control plane for advisor analytics" in text  # hub summary
        assert "career" in text
        assert "AI-transformation leadership" in text

        # Patterns
        assert "Discipline beats velocity" in text
        assert "100% quality-passing" in text

        # Blind spots
        assert "Life hub thin" in text
        assert "medium" not in text  # severity isn't rendered as a label — it's only on a CSS class
        # But check the title is present:
        assert "General hub catch-all" in text


def test_minimal_rich_dict_renders_no_optional_sections():
    """Minimal valid dict → HTML has cover + hub cards but no optional section content."""
    from skills.ingest.scripts.mcp.wiki_tools import _generate_report_html

    minimal = {
        "title": "Minimal", "name": "X", "date": "2026-05-11",
        "synthesis": "Synthesis " + "x" * 100,
        "stats": {"pages": 1, "hubs": 1, "sources": 1, "words": "1", "cross_refs": 0},
        "hub_sections": [{
            "name": "brain", "source_count": 1,
            "summary": "Summary " + "y" * 60,
            "icon": "🧠", "color": "#8b5cf6",
        }],
        "portfolio": {"profile": "", "logo": "", "cover": "", "hub_images": {}},
    }

    with tempfile.TemporaryDirectory() as td:
        result_json = _generate_report_html(minimal, output_dir=td)
        result = json.loads(result_json)
        assert result["success"], f"render failed: {result}"

        html = Path(result["html_path"]).read_text(encoding="utf-8")
        text = _strip_html(html)

        # Required content present
        assert "Synthesis " in text
        assert "Summary " in text

        # Optional sections OMITTED (no chrome leaked)
        assert "Expertise Stack" not in text, "expertise card chrome leaked"
        assert "Patterns Your AI Noticed" not in text, "patterns column chrome leaked"
        assert "Blind Spots" not in text, "blind_spots column chrome leaked"


def test_sidecar_yaml_written_alongside_html():
    """ADR-723 sidecar must exist next to HTML with required fields."""
    from skills.ingest.scripts.mcp.wiki_tools import _generate_report_html

    with tempfile.TemporaryDirectory() as td:
        result_json = _generate_report_html(_rich_dict(), output_dir=td)
        result = json.loads(result_json)
        sidecar_path = Path(result["sidecar_path"])
        assert sidecar_path.exists()

        body = sidecar_path.read_text()
        # ADR-723 required sidecar fields
        assert "slug:" in body
        assert "kind: generated" in body
        assert "hub: brain" in body
        assert "type: agent-synthesized" in body
        assert "tags: [wiki, report, second-brain]" in body
```

- [ ] **Step 2: Run the e2e tests**

Run:
```bash
pytest tests/unit/test_wiki_report_e2e.py -v
```
Expected: all 4 tests pass.

- [ ] **Step 3: Run BOTH test files together**

Run:
```bash
pytest tests/unit/test_wiki_report_contract.py tests/unit/test_wiki_report_e2e.py -v
```
Expected: all tests green (~25 total).

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_wiki_report_e2e.py
git commit -m "$(cat <<'EOF'
test(wiki): end-to-end test for the rich-dict render pipeline

Four scenarios:
  - Validator rejects empty dict (integration sanity check)
  - Full rich dict produces HTML containing every section's content
    (cover synthesis, stats bar, Who You Are, Expertise Stack, hub
    summaries, patterns, blind spots)
  - Minimal valid dict produces HTML with required content only —
    optional sections (Expertise Stack, Patterns, Blind Spots) are
    omitted, not rendered as empty chrome
  - ADR-723 sidecar yaml is written alongside the HTML with required
    fields (slug, kind, hub, source.type, tags)

Tests call _generate_report_html directly — bypasses the @mcp.tool
async wrapper. No MCP server required.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Final integration verification + push

**Files:** none — verification only.

- [ ] **Step 1: Run the complete test suite for this feature**

```bash
pytest tests/unit/test_wiki_report_contract.py tests/unit/test_wiki_report_e2e.py -v --tb=short
```
Expected: all tests green.

- [ ] **Step 2: Verify the live wiki-report-data → wiki-report-generate chain produces real output (manual integration)**

Run from inside an AI client session OR via a direct python invocation that includes the synthesis step:

```bash
python3 << 'PY'
import sys, json, tempfile
from datetime import date
sys.path.insert(0, '.')
sys.path.insert(0, 'shared-vault')

from src.config.paths import get_documents_dir, get_runtime_dir, get_vault_dir, get_compiled_wiki_dir
from skills.ingest.scripts.wiki_report import aggregate_report_data
from skills.ingest.scripts.wiki_report_contract import SYNTHESIS_SCHEMA, hub_sections_skeleton, validate_rich_dict
from skills.ingest.scripts.mcp.wiki_tools import _generate_report_html

# Step 1: aggregate
data = aggregate_report_data(
    wiki_dir=get_compiled_wiki_dir(),
    runtime_wiki_dir=get_runtime_dir() / "wiki",
    portfolio_dir=get_vault_dir() / "portfolio",
    vault_dir=get_vault_dir(),
    documents_dir=get_documents_dir(),
    hub=None,
)

# Step 2: agent synthesizes (here: a minimal hand-crafted dict)
hub_sections = hub_sections_skeleton(data.hubs)
for h in hub_sections:
    h["summary"] = f"Hub '{h['name']}' has {h['source_count']} sources across compiled wiki pages."
    h["icon"] = "📁"
    h["color"] = "#6366f1"

stats = data.stats
report = {
    "title": "Integration Smoke Test",
    "name": "Test",
    "date": date.today().strftime("%B %-d, %Y"),
    "synthesis": (
        f"A {stats.get('total_pages', 0)}-page wiki across {stats.get('total_hubs', 0)} hubs "
        f"with {stats.get('total_cross_refs', 0)} cross-references — integration smoke test."
    ),
    "stats": {
        "pages": stats.get("total_pages", 0),
        "hubs": stats.get("total_hubs", 0),
        "sources": stats.get("total_sources", 0),
        "words": f"{stats.get('total_words', 0):,}",
        "cross_refs": stats.get("total_cross_refs", 0),
    },
    "hub_sections": hub_sections,
    "portfolio": data.portfolio,
}

# Validate
v = validate_rich_dict(report)
assert v.success, f"validation failed: {v.missing_required}"

# Step 3: render
with tempfile.TemporaryDirectory() as td:
    result = json.loads(_generate_report_html(report, output_dir=td))
    assert result["success"]
    html_path = result["html_path"]
    print(f"OK — integration produced {html_path}")
    print(f"     stats: {report['stats']}")
PY
```
Expected: `OK — integration produced /tmp/.../second-brain-report-2026-05-11.html`.

- [ ] **Step 3: Verify the agent_step_required error fires on invalid input**

```bash
python3 << 'PY'
import sys, json, tempfile
sys.path.insert(0, '.')
sys.path.insert(0, 'shared-vault')

# Build the validator inline (skipping the MCP async wrapper) — same flow
# but exercising the validator-rejects path
from skills.ingest.scripts.wiki_report_contract import validate_rich_dict

invalid = {"synthesis": "too short", "hub_sections": []}
v = validate_rich_dict(invalid)
assert not v.success
print(f"OK — invalid input rejected. missing: {v.missing_required}")
PY
```
Expected: `OK — invalid input rejected. missing: ['synthesis', 'hub_sections']`.

- [ ] **Step 4: Push to origin**

```bash
git push origin main 2>&1 | tail -3
```
Expected: push succeeds.

- [ ] **Step 5: Final summary commit (optional — only if a follow-on cleanup is needed)**

If anything turned up during integration (a missed import, a leftover broken file path), add a small follow-on cleanup commit. Otherwise, the feature is complete — no extra commit needed.

---

## Self-Review Notes

**Spec coverage:**

| Spec section | Implementing task |
|---|---|
| §3 Decision summary (3-step pipeline) | Tasks 3 + 4 + 5 (data → generate → sidecar) |
| §4 Contract: rich dict shape | Task 1 (contract module) |
| §4.1 Tier semantics | Task 1 (validator), Task 6 (template guards) |
| §4.2 Failure mode | Task 4 (validation returns structured error) |
| §5 Contract surface 1: synthesis_schema in wiki-report-data | Task 3 |
| §6 Contract surface 2: /wiki report action | Task 7 |
| §7 Contract surface 3: validation in wiki-report-generate | Task 4 |
| §8 ADR-723 alignment (path + sidecar) | Task 5 |
| §9 Implementation order (5 checkpoints) | Tasks 1+2 (C1, C2 contract); Task 3 (C1 wiki-report-data); Task 4 (C2 generate); Task 6 (C3 template); Task 7 (C4 command); Task 8 (C5 e2e) |
| §10 Edge cases | Tests in Tasks 2 and 8 cover empty hubs, missing fields, invalid severity, etc. |

All spec sections implemented. No gaps.

**Type consistency:**

- `validate_rich_dict(report: dict) → ValidationResult` — same signature in Tasks 1, 2, 4, 8
- `hub_sections_skeleton(hubs: dict) → list[dict]` — same signature in Tasks 1, 2, 3
- `_generate_report_html(report: dict, output_dir: str) → str (JSON)` — same in Tasks 4, 5, 8
- `_write_report_sidecar(*, html_path, slug, stats, today) → Path` — same in Task 5
- Field names: `synthesis`, `hub_sections`, `who_you_are.what_you_do`, `who_you_are.how_you_think`, `expertise`, `patterns`, `blind_spots`, `severity`, `level` — used identically across tasks.

**Placeholder scan:**

- No "TBD", "TODO", "implement later", "fill in details"
- Every step has actual code or an actual command
- Every test step has actual assertion code
- Synthesis examples in Task 7 are real prose, not "add examples here"

No placeholders.

**Risk areas:**

- Task 4 is the largest single edit (refactor + helper extraction). If the extraction misses an import or breaks the existing chart rendering, Task 9's integration smoke test catches it.
- Task 6 (template guards) modifies a 700+ line Jinja template. The render-test step (Task 6 Step 5) validates the template parses and the optional sections are correctly hidden.
- The existing `wiki-report-data` returns BOTH `hubs` (dict) and now `hub_sections` (list). This is intentional during the transition — downstream consumers that expected `hubs` still work; new consumers use `hub_sections`. A future cleanup can drop `hubs` once nothing reads it.
