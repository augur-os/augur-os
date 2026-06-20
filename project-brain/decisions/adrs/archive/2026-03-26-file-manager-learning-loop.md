# File Manager Learning Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add confidence-based routing with a learning feedback loop to the file-manager skill — users review pending files in a card UI with AI summaries, decisions feed back into the scoring engine for increasingly accurate auto-routing.

**Architecture:** A confidence scoring engine (pure pattern matching, no LLM) scores files against past user decisions stored in `decisions.yaml`. The nightly autoloop generates AI summaries for pending files via the LLM-Assisted MCP pattern. The Organize tab's pending section is redesigned as a card list with summaries, confidence badges, and skill dropdowns. Each user decision is recorded and improves future scoring.

**Tech Stack:** Python 3.11+ (scoring engine, decision storage, autoloop), TypeScript/React (dashboard), FastMCP (MCP tools), YAML (decision persistence)

**Spec:** `docs/superpowers/specs/2026-03-26-file-manager-learning-loop-design.md`

---

## File Structure

```
New files:
  skills/file-manager/scripts/confidence.py           # Signal extraction + confidence scoring
  skills/file-manager/scripts/decisions.py             # decisions.yaml load/save/append/compact
  skills/file-manager/augur/tests/test_confidence.py   # Scoring engine tests
  skills/file-manager/augur/tests/test_decisions.py    # Decision storage tests
  src/lib/llm_cli.py                                   # System-level CLI config + spawn

Modified files:
  skills/file-manager/scripts/autoloop.py              # Wire scoring + summary generation
  skills/file-manager/scripts/mcp/tools_organize.py    # New tools: save-pending-files, get-pending-detailed, route-pending-file, get-routing-confidence
  skills/file-manager/augur/dashboard/organize/page.tsx # Redesigned pending section
  skills/document-extractor/scripts/extractor.py:111   # Replace _load_cli_config with shared loader
```

---

## Phase 1: Scoring Engine & Decision Storage

### Task 1: Decision storage — load, save, append, compact

**Files:**
- Create: `skills/file-manager/scripts/decisions.py`
- Create: `skills/file-manager/augur/tests/test_decisions.py`

- [ ] **Step 1: Write failing tests**

```python
# skills/file-manager/augur/tests/test_decisions.py
"""Tests for decision storage."""
from __future__ import annotations

import pytest
from decisions import load_decisions, append_decision, compact_decisions, get_decisions_path


class TestLoadDecisions:
    def test_empty_when_no_file(self, tmp_path):
        decisions = load_decisions(tmp_path / "decisions.yaml")
        assert decisions == []

    def test_loads_existing(self, tmp_path):
        path = tmp_path / "decisions.yaml"
        path.write_text("- file: test.pdf\n  routed_to: health\n")
        decisions = load_decisions(path)
        assert len(decisions) == 1
        assert decisions[0]["routed_to"] == "health"


class TestAppendDecision:
    def test_appends_to_empty(self, tmp_path):
        path = tmp_path / "decisions.yaml"
        append_decision(path, {
            "file": "test.pdf",
            "routed_to": "health",
            "signals": {"filename_keywords": ["test"], "content_keywords": ["medical"]},
            "confidence_at_decision": 0.45,
            "user_override": False,
        })
        decisions = load_decisions(path)
        assert len(decisions) == 1
        assert "timestamp" in decisions[0]

    def test_appends_multiple(self, tmp_path):
        path = tmp_path / "decisions.yaml"
        for i in range(3):
            append_decision(path, {
                "file": f"file{i}.pdf",
                "routed_to": "finance",
                "signals": {},
                "confidence_at_decision": 0.5,
                "user_override": False,
            })
        decisions = load_decisions(path)
        assert len(decisions) == 3


class TestCompactDecisions:
    def test_compacts_old_similar_entries(self, tmp_path):
        path = tmp_path / "decisions.yaml"
        # Write 10 similar decisions (same skill + extension + folder)
        import yaml
        entries = []
        for i in range(10):
            entries.append({
                "file": f"invoice_{i}.pdf",
                "routed_to": "finance",
                "signals": {
                    "filename_keywords": ["invoice"],
                    "content_keywords": ["payment", "amount"],
                    "extension": ".pdf",
                    "source_folder": "~/Desktop",
                    "size_range": "1k-10k",
                },
                "confidence_at_decision": 0.6,
                "user_override": False,
                "timestamp": "2026-01-01T00:00:00",
            })
        path.write_text(yaml.dump(entries))

        compacted = compact_decisions(path, max_entries=0, max_age_days=0)
        assert len(compacted) < 10

    def test_preserves_recent_entries(self, tmp_path):
        path = tmp_path / "decisions.yaml"
        from datetime import datetime
        import yaml
        entries = [{
            "file": "recent.pdf",
            "routed_to": "health",
            "signals": {},
            "confidence_at_decision": 0.7,
            "user_override": False,
            "timestamp": datetime.now().isoformat(),
        }]
        path.write_text(yaml.dump(entries))
        compacted = compact_decisions(path, max_age_days=90)
        assert len(compacted) == 1
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run python -m pytest skills/file-manager/augur/tests/test_decisions.py -v
```

