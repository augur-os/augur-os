# File Manager Consolidation & Evolution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate `file-manager` and `organizer` into a single high-capability skill with a rules engine, 7 MCP tools, trust-aware autoloop, and attention inbox integration.

**Architecture:** `file-manager` absorbs `organizer` and becomes the surviving skill. A Python rules engine (FileAction dataclass + triage decision tree) powers all consumption modes. MCP tools provide data and execution; AI clients make decisions. The attention skill gains a `"file-action"` source type for autoloop approval workflows. Dashboard gets Browse + Organize tabs.

**Tech Stack:** Python 3.11+ (rules engine, MCP tools, autoloop), TypeScript/React (dashboard), FastMCP (tool registration), YAML frontmatter (skill metadata)

**Spec:** `docs/superpowers/specs/2026-03-25-file-manager-consolidation-design.md`

---

## Phase 1: Skill Consolidation

### Task 1: Migrate organizer seeds and tests to file-manager

**Files:**
- Copy from: `skills/organizer/assets/seeds/config.yaml`
- Copy from: `skills/organizer/assets/seeds/prompts/*.md`
- Copy to: `skills/file-manager/assets/seeds/`
- Copy from: `skills/organizer/augur/tests/test_organizer.py`
- Copy from: `skills/organizer/augur/tests/test_organizer_mcp.py`
- Modify: `skills/file-manager/augur/tests/` (add migrated tests)

- [ ] **Step 1: Copy organizer seeds to file-manager**

```bash
# Copy config.yaml
cp skills/organizer/assets/seeds/config.yaml skills/file-manager/assets/seeds/organizer-config.yaml

# Copy action prompts
cp skills/organizer/assets/seeds/prompts/apply-organize-changes.md skills/file-manager/assets/seeds/prompts/
cp skills/organizer/assets/seeds/prompts/delete-duplicate-file.md skills/file-manager/assets/seeds/prompts/
cp skills/organizer/assets/seeds/prompts/edit-organize-rules.md skills/file-manager/assets/seeds/prompts/
```

- [ ] **Step 2: Copy useful organizer tests to file-manager**

Copy `skills/organizer/augur/tests/test_organizer.py` → `skills/file-manager/augur/tests/test_organizer_migrated.py`. Update imports to reference file-manager's scripts (the `service.py` functions will be absorbed into the rules engine in Phase 2). For now, just preserve the test structure as a reference.

```bash
cp skills/organizer/augur/tests/test_organizer.py skills/file-manager/augur/tests/test_organizer_migrated.py
cp skills/organizer/augur/tests/test_organizer_mcp.py skills/file-manager/augur/tests/test_organizer_mcp_migrated.py
```

- [ ] **Step 3: Verify copies exist**

```bash
ls -la skills/file-manager/assets/seeds/
ls -la skills/file-manager/assets/seeds/prompts/
ls -la skills/file-manager/augur/tests/
```

Expected: All files present in new locations.

- [ ] **Step 4: Commit**

```bash
git add skills/file-manager/assets/seeds/ skills/file-manager/augur/tests/
git commit -m "feat(file-manager): migrate organizer seeds and tests before deletion"
```

### Task 2: Delete organizer skill and generated dashboard pages

**Files:**
- Delete: `skills/organizer/` (entire directory)
- Delete: `skills/dashboard/pages/life/organizer/` (generated dashboard pages)

- [ ] **Step 1: Verify organizer directory contents before deletion**

```bash
find skills/organizer/ -type f | head -30
find skills/dashboard/pages/life/organizer/ -type f 2>/dev/null
```

- [ ] **Step 2: Delete organizer skill directory**

```bash
rm -rf skills/organizer/
```

- [ ] **Step 3: Delete generated organizer dashboard pages**

```bash
rm -rf skills/dashboard/pages/life/organizer/
```

- [ ] **Step 4: Search for stale organizer references**

Grep the codebase for references to the deleted skill. Fix any that would break imports or routing.

```bash
rg -l "organizer" --type py --type ts --type yaml | grep -v node_modules | grep -v .next | grep -v __pycache__
```

Remove or update any stale references found (route mounts for `/productivity/organizer`, `/productivity/organize`, `/productivity/duplicates`, `/productivity/cleanup`).

- [ ] **Step 5: Commit**

```bash
git add -A skills/organizer/ skills/dashboard/pages/life/organizer/
git commit -m "feat(file-manager): delete organizer skill — absorbed into file-manager

Supersedes ADR-111 and ADR-220 per consolidation spec."
```

### Task 3: Clean up legacy file-manager seed directory

**Files:**
- Delete: `skills/file-manager/augur/seed/` (violates rule 19 — seeds belong in `assets/seeds/`)

- [ ] **Step 1: Check if augur/seed/ has content worth preserving**

Read `skills/file-manager/augur/seed/_seed.yaml` and `skills/file-manager/augur/seed/example-file-manager.yaml`. The exploration showed these are auto-generated stubs — safe to delete.

- [ ] **Step 2: Delete legacy seed directory**

```bash
rm -rf skills/file-manager/augur/seed/
```

- [ ] **Step 3: Commit**

```bash
git add skills/file-manager/augur/seed/
git commit -m "chore(file-manager): remove legacy augur/seed/ — seeds live in assets/seeds/"
```

### Task 4: Update file-manager SKILL.md with new metadata

**Files:**
- Modify: `skills/file-manager/SKILL.md`

- [ ] **Step 1: Read current SKILL.md**

Read `skills/file-manager/SKILL.md` in full.

- [ ] **Step 2: Rewrite SKILL.md frontmatter**

Update the SKILL.md frontmatter with:
- New description reflecting consolidated scope (file intelligence, organization, triage)
- `x-augur-type: domain`
- Updated `x-augur-mcp-tools` list (all 7 new tools + 3 existing)
- `x-augur-file-intake` declaration for the file-manager's own archive/pending folders
- `x-augur-loop` frontmatter for the nightly autoloop
- Updated `x-augur-dashboard-pages`

```yaml
---
name: file-manager
description: >-
  Intelligent file organization engine — triages files by content and context,
  routes to skill domains, renames for consistency, archives low-value content,
  and discovers when new skills are needed. Powers dashboard Browse/Organize tabs,
  nightly autoloop, and external MCP clients.
x-augur-type: domain
x-augur-hub: life
x-augur-tab: home
x-augur-requires-platform: true
x-augur-data-dir: file-manager
x-augur-mcp-tools:
  - get-file-manager-status
  - list-collateral-files
  - get-context-files
  - scan-folder
  - get-domain-map
  - get-rules
  - update-rules
  - apply-file-actions
  - get-pending
  - get-archive
  - get-file-history
x-augur-dashboard-pages:
  - /life/file-manager
  - /life/file-manager/organize
x-augur-file-intake:
  accepts: ["unsorted files", "downloads", "desktop clutter"]
  folder: file-manager
  subfolders: [archive, pending]
x-augur-loop:
  name: file-organizer
  tier: 1
  trigger: nightly
  config:
    max_difficulty: 4
    trust_aware: true
    attention_source_type: file-action
x-augur-commands:
  - name: save
    description: Save assets (images, PDFs, slides, files) to the correct skill's assets folder
x-augur-config-file: config.yaml
---
```

- [ ] **Step 3: Update SKILL.md body**

Rewrite the body to describe the consolidated skill's capabilities, referencing the rules engine, autoloop, and external client workflow.

- [ ] **Step 4: Commit**

```bash
git add skills/file-manager/SKILL.md
git commit -m "feat(file-manager): update SKILL.md with consolidated metadata and loop config"
```

---

## Phase 2: Rules Engine

### Task 5a: Create test conftest.py for file-manager

**Files:**
- Create: `skills/file-manager/augur/tests/conftest.py`

