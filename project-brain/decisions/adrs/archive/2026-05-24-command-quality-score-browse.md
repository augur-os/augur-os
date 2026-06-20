# Command Quality Score in Browse — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every Augur command a docs+wiring health score (0-100, tier A–F) that shows on its Browse card and is filterable by score, with a side `KPI ✓/✗` chip on the command-KPI-tested commands.

**Architecture:** A new pure library scorer `src/lib/command_scorer.py` (mirrors `src/lib/skill_scorer.py`) computes per-command scores from the command `.md` (docs) and `capability_exposure.yaml` (wiring), plus a best-effort KPI overlay read from the command-KPI aggregate JSON. `browse/index.py` enriches served command items with the score (a sibling of the existing `_populate_skill_enrichment`). The dashboard reuses the existing `qualityTier` badge/detail/sort/tag-filter that skills already use; the only new UI is a KPI chip and a commands-view filter key.

**Tech Stack:** Python 3.11+ (`src.config.paths`, `src.plugins.command_discovery`, PyYAML), Next.js/TypeScript dashboard (existing Browse components). Tests via the repo `pytest tests/` runner and the managed pytest wrapper.

---

## File Structure

- **Create** `src/lib/command_scorer.py` — pure scorer: `score_command`, `score_all_commands`, docs/wiring sub-scorers, tier mapping, KPI overlay. One responsibility: turn a command into a health score.
- **Create** `tests/test_command_scorer.py` — unit tests for the scorer (repo-root test, like `tests/test_adr_utils.py`).
- **Modify** `src/mcp/augur_framework/tools/infrastructure/browse/index.py` — add `_populate_command_enrichment` + `_get_command_enrichment` cache and a `category == "commands"` merge branch (mirror the skills path at lines 1137-1141 / 1177-1181).
- **Modify** `apps/dashboard/components/shared/BrowseCard.tsx` — render a `KPI ✓/✗` chip when `metadata.kpiStatus` is `pass`/`fail` (next to the existing `qualityTier` badge at ~line 313).
- **Modify** `apps/dashboard/components/shared/BrowseDetailPanel.tsx` — add docs/wiring/KPI breakdown rows under the existing tier+score display (~line 1016).
- **Modify** `apps/dashboard/app/(views)/browse/useBrowseState.ts` — add `case "commands": return "qualityTier";` to the `tagKey` switch (~line 1291) so the commands view gets the score tag-filter.

---

## Task 1: Command scorer — docs dimension

**Files:**
- Create: `src/lib/command_scorer.py`
- Test: `tests/test_command_scorer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_command_scorer.py
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_command_scorer.py::test_docs_score_rewards_rich_command_doc -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.lib.command_scorer'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/lib/command_scorer.py
"""Command quality scorer — docs+wiring health used by Browse enrichment.

Plain library module (mirrors src/lib/skill_scorer.py). No LLM calls; pure
functions over the command .md and capability_exposure policy. Process-cached.
"""
from __future__ import annotations

import re
from typing import Any

import yaml


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        fm = {}
    return (fm if isinstance(fm, dict) else {}), parts[2]


def score_docs(md_text: str) -> float:
    """Score a command's documentation 0-100 from its SKILL/command .md text."""
    fm, body = _split_frontmatter(md_text)
    desc = str(fm.get("description", "") or "")
    desc_words = len(desc.split()) if desc.strip() else 0
    lines = body.strip().split("\n") if body.strip() else []
    body_lines = len(lines)
    sections = len(re.findall(r"^#{1,3}\s+", body, re.MULTILINE))

    desc_score = 25 if desc_words >= 20 else 15 if desc_words >= 10 else 8 if desc_words >= 5 else 3 if desc_words else 0
    body_score = 30 if body_lines >= 60 else 22 if body_lines >= 30 else 15 if body_lines >= 12 else 5 if body_lines >= 4 else 0
    section_score = 20 if sections >= 4 else 14 if sections >= 2 else 8 if sections >= 1 else 0

    has_usage = bool(re.search(r"(?i)^#{1,3}\s+(usage|dispatch|arguments?)", body, re.MULTILINE))
    has_examples = bool(re.search(r"(?i)(example|```)", body))
    has_contract = bool(re.search(r"(?i)(argument|\$ARGUMENTS|--help|sub-?command)", body))
    richness = sum([10 if has_usage else 0, 10 if has_examples else 0, 5 if has_contract else 0])

    return float(min(100, desc_score + body_score + section_score + richness))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_command_scorer.py::test_docs_score_rewards_rich_command_doc -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/command_scorer.py tests/test_command_scorer.py