- [ ] **Step 3: Implement decisions.py**

```python
# skills/file-manager/scripts/decisions.py
"""Decision storage for file-manager learning loop.

Stores user routing decisions in flat YAML. Each decision records the file,
target skill, extracted signals, and confidence at time of decision.
Used by the confidence scoring engine to improve future routing.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.config.paths import get_skill_vault_dir


def get_decisions_path() -> Path:
    return get_skill_vault_dir("file-manager") / "decisions.yaml"


def load_decisions(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or get_decisions_path()
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def append_decision(
    path: Path | None,
    decision: dict[str, Any],
) -> None:
    path = path or get_decisions_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    entries = load_decisions(path)
    decision["timestamp"] = datetime.now().isoformat()
    entries.append(decision)

    path.write_text(
        yaml.dump(entries, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def compact_decisions(
    path: Path | None = None,
    max_entries: int = 500,
    max_age_days: int = 90,
) -> list[dict[str, Any]]:
    """Compact old decisions by merging similar entries.

    Groups by (routed_to, extension, source_folder), merges keyword sets,
    keeps count. Returns compacted list. Writes back to file.
    """
    path = path or get_decisions_path()
    entries = load_decisions(path)

    if len(entries) < max_entries:
        return entries

    cutoff = datetime.now() - timedelta(days=max_age_days)
    recent = []
    old = []

    for entry in entries:
        ts = entry.get("timestamp", "")
        try:
            entry_time = datetime.fromisoformat(ts)
            if entry_time > cutoff:
                recent.append(entry)
            else:
                old.append(entry)
        except (ValueError, TypeError):
            old.append(entry)

    # Group old entries by (routed_to, extension, source_folder)
    groups: dict[tuple, dict] = defaultdict(lambda: {
        "count": 0,
        "filename_keywords": set(),
        "content_keywords": set(),
    })

    for entry in old:
        signals = entry.get("signals", {})
        key = (
            entry.get("routed_to", ""),
            signals.get("extension", ""),
            signals.get("source_folder", ""),
        )
        g = groups[key]
        g["count"] += 1
        g["filename_keywords"].update(signals.get("filename_keywords", []))
        g["content_keywords"].update(signals.get("content_keywords", []))

    # Convert groups to compacted entries
    compacted = []
    for (skill, ext, folder), g in groups.items():
        compacted.append({
            "routed_to": skill,
            "signals": {
                "extension": ext,
                "source_folder": folder,
                "filename_keywords": sorted(g["filename_keywords"]),
                "content_keywords": sorted(g["content_keywords"]),
            },
            "count": g["count"],
            "compacted": True,
            "timestamp": cutoff.isoformat(),
        })

    result = compacted + recent
    path.write_text(
        yaml.dump(result, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return result
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run python -m pytest skills/file-manager/augur/tests/test_decisions.py -v
```

- [ ] **Step 5: Commit**

```bash
git add skills/file-manager/scripts/decisions.py skills/file-manager/augur/tests/test_decisions.py
git commit -m "feat(file-manager): add decision storage with compaction for learning loop"
```

### Task 2: Confidence scoring engine

**Files:**
- Create: `skills/file-manager/scripts/confidence.py`
- Create: `skills/file-manager/augur/tests/test_confidence.py`

- [ ] **Step 1: Write failing tests**