All file-manager test files need `sys.path` bootstrapping for the `scripts/` directory (Python can't import `skills.file-manager` due to the hyphen). A shared conftest.py handles this once.

- [ ] **Step 1: Create conftest.py**

```python
# skills/file-manager/augur/tests/conftest.py
"""Shared test fixtures and path bootstrap for file-manager tests."""
import sys
from pathlib import Path

# Project root
_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# file-manager scripts dir — enables `from rules_engine import ...`
# and `from mcp.tools_organize import ...`
_scripts_dir = str(Path(__file__).resolve().parents[2] / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
```

- [ ] **Step 2: Commit**

```bash
git add skills/file-manager/augur/tests/conftest.py
git commit -m "chore(file-manager): add test conftest.py with sys.path bootstrap"
```

### Task 5b: Write FileAction dataclass and rules engine core

**Files:**
- Create: `skills/file-manager/scripts/rules_engine.py`
- Create: `skills/file-manager/augur/tests/test_rules_engine.py`

- [ ] **Step 1: Write failing tests for FileAction and triage functions**

```python
# skills/file-manager/augur/tests/test_rules_engine.py
"""Tests for the file-manager rules engine."""
from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import patch

import pytest

# conftest.py handles sys.path bootstrap — imports "just work"
from rules_engine import (
    FileAction,
    TrustLevel,
    load_rules,
    save_rules,
    load_history,
    append_history,
    get_trust_level,
)


class TestFileAction:
    def test_create_move_action(self):
        action = FileAction(
            source_path="/tmp/test.pdf",
            new_name="2026-03-invoice.pdf",
            destination="/docs/finance/invoices",
            action="move",
            reason="Matched finance domain by content",
            skill_target="finance",
        )
        assert action.action == "move"
        assert action.skill_target == "finance"
        assert action.new_name == "2026-03-invoice.pdf"

    def test_create_archive_action(self):
        action = FileAction(
            source_path="/tmp/old.log",
            new_name=None,
            destination="/archive",
            action="archive",
            reason="Low-value log file",
            skill_target=None,
        )
        assert action.action == "archive"
        assert action.new_name is None
        assert action.skill_target is None

    def test_create_pending_action(self):
        action = FileAction(
            source_path="/tmp/car-manual.pdf",
            new_name=None,
            destination="/pending/car-maintenance",
            action="pending",
            reason="No matching skill for car maintenance content",
            skill_target=None,
        )
        assert action.action == "pending"

    def test_serialization_roundtrip(self):
        action = FileAction(
            source_path="/tmp/test.pdf",
            new_name="renamed.pdf",
            destination="/docs/health",
            action="move",
            reason="Health domain match",
            skill_target="health",
        )
        d = asdict(action)
        restored = FileAction(**d)
        assert restored == action

    def test_invalid_action_type(self):
        with pytest.raises(ValueError, match="action must be one of"):
            FileAction(
                source_path="/tmp/test.pdf",
                new_name=None,
                destination="/archive",
                action="delete",  # not allowed
                reason="test",
                skill_target=None,
            )


class TestTrustLevel:
    def test_low_trust_defaults(self):
        trust = TrustLevel()
        assert trust.level == "low"
        assert trust.auto_apply_threshold == 0.9
        assert trust.consecutive_approvals == 0

    def test_trust_escalation(self):
        trust = TrustLevel(level="low", consecutive_approvals=10)
        escalated = trust.maybe_escalate()
        assert escalated.level == "medium"

    def test_trust_rejection_resets(self):
        trust = TrustLevel(level="medium", consecutive_approvals=15)
        reset = trust.on_rejection("move")
        assert reset.consecutive_approvals == 0
        assert reset.level == "low"


class TestRulesIO:
    def test_load_rules_default(self, tmp_path):
        """When no rules file exists, return defaults."""
        rules = load_rules(tmp_path / "rules.yaml")
        assert "watched_folders" in rules
        assert isinstance(rules["watched_folders"], list)

    def test_save_and_load_rules(self, tmp_path):
        rules_path = tmp_path / "rules.yaml"
        rules = {
            "watched_folders": ["~/Downloads", "~/Desktop"],
            "overrides": [],
        }
        save_rules(rules_path, rules)
        loaded = load_rules(rules_path)
        assert loaded["watched_folders"] == ["~/Downloads", "~/Desktop"]


class TestHistoryIO:
    def test_append_and_load_history(self, tmp_path):
        history_path = tmp_path / "history.yaml"
        action = FileAction(
            source_path="/tmp/test.pdf",
            new_name="renamed.pdf",
            destination="/docs/health",
            action="move",
            reason="test",
            skill_target="health",
        )
        append_history(history_path, action, "autoloop")
        entries = load_history(history_path)
        assert len(entries) == 1
        assert entries[0]["source_path"] == "/tmp/test.pdf"
        assert entries[0]["moved_by"] == "autoloop"

    def test_history_appends_not_overwrites(self, tmp_path):
        history_path = tmp_path / "history.yaml"
        for i in range(3):
            action = FileAction(
                source_path=f"/tmp/file{i}.pdf",
                new_name=None,
                destination="/archive",
                action="archive",
                reason="test",
                skill_target=None,
            )
            append_history(history_path, action, "autoloop")
        entries = load_history(history_path)
        assert len(entries) == 3


class TestGetTrustLevel:
    def test_no_history_returns_low(self, tmp_path):
        trust = get_trust_level(tmp_path / "history.yaml")
        assert trust.level == "low"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_rules_engine.py -v 2>&1 | head -40
```

Expected: ImportError — `rules_engine` module doesn't exist yet.

- [ ] **Step 3: Implement the rules engine**

```python
# skills/file-manager/scripts/rules_engine.py
"""File-manager rules engine — FileAction model, trust, rules and history I/O.

The AI client (IDE agent, Cowork, autoloop) makes triage decisions.
This module provides the data structures and persistence layer.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

# Path bootstrap
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.config.paths import (
    get_skill_vault_dir,
    get_skill_documents_dir,
)

VALID_ACTIONS = {"move", "archive", "pending"}

# Trust escalation thresholds
TRUST_ESCALATION_THRESHOLD = 10  # consecutive approvals to escalate
TRUST_LEVELS = {
    "low": {"auto_apply_threshold": 0.9, "next": "medium"},
    "medium": {"auto_apply_threshold": 0.8, "next": "high"},
    "high": {"auto_apply_threshold": 0.6, "next": "high"},
}

DEFAULT_RULES = {
    "watched_folders": ["~/Downloads", "~/Desktop", "~/Documents/Inbox"],
    "overrides": [],
}


@dataclass
class FileAction:
    """A single file triage decision — rename + move as atomic operation."""

    source_path: str          # original location
    new_name: str | None      # rename (None = keep original name)
    destination: str          # target folder
    action: str               # "move" | "archive" | "pending"
    reason: str               # AI's reasoning
    skill_target: str | None  # which skill domain, if matched

    def __post_init__(self):
        if self.action not in VALID_ACTIONS:
            raise ValueError(
                f"action must be one of {VALID_ACTIONS}, got '{self.action}'"
            )


@dataclass
class TrustLevel:
    """Trust state for autoloop approval gating."""

    level: str = "low"
    auto_apply_threshold: float = 0.9
    consecutive_approvals: int = 0
    last_rejection_type: str | None = None

    def maybe_escalate(self) -> TrustLevel:
        """Return escalated trust if threshold met, else self."""
        if self.consecutive_approvals >= TRUST_ESCALATION_THRESHOLD:
            next_level = TRUST_LEVELS.get(self.level, {}).get("next", self.level)
            next_threshold = TRUST_LEVELS.get(next_level, {}).get(
                "auto_apply_threshold", self.auto_apply_threshold
            )
            return TrustLevel(
                level=next_level,
                auto_apply_threshold=next_threshold,
                consecutive_approvals=0,
            )
        return self

    def on_rejection(self, action_type: str) -> TrustLevel:
        """Reset trust on user rejection."""
        return TrustLevel(
            level="low",
            auto_apply_threshold=TRUST_LEVELS["low"]["auto_apply_threshold"],
            consecutive_approvals=0,
            last_rejection_type=action_type,
        )

    def on_approval(self) -> TrustLevel:
        """Increment approval count and maybe escalate."""
        updated = TrustLevel(
            level=self.level,
            auto_apply_threshold=self.auto_apply_threshold,
            consecutive_approvals=self.consecutive_approvals + 1,
        )
        return updated.maybe_escalate()


# ---------------------------------------------------------------------------
# Rules I/O
# ---------------------------------------------------------------------------

def load_rules(rules_path: Path) -> dict[str, Any]:
    """Load user rules from YAML, returning defaults if file missing."""
    if not rules_path.exists():
        return dict(DEFAULT_RULES)
    try:
        data = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return dict(DEFAULT_RULES)
        return data
    except Exception:
        return dict(DEFAULT_RULES)


def save_rules(rules_path: Path, rules: dict[str, Any]) -> None:
    """Persist rules to YAML."""
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules_path.write_text(
        yaml.dump(rules, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# History / audit trail
# ---------------------------------------------------------------------------

def load_history(history_path: Path, limit: int = 100) -> list[dict[str, Any]]:
    """Load action history entries (most recent first)."""
    if not history_path.exists():
        return []
    try:
        data = yaml.safe_load(history_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return list(reversed(data[-limit:]))
    except Exception:
        return []


def append_history(
    history_path: Path,
    action: FileAction,
    moved_by: str,
) -> None:
    """Append a FileAction to the history log."""
    history_path.parent.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    if history_path.exists():
        try:
            data = yaml.safe_load(history_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                entries = data
        except Exception:
            pass

    entry = asdict(action)
    entry["moved_by"] = moved_by
    entry["timestamp"] = datetime.now().isoformat()
    entries.append(entry)

    history_path.write_text(
        yaml.dump(entries, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Trust level
# ---------------------------------------------------------------------------

def get_trust_level(history_path: Path) -> TrustLevel:
    """Compute current trust level from history."""
    entries = load_history(history_path, limit=200)
    if not entries:
        return TrustLevel()

    consecutive = 0
    for entry in entries:
        status = entry.get("approval_status")
        if status == "approved":
            consecutive += 1
        elif status == "rejected":
            break
        # Entries without approval_status (auto-applied) count as approvals
        elif status is None and entry.get("moved_by") == "autoloop":
            consecutive += 1

    trust = TrustLevel(consecutive_approvals=consecutive)
    # Escalate through levels
    while trust.consecutive_approvals >= TRUST_ESCALATION_THRESHOLD:
        trust = trust.maybe_escalate()

    return trust


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_archive_dir() -> Path:
    """Archive directory for low-value files."""
    return get_skill_documents_dir("file-manager") / "archive"


def get_pending_dir(topic: str | None = None) -> Path:
    """Pending directory for files awaiting skill creation."""
    base = get_skill_documents_dir("file-manager") / "pending"
    if topic:
        return base / topic
    return base


def get_rules_path() -> Path:
    """Path to user's rules config."""
    return get_skill_vault_dir("file-manager") / "rules.yaml"


def get_history_path() -> Path:
    """Path to action history log."""
    return get_skill_vault_dir("file-manager") / "history.yaml"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_rules_engine.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/file-manager/scripts/rules_engine.py skills/file-manager/augur/tests/test_rules_engine.py
git commit -m "feat(file-manager): add rules engine — FileAction, TrustLevel, rules/history I/O"
```

---

## Phase 3: MCP Tools

### Task 6: Add `x-augur-file-intake` to SkillRecord

**Files:**
- Modify: `src/plugins/skill_discovery.py:52-77` (SkillRecord dataclass)
- Modify: `src/plugins/skill_discovery.py:351-363` (field extraction in `_process_skill_dir`)

- [ ] **Step 1: Add `file_intake` field to SkillRecord**

In `src/plugins/skill_discovery.py`, add to the SkillRecord dataclass in the defaults section (after `origin: str = ""`, around line 76):

```python
    file_intake: dict = field(default_factory=dict)  # x-augur-file-intake
```

Note: Must go in the defaults section (after fields with defaults) to avoid `TypeError: non-default argument follows default argument`.

- [ ] **Step 2: Extract `x-augur-file-intake` in `_process_skill_dir`**

After line 363 (`config = _extract_dict_field(frontmatter, "x-augur-config")`), add:

```python
    file_intake = _extract_dict_field(frontmatter, "x-augur-file-intake")
```

And add `file_intake=file_intake,` to the SkillRecord constructor call (after `config=config,`).

- [ ] **Step 3: Run existing discovery tests**

```bash
cd ~/Projects/Augur && python -m pytest -k "skill_discovery or discover" -v 2>&1 | tail -20
```

Expected: All existing tests still pass.

- [ ] **Step 4: Commit**

```bash
git add src/plugins/skill_discovery.py
git commit -m "feat(skill-discovery): add file_intake field to SkillRecord for x-augur-file-intake"
```

### Task 7: Implement `scan-folder` MCP tool

**Files:**
- Create: `skills/file-manager/scripts/mcp/tools_organize.py`
- Create: `skills/file-manager/augur/tests/test_tools_organize.py`
- Modify: `skills/file-manager/scripts/mcp/__init__.py` (register new tools)

- [ ] **Step 1: Write failing test for scan-folder**

```python
# skills/file-manager/augur/tests/test_tools_organize.py
"""Tests for file-manager organize MCP tools."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# conftest.py handles sys.path bootstrap
from mcp.tools_organize import scan_folder_impl


class TestScanFolder:
    """Tests for scan_folder_impl (pure function, no MCP decorator)."""

    def test_scan_single_file(self, tmp_path):

        test_file = tmp_path / "report.pdf"
        test_file.write_bytes(b"fake pdf content here")

        result = json.loads(scan_folder_impl(str(test_file)))
        assert result["success"] is True
        assert len(result["files"]) == 1
        assert result["files"][0]["name"] == "report.pdf"
        assert result["files"][0]["extension"] == ".pdf"
        assert result["files"][0]["size"] > 0

    def test_scan_directory(self, tmp_path):

        (tmp_path / "a.txt").write_text("hello")
        (tmp_path / "b.pdf").write_bytes(b"pdf")
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "c.md").write_text("# doc")

        result = json.loads(scan_folder_impl(str(tmp_path)))
        assert result["success"] is True
        assert result["total_files"] >= 3
        assert result["total_size"] > 0
        assert len(result["extensions"]) >= 2

    def test_scan_nonexistent_path(self):

        result = json.loads(scan_folder_impl("/nonexistent/path"))
        assert result["success"] is False
        assert "error" in result

    def test_scan_hidden_files_skipped(self, tmp_path):

        (tmp_path / "visible.txt").write_text("yes")
        (tmp_path / ".hidden").write_text("no")

        result = json.loads(scan_folder_impl(str(tmp_path)))
        names = [f["name"] for f in result["files"]]
        assert "visible.txt" in names
        assert ".hidden" not in names

    def test_content_sample_for_text_files(self, tmp_path):

        (tmp_path / "readme.md").write_text("# Medical Records\n\nBlood test results from 2026.")

        result = json.loads(scan_folder_impl(str(tmp_path), include_content_sample=True))
        file_entry = result["files"][0]
        assert "content_sample" in file_entry
        assert "Medical Records" in file_entry["content_sample"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_tools_organize.py -v 2>&1 | head -20
```

Expected: ImportError.

- [ ] **Step 3: Implement scan-folder**

```python
# skills/file-manager/scripts/mcp/tools_organize.py
"""File organization MCP tools — scan, domain-map, rules, apply, browse.

Tools provide data and execution. AI clients make triage decisions.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# Path bootstrap
_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.config.paths import (
    get_skill_vault_dir,
    get_skill_documents_dir,
)
from src.logging import get_entity_logger

logger = get_entity_logger("file-manager.tools_organize")

# Add scripts dir so bare imports (rules_engine) resolve
_scripts_dir = Path(__file__).resolve().parents[1]
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

# Constants
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".next", "runtime", ".DS_Store"}
MAX_FILES = 200
MAX_DEPTH = 5
CONTENT_SAMPLE_MAX = 500  # chars
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".py", ".ts", ".js", ".html", ".xml", ".log"}


# ---------------------------------------------------------------------------
# scan-folder implementation (pure function for testability)
# ---------------------------------------------------------------------------

def scan_folder_impl(
    path: str,
    include_content_sample: bool = False,
    max_files: int = MAX_FILES,
) -> str:
    """Analyze a folder or file, return metadata + optional content sample.

    Returns JSON string with file metadata for AI triage.
    """
    target = Path(path).expanduser().resolve()

    if not target.exists():
        return json.dumps({"success": False, "error": f"Path not found: {path}"})

    files: list[dict[str, Any]] = []
    extensions: Counter = Counter()
    total_size = 0

    if target.is_file():
        entry = _file_entry(target, target.parent, include_content_sample)
        files.append(entry)
        extensions[entry["extension"]] += 1
        total_size = entry["size"]
    else:
        _scan_dir(target, target, files, extensions, include_content_sample, max_files, 0)
        total_size = sum(f["size"] for f in files)

    return json.dumps({
        "success": True,
        "path": str(target),
        "is_directory": target.is_dir(),
        "total_files": len(files),
        "total_size": total_size,
        "extensions": dict(extensions.most_common()),
        "files": files,
    })


def _scan_dir(
    directory: Path,
    root: Path,
    files: list,
    extensions: Counter,
    include_content: bool,
    max_files: int,
    depth: int,
) -> None:
    """Recursively scan directory."""
    if depth > MAX_DEPTH or len(files) >= max_files:
        return

    try:
        entries = sorted(directory.iterdir(), key=lambda p: p.name)
    except PermissionError:
        return

    for entry in entries:
        if len(files) >= max_files:
            return
        if entry.name.startswith(".") or entry.name in SKIP_DIRS:
            continue
        if entry.is_dir():
            _scan_dir(entry, root, files, extensions, include_content, max_files, depth + 1)
        elif entry.is_file():
            file_data = _file_entry(entry, root, include_content)
            files.append(file_data)
            extensions[file_data["extension"]] += 1


def _file_entry(path: Path, root: Path, include_content: bool) -> dict[str, Any]:
    """Build metadata dict for a single file."""
    try:
        stat = path.stat()
        size = stat.st_size
        modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
    except OSError:
        size = 0
        modified = ""

    entry: dict[str, Any] = {
        "name": path.name,
        "path": str(path),
        "relative_path": str(path.relative_to(root)) if _is_relative_to(path, root) else str(path),
        "extension": path.suffix.lower(),
        "size": size,
        "modified": modified,
        "is_directory": False,
    }

    if include_content and path.suffix.lower() in TEXT_EXTENSIONS and size < 50_000:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            entry["content_sample"] = content[:CONTENT_SAMPLE_MAX]
        except Exception:
            pass

    return entry


def _is_relative_to(path: Path, root: Path) -> bool:
    """Check if path is relative to root (Python 3.9+ compat)."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register_organize_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable,
    metrics: Any = None,
) -> None:
    """Register file organization MCP tools."""

    from ._shared import tool_annotations

    @mcp.tool(
        name="scan-folder",
        annotations=tool_annotations({
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        }),
    )
    @mcp_tool_interceptor
    async def scan_folder_tool(
        path: str = "~/Downloads",
        include_content_sample: bool = False,
    ) -> str:
        """Analyze a folder or file — returns metadata and optional content samples for AI triage.

        Args:
            path: File or folder path to scan. Defaults to ~/Downloads.
            include_content_sample: If true, include first 500 chars of text files.

        Returns:
            JSON with file metadata: name, path, extension, size, modified, content_sample.
        """
        return scan_folder_impl(path, include_content_sample)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_tools_organize.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/file-manager/scripts/mcp/tools_organize.py skills/file-manager/augur/tests/test_tools_organize.py
git commit -m "feat(file-manager): add scan-folder MCP tool"
```

### Task 8: Implement `get-domain-map` MCP tool

**Files:**
- Modify: `skills/file-manager/scripts/mcp/tools_organize.py`
- Modify: `skills/file-manager/augur/tests/test_tools_organize.py`

- [ ] **Step 1: Write failing test for get-domain-map**

Add to `test_tools_organize.py`:

```python
class TestGetDomainMap:
    def test_returns_skills_with_file_intake(self):
        from mcp.tools_organize import get_domain_map_impl

        # Mock discover_all_skills to return fake skill records
        from unittest.mock import MagicMock

        mock_skill = MagicMock()
        mock_skill.name = "health"
        mock_skill.file_intake = {
            "accepts": ["medical records", "lab results"],
            "folder": "health",
            "subfolders": ["labs", "insurance"],
        }

        mock_skill_no_intake = MagicMock()
        mock_skill_no_intake.name = "adr"
        mock_skill_no_intake.file_intake = {}

        with patch(
            "mcp.tools_organize.discover_all_skills",
            return_value=[mock_skill, mock_skill_no_intake],
        ):
            result = json.loads(get_domain_map_impl())

        assert result["success"] is True
        assert len(result["skills"]) == 1
        assert result["skills"][0]["name"] == "health"
        assert "archive_path" in result
        assert "pending_path" in result

    def test_returns_empty_when_no_intake_skills(self):
        from mcp.tools_organize import get_domain_map_impl

        with patch(
            "mcp.tools_organize.discover_all_skills",
            return_value=[],
        ):
            result = json.loads(get_domain_map_impl())

        assert result["success"] is True
        assert result["skills"] == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_tools_organize.py::TestGetDomainMap -v
```

- [ ] **Step 3: Implement get-domain-map**

Add to `tools_organize.py`:

```python
from src.plugins.skill_discovery import discover_all_skills


def get_domain_map_impl() -> str:
    """Assemble domain map from all skills with x-augur-file-intake declarations."""
    skills = discover_all_skills()
    intake_skills = []

    for skill in skills:
        if not skill.file_intake:
            continue
        intake = skill.file_intake
        docs_dir = get_skill_documents_dir(skill.name)
        intake_skills.append({
            "name": skill.name,
            "documents_dir": str(docs_dir),
            "accepts": intake.get("accepts", []),
            "folder": intake.get("folder", skill.name),
            "subfolders": intake.get("subfolders", []),
        })

    return json.dumps({
        "success": True,
        "skills": intake_skills,
        "archive_path": str(get_skill_documents_dir("file-manager") / "archive"),
        "pending_path": str(get_skill_documents_dir("file-manager") / "pending"),
    })
```

And register the tool in `register_organize_tools`:

```python
    @mcp.tool(
        name="get-domain-map",
        annotations=tool_annotations({
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def get_domain_map_tool() -> str:
        """Return all skills with x-augur-file-intake declarations and their document directories.

        Used by AI clients to understand which skills accept which file types.
        """
        return get_domain_map_impl()
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_tools_organize.py -v
```

- [ ] **Step 5: Commit**

```bash
git add skills/file-manager/scripts/mcp/tools_organize.py skills/file-manager/augur/tests/test_tools_organize.py
git commit -m "feat(file-manager): add get-domain-map MCP tool"
```

### Task 9: Implement `apply-file-actions` MCP tool

**Files:**
- Modify: `skills/file-manager/scripts/mcp/tools_organize.py`
- Modify: `skills/file-manager/augur/tests/test_tools_organize.py`

- [ ] **Step 1: Write failing test for apply-file-actions**

```python
class TestApplyFileActions:
    def test_move_file(self, tmp_path):
        from mcp.tools_organize import apply_file_actions_impl

        # Create source file
        source = tmp_path / "source" / "report.pdf"
        source.parent.mkdir()
        source.write_bytes(b"pdf content")

        dest = tmp_path / "dest"
        history_path = tmp_path / "history.yaml"

        actions = [{
            "source_path": str(source),
            "new_name": "2026-03-report.pdf",
            "destination": str(dest),
            "action": "move",
            "reason": "Finance domain match",
            "skill_target": "finance",
        }]

        result = json.loads(apply_file_actions_impl(
            json.dumps(actions), "test-agent", str(history_path)
        ))

        assert result["success"] is True
        assert result["applied"] == 1
        assert result["failed"] == 0
        assert (dest / "2026-03-report.pdf").exists()
        assert not source.exists()

    def test_archive_file(self, tmp_path):
        from mcp.tools_organize import apply_file_actions_impl

        source = tmp_path / "old.log"
        source.write_text("stale log")

        archive = tmp_path / "archive"
        history_path = tmp_path / "history.yaml"

        actions = [{
            "source_path": str(source),
            "new_name": None,
            "destination": str(archive),
            "action": "archive",
            "reason": "Low-value log",
            "skill_target": None,
        }]

        result = json.loads(apply_file_actions_impl(
            json.dumps(actions), "test-agent", str(history_path)
        ))

        assert result["success"] is True
        assert (archive / "old.log").exists()

    def test_handles_missing_source(self, tmp_path):
        from mcp.tools_organize import apply_file_actions_impl

        history_path = tmp_path / "history.yaml"
        actions = [{
            "source_path": "/nonexistent/file.txt",
            "new_name": None,
            "destination": str(tmp_path / "dest"),
            "action": "move",
            "reason": "test",
            "skill_target": None,
        }]

        result = json.loads(apply_file_actions_impl(
            json.dumps(actions), "test-agent", str(history_path)
        ))

        assert result["applied"] == 0
        assert result["failed"] == 1

    def test_logs_to_history(self, tmp_path):
        from mcp.tools_organize import apply_file_actions_impl
        from rules_engine import load_history

        source = tmp_path / "test.txt"
        source.write_text("hello")

        dest = tmp_path / "dest"
        history_path = tmp_path / "history.yaml"

        actions = [{
            "source_path": str(source),
            "new_name": None,
            "destination": str(dest),
            "action": "move",
            "reason": "test",
            "skill_target": None,
        }]

        apply_file_actions_impl(json.dumps(actions), "test-agent", str(history_path))

        entries = load_history(history_path)
        assert len(entries) == 1
        assert entries[0]["moved_by"] == "test-agent"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_tools_organize.py::TestApplyFileActions -v
```

- [ ] **Step 3: Implement apply-file-actions**

Add to `tools_organize.py`:

```python
import shutil

from rules_engine import FileAction, append_history, get_history_path as _default_history_path


def apply_file_actions_impl(
    actions_json: str,
    moved_by: str = "unknown",
    history_path_override: str | None = None,
) -> str:
    """Execute a list of file actions (rename + move), log to history.

    Args:
        actions_json: JSON array of FileAction dicts.
        moved_by: Who initiated the actions (agent name, "autoloop", etc.).
        history_path_override: Override history path (for testing).
    """
    try:
        raw_actions = json.loads(actions_json)
    except json.JSONDecodeError as e:
        return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})

    if not isinstance(raw_actions, list):
        return json.dumps({"success": False, "error": "Expected JSON array of actions"})

    history_path = Path(history_path_override) if history_path_override else _default_history_path()

    applied = 0
    failed = 0
    errors: list[str] = []
    affected_skills: set[str] = set()

    for raw in raw_actions:
        try:
            action = FileAction(**raw)
        except (TypeError, ValueError) as e:
            errors.append(f"Invalid action: {e}")
            failed += 1
            continue

        source = Path(action.source_path).expanduser().resolve()
        if not source.exists():
            errors.append(f"Source not found: {action.source_path}")
            failed += 1
            continue

        dest_dir = Path(action.destination).expanduser().resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)

        final_name = action.new_name or source.name
        dest_file = dest_dir / final_name

        # Avoid overwriting existing files
        if dest_file.exists():
            stem = dest_file.stem
            suffix = dest_file.suffix
            counter = 1
            while dest_file.exists():
                dest_file = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        try:
            shutil.move(str(source), str(dest_file))
            append_history(history_path, action, moved_by)
            applied += 1
            if action.skill_target:
                affected_skills.add(action.skill_target)
        except Exception as e:
            errors.append(f"Failed to move {source.name}: {e}")
            failed += 1

    return json.dumps({
        "success": failed == 0,
        "applied": applied,
        "failed": failed,
        "errors": errors,
        "affected_skills": sorted(affected_skills),
    })
```

Register the tool:

```python
    @mcp.tool(
        name="apply-file-actions",
        annotations=tool_annotations({
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        }),
    )
    @mcp_tool_interceptor
    async def apply_file_actions_tool(
        actions: str,
        moved_by: str = "ide-agent",
    ) -> str:
        """Execute a plan of file actions — rename + move files, log to history.

        Args:
            actions: JSON array of FileAction objects. Each has: source_path, new_name (nullable),
                     destination, action ("move"|"archive"|"pending"), reason, skill_target (nullable).
            moved_by: Who initiated (e.g. "ide-agent", "autoloop", "cowork").

        Returns:
            JSON with applied count, failed count, errors, affected skill names.
        """
        return apply_file_actions_impl(actions, moved_by)
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_tools_organize.py -v
```

- [ ] **Step 5: Commit**

```bash
git add skills/file-manager/scripts/mcp/tools_organize.py skills/file-manager/augur/tests/test_tools_organize.py
git commit -m "feat(file-manager): add apply-file-actions MCP tool"
```

### Task 10: Implement remaining MCP tools (get-rules, update-rules, get-pending, get-archive, get-file-history)

**Files:**
- Modify: `skills/file-manager/scripts/mcp/tools_organize.py`
- Modify: `skills/file-manager/augur/tests/test_tools_organize.py`

- [ ] **Step 1: Write failing tests for rules tools**

```python
class TestGetRules:
    def test_returns_defaults_when_no_file(self, tmp_path):
        from mcp.tools_organize import get_rules_impl
        result = json.loads(get_rules_impl(str(tmp_path / "rules.yaml")))
        assert result["success"] is True
        assert "watched_folders" in result["rules"]

    def test_returns_saved_rules(self, tmp_path):
        from mcp.tools_organize import get_rules_impl, update_rules_impl
        rules_path = str(tmp_path / "rules.yaml")
        update_rules_impl(
            json.dumps({"watched_folders": ["~/Desktop"]}),
            rules_path,
        )
        result = json.loads(get_rules_impl(rules_path))
        assert result["rules"]["watched_folders"] == ["~/Desktop"]


class TestUpdateRules:
    def test_save_rules(self, tmp_path):
        from mcp.tools_organize import update_rules_impl
        rules_path = str(tmp_path / "rules.yaml")
        result = json.loads(update_rules_impl(
            json.dumps({"watched_folders": ["~/Custom"]}),
            rules_path,
        ))
        assert result["success"] is True


class TestGetPending:
    def test_lists_pending_topics(self, tmp_path):
        from mcp.tools_organize import get_pending_impl
        pending = tmp_path / "pending"
        (pending / "car-maintenance").mkdir(parents=True)
        (pending / "car-maintenance" / "manual.pdf").write_bytes(b"pdf")
        (pending / "recipes").mkdir(parents=True)

        result = json.loads(get_pending_impl(str(pending)))
        assert result["success"] is True
        assert len(result["topics"]) == 2

    def test_empty_pending(self, tmp_path):
        from mcp.tools_organize import get_pending_impl
        result = json.loads(get_pending_impl(str(tmp_path / "nonexistent")))
        assert result["success"] is True
        assert result["topics"] == []


class TestGetArchive:
    def test_lists_archive_files(self, tmp_path):
        from mcp.tools_organize import get_archive_impl
        archive = tmp_path / "archive"
        archive.mkdir()
        (archive / "old.log").write_text("stale")
        (archive / "junk.tmp").write_text("junk")

        result = json.loads(get_archive_impl(str(archive)))
        assert result["success"] is True
        assert result["total_files"] == 2


class TestGetFileHistory:
    def test_returns_history(self, tmp_path):
        from mcp.tools_organize import get_file_history_impl
        from rules_engine import FileAction, append_history

        history_path = tmp_path / "history.yaml"
        action = FileAction(
            source_path="/tmp/test.pdf",
            new_name="renamed.pdf",
            destination="/docs",
            action="move",
            reason="test",
            skill_target="health",
        )
        append_history(history_path, action, "test")

        result = json.loads(get_file_history_impl(str(history_path)))
        assert result["success"] is True
        assert len(result["entries"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_tools_organize.py -k "Rules or Pending or Archive or History" -v
```

- [ ] **Step 3: Implement the remaining tools**

Add to `tools_organize.py`:

```python
from rules_engine import load_rules, save_rules, load_history, get_rules_path, get_archive_dir, get_pending_dir


def get_rules_impl(rules_path_override: str | None = None) -> str:
    """Return user rules config."""
    path = Path(rules_path_override) if rules_path_override else get_rules_path()
    rules = load_rules(path)
    return json.dumps({"success": True, "rules": rules})


def update_rules_impl(rules_json: str, rules_path_override: str | None = None) -> str:
    """Update user rules config."""
    try:
        rules = json.loads(rules_json)
    except json.JSONDecodeError as e:
        return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})

    path = Path(rules_path_override) if rules_path_override else get_rules_path()
    save_rules(path, rules)
    return json.dumps({"success": True})


def get_pending_impl(pending_dir_override: str | None = None) -> str:
    """List files in pending/ awaiting skill creation decisions."""
    pending_dir = Path(pending_dir_override) if pending_dir_override else get_pending_dir()
    if not pending_dir.exists():
        return json.dumps({"success": True, "topics": []})

    topics = []
    for topic_dir in sorted(pending_dir.iterdir()):
        if not topic_dir.is_dir() or topic_dir.name.startswith("."):
            continue
        files = [f.name for f in topic_dir.iterdir() if f.is_file()]
        topics.append({
            "topic": topic_dir.name,
            "file_count": len(files),
            "files": files[:20],
        })

    return json.dumps({"success": True, "topics": topics})


def get_archive_impl(archive_dir_override: str | None = None) -> str:
    """Browse archive folder."""
    archive_dir = Path(archive_dir_override) if archive_dir_override else get_archive_dir()
    if not archive_dir.exists():
        return json.dumps({"success": True, "total_files": 0, "files": []})

    files = []
    for f in sorted(archive_dir.rglob("*")):
        if f.is_file() and not f.name.startswith("."):
            try:
                stat = f.stat()
                files.append({
                    "name": f.name,
                    "path": str(f),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except OSError:
                continue

    return json.dumps({"success": True, "total_files": len(files), "files": files[:100]})


def get_file_history_impl(history_path_override: str | None = None, limit: int = 50) -> str:
    """Return audit trail of past file moves/renames."""
    path = Path(history_path_override) if history_path_override else _default_history_path()
    entries = load_history(path, limit=limit)
    return json.dumps({"success": True, "entries": entries, "total": len(entries)})
```

Register all tools in `register_organize_tools`:

```python
    @mcp.tool(name="get-rules", annotations=tool_annotations({"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def get_rules_tool() -> str:
        """Return user's file organization rules config (watched folders, overrides)."""
        return get_rules_impl()

    @mcp.tool(name="update-rules", annotations=tool_annotations({"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def update_rules_tool(rules: str) -> str:
        """Update user's file organization rules. Args: rules — JSON object with watched_folders, overrides, etc."""
        return update_rules_impl(rules)

    @mcp.tool(name="get-pending", annotations=tool_annotations({"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def get_pending_tool() -> str:
        """List files in pending/ awaiting skill creation decisions — grouped by topic."""
        return get_pending_impl()

    @mcp.tool(name="get-archive", annotations=tool_annotations({"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def get_archive_tool() -> str:
        """Browse the archive folder — low-value files sorted by extension/date."""
        return get_archive_impl()

    @mcp.tool(name="get-file-history", annotations=tool_annotations({"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}))
    @mcp_tool_interceptor
    async def get_file_history_tool(limit: int = 50) -> str:
        """Audit trail of past file moves/renames — what moved, where, when, by whom."""
        return get_file_history_impl(limit=limit)
```

- [ ] **Step 4: Run all tests**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_tools_organize.py -v
```

- [ ] **Step 5: Commit**

```bash
git add skills/file-manager/scripts/mcp/tools_organize.py skills/file-manager/augur/tests/test_tools_organize.py
git commit -m "feat(file-manager): add get-rules, update-rules, get-pending, get-archive, get-file-history tools"
```

### Task 11: Wire new tools into MCP registration

**Files:**
- Modify: `skills/file-manager/scripts/mcp/__init__.py`

- [ ] **Step 1: Read current __init__.py**

Read `skills/file-manager/scripts/mcp/__init__.py`.

- [ ] **Step 2: Add import and call for register_organize_tools**

The existing `__init__.py` calls `register_status_tools()` and `register_context_tools()`. Add `register_organize_tools()`:

```python
from .tools_organize import register_organize_tools

def register_tools(mcp, mcp_tool_interceptor, metrics=None):
    register_status_tools(mcp, mcp_tool_interceptor, metrics)
    register_context_tools(mcp, mcp_tool_interceptor, metrics)
    register_organize_tools(mcp, mcp_tool_interceptor, metrics)
```

- [ ] **Step 3: Verify MCP tool listing**

```bash
cd ~/Projects/Augur && python -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'skills/file-manager/scripts')
from mcp.tools_organize import register_organize_tools
print('Import OK — tools_organize module loads')
"
```

- [ ] **Step 4: Commit**

```bash
git add skills/file-manager/scripts/mcp/__init__.py
git commit -m "feat(file-manager): wire organize tools into MCP registration"
```

---

## Phase 4: Attention Skill Extension

### Task 12: Add `"file-action"` source type to attention system

**Files:**
- Modify: `skills/attention/scripts/triage.py:194` (source_weights dict)
- Modify: `skills/attention/scripts/mcp/tools_attention.py:93-198` (act_on_attention_item)
- Modify: `skills/channels/augur/lib/registry.py:435` (raise_attention docstring — update accepted source_types)

- [ ] **Step 1: Add `"file-action"` to source_weights in triage.py**

In `skills/attention/scripts/triage.py`, find the `source_weights` dict (line ~194) and add:

```python
    source_weights: dict[str, float] = {
        "review": 0.3,
        "inbox": 0.2,
        "notification": 0.15,
        "file-action": 0.25,  # Structured action with serialized FileAction payload
        "unknown": 0.05,
    }
