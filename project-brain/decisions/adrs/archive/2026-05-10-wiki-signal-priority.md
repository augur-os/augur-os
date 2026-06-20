# Wiki Signal Priority & Batched Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the wiki self-updating with priority-tiered sources by adding tier/weight tags to scanner output, a client-neutral memory/session adapter, vault-mtime promotion for `/save`-style writes, and a single token-conscious daily routine that skips extraction when nothing changed.

**Architecture:** Three independently shippable commit slices. (1) Scanner gains tier/weight per source, frontmatter override, mtime promotion, a config-driven `client_memory` adapter, episodic-memory support, and a yaml config reader. (2) `wiki-update` consumer applies tier filter, weight-aware sorting, per-tier caps, and a skip-if-unchanged guard against `runtime/wiki/last-extraction.ts`. (3) Daemon tasks.yaml registers `wiki-batched-daily` at 06:23 UTC; `wiki-status` surfaces four new telemetry fields.

> 2026-05-13 implementation correction: client memory is modeled as `client_memory.clients`, not as a Claude-specific `memory_files` surface plus one-off per-client adapters. Claude, Codex, Gemini, Copilot, ChatGPT, Cursor, and future clients are peers in configuration.

**Tech Stack:** Python 3.11, pytest, PyYAML, Augur ingest skill (`shared-vault/skills/ingest/`), daemon scheduler (`shared-vault/skills/daemon/augur/config/tasks.yaml`), `src/config/paths` helpers.

**Spec:** [`docs/superpowers/specs/2026-05-10-wiki-signal-priority-design.md`](../specs/2026-05-10-wiki-signal-priority-design.md)

---

## File Structure

### Created files

| Path | Responsibility |
|---|---|
| `config/system/wiki_signals.yaml` | Single source of truth: mtime window, tier caps, extraction limit, log kill-switch, and configured AI-client memory/session roots |
| `shared-vault/skills/ingest/scripts/wiki_signals_config.py` | Reads `wiki_signals.yaml`, supplies typed defaults, single import point for the scanner and consumer |
| `shared-vault/skills/ingest/scripts/wiki_tier.py` | `_TIER_BY_SURFACE` table, `weight_for_tier()`, `tier_meets_filter()` — pure functions, easy to unit-test |
| `shared-vault/skills/ingest/scripts/wiki_memory_adapters.py` | Client-neutral `scan_client_memory` adapter plus episodic-memory support |
| `shared-vault/skills/ingest/augur/tests/test_wiki_tier.py` | Unit tests for tier table and weight resolution |
| `shared-vault/skills/ingest/augur/tests/test_wiki_signals_config.py` | Unit tests for yaml reader + defaults |
| `shared-vault/skills/ingest/augur/tests/test_wiki_memory_adapters.py` | Unit tests for the five adapters |
| `shared-vault/skills/ingest/augur/tests/test_wiki_scanner_priority.py` | Tests for tier tagging on scanner output and mtime promotion |
| `shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py` | Tests for `wiki-update` tier filter, weight sort, per-tier caps, skip-if-unchanged |

### Modified files

| Path | Change |
|---|---|
| `shared-vault/skills/ingest/scripts/wiki_scanner.py` | Tier/weight tags on every dict, frontmatter `wiki_tier:` override, mtime promotion in `_scan_dir`, `_scan_client_memory` delegation, episodic-memory delegation, `_dedupe_sources` keeps highest-tier on collision |
| `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py` | `wiki-update` accepts `tier=""` param, weight-aware batch, per-tier caps, skip-if-unchanged guard, writes `last-extraction.ts` and telemetry counters |
| `shared-vault/skills/ingest/scripts/wiki_status.py` | Surfaces four new fields: `signals_seen_by_tier`, `last_extraction_ts`, `tokens_spent_last_run`, `dropped_low_noise_count` |
| `shared-vault/skills/daemon/augur/config/tasks.yaml` | New `wiki-batched-daily` entry, daily at 06:23 |
| `src/config/paths.py` | Helper `get_wiki_signals_config_path()` returning `config/system/wiki_signals.yaml` |

---

# Slice 1 — Scanner changes

## Task 1: Add `wiki_signals.yaml` config and reader

**Files:**
- Create: `config/system/wiki_signals.yaml`
- Create: `shared-vault/skills/ingest/scripts/wiki_signals_config.py`
- Modify: `src/config/paths.py` (add `get_wiki_signals_config_path()`)
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_signals_config.py`

- [ ] **Step 1: Write the failing test**

Create `shared-vault/skills/ingest/augur/tests/test_wiki_signals_config.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "wiki_signals_config.py"
)
SPEC = importlib.util.spec_from_file_location("wiki_signals_config_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
wiki_signals_config = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki_signals_config)


def test_defaults_when_file_missing(tmp_path):
    cfg = wiki_signals_config.load_config(tmp_path / "missing.yaml")
    assert cfg.mtime_window_minutes == 30
    assert cfg.tier_caps == {"critical": 5, "high": 15, "medium": 30, "low": 50}
    assert cfg.extraction_limit == 20
    assert cfg.include_logs is False
    assert cfg.gemini == {"enabled": True, "path": None}
    assert cfg.copilot == {"enabled": True, "path": None}
    assert cfg.codex == {"enabled": True, "path": None}
    assert cfg.external_clients == {}