```python
# skills/file-manager/augur/tests/test_confidence.py
"""Tests for confidence scoring engine."""
from __future__ import annotations

import pytest
from confidence import extract_signals, score_file, ScoredFile


class TestExtractSignals:
    def test_extracts_filename_keywords(self):
        signals = extract_signals(
            filename="מנורה-insurance-2026.pdf",
            content="ביטוח בריאות תביעות",
            extension=".pdf",
            source_folder="~/Desktop",
            size_bytes=5000,
        )
        assert "מנורה" in signals["filename_keywords"]
        assert "insurance" in signals["filename_keywords"]
        assert signals["extension"] == ".pdf"
        assert signals["source_folder"] == "~/Desktop"
        assert signals["size_range"] == "1k-10k"

    def test_extracts_content_keywords(self):
        signals = extract_signals(
            filename="doc.pdf",
            content="The patient visited the doctor for a medical examination at the hospital clinic",
            extension=".pdf",
            source_folder="~/Desktop",
            size_bytes=1000,
        )
        # Should extract frequent meaningful words
        assert len(signals["content_keywords"]) <= 10
        assert len(signals["content_keywords"]) > 0

    def test_size_range_buckets(self):
        assert extract_signals("f", "", ".txt", "~/", 500)["size_range"] == "tiny"
        assert extract_signals("f", "", ".txt", "~/", 5000)["size_range"] == "1k-10k"
        assert extract_signals("f", "", ".txt", "~/", 50000)["size_range"] == "10k-100k"
        assert extract_signals("f", "", ".txt", "~/", 500000)["size_range"] == "large"


class TestScoreFile:
    def test_zero_decisions_scores_low(self):
        signals = extract_signals("test.pdf", "some content", ".pdf", "~/Desktop", 5000)
        result = score_file(signals, decisions=[], intake_skills=[])
        assert result.confidence < 0.3

    def test_matching_intake_gives_some_score(self):
        signals = extract_signals("invoice.pdf", "payment receipt bank", ".pdf", "~/Desktop", 5000)
        intake_skills = [{
            "name": "finance",
            "accepts": ["invoices", "receipts", "bank statements"],
        }]
        result = score_file(signals, decisions=[], intake_skills=intake_skills)
        assert result.suggested_skill == "finance"
        assert result.confidence > 0

    def test_past_decisions_increase_confidence(self):
        signals = extract_signals("מנורה.pdf", "ביטוח בריאות", ".pdf", "~/Desktop", 5000)
        decisions = [
            {"routed_to": "health", "signals": {
                "filename_keywords": ["מנורה"],
                "content_keywords": ["ביטוח", "בריאות"],
                "extension": ".pdf",
                "source_folder": "~/Desktop",
            }}
        ] * 5
        result = score_file(signals, decisions=decisions, intake_skills=[])
        assert result.suggested_skill == "health"
        assert result.confidence > 0.5

    def test_no_match_returns_none_skill(self):
        signals = extract_signals("random.xyz", "", ".xyz", "~/tmp", 100)
        result = score_file(signals, decisions=[], intake_skills=[])
        assert result.suggested_skill is None
        assert result.confidence < 0.1
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run python -m pytest skills/file-manager/augur/tests/test_confidence.py -v
```

- [ ] **Step 3: Implement confidence.py**