git commit -m "feat(command-scorer): docs dimension"
```

## Task 2: Command scorer — wiring dimension

**Files:**
- Modify: `src/lib/command_scorer.py`
- Test: `tests/test_command_scorer.py`

- [ ] **Step 1: Write the failing test**

```python
def test_wiring_score_from_capability_exposure():
    from src.lib.command_scorer import score_wiring

    full = {"classification_status": "approved", "export_to": ["cli", "agents-md"]}
    missing = None
    unapproved = {"classification_status": "draft", "export_to": []}

    assert score_wiring(full, file_exists=True) == 100.0
    assert score_wiring(missing, file_exists=True) < 40.0
    assert score_wiring(unapproved, file_exists=True) < score_wiring(full, file_exists=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_command_scorer.py::test_wiring_score_from_capability_exposure -v`
Expected: FAIL — `ImportError: cannot import name 'score_wiring'`.

- [ ] **Step 3: Write minimal implementation** (append to `src/lib/command_scorer.py`)

```python
def score_wiring(entry: dict[str, Any] | None, *, file_exists: bool) -> float:
    """Score a command's wiring 0-100 from its capability_exposure entry + file presence.

    Signals: capability entry present (40), classification approved (25),
    non-empty export_to (20), command file exists (15).
    """
    score = 0.0
    if entry is not None:
        score += 40.0
        if str(entry.get("classification_status", "")).lower() == "approved":
            score += 25.0
        export_to = entry.get("export_to") or []
        if isinstance(export_to, list) and export_to:
            score += 20.0
    if file_exists:
        score += 15.0
    return float(min(100.0, score))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_command_scorer.py::test_wiring_score_from_capability_exposure -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/command_scorer.py tests/test_command_scorer.py
git commit -m "feat(command-scorer): wiring dimension"
```

## Task 3: Command scorer — tier mapping + overall score

**Files:**
- Modify: `src/lib/command_scorer.py`
- Test: `tests/test_command_scorer.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_command_scorer.py::test_overall_blends_docs_and_wiring_and_maps_tier -v`
Expected: FAIL — `ImportError: cannot import name 'blend_score'`.

- [ ] **Step 3: Write minimal implementation** (append to `src/lib/command_scorer.py`)

```python
DOCS_WEIGHT = 0.60
WIRING_WEIGHT = 0.40


def blend_score(docs: float, wiring: float) -> float:
    return round(docs * DOCS_WEIGHT + wiring * WIRING_WEIGHT, 1)


def score_to_tier(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 45:
        return "C"
    if score >= 25:
        return "D"
    return "F"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_command_scorer.py::test_overall_blends_docs_and_wiring_and_maps_tier -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/command_scorer.py tests/test_command_scorer.py
git commit -m "feat(command-scorer): blend + tier mapping"
```

## Task 4: Command scorer — KPI overlay (best-effort, no skill import)

**Files:**
- Modify: `src/lib/command_scorer.py`
- Test: `tests/test_command_scorer.py`

- [ ] **Step 1: Write the failing test**

```python
def test_kpi_status_from_aggregate(tmp_path):
    import json
    from src.lib.command_scorer import kpi_status_map

    reports = tmp_path / "evals" / "commands" / "reports"
    reports.mkdir(parents=True)
    (reports / "run-aggregate.json").write_text(json.dumps({
        "by_command": {
            "keep": {"total": 6, "pass": 6, "warn": 0, "fail": 0},
            "ask": {"total": 4, "pass": 3, "warn": 0, "fail": 1},
        }
    }), encoding="utf-8")

    statuses = kpi_status_map(documents_dir=tmp_path)

    assert statuses["keep"] == "pass"
    assert statuses["ask"] == "fail"
    assert statuses.get("discover", "untested") == "untested"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_command_scorer.py::test_kpi_status_from_aggregate -v`
Expected: FAIL — `ImportError: cannot import name 'kpi_status_map'`.

- [ ] **Step 3: Write minimal implementation** (append to `src/lib/command_scorer.py`)

```python
import json
from pathlib import Path


def kpi_status_map(*, documents_dir: Path | None = None) -> dict[str, str]:
    """Best-effort per-command KPI status from the latest command-KPI aggregate.

    Returns {command_id: 'pass'|'fail'}. Commands absent from the map are
    'untested'. Never raises — a missing/broken aggregate yields {}.
    """
    if documents_dir is None:
        from src.config.paths import get_documents_dir
        documents_dir = get_documents_dir()
    reports = Path(documents_dir) / "evals" / "commands" / "reports"
    try:
        aggregates = sorted(reports.glob("*-aggregate.json"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return {}
    if not aggregates:
        return {}
    try:
        data = json.loads(aggregates[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, str] = {}
    for cmd, stats in (data.get("by_command") or {}).items():
        if not isinstance(stats, dict) or int(stats.get("total") or 0) <= 0:
            continue
        out[str(cmd)] = "fail" if int(stats.get("fail") or 0) > 0 else "pass"
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_command_scorer.py::test_kpi_status_from_aggregate -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/command_scorer.py tests/test_command_scorer.py
git commit -m "feat(command-scorer): KPI overlay"
```

## Task 5: Command scorer — `score_command` + `score_all_commands` (cached)

**Files:**
- Modify: `src/lib/command_scorer.py`
- Test: `tests/test_command_scorer.py`

- [ ] **Step 1: Write the failing test**

```python
def test_score_all_commands_real_data():
    from src.lib.command_scorer import score_all_commands

    result = score_all_commands()
    cmds = result["commands"]
    assert len(cmds) >= 7
    sample = cmds[0]
    assert set(sample) >= {"id", "score", "tier", "dimensions", "kpiStatus"}
    assert 0.0 <= sample["score"] <= 100.0
    assert sample["tier"] in {"A", "B", "C", "D", "F"}
    assert set(sample["dimensions"]) == {"docs", "wiring"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_command_scorer.py::test_score_all_commands_real_data -v`
Expected: FAIL — `ImportError: cannot import name 'score_all_commands'`.

- [ ] **Step 3: Write minimal implementation** (append to `src/lib/command_scorer.py`)

```python
import time as _time

from src.config.paths import get_project_root

_CACHE: dict[str, Any] = {}
_CACHE_TS: float = 0.0
_CACHE_TTL = 60.0


def _load_capability_command_entries() -> dict[str, dict[str, Any]]:
    path = get_project_root() / "config" / "system" / "capability_exposure.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    caps = data.get("capabilities", data) if isinstance(data, dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for key, val in (caps.items() if isinstance(caps, dict) else []):
        if isinstance(key, str) and key.startswith("command:") and isinstance(val, dict):
            out[key.split("command:", 1)[1].rstrip(":")] = val
    return out


def score_command(cmd: Any, entry: dict[str, Any] | None, kpi: dict[str, str]) -> dict[str, Any]:
    path = getattr(cmd, "path", None)
    md_text = ""
    file_exists = False
    if path is not None:
        try:
            md_text = Path(path).read_text(encoding="utf-8")
            file_exists = True
        except OSError:
            file_exists = False
    docs = score_docs(md_text) if md_text else (15.0 if getattr(cmd, "description", "") else 0.0)
    wiring = score_wiring(entry, file_exists=file_exists)
    overall = blend_score(docs, wiring)
    return {
        "id": cmd.id,
        "score": overall,
        "tier": score_to_tier(overall),
        "dimensions": {"docs": round(docs, 1), "wiring": round(wiring, 1)},
        "kpiStatus": kpi.get(cmd.id, "untested"),
    }


def score_all_commands() -> dict[str, Any]:
    global _CACHE, _CACHE_TS
    if _CACHE and _time.time() - _CACHE_TS < _CACHE_TTL:
        return _CACHE
    from src.plugins.command_discovery import discover_commands

    entries = _load_capability_command_entries()
    kpi = kpi_status_map()
    scored = []
    for cmd in discover_commands():
        try:
            scored.append(score_command(cmd, entries.get(cmd.id), kpi))
        except Exception:  # noqa: BLE001 — a bad command must not break the catalog
            continue
    _CACHE = {"commands": scored}
    _CACHE_TS = _time.time()
    return _CACHE
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_command_scorer.py::test_score_all_commands_real_data -v`
Expected: PASS.

- [ ] **Step 5: Real-data sanity check**

Run:
```bash
.venv/bin/python -c 'import sys; sys.path.insert(0,".");
from src.lib.command_scorer import score_all_commands; import collections;
c=score_all_commands()["commands"];
print("commands:", len(c));
print("tiers:", dict(collections.Counter(x["tier"] for x in c)))'
```
Expected: a sane non-degenerate tier spread (not all-F, not all-A), count ≥ 100.

- [ ] **Step 6: Commit**

```bash
git add src/lib/command_scorer.py tests/test_command_scorer.py
git commit -m "feat(command-scorer): score_command + cached score_all_commands"
```

## Task 6: Browse enrichment for commands

**Files:**
- Modify: `src/mcp/augur_framework/tools/infrastructure/browse/index.py`
- Test: extend `tests/test_command_scorer.py` (enrichment helper is thin; cover via the merge contract)

- [ ] **Step 1: Add the command enrichment cache + populate (mirror skills)**

Add near `_populate_skill_enrichment` (after line ~133):

```python
_command_enrichment_cache: dict[str, dict[str, str]] = {}
_command_enrichment_ts: float = 0.0
_command_enrichment_populating = False


def _populate_command_enrichment() -> None:
    global _command_enrichment_cache, _command_enrichment_ts, _command_enrichment_populating
    enrichment: dict[str, dict[str, str]] = {}
    try:
        from src.lib.command_scorer import score_all_commands

        for c in score_all_commands().get("commands", []):
            enrichment[c["id"]] = {
                "qualityTier": str(c["tier"]),
                "qualityScore": str(c["score"]),
                "kpiStatus": str(c.get("kpiStatus", "untested")),
                "docsScore": str(c["dimensions"]["docs"]),
                "wiringScore": str(c["dimensions"]["wiring"]),
            }
    except Exception:
        pass
    _command_enrichment_cache = enrichment
    _command_enrichment_ts = _time.time()
    _command_enrichment_populating = False


def _get_command_enrichment() -> dict[str, dict[str, str]]:
    global _command_enrichment_populating
    if _command_enrichment_cache and _time.time() - _command_enrichment_ts < _SKILL_ENRICHMENT_TTL:
        return _command_enrichment_cache
    if not _command_enrichment_populating:
        _command_enrichment_populating = True
        threading.Thread(target=_populate_command_enrichment, daemon=True).start()
    return _command_enrichment_cache
```

- [ ] **Step 2: Wire the merge branch (mirror skills at line ~1139)**

Change:
```python
    skill_enrichment: dict[str, dict[str, str]] = {}
    if category == "skills":
        skill_enrichment = _get_skill_enrichment()
```
to also cover commands (commands key by `id`):
```python
    skill_enrichment: dict[str, dict[str, str]] = {}
    if category == "skills":
        skill_enrichment = _get_skill_enrichment()
    elif category == "commands":
        skill_enrichment = _get_command_enrichment()
```
The existing merge at line ~1177 uses `name`; ensure command entries match by `id`. Update the lookup key in the merge block to fall back to id:
```python
        enrich_key = name if name in skill_enrichment else item_id
        if skill_enrichment and enrich_key in skill_enrichment:
            enrichment = dict(skill_enrichment[enrich_key])
            metadata.update(enrichment)
```

- [ ] **Step 3: Verify enrichment serves for commands**

Run:
```bash
AUGUR_ROOT="$PWD" .venv/bin/python -m src.cli browse-index --category commands 2>/dev/null | \
  .venv/bin/python -c 'import json,sys; d=json.load(sys.stdin);
items=d.get("items", d if isinstance(d,list) else []);
scored=[i for i in items if i.get("metadata",{}).get("qualityTier")];
print("commands with qualityTier:", len(scored), "of", len(items))'
```
Expected: a large fraction of commands carry `qualityTier` (allow for background-cache warmup — re-run once if 0 on a cold cache).

- [ ] **Step 4: Run managed focused pytest**

Run the managed pytest wrapper over `tests/test_command_scorer.py` and the browse tests; expected all pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/augur_framework/tools/infrastructure/browse/index.py
git commit -m "feat(browse): enrich command items with quality score + KPI status"
```

## Task 7: Dashboard — commands score filter + KPI chip + detail breakdown

**Files:**
- Modify: `apps/dashboard/app/(views)/browse/useBrowseState.ts:~1291`
- Modify: `apps/dashboard/components/shared/BrowseCard.tsx:~313`
- Modify: `apps/dashboard/components/shared/BrowseDetailPanel.tsx:~1016`

- [ ] **Step 1: Add the commands tag-filter key**

In `useBrowseState.ts` `tagKey` switch, add above `case "notes"`:
```ts
      case "commands": return "qualityTier";
```

- [ ] **Step 2: Add the KPI chip to BrowseCard**

After the `qualityTier` badge block (~line 318, after the tier badge push), add:
```tsx
  if (m?.kpiStatus === "pass" || m?.kpiStatus === "fail") {
    const pass = m.kpiStatus === "pass";
    badges.push({ key: "kpi", node: (
      <span className={pass
        ? "bg-[var(--accent-success)]/15 text-[var(--accent-success)]"
        : "bg-[var(--accent-danger)]/15 text-[var(--accent-danger)]"}>
        KPI {pass ? "✓" : "✗"}
      </span>
    )});
  }
```
(Match the exact `<span>` class/style pattern already used by the neighboring badges in this file — copy their wrapper element so styling is consistent.)

- [ ] **Step 3: Add the docs/wiring breakdown to BrowseDetailPanel**

After the tier+score display (~line 1023), add rows when present:
```tsx
{detail.docsScore && (
  <div className="text-xs text-[var(--text-secondary)]">docs {detail.docsScore} · wiring {detail.wiringScore}{detail.kpiStatus && detail.kpiStatus !== 'untested' ? ` · KPI ${detail.kpiStatus}` : ''}</div>
)}
```
Ensure `docsScore`, `wiringScore`, `kpiStatus` are threaded into `detail` the same way `qualityScore` is (follow the existing mapping at ~line 961).

- [ ] **Step 4: Build + browser verify (rules 28/31)**

Run `/dev-build` (or `aug` dashboard build) to rebuild, then load the Browse **commands** view in a real browser:
- Command cards show a colored tier badge (A green … F red).
- Tested commands show a `KPI ✓/✗` chip.
- The score tag-filter (A/B/C/D/F chips) filters the command grid.
- Opening a command shows the docs/wiring/KPI breakdown in the detail panel.
Capture a screenshot for the handoff. If the browser is unavailable, say so explicitly — do not report visual success from curl alone.

- [ ] **Step 5: Commit**

```bash
git add "apps/dashboard/app/(views)/browse/useBrowseState.ts" \
  apps/dashboard/components/shared/BrowseCard.tsx \
  apps/dashboard/components/shared/BrowseDetailPanel.tsx
git commit -m "feat(browse-ui): command score filter, KPI chip, detail breakdown

Verified-Browser: localhost:3000 /browse commands view (badges, filter, detail)"
```

## Task 8: Final verification

- [ ] **Step 1: Managed focused pytest** over `tests/test_command_scorer.py` + browse + dashboard jest for the touched components.
- [ ] **Step 2: ruff** on `src/lib/command_scorer.py` and the modified Python.
- [ ] **Step 3: Managed lint scan** — no issues.
- [ ] **Step 4: Real-data proof** — `score_all_commands()` tier distribution + the `browse-index --category commands` count of scored items; paste concrete numbers.
- [ ] **Step 5: Browser proof** — commands Browse view screenshot showing badges + a score filter applied.
- [ ] **Step 6: Merge** the worktree branch to local main (no push unless asked).

---

## Self-Review

**Spec coverage:**
- Docs+wiring score, comparable across all commands → Tasks 1-3, 5. ✓
- KPI as side chip, not blended → Task 4 (`kpiStatus` separate), Task 7 Step 2 (chip). ✓
- Reuse existing badge/detail/sort/tag-filter → Task 6 (qualityTier/qualityScore metadata), Task 7 (filter key + chip + breakdown). ✓
- Rides existing command cards, no new panel (rule 32) → Task 7 modifies existing components only. ✓
- Error handling: scorer never raises into Browse → `score_all_commands` per-command try/except + `_populate_command_enrichment` try/except (Tasks 5, 6). ✓
- Testing + browser verification → Tasks 1-5 unit, Task 7 Step 4 + Task 8 browser. ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code. Tier cutoffs are concrete (A≥80…F<25). ✓

**Type consistency:** `score_docs(text)->float`, `score_wiring(entry, file_exists=)->float`, `blend_score(docs,wiring)->float`, `score_to_tier(score)->str`, `kpi_status_map(documents_dir=)->dict`, `score_command(cmd, entry, kpi)->dict`, `score_all_commands()->{"commands":[...]}` — names/signatures consistent across tasks. Metadata keys (`qualityTier`, `qualityScore`, `kpiStatus`, `docsScore`, `wiringScore`) consistent between Task 6 (Python) and Task 7 (TSX). ✓

**Known integration caveat:** the merge block in `browse/index.py` (~line 1177) currently keys by `name`; Task 6 Step 2 adds an `id` fallback so command items (keyed by id) enrich correctly. Verify the exact variable names (`name`, `item_id`) at implementation time and adjust the fallback to match.