```

- [ ] **Step 2: Add `"file-action"` dispatch branch in act_on_attention_item**

In `skills/attention/scripts/mcp/tools_attention.py`, after the review delegation block (line ~165, before the route validation), add a file-action dispatch branch:

```python
    # For approve on file-action items, execute the stored file actions
    if action == "approve" and item.get("source_type") == "file-action":
        callback_payload = item.get("action", {}).get("callback")
        if callback_payload:
            try:
                # Import file-manager's apply tool via importlib to avoid
                # namespace collision with the `mcp` PyPI package
                import importlib.util
                from src.config.paths import get_skills_dir
                fm_tools = get_skills_dir() / "file-manager" / "scripts" / "mcp" / "tools_organize.py"
                spec = importlib.util.spec_from_file_location("fm_tools_organize", fm_tools)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                apply_result = json.loads(mod.apply_file_actions_impl(
                    json.dumps(callback_payload),
                    moved_by="attention-approve",
                ))
                resolution["apply_result"] = apply_result
            except Exception as e:
                logger.warning(
                    "Failed to apply file actions for %s: %s", item_id, e,
                )
                resolution["apply_error"] = str(e)
```

- [ ] **Step 3: Update raise_attention docstring**

In `skills/channels/augur/lib/registry.py`, update the `source_type` parameter docstring to include `"file-action"`:

```python
        source_type: Origin channel — ``"review"``, ``"inbox"``, ``"notification"``,
            or ``"file-action"``.