```python
# skills/file-manager/scripts/confidence.py
"""Confidence scoring engine — pattern matching against past decisions.

No LLM needed. Scores files by comparing extracted signals against
user decisions in decisions.yaml and x-augur-file-intake declarations.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stopwords to filter from filenames/content (English + common)
STOPWORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "is", "it", "by", "with", "from"}

# Size range buckets
SIZE_RANGES = [
    (1024, "tiny"),
    (10240, "1k-10k"),
    (102400, "10k-100k"),
]

# Signal weights
WEIGHTS = {
    "filename_keywords": 0.15,
    "content_keywords": 0.35,
    "extension": 0.10,
    "source_folder": 0.10,
    "size_range": 0.05,
    "past_decisions": 0.25,
}


@dataclass
class ScoredFile:
    """Result of scoring a file for routing."""
    suggested_skill: str | None
    confidence: float
    signals: dict[str, Any]
    skill_scores: dict[str, float]


def extract_signals(
    filename: str,
    content: str,
    extension: str,
    source_folder: str,
    size_bytes: int,
) -> dict[str, Any]:
    """Extract routing signals from a file."""
    # Filename keywords: split on delimiters, filter stopwords + short tokens
    name_no_ext = Path(filename).stem
    tokens = re.split(r"[-_.\s/\\()\[\]{}]+", name_no_ext)
    filename_keywords = [
        t.lower() for t in tokens
        if len(t) > 1 and t.lower() not in STOPWORDS
    ]

    # Content keywords: top 10 most frequent meaningful words
    words = re.findall(r"\b\w{2,}\b", content.lower())
    word_counts = Counter(w for w in words if w not in STOPWORDS and len(w) > 2)
    content_keywords = [w for w, _ in word_counts.most_common(10)]

    # Size range
    size_range = "large"
    for threshold, label in SIZE_RANGES:
        if size_bytes < threshold:
            size_range = label
            break

    return {
        "filename_keywords": filename_keywords,
        "content_keywords": content_keywords,
        "extension": extension.lower(),
        "source_folder": source_folder,
        "size_range": size_range,
    }


def score_file(
    signals: dict[str, Any],
    decisions: list[dict[str, Any]],
    intake_skills: list[dict[str, Any]],
) -> ScoredFile:
    """Score a file against all known skills.

    Args:
        signals: Extracted signals from the file.
        decisions: Past user decisions from decisions.yaml.
        intake_skills: Skills with x-augur-file-intake (from domain map).

    Returns:
        ScoredFile with best skill suggestion and confidence.
    """
    # Collect all known skills
    skill_names: set[str] = set()
    for d in decisions:
        if d.get("routed_to"):
            skill_names.add(d["routed_to"])
    for s in intake_skills:
        skill_names.add(s["name"])

    if not skill_names:
        return ScoredFile(
            suggested_skill=None, confidence=0.0,
            signals=signals, skill_scores={},
        )

    skill_scores: dict[str, float] = {}

    for skill in skill_names:
        score = 0.0

        # 1. Filename keywords vs intake accepts
        intake = next((s for s in intake_skills if s["name"] == skill), None)
        if intake and signals["filename_keywords"]:
            accepts = [a.lower() for a in intake.get("accepts", [])]
            fn_matched = sum(
                1 for kw in signals["filename_keywords"]
                if any(kw in acc for acc in accepts)
            )
            if signals["filename_keywords"]:
                score += WEIGHTS["filename_keywords"] * (fn_matched / len(signals["filename_keywords"]))

        # 2. Content keywords vs past decisions for this skill
        skill_decisions = [d for d in decisions if d.get("routed_to") == skill]
        if signals["content_keywords"] and skill_decisions:
            past_content_kws: set[str] = set()
            for d in skill_decisions:
                past_content_kws.update(d.get("signals", {}).get("content_keywords", []))
            if past_content_kws:
                content_matched = sum(
                    1 for kw in signals["content_keywords"]
                    if kw in past_content_kws
                )
                score += WEIGHTS["content_keywords"] * (content_matched / len(signals["content_keywords"]))

        # Also check content keywords against intake accepts
        if intake and signals["content_keywords"]:
            accepts = [a.lower() for a in intake.get("accepts", [])]
            content_intake_matched = sum(
                1 for kw in signals["content_keywords"]
                if any(kw in acc for acc in accepts)
            )
            score += WEIGHTS["content_keywords"] * 0.3 * (content_intake_matched / len(signals["content_keywords"]))

        # 3. Extension match (binary)
        if skill_decisions:
            past_exts = {d.get("signals", {}).get("extension") for d in skill_decisions}
            if signals["extension"] in past_exts:
                score += WEIGHTS["extension"]

        # 4. Source folder match (binary)
        if skill_decisions:
            past_folders = {d.get("signals", {}).get("source_folder") for d in skill_decisions}
            if signals["source_folder"] in past_folders:
                score += WEIGHTS["source_folder"]

        # 5. Size range match (binary)
        if skill_decisions:
            past_sizes = {d.get("signals", {}).get("size_range") for d in skill_decisions}
            if signals["size_range"] in past_sizes:
                score += WEIGHTS["size_range"]

        # 6. Past decisions count (saturation curve)
        n = len(skill_decisions)
        if n > 0:
            score += WEIGHTS["past_decisions"] * (n / (n + 5))

        skill_scores[skill] = round(score, 4)

    # Find best skill
    if not skill_scores:
        return ScoredFile(
            suggested_skill=None, confidence=0.0,
            signals=signals, skill_scores={},
        )

    best_skill = max(skill_scores, key=skill_scores.get)
    best_score = skill_scores[best_skill]

    return ScoredFile(
        suggested_skill=best_skill if best_score > 0.05 else None,
        confidence=round(min(best_score, 1.0), 4),
        signals=signals,
        skill_scores=skill_scores,
    )
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run python -m pytest skills/file-manager/augur/tests/test_confidence.py -v
```

- [ ] **Step 5: Commit**

```bash
git add skills/file-manager/scripts/confidence.py skills/file-manager/augur/tests/test_confidence.py
git commit -m "feat(file-manager): add confidence scoring engine with signal extraction"
```

---

## Phase 2: System LLM CLI Config

### Task 3: Shared LLM CLI loader

**Files:**
- Create: `src/lib/llm_cli.py`
- Modify: `skills/document-extractor/scripts/extractor.py:111` (replace `_load_cli_config`)