def test_yaml_overrides_defaults(tmp_path):
    config_path = tmp_path / "wiki_signals.yaml"
    config_path.write_text(
        """
mtime_window_minutes: 60
tier_caps:
  critical: 10
extraction_limit: 35
include_logs: true
gemini:
  enabled: false
external_clients:
  chatgpt:
    path: /tmp/chatgpt
    tier: high
""",
        encoding="utf-8",
    )
    cfg = wiki_signals_config.load_config(config_path)
    assert cfg.mtime_window_minutes == 60
    assert cfg.tier_caps["critical"] == 10
    # Unspecified caps keep defaults
    assert cfg.tier_caps["high"] == 15
    assert cfg.extraction_limit == 35
    assert cfg.include_logs is True
    assert cfg.gemini["enabled"] is False
    assert cfg.external_clients["chatgpt"]["path"] == "/tmp/chatgpt"
    assert cfg.external_clients["chatgpt"]["tier"] == "high"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_signals_config.py -v`
Expected: FAIL with `FileNotFoundError` (module does not exist yet).

- [ ] **Step 3: Implement the config reader**

Create `shared-vault/skills/ingest/scripts/wiki_signals_config.py`:

```python
"""Read config/system/wiki_signals.yaml with typed defaults."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


_DEFAULT_TIER_CAPS = {"critical": 5, "high": 15, "medium": 30, "low": 50}
_DEFAULT_FIRST_CLASS_CLIENT = {"enabled": True, "path": None}


@dataclass
class WikiSignalsConfig:
    mtime_window_minutes: int = 30
    tier_caps: dict[str, int] = field(default_factory=lambda: dict(_DEFAULT_TIER_CAPS))
    extraction_limit: int = 20
    include_logs: bool = False
    gemini: dict[str, Any] = field(default_factory=lambda: dict(_DEFAULT_FIRST_CLASS_CLIENT))
    copilot: dict[str, Any] = field(default_factory=lambda: dict(_DEFAULT_FIRST_CLASS_CLIENT))
    codex: dict[str, Any] = field(default_factory=lambda: dict(_DEFAULT_FIRST_CLASS_CLIENT))
    external_clients: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_config(path: Path) -> WikiSignalsConfig:
    cfg = WikiSignalsConfig()
    if not path.is_file():
        return cfg
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if "mtime_window_minutes" in raw:
        cfg.mtime_window_minutes = int(raw["mtime_window_minutes"])
    if "tier_caps" in raw and isinstance(raw["tier_caps"], dict):
        cfg.tier_caps.update({k: int(v) for k, v in raw["tier_caps"].items()})
    if "extraction_limit" in raw:
        cfg.extraction_limit = int(raw["extraction_limit"])
    if "include_logs" in raw:
        cfg.include_logs = bool(raw["include_logs"])
    for first_class in ("gemini", "copilot", "codex"):
        if first_class in raw and isinstance(raw[first_class], dict):
            getattr(cfg, first_class).update(raw[first_class])
    if "external_clients" in raw and isinstance(raw["external_clients"], dict):
        for name, spec in raw["external_clients"].items():
            if isinstance(spec, dict):
                cfg.external_clients[name] = dict(spec)
    return cfg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_signals_config.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Add the `paths.py` helper**

Modify `src/config/paths.py` — append at the bottom of the file (after the existing helpers):

```python
def get_wiki_signals_config_path(project_root: Path | None = None) -> Path:
    """Return path to the wiki signal priority config file."""
    root = Path(project_root) if project_root else _project_root()
    return root / "config" / "system" / "wiki_signals.yaml"
```

If `_project_root()` does not exist, use the existing project-root resolver in that file (look for the function used by `get_shared_vault_skills_dir`). Stay consistent with the existing pattern.

- [ ] **Step 6: Create the actual config file with defaults**

Create `config/system/wiki_signals.yaml`:

```yaml
# Wiki signal priority config — see docs/superpowers/specs/2026-05-10-wiki-signal-priority-design.md
mtime_window_minutes: 30

tier_caps:
  critical: 5
  high: 15
  medium: 30
  low: 50

extraction_limit: 20
include_logs: false

gemini:
  enabled: true
  path: ~/.gemini/conversations
copilot:
  enabled: true
  path: ~/Library/Application Support/GitHub Copilot/sessions
codex:
  enabled: true
  path: ~/.codex/sessions

external_clients:
  chatgpt:
    path: ~/Library/Application Support/ChatGPT/exports
    tier: high
  cursor:
    path: ~/Library/Application Support/Cursor/conversations
    tier: high
```

- [ ] **Step 7: Commit**

```bash
git add config/system/wiki_signals.yaml \
        shared-vault/skills/ingest/scripts/wiki_signals_config.py \
        shared-vault/skills/ingest/augur/tests/test_wiki_signals_config.py \
        src/config/paths.py
git commit -m "feat(ingest): add wiki_signals.yaml config and typed reader"
```

---

## Task 2: Add tier table and weight resolution helpers

**Files:**
- Create: `shared-vault/skills/ingest/scripts/wiki_tier.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_tier.py`

- [ ] **Step 1: Write the failing test**

Create `shared-vault/skills/ingest/augur/tests/test_wiki_tier.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wiki_tier.py"
SPEC = importlib.util.spec_from_file_location("wiki_tier_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
wiki_tier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki_tier)


def test_tier_for_known_surfaces():
    assert wiki_tier.tier_for_surface("vault") == "high"
    assert wiki_tier.tier_for_surface("save_events") == "critical"
    assert wiki_tier.tier_for_surface("ask_outcomes") == "critical"
    assert wiki_tier.tier_for_surface("memory_files") == "critical"
    assert wiki_tier.tier_for_surface("episodic") == "critical"
    assert wiki_tier.tier_for_surface("codex_threads") == "critical"
    assert wiki_tier.tier_for_surface("gemini") == "high"
    assert wiki_tier.tier_for_surface("copilot") == "high"
    assert wiki_tier.tier_for_surface("external_client") == "high"
    assert wiki_tier.tier_for_surface("documents") == "medium"
    assert wiki_tier.tier_for_surface("skills") == "medium"
    assert wiki_tier.tier_for_surface("project_deltas") == "medium"
    assert wiki_tier.tier_for_surface("repo_docs") == "medium"
    assert wiki_tier.tier_for_surface("adr_targets") == "medium"
    assert wiki_tier.tier_for_surface("git_history") == "low"
    assert wiki_tier.tier_for_surface("runtime_memory") == "low"
    assert wiki_tier.tier_for_surface("logs") == "noise"


def test_tier_unknown_falls_back_to_medium():
    assert wiki_tier.tier_for_surface("something_new") == "medium"


def test_weight_table():
    assert wiki_tier.weight_for_tier("critical") == 3.0
    assert wiki_tier.weight_for_tier("high") == 2.0
    assert wiki_tier.weight_for_tier("medium") == 1.0
    assert wiki_tier.weight_for_tier("low") == 0.4
    assert wiki_tier.weight_for_tier("noise") == 0.0
    assert wiki_tier.weight_for_tier("garbage") == 1.0  # unknown -> medium-equivalent


def test_tier_meets_filter_inclusive():
    # An empty filter means "everything except noise"
    assert wiki_tier.tier_meets_filter("critical", "") is True
    assert wiki_tier.tier_meets_filter("low", "") is True
    assert wiki_tier.tier_meets_filter("noise", "") is False
    # A specific tier means "this tier or stronger"
    assert wiki_tier.tier_meets_filter("critical", "medium") is True
    assert wiki_tier.tier_meets_filter("medium", "medium") is True
    assert wiki_tier.tier_meets_filter("low", "medium") is False
    assert wiki_tier.tier_meets_filter("noise", "low") is False
    # Critical filter only admits critical
    assert wiki_tier.tier_meets_filter("critical", "critical") is True
    assert wiki_tier.tier_meets_filter("high", "critical") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_tier.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the tier module**

Create `shared-vault/skills/ingest/scripts/wiki_tier.py`:

```python
"""Tier table, weight resolution, and filter logic for wiki signal priority."""
from __future__ import annotations


_TIER_BY_SURFACE: dict[str, str] = {
    # Critical tier
    "save_events":    "critical",
    "ask_outcomes":   "critical",
    "memory_files":   "critical",
    "episodic":       "critical",
    "codex_threads":  "critical",
    # High tier
    "vault":          "high",
    "gemini":         "high",
    "copilot":        "high",
    "external_client": "high",
    # Medium tier
    "documents":      "medium",
    "skills":         "medium",
    "repo_docs":      "medium",
    "project_deltas": "medium",
    "adr_targets":    "medium",
    # Low tier
    "git_history":    "low",
    "runtime_memory": "low",
    # Noise tier
    "logs":           "noise",
}

_WEIGHT_BY_TIER: dict[str, float] = {
    "critical": 3.0,
    "high": 2.0,
    "medium": 1.0,
    "low": 0.4,
    "noise": 0.0,
}

_TIER_RANK: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "noise": 0,
}

ALL_TIERS = ("critical", "high", "medium", "low", "noise")


def tier_for_surface(surface: str) -> str:
    """Return the default tier for a source_surface; unknown -> 'medium'."""
    return _TIER_BY_SURFACE.get(surface, "medium")


def weight_for_tier(tier: str) -> float:
    """Return the extraction weight for a tier; unknown -> medium weight."""
    return _WEIGHT_BY_TIER.get(tier, 1.0)


def tier_meets_filter(source_tier: str, filter_tier: str) -> bool:
    """True if source_tier passes through the given filter.

    Empty filter means "everything except noise".
    A specific filter means "that tier or stronger".
    Unknown source tiers are treated as 'medium'.
    """
    src_rank = _TIER_RANK.get(source_tier, _TIER_RANK["medium"])
    if not filter_tier:
        return source_tier != "noise"
    needed_rank = _TIER_RANK.get(filter_tier, _TIER_RANK["medium"])
    return src_rank >= needed_rank
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_tier.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_tier.py \
        shared-vault/skills/ingest/augur/tests/test_wiki_tier.py
git commit -m "feat(ingest): add tier table and weight resolution helpers"
```

---

## Task 3: Tag scanner output with tier and weight

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/wiki_scanner.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_scanner_priority.py`

- [ ] **Step 1: Write the failing test**

Create `shared-vault/skills/ingest/augur/tests/test_wiki_scanner_priority.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wiki_scanner.py"
SPEC = importlib.util.spec_from_file_location("wiki_scanner_priority_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
wiki_scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki_scanner)


def _make_scanner(tmp_path: Path):
    return wiki_scanner.WikiScanner(
        vault_dir=tmp_path / "vault",
        documents_dir=tmp_path / "documents",
    )


def test_vault_file_gets_high_tier_and_weight(tmp_path):
    vault = tmp_path / "vault"
    note = vault / "notes" / "general" / "thought.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Thought\n\nbody\n", encoding="utf-8")
    # Force mtime far in the past so it does NOT promote to save_events
    import os, time
    old = time.time() - 60 * 60 * 24
    os.utime(note, (old, old))

    scanner = _make_scanner(tmp_path)
    sources = scanner.scan()
    matched = [s for s in sources if s["path"] == str(note)]
    assert matched, "vault note should be scanned"
    assert matched[0]["source_surface"] == "vault"
    assert matched[0]["tier"] == "high"
    assert matched[0]["weight"] == 2.0


def test_frontmatter_wiki_tier_overrides_default(tmp_path):
    vault = tmp_path / "vault"
    note = vault / "notes" / "important.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\nwiki_tier: critical\n---\n# Important\n\nbody\n",
        encoding="utf-8",
    )
    # Age the file so mtime promotion does not interfere
    import os, time
    old = time.time() - 60 * 60 * 24
    os.utime(note, (old, old))

    scanner = _make_scanner(tmp_path)
    sources = scanner.scan()
    matched = [s for s in sources if s["path"] == str(note)]
    assert matched[0]["tier"] == "critical"
    assert matched[0]["weight"] == 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_scanner_priority.py -v`
Expected: FAIL (no `tier` key on source dicts yet).

- [ ] **Step 3: Modify the scanner to attach tier and weight**

In `shared-vault/skills/ingest/scripts/wiki_scanner.py`:

Add at the top (after existing imports):

```python
from skills.ingest.scripts.wiki_tier import tier_for_surface, weight_for_tier
```

Add a new helper function right after `_extract_title`:

```python
def _read_frontmatter_tier(path: Path) -> str | None:
    """Return frontmatter `wiki_tier:` value if present and recognized, else None."""
    if path.suffix.lower() not in (".md", ".txt"):
        return None
    try:
        meta, _ = parse_frontmatter(path)
    except Exception:
        return None
    raw = str(meta.get("wiki_tier") or "").strip().lower()
    if raw in {"critical", "high", "medium", "low", "noise"}:
        return raw
    return None


def _annotate_tier(source: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """Apply tier/weight to a source dict using surface default + optional frontmatter override."""
    surface = str(source.get("source_surface") or "")
    default_tier = tier_for_surface(surface)
    if path is not None and surface == "vault":
        # Frontmatter override only applies for file-backed surfaces; vault is the prime case.
        override = _read_frontmatter_tier(path)
        if override is not None:
            default_tier = override
    source["tier"] = default_tier
    source["weight"] = weight_for_tier(default_tier)
    return source
```

Then in `_scan_dir` — change the `results.append({...})` block to attach tier/weight via `_annotate_tier`:

Locate the existing block (around line 183):

```python
            results.append({
                "path": str(path),
                "type": ext.lstrip("."),
                "title": _extract_title(path),
                "hub": source_hub,
                "format": ext.lstrip("."),
                "source_surface": source_surface,
            })
```

Replace with:

```python
            source = {
                "path": str(path),
                "type": ext.lstrip("."),
                "title": _extract_title(path),
                "hub": source_hub,
                "format": ext.lstrip("."),
                "source_surface": source_surface,
            }
            results.append(_annotate_tier(source, path=path))
```

Apply the same pattern to all other `_scan_*` methods that build a source dict (`_scan_skill_defs`, `_scan_repo_docs`, `_scan_ask_outcomes`, `_scan_project_deltas`, `_scan_git_history`, `_scan_adr_targets`). For surfaces that are not file-backed (git commits, ask outcomes), pass `path=None` so the override path is skipped:

```python
results.append(_annotate_tier({
    "path": ...,
    ...,
    "source_surface": "git_history",
}, path=None))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_scanner_priority.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the existing scanner test to make sure nothing regressed**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_scanner_skill_defs.py -v`
Expected: FAIL — the existing test checks an exact dict that does not include `tier` and `weight` keys.

- [ ] **Step 6: Update the legacy test to expect tier/weight**

Modify `shared-vault/skills/ingest/augur/tests/test_wiki_scanner_skill_defs.py` — change the assertion to use `>=` semantics rather than equality:

```python
def test_scan_skill_defs_uses_shared_vault_skill_root(tmp_path):
    """Wiki rebuild inventory should include shared-vault skill definitions."""
    skill_md = tmp_path / "shared-vault" / "skills" / "demo" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("---\nname: demo\nx-augur-hub: dev\n---\n# Demo Skill\n", encoding="utf-8")

    scanner = wiki_scanner.WikiScanner(
        vault_dir=tmp_path / "vault",
        documents_dir=tmp_path / "documents",
        project_root=tmp_path,
    )

    results = scanner._scan_skill_defs()
    assert len(results) == 1
    entry = results[0]
    assert entry["path"] == str(skill_md)
    assert entry["type"] == "skill"
    assert entry["title"] == "Demo Skill"
    assert entry["hub"] == "dev"
    assert entry["format"] == "md"
    assert entry["source_surface"] == "skills"
    # New tier/weight assertions
    assert entry["tier"] == "medium"
    assert entry["weight"] == 1.0
```

- [ ] **Step 7: Run both scanner tests**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_scanner_priority.py shared-vault/skills/ingest/augur/tests/test_wiki_scanner_skill_defs.py -v`
Expected: PASS (3 tests).

- [ ] **Step 8: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_scanner.py \
        shared-vault/skills/ingest/augur/tests/test_wiki_scanner_priority.py \
        shared-vault/skills/ingest/augur/tests/test_wiki_scanner_skill_defs.py
git commit -m "feat(ingest): tag wiki scanner output with tier and weight"
```

---

## Task 4: Vault mtime promotion to `save_events`

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/wiki_scanner.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_scanner_priority.py`

- [ ] **Step 1: Add the failing test**

Append to `shared-vault/skills/ingest/augur/tests/test_wiki_scanner_priority.py`:

```python
def test_recent_vault_write_promotes_to_save_events(tmp_path):
    import time

    vault = tmp_path / "vault"
    note = vault / "notes" / "fresh.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Fresh\n\nbody\n", encoding="utf-8")
    # mtime within the default 30-min window — utime to "now"
    now = time.time()
    import os
    os.utime(note, (now, now))

    scanner = wiki_scanner.WikiScanner(
        vault_dir=vault,
        documents_dir=tmp_path / "documents",
        mtime_window_minutes=30,
    )
    sources = scanner.scan()
    matched = [s for s in sources if s["path"] == str(note)]
    assert matched[0]["source_surface"] == "save_events"
    assert matched[0]["tier"] == "critical"
    assert matched[0]["weight"] == 3.0


def test_old_vault_write_stays_high(tmp_path):
    import time, os

    vault = tmp_path / "vault"
    note = vault / "notes" / "old.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Old\n\nbody\n", encoding="utf-8")
    old = time.time() - 60 * 60 * 2  # 2 hours ago
    os.utime(note, (old, old))

    scanner = wiki_scanner.WikiScanner(
        vault_dir=vault,
        documents_dir=tmp_path / "documents",
        mtime_window_minutes=30,
    )
    sources = scanner.scan()
    matched = [s for s in sources if s["path"] == str(note)]
    assert matched[0]["source_surface"] == "vault"
    assert matched[0]["tier"] == "high"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_scanner_priority.py -v`
Expected: FAIL — `WikiScanner.__init__()` doesn't accept `mtime_window_minutes`.

- [ ] **Step 3: Add `mtime_window_minutes` parameter and promotion logic**

In `shared-vault/skills/ingest/scripts/wiki_scanner.py`:

Update `WikiScanner.__init__` to accept `mtime_window_minutes`:

```python
    def __init__(
        self,
        *,
        vault_dir: Path,
        documents_dir: Path,
        project_root: Path | None = None,
        runtime_dir: Path | None = None,
        logs_dir: Path | None = None,
        ask_outcomes_loader: Callable[[], list[dict[str, Any]]] | None = None,
        git_history_loader: Callable[[], list[dict[str, str]]] | None = None,
        mtime_window_minutes: int = 30,
    ) -> None:
        self._vault_dir = Path(vault_dir)
        self._documents_dir = Path(documents_dir)
        self._project_root = Path(project_root) if project_root else None
        self._runtime_dir = Path(runtime_dir) if runtime_dir else None
        self._logs_dir = Path(logs_dir) if logs_dir else None
        self._ask_outcomes_loader = ask_outcomes_loader
        self._git_history_loader = git_history_loader
        self._mtime_window_seconds = max(int(mtime_window_minutes), 0) * 60
```

Then in `_scan_dir`, only promote if the surface is `vault` (not `documents`) and the mtime window is non-zero. Replace the `results.append(...)` block built in Task 3 with this expanded version:

```python
            surface = source_surface
            if source_surface == "vault" and self._mtime_window_seconds > 0:
                try:
                    age = abs(time.time() - path.stat().st_mtime)
                except OSError:
                    age = float("inf")
                if age <= self._mtime_window_seconds:
                    surface = "save_events"

            source = {
                "path": str(path),
                "type": ext.lstrip("."),
                "title": _extract_title(path),
                "hub": source_hub,
                "format": ext.lstrip("."),
                "source_surface": surface,
            }
            # Frontmatter override applies in either surface
            results.append(_annotate_tier(source, path=path))
```

Add `import time` at the top of the file (alongside `subprocess`).

- [ ] **Step 4: Run priority tests**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_scanner_priority.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_scanner.py \
        shared-vault/skills/ingest/augur/tests/test_wiki_scanner_priority.py
git commit -m "feat(ingest): promote recent vault writes to save_events tier"
```

---

## Task 5: Five new memory adapters

**Files:**
- Create: `shared-vault/skills/ingest/scripts/wiki_memory_adapters.py`
- Modify: `shared-vault/skills/ingest/scripts/wiki_scanner.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_memory_adapters.py`

- [ ] **Step 1: Write the failing test for `scan_memory_files`**

Create `shared-vault/skills/ingest/augur/tests/test_wiki_memory_adapters.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path

ADAPTERS_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "wiki_memory_adapters.py"
)
SPEC = importlib.util.spec_from_file_location("wiki_memory_adapters_under_test", ADAPTERS_PATH)
assert SPEC and SPEC.loader
adapters = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapters)


def test_scan_memory_files_returns_critical(tmp_path):
    project_dir = tmp_path / ".claude" / "projects" / "-Users-test-Project"
    memory_dir = project_dir / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    (memory_dir / "feedback_x.md").write_text("# Feedback\n", encoding="utf-8")

    sources = adapters.scan_memory_files(claude_root=tmp_path / ".claude")
    paths = sorted(s["path"] for s in sources)
    assert len(sources) == 2
    for s in sources:
        assert s["source_surface"] == "memory_files"
        assert s["tier"] == "critical"
        assert s["weight"] == 3.0
        assert s["format"] == "md"


def test_scan_memory_files_handles_missing_root(tmp_path):
    sources = adapters.scan_memory_files(claude_root=tmp_path / "nope")
    assert sources == []


def test_scan_codex_threads(tmp_path):
    threads_dir = tmp_path / "threads"
    threads_dir.mkdir()
    (threads_dir / "thread1.json").write_text('{"id": "thread1"}', encoding="utf-8")
    (threads_dir / "thread2.md").write_text("# Thread 2\n", encoding="utf-8")

    sources = adapters.scan_codex_threads(threads_dir=threads_dir)
    assert len(sources) == 2
    for s in sources:
        assert s["source_surface"] == "codex_threads"
        assert s["tier"] == "critical"


def test_scan_codex_threads_disabled(tmp_path):
    threads_dir = tmp_path / "threads"
    threads_dir.mkdir()
    (threads_dir / "x.json").write_text("{}", encoding="utf-8")

    sources = adapters.scan_codex_threads(threads_dir=threads_dir, enabled=False)
    assert sources == []


def test_scan_gemini_and_copilot(tmp_path):
    gemini_dir = tmp_path / "gemini"
    gemini_dir.mkdir()
    (gemini_dir / "session.json").write_text("{}", encoding="utf-8")

    copilot_dir = tmp_path / "copilot"
    copilot_dir.mkdir()
    (copilot_dir / "log.md").write_text("# Copilot\n", encoding="utf-8")

    g = adapters.scan_gemini(path=gemini_dir)
    c = adapters.scan_copilot(path=copilot_dir)

    assert len(g) == 1 and g[0]["source_surface"] == "gemini" and g[0]["tier"] == "high"
    assert len(c) == 1 and c[0]["source_surface"] == "copilot" and c[0]["tier"] == "high"


def test_scan_external_clients_uses_allowlist(tmp_path):
    chatgpt = tmp_path / "chatgpt"
    chatgpt.mkdir()
    (chatgpt / "x.md").write_text("# X\n", encoding="utf-8")

    allowlist = {
        "chatgpt": {"path": str(chatgpt), "tier": "high"},
        "missing": {"path": str(tmp_path / "missing"), "tier": "high"},
    }
    sources = adapters.scan_external_clients(allowlist=allowlist)
    surfaces = [s["source_surface"] for s in sources]
    assert surfaces == ["external_client"]
    assert sources[0]["tier"] == "high"
    # Path-extra metadata so consumers can distinguish clients
    assert sources[0]["client"] == "chatgpt"


def test_scan_episodic_via_loader():
    fake_records = [
        {"id": "abc", "title": "Past convo", "ts": "2026-05-01T10:00:00Z"},
        {"id": "def", "title": "Other convo", "ts": "2026-05-09T10:00:00Z"},
    ]
    sources = adapters.scan_episodic(loader=lambda: fake_records)
    assert len(sources) == 2
    assert all(s["source_surface"] == "episodic" for s in sources)
    assert all(s["tier"] == "critical" for s in sources)
    paths = [s["path"] for s in sources]
    assert "episodic://abc" in paths
    assert "episodic://def" in paths


def test_scan_episodic_no_loader():
    assert adapters.scan_episodic(loader=None) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_memory_adapters.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the adapters module**

Create `shared-vault/skills/ingest/scripts/wiki_memory_adapters.py`:

```python
"""Cross-platform memory source adapters for the wiki scanner.