```

- [ ] **Step 4: Run attention tests**

```bash
cd ~/Projects/Augur && python -m pytest skills/attention/augur/tests/ -v 2>&1 | tail -20
```

Expected: All existing tests still pass.

- [ ] **Step 5: Commit**

```bash
git add skills/attention/scripts/triage.py skills/attention/scripts/mcp/tools_attention.py skills/channels/augur/lib/registry.py
git commit -m "feat(attention): add file-action source type — pilot for autoloop-to-inbox pattern"
```

---

## Phase 5: Autoloop

### Task 13: Create file-organizer autoloop script

**Files:**
- Create: `skills/file-manager/scripts/autoloop.py`
- Create: `skills/file-manager/augur/tests/test_autoloop.py`

- [ ] **Step 1: Write failing test for autoloop scan phase**

```python
# skills/file-manager/augur/tests/test_autoloop.py
"""Tests for file-organizer autoloop."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


class TestAutoloopScan:
    def test_scan_finds_files_in_watched_folders(self, tmp_path):
        from autoloop import scan_watched_folders

        watched = tmp_path / "Downloads"
        watched.mkdir()
        (watched / "report.pdf").write_bytes(b"pdf")
        (watched / "photo.jpg").write_bytes(b"jpg")

        rules = {"watched_folders": [str(watched)]}
        result = scan_watched_folders(rules)

        assert result["total_files"] >= 2
        assert len(result["folders"]) == 1

    def test_scan_skips_empty_folders(self, tmp_path):
        from autoloop import scan_watched_folders

        watched = tmp_path / "EmptyDir"
        watched.mkdir()

        rules = {"watched_folders": [str(watched)]}
        result = scan_watched_folders(rules)
        assert result["total_files"] == 0

    def test_scan_handles_missing_folders(self, tmp_path):
        from autoloop import scan_watched_folders

        rules = {"watched_folders": [str(tmp_path / "nonexistent")]}
        result = scan_watched_folders(rules)
        assert result["total_files"] == 0
        assert len(result["errors"]) == 0  # Missing folders are silently skipped


class TestAutoloopDifficulty:
    def test_d0_report_only(self, tmp_path):
        from autoloop import should_auto_apply

        # At d0, nothing is auto-applied
        assert should_auto_apply(difficulty=0, confidence=0.99, trust_level="high") is False

    def test_d1_rename_with_high_confidence(self):
        from autoloop import should_auto_apply

        # d1 allows renames with high confidence + trust
        assert should_auto_apply(difficulty=1, confidence=0.95, trust_level="low", action="move") is False
        assert should_auto_apply(difficulty=1, confidence=0.95, trust_level="high", action="move") is True

    def test_d4_always_needs_human(self):
        from autoloop import should_auto_apply

        # d4 (skill discovery) always goes to attention inbox
        assert should_auto_apply(difficulty=4, confidence=0.99, trust_level="high") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_autoloop.py -v 2>&1 | head -20
```

- [ ] **Step 3: Implement autoloop**

```python
# skills/file-manager/scripts/autoloop.py
"""File-organizer nightly autoloop — scan watched folders, apply trust-gated actions.