- [ ] **Step 1: Implement src/lib/llm_cli.py**

```python
# src/lib/llm_cli.py
"""System-level LLM CLI config and spawner.

Reads from get_vault_dir()/config/llm_cli.yaml.
Used by any skill that needs to spawn a CLI agent session.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.config.paths import get_vault_dir

DEFAULTS = {
    "preferred": "claude",
    "fallback": "ollama",
    "ollama_model": "llama3",
    "ollama_vision_model": "llava",
    "timeout": 120,
}


def get_llm_cli_config() -> dict[str, Any]:
    """Load system-level LLM CLI config."""
    config_path = get_vault_dir() / "config" / "llm_cli.yaml"
    if config_path.exists():
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**DEFAULTS, **data}
        except Exception:
            pass
    return dict(DEFAULTS)


def get_preferred_cli() -> str | None:
    """Return name of best available CLI ('claude', 'ollama', or None)."""
    config = get_llm_cli_config()

    if config["preferred"] == "claude" and shutil.which("claude"):
        return "claude"
    if config["preferred"] == "ollama" and _ollama_running():
        return "ollama"

    # Try fallback
    if config["fallback"] == "claude" and shutil.which("claude"):
        return "claude"
    if config["fallback"] == "ollama" and _ollama_running():
        return "ollama"

    return None


def spawn_cli_prompt(prompt: str, timeout: int | None = None) -> str | None:
    """Spawn preferred CLI with prompt, return output.

    Returns:
        CLI output as string, or None if no CLI available.
    """
    cli = get_preferred_cli()
    if not cli:
        return None

    config = get_llm_cli_config()
    timeout = timeout or config.get("timeout", 120)

    try:
        if cli == "claude":
            result = subprocess.run(
                ["claude", "--print", "--prompt", prompt],
                capture_output=True, text=True, timeout=timeout,
                env={**os.environ, "AUGUR_AGENT_SESSION": "true"},
            )
            return result.stdout.strip() if result.returncode == 0 else None

        if cli == "ollama":
            model = config.get("ollama_model", "llama3")
            result = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True, text=True, timeout=timeout,
            )
            return result.stdout.strip() if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return None

    return None


def _ollama_running() -> bool:
    """Check if Ollama is responding."""
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False
```

- [ ] **Step 2: Update document-extractor to use shared loader**

In `skills/document-extractor/scripts/extractor.py`, replace `_load_cli_config()` (line 111) and its callers with:

```python
from src.lib.llm_cli import get_llm_cli_config, spawn_cli_prompt
```

Delete the `_load_cli_config()` function entirely.

- [ ] **Step 3: Delete the old vault config**

The per-skill config at `get_skill_vault_dir("document-extractor")/config.yaml` that only contained `llm_cli:` — delete it if it exists. The system-level config at `get_vault_dir()/config/llm_cli.yaml` already has the data.

- [ ] **Step 4: Run document-extractor tests**

```bash
uv run python -m pytest skills/document-extractor/augur/tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git add src/lib/llm_cli.py skills/document-extractor/scripts/extractor.py
git commit -m "feat: add shared LLM CLI config at src/lib/llm_cli.py, migrate document-extractor"
```

---

## Phase 3: MCP Tools

### Task 4: New MCP tools — save-pending-files, get-pending-detailed, route-pending-file, get-routing-confidence

**Files:**
- Modify: `skills/file-manager/scripts/mcp/tools_organize.py`
- Modify: `skills/file-manager/augur/tests/test_tools_organize.py`

- [ ] **Step 1: Write failing tests for new tools**

Add to `test_tools_organize.py`:

```python
from mcp.tools_organize import (
    save_pending_files_impl,
    get_pending_detailed_impl,
    route_pending_file_impl,
    get_routing_confidence_impl,
)


class TestSavePendingFiles:
    def test_saves_pending_metadata(self, tmp_path):
        files = [{
            "source_path": "/tmp/test.pdf",
            "filename": "test.pdf",
            "summary": "A test document",
            "confidence": 0.45,
            "suggested_skill": "health",
            "signals": {"extension": ".pdf"},
        }]
        result = json.loads(save_pending_files_impl(
            json.dumps(files), str(tmp_path),
        ))
        assert result["success"] is True
        assert result["saved"] == 1
        # Check YAML file was written
        yamls = list(tmp_path.glob("*.yaml"))
        assert len(yamls) == 1

    def test_deduplicates_by_source_path(self, tmp_path):
        files = [{"source_path": "/tmp/same.pdf", "filename": "same.pdf",
                   "summary": "v1", "confidence": 0.3, "suggested_skill": None, "signals": {}}]
        save_pending_files_impl(json.dumps(files), str(tmp_path))
        files[0]["summary"] = "v2"
        save_pending_files_impl(json.dumps(files), str(tmp_path))
        yamls = list(tmp_path.glob("*.yaml"))
        assert len(yamls) == 1  # Updated, not duplicated


class TestGetPendingDetailed:
    def test_returns_files_with_metadata(self, tmp_path):
        import yaml
        meta = {
            "id": "pending-test",
            "source_path": "/tmp/test.pdf",
            "filename": "test.pdf",
            "summary": "A test document",
            "confidence": 0.72,
            "suggested_skill": "health",
        }
        (tmp_path / "pending-test.yaml").write_text(yaml.dump(meta))
        result = json.loads(get_pending_detailed_impl(str(tmp_path)))
        assert result["success"] is True
        assert len(result["files"]) == 1
        assert result["files"][0]["summary"] == "A test document"


class TestRoutePendingFile:
    def test_routes_and_records_decision(self, tmp_path):
        import yaml
        # Set up pending file
        source = tmp_path / "source" / "test.pdf"
        source.parent.mkdir()
        source.write_bytes(b"pdf content")

        pending_dir = tmp_path / "pending"
        pending_dir.mkdir()
        meta = {
            "id": "pending-test",
            "source_path": str(source),
            "filename": "test.pdf",
            "summary": "Test doc",
            "confidence": 0.45,
            "suggested_skill": "finance",
            "signals": {"extension": ".pdf"},
        }
        (pending_dir / "pending-test.yaml").write_text(yaml.dump(meta))

        dest = tmp_path / "dest"
        decisions_path = tmp_path / "decisions.yaml"

        result = json.loads(route_pending_file_impl(
            pending_id="pending-test",
            target_skill="health",
            pending_dir_override=str(pending_dir),
            dest_dir_override=str(dest),
            decisions_path_override=str(decisions_path),
        ))
        assert result["success"] is True
        assert (dest / "test.pdf").exists()
        assert not (pending_dir / "pending-test.yaml").exists()
        # Decision was recorded
        decisions = yaml.safe_load(decisions_path.read_text())
        assert len(decisions) == 1
        assert decisions[0]["routed_to"] == "health"
        assert decisions[0]["user_override"] is True  # Changed from finance to health
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run python -m pytest skills/file-manager/augur/tests/test_tools_organize.py -k "Pending or Route or Confidence" -v
```

- [ ] **Step 3: Implement the new tools**

Add `_impl` functions and MCP tool registrations to `tools_organize.py`. Each tool follows the existing pattern in that file.

Key implementation details:
- `save_pending_files_impl`: Write YAML metadata per file to pending dir. ID format: `pending-{YYYYMMDD}-{HHMMSS}-{slug[:30]}`. Dedup by checking existing YAMLs for matching `source_path`.
- `get_pending_detailed_impl`: Read all `.yaml` files from pending dir, return sorted by confidence (lowest first — those need most attention).
- `route_pending_file_impl`: Load pending YAML, move source file via shutil.move, record decision via `append_decision`, delete pending YAML.
- `get_routing_confidence_impl`: Extract content via document-extractor, extract signals, score against decisions + domain map.

- [ ] **Step 4: Register new tools in MCP**

Add to `register_organize_tools()`:
- `save-pending-files`: NOT readOnly
- `get-pending-detailed`: readOnly
- `route-pending-file`: NOT readOnly, destructive
- `get-routing-confidence`: readOnly

- [ ] **Step 5: Run all file-manager tests**

```bash
uv run python -m pytest skills/file-manager/augur/tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add skills/file-manager/scripts/mcp/tools_organize.py skills/file-manager/augur/tests/test_tools_organize.py
git commit -m "feat(file-manager): add save-pending, get-pending-detailed, route-pending, get-routing-confidence tools"
```

---

## Phase 4: Autoloop Wiring

### Task 5: Wire confidence scoring + CLI summaries into autoloop

**Files:**
- Modify: `skills/file-manager/scripts/autoloop.py`
- Modify: `skills/file-manager/augur/tests/test_autoloop.py`

- [ ] **Step 1: Write failing tests for enhanced autoloop**

Add to `test_autoloop.py`:

```python
from confidence import extract_signals, score_file
from decisions import load_decisions


class TestAutoloopScoring:
    def test_score_files_from_scan(self, tmp_path):
        from autoloop import score_scanned_files

        files = [
            {"name": "invoice.pdf", "content_sample": "payment receipt total amount", "extension": ".pdf",
             "path": str(tmp_path / "invoice.pdf"), "size": 5000},
        ]
        decisions = [
            {"routed_to": "finance", "signals": {
                "content_keywords": ["payment", "receipt", "amount"],
                "extension": ".pdf", "source_folder": str(tmp_path),
            }}
        ] * 3
        intake_skills = [{"name": "finance", "accepts": ["invoices", "receipts"]}]

        scored = score_scanned_files(files, decisions, intake_skills)
        assert len(scored) == 1
        assert scored[0]["suggested_skill"] == "finance"
        assert scored[0]["confidence"] > 0.3


class TestAutoloopSummaryGeneration:
    def test_generate_summaries_returns_dict(self):
        from autoloop import generate_summaries
        from unittest.mock import patch

        files = [
            {"name": "test.pdf", "content_sample": "Medical report from clinic"},
        ]
        with patch("autoloop.spawn_cli_prompt", return_value="test.pdf: Medical report from a clinic visit"):
            summaries = generate_summaries(files)
        assert "test.pdf" in summaries

    def test_fallback_when_no_cli(self):
        from autoloop import generate_summaries
        from unittest.mock import patch

        files = [
            {"name": "test.pdf", "content_sample": "Medical report from clinic blah blah"},
        ]
        with patch("autoloop.spawn_cli_prompt", return_value=None):
            summaries = generate_summaries(files)
        # Falls back to first 100 chars of content
        assert "Medical report" in summaries.get("test.pdf", "")
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run python -m pytest skills/file-manager/augur/tests/test_autoloop.py -k "Scoring or Summary" -v
```

- [ ] **Step 3: Implement autoloop enhancements**

Add to `autoloop.py`:

```python
from confidence import extract_signals, score_file
from decisions import load_decisions, get_decisions_path
from src.lib.llm_cli import spawn_cli_prompt


def score_scanned_files(
    files: list[dict],
    decisions: list[dict],
    intake_skills: list[dict],
) -> list[dict]:
    """Score a list of scanned files for routing confidence."""
    scored = []
    for f in files:
        signals = extract_signals(
            filename=f["name"],
            content=f.get("content_sample", ""),
            extension=f.get("extension", Path(f["name"]).suffix),
            source_folder=str(Path(f.get("path", "")).parent),
            size_bytes=f.get("size", 0),
        )
        result = score_file(signals, decisions, intake_skills)
        scored.append({
            "name": f["name"],
            "path": f.get("path", ""),
            "content_sample": f.get("content_sample", ""),
            "confidence": result.confidence,
            "suggested_skill": result.suggested_skill,
            "signals": result.signals,
            "size": f.get("size", 0),
            "extension": f.get("extension", ""),
        })
    return scored


def generate_summaries(files: list[dict]) -> dict[str, str]:
    """Generate one-line summaries for files using CLI agent.

    Falls back to content snippet if no CLI available.
    """
    if not files:
        return {}

    # Build batch prompt
    file_blocks = []
    for f in files:
        content = f.get("content_sample", "")[:500]
        file_blocks.append(f"File: {f['name']}\nContent: {content}\n---")

    prompt = (
        "For each file below, write a one-line summary (under 100 chars) "
        "describing what the document is about. Format: 'filename: summary'\n\n"
        + "\n".join(file_blocks)
    )

    output = spawn_cli_prompt(prompt)

    summaries = {}
    if output:
        for line in output.strip().split("\n"):
            if ":" in line:
                name, _, summary = line.partition(":")
                name = name.strip()
                # Match against known filenames
                for f in files:
                    if f["name"] in name or name in f["name"]:
                        summaries[f["name"]] = summary.strip()
                        break

    # Fallback: use content snippet for files without summaries
    for f in files:
        if f["name"] not in summaries:
            content = f.get("content_sample", "")
            summaries[f["name"]] = content[:100].replace("\n", " ").strip()

    return summaries
```

- [ ] **Step 4: Run all autoloop tests**

```bash
uv run python -m pytest skills/file-manager/augur/tests/test_autoloop.py -v
```

- [ ] **Step 5: Commit**

```bash
git add skills/file-manager/scripts/autoloop.py skills/file-manager/augur/tests/test_autoloop.py
git commit -m "feat(file-manager): wire confidence scoring and CLI summary generation into autoloop"
```

---

## Phase 5: Dashboard

### Task 6: Redesign Organize tab pending section