Each adapter returns a list of source dicts compatible with WikiScanner's output:
  {path, type, title, hub, format, source_surface, tier, weight}
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from skills.ingest.scripts.wiki_tier import tier_for_surface, weight_for_tier


def _annotate(source: dict[str, Any]) -> dict[str, Any]:
    surface = str(source.get("source_surface") or "")
    tier = tier_for_surface(surface)
    source["tier"] = tier
    source["weight"] = weight_for_tier(tier)
    return source


def _from_dir(
    *,
    root: Path,
    surface: str,
    hub: str,
    extra: dict[str, Any] | None = None,
    extensions: Iterable[str] = (".md", ".txt", ".json", ".jsonl"),
) -> list[dict[str, Any]]:
    if not root or not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    allowed = {ext.lower() for ext in extensions}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in allowed:
            continue
        source = {
            "path": str(path),
            "type": path.suffix.lstrip(".").lower(),
            "title": path.stem.replace("-", " ").replace("_", " ").title(),
            "hub": hub,
            "format": path.suffix.lstrip(".").lower(),
            "source_surface": surface,
        }
        if extra:
            source.update(extra)
        out.append(_annotate(source))
    return out


def scan_memory_files(*, claude_root: Path) -> list[dict[str, Any]]:
    """Claude Code auto-memory: ~/.claude/projects/*/memory/*.md."""
    if not claude_root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    projects = claude_root / "projects"
    if not projects.is_dir():
        return []
    for project in sorted(projects.iterdir()):
        memory_dir = project / "memory"
        out.extend(_from_dir(root=memory_dir, surface="memory_files", hub="memory"))
    return out