Difficulty levels:
  d0 — Scan and report only
  d1 — Rename high-confidence matches
  d2 — Rename + move to skill domains
  d3 — Full triage: archive + action detection
  d4 — Skill discovery suggestions (always needs human)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Add scripts dir so bare imports (rules_engine, mcp.*) resolve
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from src.config.paths import get_skill_vault_dir
from src.logging import get_entity_logger

from rules_engine import (
    load_rules,
    get_trust_level,
    get_history_path,
    get_rules_path,
    TrustLevel,
    TRUST_LEVELS,
)
from mcp.tools_organize import scan_folder_impl

logger = get_entity_logger("file-manager.autoloop")


def scan_watched_folders(rules: dict[str, Any]) -> dict[str, Any]:
    """Scan all watched folders and return aggregated metadata.

    Args:
        rules: User rules dict with watched_folders list.

    Returns:
        Dict with total_files, folders (per-folder scan results), errors.
    """
    watched = rules.get("watched_folders", [])
    folders = []
    total_files = 0
    errors: list[str] = []

    for folder_path in watched:
        expanded = Path(folder_path).expanduser()
        if not expanded.exists():
            continue  # Silently skip missing folders

        result = json.loads(scan_folder_impl(str(expanded), include_content_sample=True))
        if result.get("success"):
            folders.append({
                "path": str(expanded),
                "files": result["files"],
                "total_files": result["total_files"],
                "extensions": result["extensions"],
            })
            total_files += result["total_files"]
        else:
            errors.append(result.get("error", f"Scan failed: {folder_path}"))

    return {
        "total_files": total_files,
        "folders": folders,
        "errors": errors,
    }