**Files:**
- Modify: `skills/file-manager/augur/dashboard/organize/page.tsx`

- [ ] **Step 1: Read existing dashboard patterns**

Read `skills/file-manager/augur/dashboard/organize/page.tsx` and `docs/agent-topics/DASHBOARD.md` for the current layout and hook patterns.

- [ ] **Step 2: Redesign the pending section**

Replace the existing pending section (which uses `get-pending`) with:

- `useMcpQuery` on `get-pending-detailed` for pending file cards
- `useMcpQuery` on `get-domain-map` for skill dropdown options
- `useMcpMutation` on `route-pending-file` for approve action

**Card structure per file:**
- AI summary headline (blue/cyan text)
- `<details>` with raw content preview
- Confidence badge: green (>=0.7) / amber (0.4-0.7) / red (<0.4)
- `<select>` dropdown pre-populated with `suggested_skill`, options from domain map + "archive"
- Approve button (green) → calls `route-pending-file`
- Skip button (grey) → removes card from view (client-side only)

**"Approve All Suggestions" button** at top — iterates all files with `confidence >= 0.4` and calls `route-pending-file` for each.

**Watched folders section** — add after existing content:
- "N decisions learned" (from a count in `get-pending-detailed` response or separate call)
- Trust level indicator

- [ ] **Step 3: Verify compilation**

```bash
pnpm --filter dashboard typecheck 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add skills/file-manager/augur/dashboard/organize/page.tsx
git commit -m "feat(file-manager): redesign pending section with card list, confidence badges, skill dropdowns"
```

---

## Phase 6: Verification

### Task 7: End-to-end verification

- [ ] **Step 1: Run all file-manager tests**

```bash
uv run python -m pytest skills/file-manager/augur/tests/ -v
```

- [ ] **Step 2: Run document-extractor tests (verify no regression from CLI migration)**

```bash
uv run python -m pytest skills/document-extractor/augur/tests/ -v
```

- [ ] **Step 3: Test confidence scoring on real Desktop files**

```bash
uv run python -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'skills/file-manager/scripts')
from confidence import extract_signals, score_file
from decisions import load_decisions, get_decisions_path
from pathlib import Path

# No decisions yet — should show low confidence
decisions = load_decisions(get_decisions_path())
intake_skills = [
    {'name': 'health', 'accepts': ['medical records', 'insurance docs']},
    {'name': 'finance', 'accepts': ['invoices', 'receipts', 'bank statements']},
]

desktop = Path('~/Desktop').expanduser()
for f in sorted(desktop.iterdir())[:10]:
    if f.is_file() and not f.name.startswith('.'):
        signals = extract_signals(f.name, '', f.suffix, str(f.parent), f.stat().st_size)
        result = score_file(signals, decisions, intake_skills)
        print(f'  {result.confidence:.2f} {result.suggested_skill or \"???\":15s} {f.name}')
"
```

- [ ] **Step 4: Test route-pending-file learning loop**

Simulate a few decisions and verify confidence improves:

```bash
uv run python -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'skills/file-manager/scripts')
from confidence import extract_signals, score_file
from decisions import append_decision
from pathlib import Path
import tempfile

decisions_path = Path(tempfile.mktemp(suffix='.yaml'))

# Simulate 5 user decisions: Hebrew insurance → health
for i in range(5):
    append_decision(decisions_path, {
        'file': f'menora_{i}.pdf', 'routed_to': 'health',
        'signals': {'filename_keywords': ['מנורה'], 'content_keywords': ['ביטוח', 'בריאות'],
                    'extension': '.pdf', 'source_folder': '~/Desktop', 'size_range': '1k-10k'},
        'confidence_at_decision': 0.3, 'user_override': False,
    })

from decisions import load_decisions
decisions = load_decisions(decisions_path)

# Now score a new similar file
signals = extract_signals('מנורה-2026.pdf', 'ביטוח בריאות תביעות', '.pdf', '~/Desktop', 5000)
result = score_file(signals, decisions, [])

print(f'After 5 decisions:')
print(f'  Suggested: {result.suggested_skill}')
print(f'  Confidence: {result.confidence:.3f}')
print(f'  (Should be health with confidence > 0.5)')

decisions_path.unlink()
"
```

- [ ] **Step 5: Verify MCP tool registration**

```bash
uv run python -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'skills/file-manager/scripts')
from mcp.tools_organize import (
    save_pending_files_impl,
    get_pending_detailed_impl,
    route_pending_file_impl,
    get_routing_confidence_impl,
)
print('All 4 new tools importable: OK')
"
```