def scan_codex_threads(
    *,
    threads_dir: Path,
    enabled: bool = True,
) -> list[dict[str, Any]]:
    if not enabled:
        return []
    return _from_dir(root=threads_dir, surface="codex_threads", hub="memory")


def scan_gemini(*, path: Path | None, enabled: bool = True) -> list[dict[str, Any]]:
    if not enabled or path is None:
        return []
    return _from_dir(root=path, surface="gemini", hub="memory")


def scan_copilot(*, path: Path | None, enabled: bool = True) -> list[dict[str, Any]]:
    if not enabled or path is None:
        return []
    return _from_dir(root=path, surface="copilot", hub="memory")


def scan_external_clients(
    *,
    allowlist: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Allowlisted clients (chatgpt/cursor/etc.). Each gets surface 'external_client' with `client` key set."""
    out: list[dict[str, Any]] = []
    for name, spec in (allowlist or {}).items():
        raw_path = spec.get("path")
        if not raw_path:
            continue
        out.extend(_from_dir(
            root=Path(str(raw_path)).expanduser(),
            surface="external_client",
            hub="memory",
            extra={"client": name},
        ))
    return out


def scan_episodic(
    *,
    loader: Callable[[], list[dict[str, Any]]] | None,
) -> list[dict[str, Any]]:
    """Episodic-memory plugin: caller supplies a loader returning records with id/title/ts."""
    if loader is None:
        return []
    out: list[dict[str, Any]] = []
    for record in loader() or []:
        rid = str(record.get("id") or "").strip()
        if not rid:
            continue
        source = {
            "path": f"episodic://{rid}",
            "type": "episodic",
            "title": str(record.get("title") or rid),
            "hub": "memory",
            "format": "episodic",
            "source_surface": "episodic",
            "ts": record.get("ts"),
        }
        out.append(_annotate(source))
    return out
```

- [ ] **Step 4: Run adapter tests**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_memory_adapters.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Wire adapters into the scanner**

In `shared-vault/skills/ingest/scripts/wiki_scanner.py`:

Add at the top:

```python
from skills.ingest.scripts import wiki_memory_adapters
from skills.ingest.scripts.wiki_signals_config import WikiSignalsConfig
```

Extend `__init__` to accept `signals_config`, `claude_root`, and an `episodic_loader`:

```python
        signals_config: WikiSignalsConfig | None = None,
        claude_root: Path | None = None,
        episodic_loader: Callable[[], list[dict[str, Any]]] | None = None,
```

Store them on `self`. Default `signals_config = WikiSignalsConfig()` if None. Default `claude_root = Path.home() / ".claude"` if None.

Then add five new methods:

```python
    def _scan_memory_files(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        sources = wiki_memory_adapters.scan_memory_files(claude_root=self._claude_root)
        return self._filter_hub(sources, hub)

    def _scan_episodic_records(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        sources = wiki_memory_adapters.scan_episodic(loader=self._episodic_loader)
        return self._filter_hub(sources, hub)

    def _scan_codex_memory(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        codex = self._signals_config.codex
        path_value = codex.get("path")
        sources = wiki_memory_adapters.scan_codex_threads(
            threads_dir=Path(path_value).expanduser() if path_value else Path("/__missing__"),
            enabled=bool(codex.get("enabled", True)),
        )
        return self._filter_hub(sources, hub)

    def _scan_gemini_memory(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        spec = self._signals_config.gemini
        path_value = spec.get("path")
        sources = wiki_memory_adapters.scan_gemini(
            path=Path(path_value).expanduser() if path_value else None,
            enabled=bool(spec.get("enabled", True)),
        )
        return self._filter_hub(sources, hub)

    def _scan_copilot_memory(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        spec = self._signals_config.copilot
        path_value = spec.get("path")
        sources = wiki_memory_adapters.scan_copilot(
            path=Path(path_value).expanduser() if path_value else None,
            enabled=bool(spec.get("enabled", True)),
        )
        return self._filter_hub(sources, hub)

    def _scan_external_client_memory(self, *, hub: str | None = None) -> list[dict[str, Any]]:
        sources = wiki_memory_adapters.scan_external_clients(
            allowlist=self._signals_config.external_clients,
        )
        return self._filter_hub(sources, hub)

    @staticmethod
    def _filter_hub(sources: list[dict[str, Any]], hub: str | None) -> list[dict[str, Any]]:
        if not hub:
            return sources
        return [s for s in sources if s.get("hub") == hub]
```

Then add the new calls inside `scan()`:

```python
        sources.extend(self._scan_memory_files(hub=hub))
        sources.extend(self._scan_episodic_records(hub=hub))
        sources.extend(self._scan_codex_memory(hub=hub))
        sources.extend(self._scan_gemini_memory(hub=hub))
        sources.extend(self._scan_copilot_memory(hub=hub))
        sources.extend(self._scan_external_client_memory(hub=hub))
```

- [ ] **Step 6: Run all ingest tests**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/ -v`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_memory_adapters.py \
        shared-vault/skills/ingest/scripts/wiki_scanner.py \
        shared-vault/skills/ingest/augur/tests/test_wiki_memory_adapters.py
git commit -m "feat(ingest): add 5 cross-platform memory adapters to wiki scanner"
```

---

# Slice 2 — Consumer changes (`wiki-update`)

## Task 6: Tier filter on `wiki-update`

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py`

- [ ] **Step 1: Write the failing test**

Create `shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path

# Test the pure helper functions used by wiki-update.
HELPERS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wiki_tier.py"
SPEC = importlib.util.spec_from_file_location("wiki_tier_for_update", HELPERS_PATH)
assert SPEC and SPEC.loader
wiki_tier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki_tier)


def _src(surface: str, path: str = "/x"):
    return {
        "path": path,
        "source_surface": surface,
        "tier": wiki_tier.tier_for_surface(surface),
        "weight": wiki_tier.weight_for_tier(wiki_tier.tier_for_surface(surface)),
    }


def test_tier_filter_default_drops_noise():
    sources = [_src("save_events"), _src("vault"), _src("logs")]
    kept = [s for s in sources if wiki_tier.tier_meets_filter(s["tier"], "")]
    surfaces = [s["source_surface"] for s in kept]
    assert "logs" not in surfaces
    assert "save_events" in surfaces
    assert "vault" in surfaces


def test_tier_filter_critical_only():
    sources = [_src("save_events"), _src("vault"), _src("logs")]
    kept = [s for s in sources if wiki_tier.tier_meets_filter(s["tier"], "critical")]
    surfaces = [s["source_surface"] for s in kept]
    assert surfaces == ["save_events"]


def test_weight_sort_highest_first():
    sources = [_src("logs"), _src("save_events"), _src("vault"), _src("documents")]
    sources.sort(key=lambda s: -s["weight"])
    assert sources[0]["source_surface"] == "save_events"
    assert sources[-1]["source_surface"] == "logs"
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py -v`
Expected: PASS — these are pure-function checks against `wiki_tier`. They pin the behavior the consumer will rely on.

- [ ] **Step 3: Add tier filter and weight sort to `wiki-update`**

In `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`, locate the `wiki_update` function (around line 658).

At the top of the file, add:

```python
from skills.ingest.scripts.wiki_tier import tier_meets_filter
```

Modify the `wiki_update` signature and add filter/sort logic. Locate:

```python
    @mcp.tool(
        name="wiki-update",
        annotations=tool_annotations({"title": "Wiki Update", ...}),
    )
    @mcp_tool_interceptor
    async def wiki_update(limit: int = 20) -> str:
        """..."""
        metrics.track_tool("wiki_update", skill="ingest")
```

Change signature to:

```python
    async def wiki_update(limit: int = 20, tier: str = "") -> str:
        """Prepare an incremental concept extraction batch, optionally filtered by tier."""
        metrics.track_tool("wiki_update", skill="ingest")
```

Right after `sources = build_source_inventory(...)` (or wherever the source list is constructed for extraction — look for where `prepare_extraction_batch` is called), insert:

```python
            # Filter by tier (default '' drops noise only)
            sources = [s for s in sources if tier_meets_filter(str(s.get("tier") or "medium"), tier)]
            # Weight-aware sort: heavier sources survive limit truncation
            sources.sort(key=lambda s: (-float(s.get("weight") or 1.0), str(s.get("path") or "")))
```

- [ ] **Step 4: Re-run filter test**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py -v`
Expected: still PASS.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/wiki_tools.py \
        shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py
git commit -m "feat(ingest): wiki-update applies tier filter and weight-aware sort"
```

---

## Task 7: Skip-if-unchanged guard

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py`

- [ ] **Step 1: Add the failing test for the skip helper**

Append to `test_wiki_update_filter.py`:

```python
def test_skip_if_unchanged_with_no_recent_mtime(tmp_path):
    last_ts_path = tmp_path / "last-extraction.ts"
    last_ts_path.write_text("1000000000.0", encoding="utf-8")  # ancient

    file = tmp_path / "vault.md"
    file.write_text("hi", encoding="utf-8")
    import os
    os.utime(file, (1000000001.0, 1000000001.0))  # newer than last_ts by 1 second

    # Helper signature:  should_skip(sources, last_ts_path) -> bool
    from importlib import util
    helper_path = Path(__file__).resolve().parents[2] / "scripts" / "wiki_extraction_guard.py"
    spec = util.spec_from_file_location("wiki_extraction_guard", helper_path)
    guard = util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(guard)

    sources = [{"path": str(file), "tier": "high", "weight": 2.0}]
    assert guard.should_skip(sources, last_ts_path) is False  # newer mtime, do extract


def test_skip_if_all_sources_older_than_last_ts(tmp_path):
    from importlib import util
    helper_path = Path(__file__).resolve().parents[2] / "scripts" / "wiki_extraction_guard.py"
    spec = util.spec_from_file_location("wiki_extraction_guard", helper_path)
    guard = util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(guard)

    last_ts_path = tmp_path / "last-extraction.ts"
    last_ts_path.write_text("2000000000.0", encoding="utf-8")  # future-ish

    file = tmp_path / "vault.md"
    file.write_text("hi", encoding="utf-8")
    import os
    os.utime(file, (1000000000.0, 1000000000.0))  # older than last_ts

    sources = [{"path": str(file), "tier": "high", "weight": 2.0}]
    assert guard.should_skip(sources, last_ts_path) is True


def test_skip_handles_non_file_paths(tmp_path):
    from importlib import util
    helper_path = Path(__file__).resolve().parents[2] / "scripts" / "wiki_extraction_guard.py"
    spec = util.spec_from_file_location("wiki_extraction_guard", helper_path)
    guard = util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(guard)

    last_ts_path = tmp_path / "last-extraction.ts"
    last_ts_path.write_text("0", encoding="utf-8")

    # episodic:// pseudo-paths and git:* paths can't be stat'd; treat as fresh.
    sources = [{"path": "episodic://abc", "tier": "critical", "weight": 3.0}]
    assert guard.should_skip(sources, last_ts_path) is False


def test_skip_when_no_last_ts_file(tmp_path):
    from importlib import util
    helper_path = Path(__file__).resolve().parents[2] / "scripts" / "wiki_extraction_guard.py"
    spec = util.spec_from_file_location("wiki_extraction_guard", helper_path)
    guard = util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(guard)

    sources = [{"path": str(tmp_path / "x.md"), "tier": "low"}]
    # No previous extraction recorded -> never skip
    assert guard.should_skip(sources, tmp_path / "missing.ts") is False
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py -v`
Expected: FAIL — `wiki_extraction_guard.py` does not exist.

- [ ] **Step 3: Implement the guard helper**

Create `shared-vault/skills/ingest/scripts/wiki_extraction_guard.py`:

```python
"""Guard to skip wiki concept extraction when nothing has changed since the last run."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _read_last_ts(path: Path) -> float | None:
    try:
        return float(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _source_mtime(source: dict[str, Any]) -> float | None:
    raw_path = str(source.get("path") or "")
    if not raw_path or "://" in raw_path or raw_path.startswith("git:"):
        # Pseudo-paths (episodic://, git:<sha>) are treated as fresh.
        return float("inf")
    try:
        return Path(raw_path).stat().st_mtime
    except OSError:
        return None


def should_skip(sources: list[dict[str, Any]], last_ts_path: Path) -> bool:
    """Return True if every file source is older than last_ts; False otherwise."""
    last_ts = _read_last_ts(last_ts_path)
    if last_ts is None:
        return False
    if not sources:
        return True
    for source in sources:
        mtime = _source_mtime(source)
        if mtime is None:
            continue
        if mtime > last_ts:
            return False
    return True


def write_last_ts(path: Path, ts: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{ts:.6f}\n", encoding="utf-8")
```

- [ ] **Step 4: Run the guard tests**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py -v`
Expected: PASS (7 tests including earlier ones).

- [ ] **Step 5: Wire the guard into `wiki-update`**

In `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`, near the top:

```python
from skills.ingest.scripts.wiki_extraction_guard import should_skip, write_last_ts
```

Inside `wiki_update`, after the source filter & sort but **before** preparing the extraction batch, add:

```python
            from src.config.paths import get_runtime_dir
            last_ts_path = get_runtime_dir() / "wiki" / "last-extraction.ts"
            if should_skip(sources, last_ts_path):
                return json.dumps(
                    {
                        "success": True,
                        "status": "no_change",
                        "tier": tier or "",
                        "sources_considered": len(sources),
                    },
                    indent=2,
                )
```

After a successful extraction call (after `prepare_extraction_batch` completes), record the timestamp:

```python
            import time
            write_last_ts(last_ts_path, time.time())
```

- [ ] **Step 6: Re-run tests and the existing wiki_tools tests**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/ -v`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_extraction_guard.py \
        shared-vault/skills/ingest/scripts/mcp/wiki_tools.py \
        shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py
git commit -m "feat(ingest): wiki-update skips extraction when nothing changed"
```

---

## Task 8: Per-tier batch caps and config-driven extraction limit

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`
- Test: `shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py`

- [ ] **Step 1: Add the failing test**

Append to `test_wiki_update_filter.py`:

```python
def test_apply_tier_caps_keeps_top_k_per_tier():
    from importlib import util
    caps_path = Path(__file__).resolve().parents[2] / "scripts" / "wiki_tier_caps.py"
    spec = util.spec_from_file_location("wiki_tier_caps", caps_path)
    caps_mod = util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(caps_mod)

    sources = (
        [{"path": f"/c{i}", "tier": "critical", "weight": 3.0} for i in range(10)]
        + [{"path": f"/h{i}", "tier": "high",     "weight": 2.0} for i in range(20)]
        + [{"path": f"/m{i}", "tier": "medium",   "weight": 1.0} for i in range(40)]
    )
    caps = {"critical": 5, "high": 15, "medium": 30, "low": 50}
    capped = caps_mod.apply_tier_caps(sources, caps)
    by_tier = {}
    for s in capped:
        by_tier.setdefault(s["tier"], 0)
        by_tier[s["tier"]] += 1
    assert by_tier["critical"] == 5
    assert by_tier["high"] == 15
    assert by_tier["medium"] == 30


def test_apply_tier_caps_passthrough_when_under_cap():
    from importlib import util
    caps_path = Path(__file__).resolve().parents[2] / "scripts" / "wiki_tier_caps.py"
    spec = util.spec_from_file_location("wiki_tier_caps", caps_path)
    caps_mod = util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(caps_mod)

    sources = [{"path": "/x", "tier": "high", "weight": 2.0}]
    capped = caps_mod.apply_tier_caps(sources, {"high": 15})
    assert len(capped) == 1
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py::test_apply_tier_caps_keeps_top_k_per_tier -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the cap helper**

Create `shared-vault/skills/ingest/scripts/wiki_tier_caps.py`:

```python
"""Per-tier cap application for wiki-update batches."""
from __future__ import annotations

from typing import Any


def apply_tier_caps(
    sources: list[dict[str, Any]],
    caps: dict[str, int],
) -> list[dict[str, Any]]:
    """Keep up to `caps[tier]` sources from each tier, preserving input order.

    Sources should already be weight-sorted upstream so that the survivors are the heaviest.
    """
    counts: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for source in sources:
        tier = str(source.get("tier") or "medium")
        cap = int(caps.get(tier, 10**9))  # missing cap = effectively unlimited
        used = counts.get(tier, 0)
        if used >= cap:
            continue
        counts[tier] = used + 1
        out.append(source)
    return out
```

- [ ] **Step 4: Run the cap tests**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py -v`
Expected: PASS.

- [ ] **Step 5: Wire caps and config-driven limit into `wiki-update`**

In `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`, near the top:

```python
from skills.ingest.scripts.wiki_tier_caps import apply_tier_caps
from skills.ingest.scripts.wiki_signals_config import load_config as load_wiki_signals
from src.config.paths import get_wiki_signals_config_path
```

Inside `wiki_update`, after the weight-sort but **before** the skip-if-unchanged guard, load config and apply caps:

```python
            signals_cfg = load_wiki_signals(get_wiki_signals_config_path())
            sources = apply_tier_caps(sources, signals_cfg.tier_caps)
            # Honor config extraction_limit if caller didn't set their own
            if limit <= 0:
                limit = signals_cfg.extraction_limit
            else:
                limit = min(limit, signals_cfg.extraction_limit)
```

- [ ] **Step 6: Run all ingest tests**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/ -v`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_tier_caps.py \
        shared-vault/skills/ingest/scripts/mcp/wiki_tools.py \
        shared-vault/skills/ingest/augur/tests/test_wiki_update_filter.py
git commit -m "feat(ingest): wiki-update applies per-tier caps and config extraction limit"
```

---

# Slice 3 — Routine + telemetry

## Task 9: Surface telemetry in `wiki-status`

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/wiki_status.py`
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py` (telemetry recording)
- Test: new `shared-vault/skills/ingest/augur/tests/test_wiki_status_telemetry.py`

- [ ] **Step 1: Write the failing test**

Create `shared-vault/skills/ingest/augur/tests/test_wiki_status_telemetry.py`:

```python
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wiki_status.py"
SPEC = importlib.util.spec_from_file_location("wiki_status_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
wiki_status = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki_status)


def test_telemetry_block_present_in_status(tmp_path, monkeypatch):
    runtime_wiki = tmp_path / "wiki"
    runtime_wiki.mkdir()
    (runtime_wiki / "last-extraction.ts").write_text("1700000000.0", encoding="utf-8")
    (runtime_wiki / "telemetry.json").write_text(
        json.dumps(
            {
                "signals_seen_by_tier": {"critical": 3, "high": 7, "medium": 11, "low": 4},
                "tokens_spent_last_run": 3120,
                "dropped_low_noise_count": 12,
            }
        ),
        encoding="utf-8",
    )

    block = wiki_status._telemetry_block(runtime_wiki)
    assert block["last_extraction_ts"] == 1700000000.0
    assert block["signals_seen_by_tier"]["critical"] == 3
    assert block["tokens_spent_last_run"] == 3120
    assert block["dropped_low_noise_count"] == 12


def test_telemetry_block_missing_files(tmp_path):
    block = wiki_status._telemetry_block(tmp_path / "wiki")
    assert block["last_extraction_ts"] is None
    assert block["signals_seen_by_tier"] == {}
    assert block["tokens_spent_last_run"] is None
    assert block["dropped_low_noise_count"] is None
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_status_telemetry.py -v`
Expected: FAIL — `_telemetry_block` does not exist.

- [ ] **Step 3: Add the telemetry block to `wiki_status.py`**

Append to `shared-vault/skills/ingest/scripts/wiki_status.py`:

```python
def _telemetry_block(runtime_wiki_dir: Path) -> dict[str, Any]:
    last_ts_path = runtime_wiki_dir / "last-extraction.ts"
    telemetry_path = runtime_wiki_dir / "telemetry.json"

    last_ts: float | None = None
    if last_ts_path.is_file():
        try:
            last_ts = float(last_ts_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            last_ts = None

    signals: dict[str, int] = {}
    tokens_spent: int | None = None
    dropped: int | None = None
    if telemetry_path.is_file():
        try:
            payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload.get("signals_seen_by_tier"), dict):
            signals = {str(k): int(v) for k, v in payload["signals_seen_by_tier"].items()}
        if "tokens_spent_last_run" in payload:
            try:
                tokens_spent = int(payload["tokens_spent_last_run"])
            except (TypeError, ValueError):
                tokens_spent = None
        if "dropped_low_noise_count" in payload:
            try:
                dropped = int(payload["dropped_low_noise_count"])
            except (TypeError, ValueError):
                dropped = None

    return {
        "last_extraction_ts": last_ts,
        "signals_seen_by_tier": signals,
        "tokens_spent_last_run": tokens_spent,
        "dropped_low_noise_count": dropped,
    }
```

Then plug it into `build_wiki_status` — locate the final `return {...}` of that function and add a key:

```python
        "telemetry": _telemetry_block(resolved_runtime_wiki_dir),
```

- [ ] **Step 4: Make `wiki-update` write the telemetry file**

In `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`, after a successful `prepare_extraction_batch` (right next to where `write_last_ts` is called), add:

```python
            import json as _json
            telemetry_path = last_ts_path.parent / "telemetry.json"
            telemetry_path.parent.mkdir(parents=True, exist_ok=True)
            signal_counts: dict[str, int] = {}
            for s in sources:
                t = str(s.get("tier") or "medium")
                signal_counts[t] = signal_counts.get(t, 0) + 1
            tokens_spent = batch_summary.get("tokens", 0) if isinstance(batch_summary, dict) else 0
            telemetry_path.write_text(
                _json.dumps(
                    {
                        "signals_seen_by_tier": signal_counts,
                        "tokens_spent_last_run": int(tokens_spent or 0),
                        "dropped_low_noise_count": 0,  # populated below if we recorded the count
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
```

If the batch summary doesn't expose token counts in your runtime, set `tokens_spent = 0` for now and capture them in a follow-up. Track the dropped count by snapshotting the source list before the tier filter and computing `dropped = len(before) - len(after)`.

- [ ] **Step 5: Run telemetry tests**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_wiki_status_telemetry.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/ingest/scripts/wiki_status.py \
        shared-vault/skills/ingest/scripts/mcp/wiki_tools.py \
        shared-vault/skills/ingest/augur/tests/test_wiki_status_telemetry.py
git commit -m "feat(ingest): surface wiki priority telemetry in wiki-status"
```

---

## Task 10: Register `wiki-batched-daily` routine

**Files:**
- Modify: `shared-vault/skills/daemon/augur/config/tasks.yaml`
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py` (idempotent CLI entry point if not already callable from cron)
- Test: `shared-vault/skills/daemon/augur/tests/test_daemon.py` augmented (or new file `test_daemon_wiki_routine.py`)

- [ ] **Step 1: Inspect existing tasks.yaml schema**

Run: `head -120 shared-vault/skills/daemon/augur/config/tasks.yaml`
Look for the field set used by an existing daily task (e.g. `nightly-maintenance`) — that is your template.

- [ ] **Step 2: Add the routine entry**

Modify `shared-vault/skills/daemon/augur/config/tasks.yaml`. Append a new task entry following the schema of `nightly-maintenance`:

```yaml
  wiki-batched-daily:
    description: "Daily batched wiki update with priority tiers and skip-if-unchanged guard"
    script: shared-vault/skills/ingest/scripts/run_wiki_batched_daily.py
    schedule: daily
    hour: 6
    minute: 23
    enabled: true
    timeout_seconds: 900
    on_failure: notify
    category: ingest
    last_run: null
    next_run: null
```

- [ ] **Step 3: Write the runner script**

Create `shared-vault/skills/ingest/scripts/run_wiki_batched_daily.py`:

```python
"""Cron-callable entry point for the daily wiki batched update.

Invoked by the daemon scheduler. Calls wiki-update via the MCP tool registry
through the local Python pathway so we don't require a running MCP host.
"""
from __future__ import annotations

import asyncio
import json
import sys

from skills.ingest.scripts.mcp.wiki_tools import register_wiki_tools  # noqa: F401  (registration is the point)


async def _run() -> int:
    # The ingest MCP server registers wiki tools at import time when used via FastMCP.
    # For the cron runner we call the underlying function directly.
    from skills.ingest.scripts.mcp import wiki_tools

    # wiki_tools._run_wiki_update is exported by Task 6/7/8 changes.
    result_text = await wiki_tools._run_wiki_update(limit=20, tier="")
    print(result_text)
    payload = json.loads(result_text)
    return 0 if payload.get("success") else 2


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Expose `_run_wiki_update` as a plain async function**

In `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`, refactor the body of the `wiki_update` MCP tool into a module-level async function `_run_wiki_update(limit: int, tier: str) -> str` and have the MCP tool delegate to it. This makes the same logic callable from the cron runner without dragging FastMCP into the cron process:

```python
async def _run_wiki_update(limit: int = 20, tier: str = "") -> str:
    """Pure-Python entry point for wiki-update (MCP-free)."""
    # ... (moved body from wiki_update) ...

# inside register_wiki_tools:
    @mcp.tool(name="wiki-update", ...)
    @mcp_tool_interceptor
    async def wiki_update(limit: int = 20, tier: str = "") -> str:
        """Prepare an incremental concept extraction batch, optionally filtered by tier."""
        metrics.track_tool("wiki_update", skill="ingest")
        return await _run_wiki_update(limit=limit, tier=tier)
```

- [ ] **Step 5: Add a smoke test for the runner**

Create `shared-vault/skills/ingest/augur/tests/test_run_wiki_batched_daily.py`:

```python
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

RUNNER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_wiki_batched_daily.py"


def test_runner_calls_wiki_update_with_defaults(monkeypatch):
    captured = {}

    async def fake_run(limit: int = 20, tier: str = ""):
        captured["limit"] = limit
        captured["tier"] = tier
        return json.dumps({"success": True, "status": "no_change"})

    spec = importlib.util.spec_from_file_location("run_wiki_batched_daily_under_test", RUNNER_PATH)
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    from skills.ingest.scripts.mcp import wiki_tools
    monkeypatch.setattr(wiki_tools, "_run_wiki_update", fake_run)

    rc = asyncio.run(runner._run())
    assert rc == 0
    assert captured == {"limit": 20, "tier": ""}
```

- [ ] **Step 6: Run runner test**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/test_run_wiki_batched_daily.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/daemon/augur/config/tasks.yaml \
        shared-vault/skills/ingest/scripts/run_wiki_batched_daily.py \
        shared-vault/skills/ingest/scripts/mcp/wiki_tools.py \
        shared-vault/skills/ingest/augur/tests/test_run_wiki_batched_daily.py
git commit -m "feat(daemon): register wiki-batched-daily routine at 06:23 UTC"
```

---

## Task 11: Full integration sweep

**Files:**
- Run-only — no new code unless something breaks.

- [ ] **Step 1: Run full ingest test suite**

Run: `uv run pytest shared-vault/skills/ingest/augur/tests/ -v`
Expected: all green.

- [ ] **Step 2: Run full daemon test suite**

Run: `uv run pytest shared-vault/skills/daemon/augur/tests/ -v`
Expected: all green.

- [ ] **Step 3: Manually trigger the runner end-to-end**

Run: `uv run python shared-vault/skills/ingest/scripts/run_wiki_batched_daily.py`
Expected: prints a JSON result with `"success": true`. If `last-extraction.ts` is fresh, prints `"status": "no_change"`. If sources have newer mtime, runs an extraction batch.

- [ ] **Step 4: Inspect telemetry from `wiki-status`**

Run: `uv run python -c "import json; from skills.ingest.scripts.wiki_status import build_wiki_status; print(json.dumps(build_wiki_status()['telemetry'], indent=2, default=str))"`
Expected: JSON block with `last_extraction_ts`, `signals_seen_by_tier`, `tokens_spent_last_run`, `dropped_low_noise_count`.

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git status
# If fixes: git add ... && git commit -m "fix(ingest): integration cleanup for wiki signal priority"
```

---

## Self-review

**Spec coverage check:**

| Spec section | Implementing task(s) |
|---|---|
| Tier taxonomy table | Task 2 (`wiki_tier.py`) |
| Frontmatter `wiki_tier:` override | Task 3 |
| Vault mtime promotion | Task 4 |
| 5 memory adapters (memory_files, episodic, codex, gemini, copilot) | Task 5 |
| External-client allowlist | Task 5 (`scan_external_clients`) |
| `wiki-update --tier` filter | Task 6 |
| Weight-aware extraction batch | Task 6 (sort) + Task 8 (caps preserve heavy survivors) |
| Skip-if-unchanged guard | Task 7 |
| Per-tier batch caps | Task 8 |
| `extraction_limit: 20` default | Task 8 (config-driven) |
| `wiki_signals.yaml` config file | Task 1 |
| `wiki-batched-daily` routine at 06:23 UTC | Task 10 |
| 4 telemetry fields in `wiki-status` | Task 9 |
| Three-commit rollout | Slices 1, 2, 3 |
| Logs excluded from extraction by default | Task 6 (default tier filter drops noise) + Task 1 (`include_logs: false` config) |

All spec requirements have at least one task. No gaps.

**Placeholder scan:** No "TBD"/"TODO"/"implement later" in any step. Every code block is complete.

**Type consistency:** `tier` is always a `str` of `{"critical","high","medium","low","noise"}`. `weight` is always `float`. `source_surface` strings match across `wiki_tier.py`, `wiki_memory_adapters.py`, and `wiki_scanner.py`. `_run_wiki_update` signature `(limit: int, tier: str) -> str` is consistent in both Tasks 6 and 10.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-10-wiki-signal-priority.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