def should_auto_apply(
    difficulty: int,
    confidence: float,
    trust_level: str = "low",
    action: str = "move",
) -> bool:
    """Determine if an action should be auto-applied based on difficulty and trust.

    Args:
        difficulty: Current autoloop difficulty level (0-4).
        confidence: AI confidence in the action (0.0-1.0).
        trust_level: Current trust level ("low", "medium", "high").
        action: The action type ("move", "archive", "pending").

    Returns:
        True if the action should be auto-applied without human approval.
    """
    # d0 is report-only
    if difficulty == 0:
        return False

    # d4 (skill discovery) always needs human
    if difficulty >= 4:
        return False

    # Check trust-based threshold
    threshold = TRUST_LEVELS.get(trust_level, TRUST_LEVELS["low"])["auto_apply_threshold"]

    # d1 only allows renames (moves with name change), not cross-folder moves
    if difficulty == 1 and action != "move":
        return False

    # d1-d2 need trust + confidence
    if difficulty <= 2:
        return confidence >= threshold

    # d3 allows archive routing + action detection
    if difficulty == 3:
        return confidence >= threshold

    return False


def raise_file_attention(
    title: str,
    summary: str,
    file_actions: list[dict],
    priority: str = "medium",
) -> str | None:
    """Raise an attention item for file actions needing approval.

    Returns the attention item ID, or None on failure.
    """
    try:
        # Import channels registry for raise_attention
        channels_lib = _project_root / "skills" / "channels" / "augur" / "lib"
        if str(channels_lib.parent.parent) not in sys.path:
            sys.path.insert(0, str(channels_lib.parent.parent))

        from augur.lib.registry import raise_attention

        item_id = raise_attention(
            skill="file-manager",
            source_type="file-action",
            title=title,
            summary=summary,
            priority=priority,
            action={"callback": file_actions},
        )
        return item_id
    except Exception as e:
        logger.warning("Failed to raise attention for file actions: %s", e)
        return None
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_autoloop.py -v
```

- [ ] **Step 5: Commit**

```bash
git add skills/file-manager/scripts/autoloop.py skills/file-manager/augur/tests/test_autoloop.py
git commit -m "feat(file-manager): add file-organizer autoloop with trust-aware difficulty levels"
```

---

## Phase 6: Dashboard

### Task 14: Create Browse tab page

**Files:**
- Create: `skills/file-manager/augur/dashboard/page.tsx`
- Create: `skills/file-manager/augur/dashboard/browse/page.tsx`

This task creates the Browse tab — file browser with folder intelligence panel and history view. Uses `useMcpQuery` for data fetching per rule 11. Uses shadcn/ui components.

- [ ] **Step 1: Read existing dashboard patterns**

Read `docs/agent-topics/DASHBOARD.md` for layout patterns. Check existing life hub pages for tab structure examples:
```bash
ls skills/dashboard/pages/life/
```

- [ ] **Step 2: Create the Browse page component**

The Browse page shows:
- File browser tree (uses `list-collateral-files` and `scan-folder` tools)
- Folder intelligence panel (inline, not separate tab)
- History view (uses `get-file-history` tool)

Create `skills/file-manager/augur/dashboard/page.tsx` using the hub's standard layout pattern with `useMcpQuery` hooks for `scan-folder` and `get-file-history`.

- [ ] **Step 3: Verify the page compiles**

```bash
cd ~/Projects/Augur && pnpm --filter dashboard typecheck 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add skills/file-manager/augur/dashboard/
git commit -m "feat(file-manager): add Browse dashboard tab — file browser + history"
```

### Task 15: Create Organize tab page

**Files:**
- Create: `skills/file-manager/augur/dashboard/organize/page.tsx`

The Organize tab shows:
- Watched folders list with status (uses `get-rules` tool)
- Rules editor (uses `get-rules` + `update-rules` tools)
- Pending queue (uses `get-pending` tool)
- Archive browser (uses `get-archive` tool)

- [ ] **Step 1: Create the Organize page component**

Build with `useMcpQuery` for `get-rules`, `get-pending`, `get-archive` and `useMcpMutation` for `update-rules`. Use shadcn/ui Card, Table, Button, Input components.

- [ ] **Step 2: Verify the page compiles**

```bash
cd ~/Projects/Augur && pnpm --filter dashboard typecheck 2>&1 | tail -20
```

- [ ] **Step 3: Commit**

```bash
git add skills/file-manager/augur/dashboard/organize/
git commit -m "feat(file-manager): add Organize dashboard tab — rules, pending, archive"
```

### Task 16: Update dashboard page config

**Files:**
- Modify: `skills/file-manager/SKILL.md` (contributions.pages section in config)

- [ ] **Step 1: Update contributions.pages in SKILL.md config**

Ensure the `x-augur-config` (or sidecar `config.yaml`) declares both pages:

```yaml
contributions:
  pages:
    - id: file-manager
      label: Browse
      icon: FolderOpen
      order: 1
    - id: organize
      label: Organize
      icon: Settings2
      order: 2
```

- [ ] **Step 2: Run dashboard build to verify pages mount**

```bash
/dev-build
```

- [ ] **Step 3: Commit**

```bash
git add skills/file-manager/
git commit -m "feat(file-manager): wire Browse + Organize tabs into dashboard page config"
```

---

## Phase 7: File Intake Declarations

### Task 17: Add `x-augur-file-intake` to existing skills

**Files:**
- Modify: SKILL.md for each skill that accepts documents

Add `x-augur-file-intake` frontmatter to skills that should accept file routing. Start with the most obvious domains:

- [ ] **Step 1: Add to health skill**

```yaml
x-augur-file-intake:
  accepts: ["medical records", "lab results", "insurance docs", "prescriptions", "health reports"]
  folder: health
  subfolders: [labs, insurance, prescriptions, records]
```

- [ ] **Step 2: Add to finance skill**

```yaml
x-augur-file-intake:
  accepts: ["invoices", "tax docs", "receipts", "bank statements", "financial reports"]
  folder: finance
  subfolders: [tax, invoices, receipts, statements]
```

- [ ] **Step 3: Add to career skill**

```yaml
x-augur-file-intake:
  accepts: ["resumes", "cover letters", "offer letters", "contracts", "certifications"]
  folder: career
  subfolders: [resumes, contracts, certifications, applications]
```

- [ ] **Step 4: Add to reading-list skill**

```yaml
x-augur-file-intake:
  accepts: ["ebooks", "papers", "articles", "PDFs to read"]
  folder: reading-list
  subfolders: [books, papers, articles]
```

- [ ] **Step 5: Add to wealth skill**

```yaml
x-augur-file-intake:
  accepts: ["investment statements", "portfolio reports", "tax documents", "property docs"]
  folder: wealth
  subfolders: [investments, tax, property]
```

- [ ] **Step 6: Verify domain map assembles correctly**

```bash
cd ~/Projects/Augur && python -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'skills/file-manager/scripts')
from mcp.tools_organize import get_domain_map_impl
import json
result = json.loads(get_domain_map_impl())
print(f'Skills with file intake: {len(result[\"skills\"])}')
for s in result['skills']:
    print(f'  {s[\"name\"]}: {s[\"accepts\"][:3]}...')
"
```

Expected: 5+ skills listed with their intake declarations.

- [ ] **Step 7: Commit**

```bash
git add skills/health/SKILL.md skills/finance/SKILL.md skills/career/SKILL.md skills/reading-list/SKILL.md skills/wealth/SKILL.md
git commit -m "feat: add x-augur-file-intake declarations to health, finance, career, reading-list, wealth"
```

---

## Phase 8: Skill Discovery Pipeline

### Task 18: Add pending topic resolution to autoloop

**Files:**
- Modify: `skills/file-manager/scripts/autoloop.py`
- Modify: `skills/file-manager/augur/tests/test_autoloop.py`

- [ ] **Step 1: Write failing test for pending resolution**

```python
class TestPendingResolution:
    def test_resolves_pending_when_skill_exists(self, tmp_path):
        from autoloop import check_pending_resolution
        from unittest.mock import MagicMock

        # Set up pending topic with files
        pending = tmp_path / "pending" / "car-maintenance"
        pending.mkdir(parents=True)
        (pending / "manual.pdf").write_bytes(b"pdf")

        # Mock a skill that now declares car-maintenance intake
        mock_skill = MagicMock()
        mock_skill.name = "car-maintenance"
        mock_skill.file_intake = {
            "accepts": ["car manuals", "maintenance records"],
            "folder": "car-maintenance",
        }

        with patch(
            "autoloop.discover_all_skills",
            return_value=[mock_skill],
        ), patch(
            "autoloop.get_skill_documents_dir",
            return_value=tmp_path / "docs" / "car-maintenance",
        ):
            resolved = check_pending_resolution(str(pending.parent))

        assert len(resolved) == 1
        assert resolved[0]["topic"] == "car-maintenance"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_autoloop.py::TestPendingResolution -v
```

- [ ] **Step 3: Implement check_pending_resolution**

Add to `autoloop.py`:

```python
from src.plugins.skill_discovery import discover_all_skills
from src.config.paths import get_skill_documents_dir


def check_pending_resolution(pending_dir: str | None = None) -> list[dict[str, Any]]:
    """Check if any pending topics now have matching skills.

    When /evolve creates a new skill with x-augur-file-intake matching a pending
    topic, this function detects it and returns resolution actions.

    Args:
        pending_dir: Override pending directory path (for testing).

    Returns:
        List of dicts with topic, matching_skill, and proposed actions.
    """
    from mcp.tools_organize import get_pending_dir as _default_pending

    base = Path(pending_dir) if pending_dir else _default_pending()
    if not base.exists():
        return []

    skills = discover_all_skills()
    intake_map: dict[str, Any] = {}
    for skill in skills:
        if skill.file_intake:
            intake_map[skill.name] = skill

    resolved = []
    for topic_dir in base.iterdir():
        if not topic_dir.is_dir() or topic_dir.name.startswith("."):
            continue
        topic = topic_dir.name

        # Check if a skill now matches this topic name
        if topic in intake_map:
            skill = intake_map[topic]
            docs_dir = get_skill_documents_dir(skill.name)
            files = [f for f in topic_dir.iterdir() if f.is_file()]
            actions = [
                {
                    "source_path": str(f),
                    "new_name": None,
                    "destination": str(docs_dir),
                    "action": "move",
                    "reason": f"Pending topic '{topic}' resolved — skill '{skill.name}' now exists",
                    "skill_target": skill.name,
                }
                for f in files
            ]
            resolved.append({
                "topic": topic,
                "matching_skill": skill.name,
                "file_count": len(files),
                "actions": actions,
            })

    return resolved
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/test_autoloop.py -v
```

- [ ] **Step 5: Commit**

```bash
git add skills/file-manager/scripts/autoloop.py skills/file-manager/augur/tests/test_autoloop.py
git commit -m "feat(file-manager): add pending topic resolution to autoloop"
```

### Task 19: Write ADR

**Files:**
- Create: ADR via `/adr write`

- [ ] **Step 1: Create ADR**

Run `/adr write` to create the ADR for this consolidation. It should:
- Supersede ADR-111 (Organizer Hub Hardening) and ADR-220 (Files Hardening)
- Reference the design spec
- Document: consolidation decision, rules engine, MCP tools, attention integration, autoloop, dashboard changes

- [ ] **Step 2: Commit ADR**

```bash
git add <adr-path>
git commit -m "docs: add ADR for file-manager consolidation — supersedes ADR-111, ADR-220"
```

### Task 20: Final verification

- [ ] **Step 1: Run all file-manager tests**

```bash
cd ~/Projects/Augur && python -m pytest skills/file-manager/augur/tests/ -v
```

- [ ] **Step 2: Run attention tests**

```bash
cd ~/Projects/Augur && python -m pytest skills/attention/augur/tests/ -v
```

- [ ] **Step 3: Verify MCP tools register**

```bash
cd ~/Projects/Augur && python -c "
import sys; sys.path.insert(0, '.')
from src.plugins.skill_discovery import discover_all_skills
skills = discover_all_skills()
fm = next(s for s in skills if s.name == 'file-manager')
print('MCP tools:', fm.mcp_tools)
print('File intake:', fm.file_intake)
print('Loop config:', fm.loop_config)
print('Dashboard pages:', fm.dashboard_pages)
"
```

- [ ] **Step 4: Verify organizer is fully removed**

```bash
# Should find nothing
ls skills/organizer/ 2>&1
ls skills/dashboard/pages/life/organizer/ 2>&1
rg "organizer" skills/ --type yaml -l
```

- [ ] **Step 5: Dashboard build**

```bash
/dev-build
```

- [ ] **Step 6: Verify external client flow (spec Section 6)**

Exercise the MCP tools in sequence as an external client would:

```bash
cd ~/Projects/Augur && python -c "
import sys, json; sys.path.insert(0, '.')
sys.path.insert(0, 'skills/file-manager/scripts')
from mcp.tools_organize import get_domain_map_impl, scan_folder_impl

# Step 1: get domain map
domain_map = json.loads(get_domain_map_impl())
print(f'Domain map: {len(domain_map[\"skills\"])} skills')

# Step 2: scan a folder
scan = json.loads(scan_folder_impl('~/Downloads', include_content_sample=False))
print(f'Scan: {scan.get(\"total_files\", 0)} files in Downloads')

print('External client flow: OK')
"
```

- [ ] **Step 7: Browser verification of Browse and Organize tabs**

Navigate to `localhost:3000/life/file-manager` and verify both tabs render.
Navigate to `localhost:3000/life/file-manager/organize` and verify rules/pending/archive sections.
